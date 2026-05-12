#!/usr/bin/env python
# coding=utf-8
# Precompute VAE latents + Qwen text embeddings for the anti-aesthetics
# dataset and write them to disk as a single safetensors file per sample.
#
# The training script can then load these without ever touching the VAE or
# text encoder, which lets us free both before training starts.
#
# Output layout (per sample):
#   {cache_dir}/{idx:08d}.safetensors
#     - "latent"          (C, H, W)   bf16  -- VAE.encode(image).latent_dist.mode()
#     - "prompt_embeds"   (T, D)      bf16
#     - "text_ids"        (T, 4)      float32
#     - "mask"            (5,)        float32
#     - "bucket_idx"      ()          int64
#
# Captions, masks, and bucket indices are also written to {cache_dir}/index.json
# so the training script can build the bucket sampler without re-loading the
# HF dataset.

import argparse
import json
import os
from pathlib import Path

import torch
from datasets import load_dataset
from PIL.ImageOps import exif_transpose
from safetensors.torch import save_file
from torchvision import transforms
from torchvision.transforms import functional as TF
from tqdm.auto import tqdm
from transformers import Qwen2TokenizerFast, Qwen3ForCausalLM

from diffusers import AutoencoderKLFlux2, Flux2KleinPipeline
from diffusers.training_utils import find_nearest_bucket, parse_buckets_string


LORA_NAMES = [
    "clarity_and_focus",
    "color_and_tone",
    "lighting_and_exposure",
    "composition_and_structure",
    "emotion_and_subject",
]
LORA_NAME_TO_IDX = {n: i for i, n in enumerate(LORA_NAMES)}
NUM_LORAS = len(LORA_NAMES)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pretrained_model_name_or_path", type=str, default="black-forest-labs/FLUX.2-klein-9B")
    p.add_argument("--dataset_name", type=str, default="weathon/merged_aa_recaptioned")
    p.add_argument("--cache_dir", type=str, default="./cache_aa")
    p.add_argument("--aspect_ratio_buckets", type=str, default="1024,1024")
    p.add_argument("--num_validation", type=int, default=20,
                   help="N valid entries are randomly sampled (seeded by --validation_seed) "
                        "and tagged as validation in index.json (not preprocessed).")
    p.add_argument("--validation_seed", type=int, default=0,
                   help="Seed used to randomly pick the validation set.")
    p.add_argument("--center_crop", action="store_true")
    p.add_argument("--revision", type=str, default=None)
    p.add_argument("--variant", type=str, default=None)
    p.add_argument("--dtype", type=str, default="bf16", choices=["fp32", "fp16", "bf16"])
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry_run", action="store_true",
                   help="Process only one training sample (plus the validation reserve) and exit.")
    return p.parse_args()


def transform_image(image, size, center_crop):
    image = transforms.Resize(size, interpolation=transforms.InterpolationMode.BILINEAR)(image)
    if center_crop:
        image = transforms.CenterCrop(size)(image)
    else:
        i, j, h, w = transforms.RandomCrop.get_params(image, output_size=size)
        image = TF.crop(image, i, j, h, w)
    image = transforms.ToTensor()(image)
    image = transforms.Normalize([0.5], [0.5])(image)
    return image


def main():
    args = parse_args()
    dtype = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}[args.dtype]
    device = torch.device(args.device)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    buckets = parse_buckets_string(args.aspect_ratio_buckets)

    print(f"Loading dataset {args.dataset_name}...")
    ds = load_dataset(args.dataset_name, split="train")

    # ---- First pass: enumerate row indices that pass the filter, so we can
    # randomly pick the validation subset before any expensive work. We only
    # need the metadata columns here, not the images.
    print("Scanning for valid rows (caption + non-empty mask)...")
    valid_indices = []
    for i, row in enumerate(tqdm(ds, desc="Scanning")):
        classes = row.get("major_classes") or []
        caption = row.get("anti_aesthetic_caption")
        if not classes or not caption:
            continue
        if not any(c in LORA_NAME_TO_IDX for c in classes):
            continue
        valid_indices.append(i)
    print(f"  {len(valid_indices)} valid rows out of {len(ds)}")

    import random as _random
    rng = _random.Random(args.validation_seed)
    n_val = min(args.num_validation, len(valid_indices))
    validation_indices = set(rng.sample(valid_indices, n_val))
    print(f"  Selected {n_val} validation indices (seed={args.validation_seed})")

    print("Loading VAE + text encoder...")
    vae = AutoencoderKLFlux2.from_pretrained(
        args.pretrained_model_name_or_path, subfolder="vae", revision=args.revision, variant=args.variant
    ).to(device=device, dtype=dtype).eval()
    vae.requires_grad_(False)

    tokenizer = Qwen2TokenizerFast.from_pretrained(
        args.pretrained_model_name_or_path, subfolder="tokenizer", revision=args.revision
    )
    text_encoder = Qwen3ForCausalLM.from_pretrained(
        args.pretrained_model_name_or_path, subfolder="text_encoder", revision=args.revision, variant=args.variant
    ).to(device=device, dtype=dtype).eval()
    text_encoder.requires_grad_(False)

    text_encoding_pipeline = Flux2KleinPipeline.from_pretrained(
        args.pretrained_model_name_or_path,
        vae=None,
        transformer=None,
        tokenizer=tokenizer,
        text_encoder=text_encoder,
        scheduler=None,
    )

    index_entries = []
    train_idx = 0
    val_count = 0
    skipped = 0

    pbar = tqdm(enumerate(ds), desc="Caching", total=len(ds))
    for row_idx, row in pbar:
        classes = row.get("major_classes") or []
        caption = row.get("anti_aesthetic_caption")
        if not classes or not caption:
            skipped += 1
            continue

        mask = torch.zeros(NUM_LORAS, dtype=torch.float32)
        for c in classes:
            if c in LORA_NAME_TO_IDX:
                mask[LORA_NAME_TO_IDX[c]] = 1.0
        if mask.sum() == 0:
            skipped += 1
            continue

        # Validation set: randomly chosen ahead of the main loop (seeded).
        if row_idx in validation_indices:
            index_entries.append({
                "split": "validation",
                "caption": caption,
                "mask": mask.tolist(),
            })
            val_count += 1
            continue

        out_path = cache_dir / f"{train_idx:08d}.safetensors"
        if out_path.exists() and not args.overwrite:
            # Still need to reconstruct the index entry — peek at bucket_idx
            # via the file would require loading; cheaper to just recompute
            # bucket_idx from the image size.
            img = row["image"]
            w, h = img.size
            bucket_idx = int(find_nearest_bucket(h, w, buckets))
            index_entries.append({
                "split": "train",
                "caption": caption,
                "mask": mask.tolist(),
                "bucket_idx": bucket_idx,
                "file": out_path.name,
            })
            train_idx += 1
            continue

        img = exif_transpose(row["image"])
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        bucket_idx = int(find_nearest_bucket(h, w, buckets))
        target_h, target_w = buckets[bucket_idx]
        tensor = transform_image(img, (target_h, target_w), center_crop=args.center_crop)

        with torch.no_grad():
            pixel = tensor.unsqueeze(0).to(device=device, dtype=dtype)
            latent = vae.encode(pixel).latent_dist.mode().squeeze(0)  # (C, H, W)

            prompt_embeds, text_ids = text_encoding_pipeline.encode_prompt(
                prompt=[caption], device=device
            )
            prompt_embeds = prompt_embeds.squeeze(0)  # (T, D)
            text_ids = text_ids.squeeze(0) if text_ids.dim() == 3 else text_ids  # (T, 4)

        save_file(
            {
                "latent": latent.detach().to(dtype=dtype).contiguous().cpu(),
                "prompt_embeds": prompt_embeds.detach().to(dtype=dtype).contiguous().cpu(),
                "text_ids": text_ids.detach().to(dtype=torch.float32).contiguous().cpu(),
                "mask": mask.contiguous(),
                "bucket_idx": torch.tensor(bucket_idx, dtype=torch.int64),
            },
            str(out_path),
        )

        index_entries.append({
            "split": "train",
            "caption": caption,
            "mask": mask.tolist(),
            "bucket_idx": bucket_idx,
            "file": out_path.name,
        })
        train_idx += 1
        pbar.set_postfix(train=train_idx, val=val_count, skipped=skipped)

        if args.dry_run and train_idx >= 1:
            print("Dry run: stopping after 1 training sample.")
            break

    index_path = cache_dir / "index.json"
    with open(index_path, "w") as f:
        json.dump(
            {
                "buckets": [list(b) for b in buckets],
                "lora_names": LORA_NAMES,
                "dtype": args.dtype,
                "dataset": args.dataset_name,
                "entries": index_entries,
            },
            f,
        )
    print(f"Wrote {train_idx} train samples + {val_count} validation entries to {cache_dir}")
    print(f"Skipped {skipped} (empty/normal images). Index: {index_path}")


if __name__ == "__main__":
    main()
