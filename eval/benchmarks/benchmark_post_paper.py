"""
Post-paper generation benchmark.

Mirrors benchmark.py but is intentionally simpler:
    - Saves images as local PNG files under output_dir/<model>/<index>_<variant>.png
    - Does NOT push to the HF dataset.
    - Does NOT call HPSv3 / the LLM judge — score with score_post_paper_hpsv3.py
      after this script finishes.

Models supported (matches the post-paper rows shown on the website):
    gpt-image-1.5, qwen_image, seeddream4,
    flux2_klein_9b, z_image, z_image_turbo, glm_image, alchemist,
    longcat_image

The non-pipeline models reuse the same API wrappers as benchmark.py, so the
OPENAI_API_KEY / OPENROUTER_API_KEY / REPLICATE_API_TOKEN env vars in .env
work unchanged. Run from this directory (paths to prompts.json are relative).

Usage:
    python3 benchmark_post_paper.py --models flux2_klein_9b z_image_turbo \\
        --cuda-device 0 --output-dir post_paper_images --num-prompts 300
"""

import argparse
import base64
import json
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Callable, List, Optional

import torch
from datasets import load_dataset
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image


# -----------------------------------------------------------------------------
# Globals (set in __main__ so the API-only models don't force a CUDA load)
# -----------------------------------------------------------------------------
DEVICE_STR = "cuda"
image_client: Optional[OpenAI] = None        # OpenAI client (gpt-image-*)
openrouter_client: Optional[OpenAI] = None    # currently unused; kept for symmetry
replicate_module = None                       # lazy-import replicate
image_pipelines: dict = {}                    # cache of loaded diffusers pipelines


# -----------------------------------------------------------------------------
# Pipeline registry
#   key                    -> (kind, hf_repo_id)
#   - "kind" picks the loader/inference branch below.
#   - API-only models (gpt-image-1.5, qwen_image, seeddream4) are NOT here;
#     they short-circuit in get_image_generator().
# -----------------------------------------------------------------------------
PIPE_CONFIG = {
    "flux2_klein_9b": ("flux2_klein", "black-forest-labs/FLUX.2-klein-9B"),
    "z_image":        ("z_image",      "Tongyi-MAI/Z-Image"),
    "z_image_turbo":  ("z_image_turbo", "Tongyi-MAI/Z-Image-Turbo"),
    "glm_image":      ("glm_image",    "zai-org/GLM-Image"),
    "alchemist":      ("sd3",          "yandex/stable-diffusion-3.5-large-alchemist"),
    "longcat_image":  ("longcat",      "meituan-longcat/LongCat-Image"),
}

API_MODELS = {"gpt-image-1.5", "qwen_image", "seeddream4"}


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    available = sorted(API_MODELS | set(PIPE_CONFIG.keys()))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--models", "-m", nargs="+", required=True,
        help="image model(s) to benchmark. Available: " + ", ".join(available),
    )
    parser.add_argument(
        "--output-dir", "-o", default="post_paper_images",
        help="local directory to save generated PNGs (default: post_paper_images)",
    )
    parser.add_argument(
        "--cuda-device", default="0",
        help="CUDA_VISIBLE_DEVICES index. Ignored for API-only models.",
    )
    parser.add_argument(
        "--num-prompts", "-n", type=int, default=300,
        help="how many prompts from the dataset to use (default: 300, matches paper)",
    )
    parser.add_argument(
        "--dataset", default="weathon/anti_aesthetics_dataset",
        help="HF dataset id for the prompt list",
    )
    parser.add_argument(
        "--skip-existing", action="store_true", default=True,
        help="skip prompts whose output PNG already exists (default on)",
    )
    parser.add_argument(
        "--variants", nargs="+", default=["original", "distorted"],
        choices=["original", "distorted"],
        help="which prompt variants to render (default: both)",
    )
    return parser.parse_args()


# -----------------------------------------------------------------------------
# API-based generators (lifted from benchmark.py; gpt-image-1.5 is new)
# -----------------------------------------------------------------------------
def gpt_image_1_5_generate(prompt: str, quality: str = "high") -> Image.Image:
    """OpenAI gpt-image-1.5 (released after the paper)."""
    last_error = None
    for attempt in range(5):
        try:
            result = image_client.images.generate(
                model="gpt-image-1.5",
                prompt=prompt,
                quality=quality,
                size="1024x1024",
            )
            image_bytes = base64.b64decode(result.data[0].b64_json)
            return Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            last_error = exc
            if attempt == 4:
                print(f"gpt-image-1.5 failed after retries: {exc}")
                return Image.new("RGB", (1024, 1024), color=(0, 0, 255))
            print(f"retrying gpt-image-1.5 due to error: {exc}")
            time.sleep(2 ** attempt)
    return Image.new("RGB", (1024, 1024), color=(0, 0, 255))


def seeddream4_generate(prompt: str) -> Image.Image:
    output = replicate_module.run(
        "bytedance/seedream-4",
        input={
            "size": "1K",
            "width": 1024,
            "height": 1024,
            "prompt": prompt,
            "max_images": 1,
            "image_input": [],
            "aspect_ratio": "1:1",
            "sequential_image_generation": "disabled",
        },
    )
    image_bytes = output[0].read()
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def qwen_image_generate(prompt: str, negative_prompt: Optional[str]) -> Image.Image:
    payload = {
        "prompt": prompt,
        "go_fast": True,
        "guidance": 4,
        "image_size": "optimize_for_quality",
        "aspect_ratio": "1:1",
        "output_format": "png",
        "enhance_prompt": False,
        "num_inference_steps": 50,
    }
    if negative_prompt is not None:
        payload["negative_prompt"] = negative_prompt
    output = replicate_module.run("qwen/qwen-image", input=payload)
    image_bytes = output[0].read()
    return Image.open(BytesIO(image_bytes)).convert("RGB")


# -----------------------------------------------------------------------------
# Local-pipeline loaders (FLUX.2 / Z-Image(-Turbo) / GLM-Image / Alchemist)
# -----------------------------------------------------------------------------
def load_image_pipeline(model_name: str):
    if model_name in image_pipelines:
        return image_pipelines[model_name]
    if model_name not in PIPE_CONFIG:
        raise ValueError(f"Unsupported pipeline model: {model_name}")

    kind, repo_id = PIPE_CONFIG[model_name]

    if kind == "flux2_klein":
        # FLUX.2 [klein] 9B — requires bleeding-edge diffusers
        # (pip install -U git+https://github.com/huggingface/diffusers.git)
        from diffusers import Flux2Pipeline
        pipe = Flux2Pipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16).to(DEVICE_STR)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pass

    elif kind == "z_image":
        # Z-Image base (CFG, ~6B params)
        from diffusers import ZImagePipeline
        pipe = ZImagePipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16).to(DEVICE_STR)

    elif kind == "z_image_turbo":
        # Z-Image-Turbo (step-distilled, 8 NFE)
        from diffusers import ZImagePipeline
        pipe = ZImagePipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16).to(DEVICE_STR)

    elif kind == "glm_image":
        # GLM-Image — hybrid AR + diffusion decoder
        from diffusers import GlmImagePipeline
        pipe = GlmImagePipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16).to(DEVICE_STR)

    elif kind == "sd3":
        # Alchemist = yandex/stable-diffusion-3.5-large-alchemist
        from diffusers import StableDiffusion3Pipeline
        pipe = StableDiffusion3Pipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16).to(DEVICE_STR)

    elif kind == "longcat":
        # LongCat-Image (Meituan) — needs CPU offload, ~17 GB VRAM
        from diffusers import LongCatImagePipeline
        pipe = LongCatImagePipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16)
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe = pipe.to(DEVICE_STR)

    else:
        raise ValueError(f"Unknown pipeline kind: {kind}")

    image_pipelines[model_name] = pipe
    return pipe


def generate_with_pipe(model_name: str, pipe, sample: dict, variant: str) -> Image.Image:
    """Run one image through a loaded diffusers pipeline."""
    kind, _ = PIPE_CONFIG[model_name]
    prompt = sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
    # For distorted variant we pass an empty negative prompt (matches benchmark.py).
    neg = "" if variant == "distorted" else None

    if kind == "flux2_klein":
        # 4-step distilled; bf16
        kwargs = dict(
            prompt=prompt,
            num_inference_steps=4,
            guidance_scale=0.0,        # distilled, no CFG
            height=1024, width=1024,
        )
        return pipe(**kwargs).images[0]

    if kind == "z_image":
        kwargs = dict(
            prompt=prompt,
            num_inference_steps=50,
            guidance_scale=3.5,
            height=1024, width=1024,
        )
        if neg is not None:
            kwargs["negative_prompt"] = neg
        return pipe(**kwargs).images[0]

    if kind == "z_image_turbo":
        # Distilled — 8 NFE, no CFG
        kwargs = dict(
            prompt=prompt,
            num_inference_steps=8,
            guidance_scale=1.0,
            height=1024, width=1024,
        )
        return pipe(**kwargs).images[0]

    if kind == "glm_image":
        kwargs = dict(
            prompt=prompt,
            num_inference_steps=50,
            guidance_scale=5.0,
            height=1024, width=1024,
        )
        if neg is not None:
            kwargs["negative_prompt"] = neg
        return pipe(**kwargs).images[0]

    if kind == "sd3":
        # Alchemist (SD3.5 Large finetune)
        kwargs = dict(
            prompt=prompt,
            prompt_2=prompt,
            prompt_3=prompt,
            num_inference_steps=40 if variant == "original" else 32,
            guidance_scale=4.0 if variant == "original" else 6.0,
            height=1024, width=1024,
        )
        if neg is not None:
            kwargs["negative_prompt"] = neg
        return pipe(**kwargs).images[0]

    if kind == "longcat":
        # LongCat-Image — square output to match the rest of the sweep
        kwargs = dict(
            prompt=prompt,
            height=1024, width=1024,
            guidance_scale=4.0,
            num_inference_steps=50,
            num_images_per_prompt=1,
            enable_cfg_renorm=True,
            enable_prompt_rewrite=False,  # off so we score what the user actually typed
        )
        return pipe(**kwargs).images[0]

    raise ValueError(f"No generator branch for kind={kind}")


def get_image_generator(model_name: str) -> Callable[[dict, str], Image.Image]:
    if model_name == "gpt-image-1.5":
        return lambda s, v: gpt_image_1_5_generate(
            s["original_prompt"] if v == "original" else s["disorted_long_prompt"]
        )
    if model_name == "seeddream4":
        return lambda s, v: seeddream4_generate(
            s["original_prompt"] if v == "original" else s["disorted_long_prompt"]
        )
    if model_name == "qwen_image":
        return lambda s, v: qwen_image_generate(
            s["disorted_long_prompt"] if v == "distorted" else s["original_prompt"],
            "" if v == "distorted" else None,
        )

    pipe = load_image_pipeline(model_name)
    return lambda s, v: generate_with_pipe(model_name, pipe, s, v)


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------
def run_one_model(model_name: str, args: argparse.Namespace) -> None:
    out_root = Path(args.output_dir) / model_name
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"[{model_name}] loading dataset {args.dataset}[:{args.num_prompts}]")
    dataset = load_dataset(args.dataset, split=f"train[:{args.num_prompts}]")

    print(f"[{model_name}] preparing generator")
    image_generator = get_image_generator(model_name)

    # Persist prompt metadata alongside the images so the scorer is standalone.
    meta_path = out_root / "_prompts.jsonl"
    with meta_path.open("w") as f:
        for index, sample in enumerate(dataset):
            f.write(json.dumps({
                "index": index,
                "prompt_original": sample["original_prompt"],
                "prompt_distorted": sample["disorted_long_prompt"],
                "selected_dims": list(sample["selected"]),
            }) + "\n")

    for index, sample in enumerate(dataset):
        for variant in args.variants:
            out_path = out_root / f"{index:04d}_{variant}.png"
            if args.skip_existing and out_path.exists():
                continue
            try:
                img = image_generator(sample, variant)
            except Exception as exc:
                print(f"[{model_name}] index={index} variant={variant} FAILED: {exc}")
                continue
            img.save(out_path, format="PNG", optimize=False)
            print(f"[{model_name}] {out_path}")


def main(args: argparse.Namespace) -> None:
    expanded: List[str] = []
    for m in args.models:
        expanded.extend(tok.strip() for tok in m.split(",") if tok.strip())

    for model in expanded:
        if model not in API_MODELS and model not in PIPE_CONFIG:
            raise SystemExit(f"unknown model: {model}")
        print(f"=== benchmark: {model} ===")
        run_one_model(model, args)


if __name__ == "__main__":
    args = parse_args()
    load_dotenv()

    # Only set up CUDA if at least one local pipeline is in the list.
    needs_cuda = any(m in PIPE_CONFIG for m in args.models)
    if needs_cuda:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA device required for the chosen pipeline models")
        device_index = int(args.cuda_device)
        if device_index < 0 or device_index >= torch.cuda.device_count():
            raise RuntimeError(f"CUDA device {device_index} out of range")
        torch.cuda.set_device(device_index)
        DEVICE_STR = f"cuda:{device_index}"

    # Lazy API clients — only built when needed.
    if "gpt-image-1.5" in args.models:
        image_client = OpenAI()
    if any(m in {"seeddream4", "qwen_image"} for m in args.models):
        import replicate
        replicate_module = replicate

    main(args)
