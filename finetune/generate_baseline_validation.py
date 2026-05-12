#!/usr/bin/env python
# coding=utf-8
# Generate baseline images for the 10 held-out validation prompts using the
# unmodified base FLUX 2 Klein model (no LoRA). Useful as a reference to
# compare against the multi-LoRA training outputs at later steps.

import argparse
import json
from pathlib import Path

import torch
from tqdm.auto import tqdm

from diffusers import Flux2KleinPipeline


LORA_NAMES = [
    "clarity_and_focus",
    "color_and_tone",
    "lighting_and_exposure",
    "composition_and_structure",
    "emotion_and_subject",
]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pretrained_model_name_or_path", type=str, default="black-forest-labs/FLUX.2-klein-base-9B")
    p.add_argument("--cache_dir", type=str, default="./cache_aa",
                   help="Path to the precompute_cache.py output; reads index.json for prompts/masks.")
    p.add_argument("--output_dir", type=str, default="./baseline_validation")
    p.add_argument("--num_inference_steps", type=int, default=28)
    p.add_argument("--guidance_scale", type=float, default=3.5)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dtype", type=str, default="bf16", choices=["fp32", "fp16", "bf16"])
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--revision", type=str, default=None)
    p.add_argument("--variant", type=str, default=None)
    return p.parse_args()


def main():
    args = parse_args()
    dtype = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}[args.dtype]
    device = torch.device(args.device)

    cache_dir = Path(args.cache_dir)
    with open(cache_dir / "index.json") as f:
        index = json.load(f)
    val_entries = [e for e in index["entries"] if e["split"] == "validation"]
    print(f"Found {len(val_entries)} validation entries in {cache_dir}/index.json")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading pipeline {args.pretrained_model_name_or_path}...")
    pipeline = Flux2KleinPipeline.from_pretrained(
        args.pretrained_model_name_or_path,
        revision=args.revision,
        variant=args.variant,
        torch_dtype=dtype,
    ).to(device)
    pipeline.set_progress_bar_config(disable=True)

    manifest = []
    for i, entry in enumerate(tqdm(val_entries, desc="Generating")):
        prompt = entry["caption"]
        mask = entry["mask"]
        active = [LORA_NAMES[j] for j, v in enumerate(mask) if v > 0]

        generator = torch.Generator(device=device).manual_seed(args.seed) if args.seed is not None else None
        image = pipeline(
            prompt=prompt,
            num_inference_steps=args.num_inference_steps,
            guidance_scale=args.guidance_scale,
            height=args.height,
            width=args.width,
            generator=generator,
        ).images[0]

        fname = f"{i:02d}.png"
        image.save(output_dir / fname)
        manifest.append({
            "file": fname,
            "caption": prompt,
            "mask": mask,
            "active_categories": active,
        })

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(
            {
                "base_model": args.pretrained_model_name_or_path,
                "num_inference_steps": args.num_inference_steps,
                "guidance_scale": args.guidance_scale,
                "height": args.height,
                "width": args.width,
                "seed": args.seed,
                "entries": manifest,
            },
            f,
            indent=2,
        )
    print(f"Wrote {len(manifest)} images + manifest.json to {output_dir}")


if __name__ == "__main__":
    main()
