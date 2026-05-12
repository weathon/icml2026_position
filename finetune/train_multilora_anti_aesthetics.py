#!/usr/bin/env python
# coding=utf-8
# Multi-LoRA anti-aesthetics training for FLUX 2 Klein.
#
# Trains 5 parallel LoRA adapters with per-sample multi-hot routing on the
# weathon/merged_aa_recaptioned dataset. Each sample's caption + multi-hot
# vector activate any subset of the 5 LoRAs during a single forward pass.

import argparse
import contextlib
import itertools
import logging
import math
import os
import random
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import transformers
from accelerate import Accelerator
from accelerate.logging import get_logger
from accelerate.utils import ProjectConfiguration, set_seed
from datasets import load_dataset
from huggingface_hub import HfApi, create_repo
from PIL.ImageOps import exif_transpose
from safetensors.torch import save_file
from torch.utils.data import Dataset
from torch.utils.data.sampler import BatchSampler
from torchvision import transforms
from torchvision.transforms import functional as TF
from tqdm.auto import tqdm
from transformers import Qwen2TokenizerFast, Qwen3ForCausalLM

import diffusers
from diffusers import (
    AutoencoderKLFlux2,
    FlowMatchEulerDiscreteScheduler,
    Flux2KleinPipeline,
    Flux2Transformer2DModel,
)
from diffusers.optimization import get_scheduler
from diffusers.training_utils import (
    compute_density_for_timestep_sampling,
    compute_loss_weighting_for_sd3,
    find_nearest_bucket,
    free_memory,
    offload_models,
    parse_buckets_string,
)


logger = get_logger(__name__)

NUM_LORAS = 5
LORA_NAMES = [
    "clarity_and_focus",
    "color_and_tone",
    "lighting_and_exposure",
    "composition_and_structure",
    "emotion_and_subject",
]
LORA_NAME_TO_IDX = {n: i for i, n in enumerate(LORA_NAMES)}


# ---------------------------------------------------------------------------
# Per-sample routing context
# ---------------------------------------------------------------------------
# All MultiLoRALinear modules read the active mask from this single tensor,
# which the training step sets before each transformer forward. We store it
# on the module class to avoid threading the mask through every forward.
class _MaskContext:
    current: torch.Tensor | None = None  # shape (B, NUM_LORAS)


@contextlib.contextmanager
def lora_mask(mask: torch.Tensor):
    # NOTE: we intentionally do NOT restore the previous mask on exit. With
    # gradient checkpointing the transformer's forward is re-run during the
    # backward pass (recomputation), and the MultiLoRALinear layers need to
    # see the same mask then. Restoring on exit would set it to None before
    # backward fires, causing a different number of saved tensors between the
    # original forward and recomputation. Callers must set the mask before
    # every forward; recomputation reuses the most-recent value.
    _MaskContext.current = mask
    try:
        yield
    finally:
        pass


# ---------------------------------------------------------------------------
# Multi-LoRA linear wrapper
# ---------------------------------------------------------------------------
class MultiLoRALinear(nn.Module):
    """Wraps a frozen nn.Linear with NUM_LORAS parallel LoRA pairs.

    out = base(x) + sum_i mask[:, i] * (B_i @ A_i @ x) * (alpha / r)

    The base linear stays frozen. Each (A_i, B_i) is a separate trainable pair.
    """

    def __init__(self, base: nn.Linear, rank: int, alpha: float, num_loras: int = NUM_LORAS, dropout: float = 0.0):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad_(False)

        self.in_features = base.in_features
        self.out_features = base.out_features
        self.rank = rank
        self.alpha = alpha
        self.scaling = alpha / rank
        self.num_loras = num_loras
        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

        # A: in -> r, B: r -> out. Stored as ParameterList so PEFT-style key naming works.
        self.lora_A = nn.ParameterList(
            [nn.Parameter(torch.empty(rank, self.in_features)) for _ in range(num_loras)]
        )
        self.lora_B = nn.ParameterList(
            [nn.Parameter(torch.zeros(self.out_features, rank)) for _ in range(num_loras)]
        )
        for a in self.lora_A:
            nn.init.kaiming_uniform_(a, a=math.sqrt(5))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_out = self.base(x)
        mask = _MaskContext.current
        if mask is None:
            return base_out

        # x: (B, *, in). Mask: (B, num_loras). Broadcast per-sample.
        # Reshape mask to (B, 1, ..., 1) matching x's leading dims after batch.
        extra_dims = x.dim() - 1
        mask_shape = (mask.shape[0],) + (1,) * extra_dims  # (B, 1, ..., 1)

        x_d = self.dropout(x)
        delta = torch.zeros_like(base_out)
        # Always run the same compute path regardless of grad state — a
        # data-dependent branch here breaks torch.utils.checkpoint, which
        # disables autograd during the recomputation pass.
        for i in range(self.num_loras):
            m_i = mask[:, i].view(mask_shape).to(dtype=x.dtype)
            hidden = F.linear(x_d, self.lora_A[i])
            update = F.linear(hidden, self.lora_B[i]) * self.scaling
            delta = delta + update * m_i
        return base_out + delta

    # PEFT-compatible key naming: lora_A.{i}.weight, lora_B.{i}.weight already.


# ---------------------------------------------------------------------------
# Target-module injection
# ---------------------------------------------------------------------------
def _matches_target(qualified_name: str, targets: list[str]) -> bool:
    """True if any target suffix matches the qualified module path."""
    for t in targets:
        # exact suffix match on dotted path
        if qualified_name == t or qualified_name.endswith("." + t):
            return True
    return False


def inject_multi_lora(
    model: nn.Module, target_modules: list[str], rank: int, alpha: float, dropout: float
) -> list[tuple[str, MultiLoRALinear]]:
    """Replaces each nn.Linear whose qualified name matches a target with MultiLoRALinear.

    Returns the list of (name, wrapper) so callers can iterate trainable params.
    """
    replaced: list[tuple[str, MultiLoRALinear]] = []

    # collect first to avoid mutating while iterating
    to_replace: list[tuple[str, str, nn.Linear]] = []
    for name, module in model.named_modules():
        for child_name, child in module.named_children():
            if not isinstance(child, nn.Linear):
                continue
            qualified = f"{name}.{child_name}" if name else child_name
            if _matches_target(qualified, target_modules):
                to_replace.append((name, child_name, child))

    name_to_module = dict(model.named_modules())
    for parent_name, child_name, linear in to_replace:
        parent = name_to_module[parent_name]
        wrapper = MultiLoRALinear(linear, rank=rank, alpha=alpha, dropout=dropout)
        # match base linear dtype/device
        wrapper = wrapper.to(device=linear.weight.device)
        # keep LoRA params in fp32 for training stability
        for p in list(wrapper.lora_A) + list(wrapper.lora_B):
            p.data = p.data.to(dtype=torch.float32)
        setattr(parent, child_name, wrapper)
        qualified = f"{parent_name}.{child_name}" if parent_name else child_name
        replaced.append((qualified, wrapper))

    return replaced


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class CachedAntiAestheticsDataset(Dataset):
    """Loads precomputed (latent, prompt_embeds, text_ids, mask) from disk.

    Built by `precompute_cache.py`. Avoids loading the VAE / text encoder
    into the training process at all.
    """

    def __init__(self, cache_dir: str):
        import json as _json
        self.cache_dir = Path(cache_dir)
        with open(self.cache_dir / "index.json") as f:
            index = _json.load(f)

        self.buckets = [tuple(b) for b in index["buckets"]]
        self.lora_names = index["lora_names"]

        self.train_entries = [e for e in index["entries"] if e["split"] == "train"]
        val_entries = [e for e in index["entries"] if e["split"] == "validation"]
        self.validation_prompts = [e["caption"] for e in val_entries]
        self.validation_masks = [torch.tensor(e["mask"], dtype=torch.float32) for e in val_entries]

        # Used by BucketBatchSampler — mimic AntiAestheticsDataset.pixel_values
        # shape: list of (placeholder, bucket_idx).
        self.pixel_values = [(None, e["bucket_idx"]) for e in self.train_entries]

    def __len__(self):
        return len(self.train_entries)

    def __getitem__(self, idx):
        entry = self.train_entries[idx]
        from safetensors.torch import load_file
        data = load_file(str(self.cache_dir / entry["file"]))
        return {
            "latent": data["latent"],
            "prompt_embeds": data["prompt_embeds"],
            "text_ids": data["text_ids"],
            "mask": data["mask"],
            "bucket_idx": entry["bucket_idx"],
        }


def collate_cached(examples):
    return {
        "latents": torch.stack([e["latent"] for e in examples]),
        "prompt_embeds": torch.stack([e["prompt_embeds"] for e in examples]),
        "text_ids": torch.stack([e["text_ids"] for e in examples]),
        "masks": torch.stack([e["mask"] for e in examples]),
    }


class AntiAestheticsDataset(Dataset):
    """HF dataset of (image, caption, major_classes) -> per-sample multi-hot mask.

    Samples with empty major_classes are dropped (they have no anti-aesthetic
    qualities and would be all-zero targets for every LoRA).
    """

    def __init__(
        self,
        hf_repo: str,
        buckets,
        repeats: int = 1,
        random_flip: bool = False,
        center_crop: bool = False,
        num_validation: int = 20,
        validation_seed: int = 0,
    ):
        ds = load_dataset(hf_repo, split="train")
        self.buckets = buckets
        self.random_flip = random_flip
        self.center_crop = center_crop

        # First pass: enumerate which row indices pass the filter so we can
        # randomly pick a stable validation subset (seeded) before doing any
        # image preprocessing.
        valid_indices = []
        for i, row in enumerate(ds):
            classes = row.get("major_classes") or []
            caption = row.get("anti_aesthetic_caption")
            if not classes or not caption:
                continue
            if not any(c in LORA_NAME_TO_IDX for c in classes):
                continue
            valid_indices.append(i)

        import random as _random
        rng = _random.Random(validation_seed)
        n_val = min(num_validation, len(valid_indices))
        validation_indices = set(rng.sample(valid_indices, n_val))

        self.pixel_values: list[tuple[torch.Tensor, int]] = []
        self.prompts: list[str] = []
        self.masks: list[torch.Tensor] = []
        self.original_indices: list[int] = []

        self.validation_prompts: list[str] = []
        self.validation_masks: list[torch.Tensor] = []

        kept = 0
        for i, row in enumerate(tqdm(ds, desc="Preprocessing dataset")):
            classes = row.get("major_classes") or []
            if not classes:
                continue
            caption = row.get("anti_aesthetic_caption")
            if not caption:
                continue

            mask = torch.zeros(NUM_LORAS, dtype=torch.float32)
            for c in classes:
                if c in LORA_NAME_TO_IDX:
                    mask[LORA_NAME_TO_IDX[c]] = 1.0
            if mask.sum() == 0:
                continue

            if i in validation_indices:
                self.validation_prompts.append(caption)
                self.validation_masks.append(mask.clone())
                continue

            img = exif_transpose(row["image"])
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            bucket_idx = find_nearest_bucket(h, w, self.buckets)
            target_h, target_w = self.buckets[bucket_idx]
            tensor = self._transform(img, (target_h, target_w))

            for _ in range(repeats):
                self.pixel_values.append((tensor, bucket_idx))
                self.prompts.append(caption)
                self.masks.append(mask)
                self.original_indices.append(i)
                kept += 1

        logger.info(f"Loaded {kept} samples (after filtering empty/normal images).")

    def _transform(self, image, size):
        resize = transforms.Resize(size, interpolation=transforms.InterpolationMode.BILINEAR)
        image = resize(image)
        if self.center_crop:
            image = transforms.CenterCrop(size)(image)
        else:
            i, j, h, w = transforms.RandomCrop.get_params(image, output_size=size)
            image = TF.crop(image, i, j, h, w)
        if self.random_flip and random.random() < 0.5:
            image = TF.hflip(image)
        image = transforms.ToTensor()(image)
        image = transforms.Normalize([0.5], [0.5])(image)
        return image

    def __len__(self):
        return len(self.pixel_values)

    def __getitem__(self, idx):
        tensor, bucket_idx = self.pixel_values[idx]
        return {
            "pixel_values": tensor,
            "prompt": self.prompts[idx],
            "mask": self.masks[idx],
            "bucket_idx": bucket_idx,
        }


def collate_fn(examples):
    pixel_values = torch.stack([e["pixel_values"] for e in examples])
    pixel_values = pixel_values.to(memory_format=torch.contiguous_format).float()
    prompts = [e["prompt"] for e in examples]
    masks = torch.stack([e["mask"] for e in examples])
    return {"pixel_values": pixel_values, "prompts": prompts, "masks": masks}


class BucketBatchSampler(BatchSampler):
    def __init__(self, dataset: AntiAestheticsDataset, batch_size: int, drop_last: bool = False):
        self.dataset = dataset
        self.batch_size = batch_size
        self.drop_last = drop_last

        self.bucket_indices = [[] for _ in range(len(dataset.buckets))]
        for idx, (_, b) in enumerate(dataset.pixel_values):
            self.bucket_indices[b].append(idx)

        self.batches = []
        for indices in self.bucket_indices:
            random.shuffle(indices)
            for i in range(0, len(indices), batch_size):
                batch = indices[i : i + batch_size]
                if len(batch) < batch_size and drop_last:
                    continue
                self.batches.append(batch)
        random.shuffle(self.batches)

    def __iter__(self):
        random.shuffle(self.batches)
        for b in self.batches:
            yield b

    def __len__(self):
        return len(self.batches)


# ---------------------------------------------------------------------------
# Validation generation
# ---------------------------------------------------------------------------
def run_validation(
    pipeline: Flux2KleinPipeline,
    prompts: list[str],
    masks: list[torch.Tensor],
    accelerator: Accelerator,
    epoch: int,
    seed: int | None,
    num_inference_steps: int = 28,
    guidance_scale: float = 3.5,
    height: int = 1024,
    width: int = 1024,
    phase: str = "validation",
):
    """Generate one image per (prompt, mask) pair with that mask active."""
    pipeline.set_progress_bar_config(disable=True)
    device = accelerator.device

    images = []
    captions = []
    for prompt, mask in zip(prompts, masks):
        generator = torch.Generator(device=device).manual_seed(seed) if seed is not None else None
        # Mask is (NUM_LORAS,) — broadcast to a single-sample batch (1, NUM_LORAS).
        mask_batched = mask.view(1, -1).to(device=device, dtype=torch.float32)
        with lora_mask(mask_batched):
            with torch.autocast(device.type, enabled=device.type != "cpu"):
                image = pipeline(
                    prompt=prompt,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    height=height,
                    width=width,
                    generator=generator,
                ).images[0]
        images.append(image)
        active = [LORA_NAMES[i] for i in range(NUM_LORAS) if mask[i] > 0]
        captions.append(f"[{','.join(active)}] {prompt}")

    for tracker in accelerator.trackers:
        if tracker.name == "tensorboard":
            import numpy as np
            np_images = np.stack([np.asarray(img) for img in images])
            tracker.writer.add_images(phase, np_images, epoch, dataformats="NHWC")
        elif tracker.name == "wandb":
            import wandb
            tracker.log(
                {phase: [wandb.Image(img, caption=cap) for img, cap in zip(images, captions)]},
                step=epoch,
            )

    return images


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
def save_multi_lora_weights(
    output_dir: str,
    replaced: list[tuple[str, MultiLoRALinear]],
    weight_dtype: torch.dtype = torch.bfloat16,
):
    """Write one safetensors file per LoRA adapter.

    Key format follows the diffusers/PEFT convention so the resulting files
    can be loaded via standard `pipeline.load_lora_weights(...)`:
        transformer.{qualified}.lora_A.weight
        transformer.{qualified}.lora_B.weight
    """
    os.makedirs(output_dir, exist_ok=True)
    for i, name in enumerate(LORA_NAMES):
        state = {}
        for qualified, wrapper in replaced:
            a = wrapper.lora_A[i].detach().to(dtype=weight_dtype).contiguous().cpu()
            b = wrapper.lora_B[i].detach().to(dtype=weight_dtype).contiguous().cpu()
            state[f"transformer.{qualified}.lora_A.weight"] = a
            state[f"transformer.{qualified}.lora_B.weight"] = b
        path = os.path.join(output_dir, f"lora_{i}_{name}.safetensors")
        save_file(state, path)
        logger.info(f"Saved {path} ({len(state)//2} layers)")


# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pretrained_model_name_or_path", type=str, default="black-forest-labs/FLUX.2-klein-9B")
    p.add_argument("--dataset_name", type=str, default="weathon/merged_aa_recaptioned")
    p.add_argument("--output_dir", type=str, default="./multi_lora_aa")
    p.add_argument("--cache_dir", type=str, default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--revision", type=str, default=None)
    p.add_argument("--variant", type=str, default=None)
    p.add_argument("--rank", type=int, default=64)
    p.add_argument("--lora_alpha", type=int, default=64)
    p.add_argument("--lora_dropout", type=float, default=0.0)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--random_flip", action="store_true")
    p.add_argument("--center_crop", action="store_true")
    p.add_argument("--train_batch_size", type=int, default=1)
    p.add_argument("--num_train_epochs", type=int, default=1)
    p.add_argument("--max_train_steps", type=int, default=None)
    p.add_argument("--gradient_accumulation_steps", type=int, default=1)
    p.add_argument("--gradient_checkpointing", action="store_true")
    p.add_argument("--learning_rate", type=float, default=1e-4)
    p.add_argument("--lr_scheduler", type=str, default="constant")
    p.add_argument("--lr_warmup_steps", type=int, default=100)
    p.add_argument("--lr_num_cycles", type=int, default=1)
    p.add_argument("--lr_power", type=float, default=1.0)
    p.add_argument("--adam_beta1", type=float, default=0.9)
    p.add_argument("--adam_beta2", type=float, default=0.999)
    p.add_argument("--adam_weight_decay", type=float, default=1e-4)
    p.add_argument("--adam_epsilon", type=float, default=1e-8)
    p.add_argument("--max_grad_norm", type=float, default=1.0)
    p.add_argument("--mixed_precision", type=str, default="bf16", choices=["no", "fp16", "bf16"])
    p.add_argument("--offload", action="store_true")
    p.add_argument("--cache_latents", action="store_true")
    p.add_argument("--precomputed_cache_dir", type=str, default=None,
                   help="If set, load latents+embeds from this dir (built by precompute_cache.py). "
                        "Skips loading VAE and text encoder entirely.")
    p.add_argument("--captions_dir", type=str, default=None,
                   help="Optional local recaption.py output directory. If set, per-row JSON files "
                        "are used for caption + major_classes instead of dataset columns. "
                        "Ignored when --precomputed_cache_dir is set.")
    p.add_argument("--aspect_ratio_buckets", type=str, default="1024,1024")
    p.add_argument("--weighting_scheme", type=str, default="none")
    p.add_argument("--logit_mean", type=float, default=0.0)
    p.add_argument("--logit_std", type=float, default=1.0)
    p.add_argument("--mode_scale", type=float, default=1.29)
    p.add_argument("--guidance_scale", type=float, default=1.0)
    p.add_argument("--checkpointing_steps", type=int, default=500)
    p.add_argument("--num_validation_samples", type=int, default=20,
                   help="N valid dataset entries randomly reserved as validation set "
                        "(only used when --precomputed_cache_dir is not set; the cache "
                        "carries its own validation set in index.json).")
    p.add_argument("--validation_seed", type=int, default=0,
                   help="Seed for the random validation pick in the non-precomputed path.")
    p.add_argument("--validation_every_n_steps", type=int, default=500,
                   help="Run validation every N optimizer steps. 0 disables.")
    p.add_argument("--validation_inference_steps", type=int, default=28,
                   help="Number of diffusion inference steps used for each validation image.")
    p.add_argument("--validation_guidance", type=float, default=3.5)
    p.add_argument("--validation_height", type=int, default=1024)
    p.add_argument("--validation_width", type=int, default=1024)
    p.add_argument("--skip_final_validation", action="store_true")
    p.add_argument("--dry_run", action="store_true",
                   help="Run 1 training step and 1 validation image, then exit. For smoke testing.")
    p.add_argument("--push_to_hub", action="store_true",
                   help="Upload checkpoints (and final weights) to the Hugging Face Hub.")
    p.add_argument("--hub_model_id", type=str, default=None,
                   help="Repo id on the Hub, e.g. 'user/multi_lora_aa'.")
    p.add_argument("--hub_private", action="store_true",
                   help="Create the Hub repo as private if it doesn't exist.")
    p.add_argument("--hub_token", type=str, default=None,
                   help="HF token. If unset, uses the cached login.")
    p.add_argument("--target_modules", type=str, default=None,
                   help="Comma-separated suffixes. Defaults to attn + qkv_mlp + single-block out projections.")
    p.add_argument("--num_single_blocks", type=int, default=24)
    p.add_argument("--report_to", type=str, default="wandb")
    p.add_argument("--wandb_project", type=str, default="multi-lora-anti-aesthetics")
    p.add_argument("--wandb_run_name", type=str, default=None)
    p.add_argument("--logging_dir", type=str, default="logs")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    logging_dir = Path(args.output_dir, args.logging_dir)
    accelerator_project_config = ProjectConfiguration(project_dir=args.output_dir, logging_dir=str(logging_dir))

    accelerator = Accelerator(
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        mixed_precision=args.mixed_precision,
        log_with=args.report_to,
        project_config=accelerator_project_config,
    )

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO)
    if accelerator.is_local_main_process:
        transformers.utils.logging.set_verbosity_warning()
        diffusers.utils.logging.set_verbosity_info()
    else:
        transformers.utils.logging.set_verbosity_error()
        diffusers.utils.logging.set_verbosity_error()

    if args.seed is not None:
        set_seed(args.seed)
    if accelerator.is_main_process:
        os.makedirs(args.output_dir, exist_ok=True)

    weight_dtype = {"no": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}[args.mixed_precision]
    using_precomputed = args.precomputed_cache_dir is not None

    if args.dry_run:
        args.max_train_steps = 1
        args.num_train_epochs = 1
        args.checkpointing_steps = 10**9  # effectively disabled
        args.validation_every_n_steps = 1
        logger.info("Dry run: max_train_steps=1, validation limited to 1 sample.")

    # Load models -------------------------------------------------------------
    noise_scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
        args.pretrained_model_name_or_path, subfolder="scheduler"
    )
    noise_scheduler_copy = FlowMatchEulerDiscreteScheduler.from_config(noise_scheduler.config)

    # VAE: still need its batch-norm stats for latent normalization even when
    # using a precomputed cache (latents were written pre-normalization).
    vae = AutoencoderKLFlux2.from_pretrained(
        args.pretrained_model_name_or_path, subfolder="vae", revision=args.revision, variant=args.variant
    )
    latents_bn_mean = vae.bn.running_mean.view(1, -1, 1, 1).to(accelerator.device)
    latents_bn_std = torch.sqrt(vae.bn.running_var.view(1, -1, 1, 1) + vae.config.batch_norm_eps).to(accelerator.device)
    vae.requires_grad_(False)

    transformer = Flux2Transformer2DModel.from_pretrained(
        args.pretrained_model_name_or_path,
        subfolder="transformer",
        revision=args.revision,
        variant=args.variant,
        torch_dtype=weight_dtype,
    )
    transformer.requires_grad_(False)
    transformer.to(device=accelerator.device, dtype=weight_dtype)

    if using_precomputed:
        # Free VAE immediately — latents already computed.
        vae.to("cpu")
        del vae
        text_encoder = None
        tokenizer = None
        free_memory()
    else:
        tokenizer = Qwen2TokenizerFast.from_pretrained(
            args.pretrained_model_name_or_path, subfolder="tokenizer", revision=args.revision
        )
        text_encoder = Qwen3ForCausalLM.from_pretrained(
            args.pretrained_model_name_or_path, subfolder="text_encoder", revision=args.revision, variant=args.variant
        )
        text_encoder.requires_grad_(False)
        to_kwargs = {"dtype": weight_dtype, "device": accelerator.device} if not args.offload else {"dtype": weight_dtype}
        vae.to(**to_kwargs)
        text_encoder.to(**to_kwargs)

    if args.gradient_checkpointing:
        transformer.enable_gradient_checkpointing()

    # ----- Inject MultiLoRA --------------------------------------------------
    if args.target_modules is not None:
        target_modules = [t.strip() for t in args.target_modules.split(",")]
    else:
        target_modules = ["to_k", "to_q", "to_v", "to_out.0", "to_qkv_mlp_proj"] + [
            f"single_transformer_blocks.{i}.attn.to_out" for i in range(args.num_single_blocks)
        ]

    replaced = inject_multi_lora(
        transformer,
        target_modules=target_modules,
        rank=args.rank,
        alpha=args.lora_alpha,
        dropout=args.lora_dropout,
    )
    logger.info(f"Injected MultiLoRALinear into {len(replaced)} layers.")
    if len(replaced) == 0:
        raise RuntimeError("No layers matched target_modules. Check naming.")

    trainable_params = []
    for _, wrapper in replaced:
        trainable_params.extend(list(wrapper.lora_A.parameters()))
        trainable_params.extend(list(wrapper.lora_B.parameters()))
    n_trainable = sum(p.numel() for p in trainable_params)
    logger.info(f"Trainable LoRA params: {n_trainable:,}")

    optimizer = torch.optim.AdamW(
        trainable_params,
        lr=args.learning_rate,
        betas=(args.adam_beta1, args.adam_beta2),
        weight_decay=args.adam_weight_decay,
        eps=args.adam_epsilon,
    )

    # ----- Dataset -----------------------------------------------------------
    if using_precomputed:
        train_dataset = CachedAntiAestheticsDataset(args.precomputed_cache_dir)
        buckets = train_dataset.buckets
        if args.dry_run:
            train_dataset.train_entries = train_dataset.train_entries[:1]
            train_dataset.pixel_values = train_dataset.pixel_values[:1]
            train_dataset.validation_prompts = train_dataset.validation_prompts[:1]
            train_dataset.validation_masks = train_dataset.validation_masks[:1]
        sampler = BucketBatchSampler(train_dataset, args.train_batch_size, drop_last=False)
        train_dataloader = torch.utils.data.DataLoader(
            train_dataset, batch_sampler=sampler, collate_fn=collate_cached, num_workers=2
        )
        prompt_embeds_cache = text_ids_cache = latents_cache = masks_cache = None
    else:
        buckets = parse_buckets_string(args.aspect_ratio_buckets)
        train_dataset = AntiAestheticsDataset(
            hf_repo=args.dataset_name,
            buckets=buckets,
            repeats=args.repeats,
            random_flip=args.random_flip,
            center_crop=args.center_crop,
            num_validation=args.num_validation_samples,
            validation_seed=args.validation_seed,
        )
        if args.dry_run:
            train_dataset.pixel_values = train_dataset.pixel_values[:1]
            train_dataset.prompts = train_dataset.prompts[:1]
            train_dataset.masks = train_dataset.masks[:1]
            train_dataset.original_indices = train_dataset.original_indices[:1]
            train_dataset.validation_prompts = train_dataset.validation_prompts[:1]
            train_dataset.validation_masks = train_dataset.validation_masks[:1]
        sampler = BucketBatchSampler(train_dataset, args.train_batch_size, drop_last=False)
        train_dataloader = torch.utils.data.DataLoader(
            train_dataset, batch_sampler=sampler, collate_fn=collate_fn, num_workers=0
        )

        text_encoding_pipeline = Flux2KleinPipeline.from_pretrained(
            args.pretrained_model_name_or_path,
            vae=None,
            transformer=None,
            tokenizer=tokenizer,
            text_encoder=text_encoder,
            scheduler=None,
        )

        def compute_text_embeddings(prompts):
            with torch.no_grad():
                prompt_embeds, text_ids = text_encoding_pipeline.encode_prompt(
                    prompt=prompts, device=accelerator.device
                )
            return prompt_embeds, text_ids

        # Precompute latents + embeddings (mask is per-sample, lives in the batch).
        prompt_embeds_cache, text_ids_cache, latents_cache, masks_cache = [], [], [], []
        for batch in tqdm(train_dataloader, desc="Caching latents/embeds"):
            with torch.no_grad():
                if args.cache_latents:
                    with offload_models(vae, device=accelerator.device, offload=args.offload):
                        pv = batch["pixel_values"].to(accelerator.device, non_blocking=True, dtype=vae.dtype)
                        latents_cache.append(vae.encode(pv).latent_dist)
                with offload_models(text_encoding_pipeline, device=accelerator.device, offload=args.offload):
                    pe, ti = compute_text_embeddings(batch["prompts"])
                prompt_embeds_cache.append(pe)
                text_ids_cache.append(ti)
                masks_cache.append(batch["masks"])

        if args.cache_latents:
            vae.to("cpu")
            del vae
        text_encoding_pipeline.to("cpu")
        del text_encoder, tokenizer
        free_memory()

    # ----- LR scheduler ------------------------------------------------------
    num_update_steps_per_epoch = math.ceil(len(train_dataloader) / args.gradient_accumulation_steps)
    if args.max_train_steps is None:
        args.max_train_steps = args.num_train_epochs * num_update_steps_per_epoch
    else:
        args.num_train_epochs = math.ceil(args.max_train_steps / num_update_steps_per_epoch)

    lr_scheduler = get_scheduler(
        args.lr_scheduler,
        optimizer=optimizer,
        num_warmup_steps=args.lr_warmup_steps * accelerator.num_processes,
        num_training_steps=args.max_train_steps * accelerator.num_processes,
        num_cycles=args.lr_num_cycles,
        power=args.lr_power,
    )

    transformer, optimizer, train_dataloader, lr_scheduler = accelerator.prepare(
        transformer, optimizer, train_dataloader, lr_scheduler
    )

    if accelerator.is_main_process:
        init_kwargs = {}
        if args.report_to == "wandb" and args.wandb_run_name is not None:
            init_kwargs["wandb"] = {"name": args.wandb_run_name}
        accelerator.init_trackers(args.wandb_project, config=vars(args), init_kwargs=init_kwargs)

    # ----- Hub setup ---------------------------------------------------------
    hub_api: HfApi | None = None
    hub_repo_id: str | None = None
    if args.push_to_hub and accelerator.is_main_process:
        if not args.hub_model_id:
            raise ValueError("--push_to_hub requires --hub_model_id.")
        hub_api = HfApi(token=args.hub_token)
        hub_repo_id = create_repo(
            repo_id=args.hub_model_id,
            exist_ok=True,
            private=args.hub_private,
            token=args.hub_token,
        ).repo_id
        logger.info(f"Will push checkpoints to https://huggingface.co/{hub_repo_id}")

    # ----- Train -------------------------------------------------------------
    def get_sigmas(timesteps, n_dim=4, dtype=torch.float32):
        sigmas = noise_scheduler_copy.sigmas.to(device=accelerator.device, dtype=dtype)
        schedule_timesteps = noise_scheduler_copy.timesteps.to(accelerator.device)
        timesteps = timesteps.to(accelerator.device)
        step_indices = [(schedule_timesteps == t).nonzero().item() for t in timesteps]
        sigma = sigmas[step_indices].flatten()
        while len(sigma.shape) < n_dim:
            sigma = sigma.unsqueeze(-1)
        return sigma

    global_step = 0
    progress_bar = tqdm(range(args.max_train_steps), desc="Steps",
                        disable=not accelerator.is_local_main_process)

    for epoch in range(args.num_train_epochs):
        transformer.train()
        for step, batch in enumerate(train_dataloader):
            with accelerator.accumulate(transformer):
                if using_precomputed:
                    prompt_embeds = batch["prompt_embeds"].to(accelerator.device, dtype=weight_dtype)
                    text_ids = batch["text_ids"].to(accelerator.device)
                    masks = batch["masks"].to(accelerator.device, dtype=weight_dtype)
                    model_input = batch["latents"].to(accelerator.device, dtype=weight_dtype)
                else:
                    prompt_embeds = prompt_embeds_cache[step].to(accelerator.device)
                    text_ids = text_ids_cache[step].to(accelerator.device)
                    masks = masks_cache[step].to(accelerator.device, dtype=weight_dtype)

                    if args.cache_latents:
                        model_input = latents_cache[step].mode()
                    else:
                        with offload_models(vae, device=accelerator.device, offload=args.offload):
                            pixel_values = batch["pixel_values"].to(accelerator.device, dtype=vae.dtype)
                            model_input = vae.encode(pixel_values).latent_dist.mode()

                model_input = Flux2KleinPipeline._patchify_latents(model_input)
                model_input = (model_input - latents_bn_mean) / latents_bn_std
                model_input_ids = Flux2KleinPipeline._prepare_latent_ids(model_input).to(device=model_input.device)

                noise = torch.randn_like(model_input)
                bsz = model_input.shape[0]

                u = compute_density_for_timestep_sampling(
                    weighting_scheme=args.weighting_scheme,
                    batch_size=bsz,
                    logit_mean=args.logit_mean,
                    logit_std=args.logit_std,
                    mode_scale=args.mode_scale,
                )
                indices = (u * noise_scheduler_copy.config.num_train_timesteps).long()
                timesteps = noise_scheduler_copy.timesteps[indices].to(device=model_input.device)
                sigmas = get_sigmas(timesteps, n_dim=model_input.ndim, dtype=model_input.dtype)
                noisy_model_input = (1.0 - sigmas) * model_input + sigmas * noise

                packed_noisy_model_input = Flux2KleinPipeline._pack_latents(noisy_model_input)

                if accelerator.unwrap_model(transformer).config.guidance_embeds:
                    guidance = torch.full([1], args.guidance_scale, device=accelerator.device)
                    guidance = guidance.expand(model_input.shape[0])
                else:
                    guidance = None

                with lora_mask(masks):
                    model_pred = transformer(
                        hidden_states=packed_noisy_model_input,
                        timestep=timesteps / 1000,
                        guidance=guidance,
                        encoder_hidden_states=prompt_embeds,
                        txt_ids=text_ids,
                        img_ids=model_input_ids,
                        return_dict=False,
                    )[0]
                model_pred = model_pred[:, : packed_noisy_model_input.size(1) :]
                model_pred = Flux2KleinPipeline._unpack_latents_with_ids(model_pred, model_input_ids)

                weighting = compute_loss_weighting_for_sd3(weighting_scheme=args.weighting_scheme, sigmas=sigmas)
                target = noise - model_input
                loss = torch.mean(
                    (weighting.float() * (model_pred.float() - target.float()) ** 2).reshape(target.shape[0], -1), 1
                ).mean()

                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(trainable_params, args.max_grad_norm)
                optimizer.step()
                lr_scheduler.step()
                optimizer.zero_grad()

            if accelerator.sync_gradients:
                progress_bar.update(1)
                global_step += 1
                if accelerator.is_main_process and global_step % args.checkpointing_steps == 0:
                    ckpt_dir = os.path.join(args.output_dir, f"checkpoint-{global_step}")
                    save_multi_lora_weights(ckpt_dir, replaced, weight_dtype=weight_dtype)
                    if hub_api is not None:
                        _upload_checkpoint(
                            hub_api, hub_repo_id, ckpt_dir,
                            path_in_repo=f"checkpoint-{global_step}",
                            commit_message=f"checkpoint-{global_step}",
                        )

                if (
                    accelerator.is_main_process
                    and train_dataset.validation_prompts
                    and args.validation_every_n_steps > 0
                    and global_step % args.validation_every_n_steps == 0
                ):
                    _run_validation_step(
                        args=args,
                        accelerator=accelerator,
                        transformer=transformer,
                        train_dataset=train_dataset,
                        weight_dtype=weight_dtype,
                        step=global_step,
                        phase="validation",
                    )
                    transformer.train()

            logs = {"loss": loss.detach().item(), "lr": lr_scheduler.get_last_lr()[0]}
            progress_bar.set_postfix(**logs)
            accelerator.log(logs, step=global_step)

            if global_step >= args.max_train_steps:
                break

        if global_step >= args.max_train_steps:
            break

    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        save_multi_lora_weights(args.output_dir, replaced, weight_dtype=weight_dtype)
        if hub_api is not None:
            _upload_checkpoint(
                hub_api, hub_repo_id, args.output_dir,
                path_in_repo="final",
                commit_message="final weights",
            )

        if not args.skip_final_validation and train_dataset.validation_prompts:
            _run_validation_step(
                args=args,
                accelerator=accelerator,
                transformer=transformer,
                train_dataset=train_dataset,
                weight_dtype=weight_dtype,
                step=global_step,
                phase="test",
            )
    accelerator.end_training()


def _upload_checkpoint(hub_api: HfApi, repo_id: str, local_dir: str, path_in_repo: str, commit_message: str):
    """Push a checkpoint directory (5 .safetensors files) to the HF Hub.

    Uploads only *.safetensors so we don't accidentally push wandb logs or
    other side artifacts that may live under output_dir.
    """
    logger.info(f"Uploading {local_dir} -> {repo_id}/{path_in_repo}")
    try:
        hub_api.upload_folder(
            folder_path=local_dir,
            repo_id=repo_id,
            path_in_repo=path_in_repo,
            commit_message=commit_message,
            allow_patterns=["*.safetensors"],
            run_as_future=False,
        )
    except Exception as e:
        # Don't let an upload failure kill the training run.
        logger.warning(f"Hub upload failed for {path_in_repo}: {e}")


def _run_validation_step(args, accelerator, transformer, train_dataset, weight_dtype, step, phase):
    """Build an inference pipeline using the trained transformer and generate
    one image per validation (prompt, mask) entry."""
    logger.info(f"Running {phase} ({len(train_dataset.validation_prompts)} samples) at step {step}.")
    unwrapped = accelerator.unwrap_model(transformer)
    pipeline = Flux2KleinPipeline.from_pretrained(
        args.pretrained_model_name_or_path,
        transformer=unwrapped,
        revision=args.revision,
        variant=args.variant,
        torch_dtype=weight_dtype,
    )
    pipeline.to(accelerator.device)
    try:
        run_validation(
            pipeline=pipeline,
            prompts=train_dataset.validation_prompts,
            masks=train_dataset.validation_masks,
            accelerator=accelerator,
            epoch=step,
            seed=args.seed,
            num_inference_steps=args.validation_inference_steps,
            guidance_scale=args.validation_guidance,
            height=args.validation_height,
            width=args.validation_width,
            phase=phase,
        )
    finally:
        del pipeline
        free_memory()


if __name__ == "__main__":
    main()
