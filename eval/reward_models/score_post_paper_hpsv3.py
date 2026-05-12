"""
Score the local images written by benchmark_post_paper.py with HPSv3.

For every PNG under <input-dir>/<model>/<index>_<variant>.png we:
    - Look up the prompt for that index from _prompts.jsonl
    - ALWAYS score under prompt_original (the user's request) — both for
      the "original" variant (sanity baseline) and the "distorted" variant
      (= how the model's anti-aesthetic attempt is judged when the reward
      model is given the user's actual intent).

Output:
    <input-dir>/<model>/_hpsv3.json — list of dicts, one per image:
        {index, variant, score, prompt_used}

Plus a console summary per model:
    HPSv3 original  = mean over *_original.png
    HPSv3 distorted = mean over *_distorted.png
    Delta           = mean(distorted) - mean(original)        (Delta reported negative
                                                              if the model dropped)

Usage:
    python3 score_post_paper_hpsv3.py \\
        --input-dir ../benchmarks/post_paper_images \\
        --models flux2_klein_9b z_image_turbo \\
        --cuda-device 0

Requires the `hpsv3` package and a CUDA device. Install with:
    pip install hpsv3
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import torch
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input-dir", "-i", required=True,
        help="directory containing per-model subdirs written by benchmark_post_paper.py",
    )
    parser.add_argument(
        "--models", "-m", nargs="+", required=True,
        help="model subdirectory names to score",
    )
    parser.add_argument(
        "--cuda-device", default="0",
        help="CUDA device index for HPSv3",
    )
    parser.add_argument(
        "--batch-size", type=int, default=8,
        help="batch size for HPSv3 inference (default 8)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="re-score everything even if _hpsv3.json already has an entry "
             "for an (index, variant). Default: skip images already scored.",
    )
    return parser.parse_args()


def load_prompts(model_dir: Path) -> Dict[int, dict]:
    meta_path = model_dir / "_prompts.jsonl"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"missing {meta_path} — was this directory produced by benchmark_post_paper.py?"
        )
    prompts: Dict[int, dict] = {}
    with meta_path.open() as f:
        for line in f:
            row = json.loads(line)
            prompts[int(row["index"])] = row
    return prompts


def collect_jobs(model_dir: Path, prompts: Dict[int, dict]) -> List[dict]:
    """One job per PNG; scored under prompt_original."""
    jobs: List[dict] = []
    for png in sorted(model_dir.glob("*.png")):
        # filename: NNNN_variant.png
        stem = png.stem
        if "_" not in stem:
            continue
        idx_str, variant = stem.split("_", 1)
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        if idx not in prompts:
            print(f"  skip {png.name}: no prompt for index {idx}")
            continue
        jobs.append({
            "path": png,
            "index": idx,
            "variant": variant,
            "prompt_used": prompts[idx]["prompt_original"],
        })
    return jobs


def score_model(inferencer, model_dir: Path, batch_size: int) -> None:
    prompts = load_prompts(model_dir)
    jobs = collect_jobs(model_dir, prompts)
    if not jobs:
        print(f"[{model_dir.name}] no images to score")
        return

    results: List[dict] = []
    for start in range(0, len(jobs), batch_size):
        batch = jobs[start:start + batch_size]
        image_paths = [str(j["path"]) for j in batch]
        prompts_batch = [j["prompt_used"] for j in batch]
        with torch.no_grad():
            with torch.cuda.amp.autocast():
                rewards = inferencer.reward(prompts=prompts_batch, image_paths=image_paths)

        # hpsv3 returns one score per (prompt, image) pair, in order.
        for j, r in zip(batch, rewards):
            score = float(r) if not isinstance(r, (list, tuple)) else float(r[0])
            results.append({
                "index": j["index"],
                "variant": j["variant"],
                "score": score,
                "prompt_used": j["prompt_used"],
            })
            print(f"[{model_dir.name}] {j['path'].name}  HPSv3={score:.3f}")

    out_path = model_dir / "_hpsv3.json"
    with out_path.open("w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[{model_dir.name}] wrote {out_path}")

    # Console summary
    by_variant: Dict[str, List[float]] = {}
    for r in results:
        by_variant.setdefault(r["variant"], []).append(r["score"])
    print(f"\n=== {model_dir.name} ===")
    for v, scores in by_variant.items():
        mean = sum(scores) / len(scores)
        print(f"  HPSv3 {v:>9s}  n={len(scores):3d}  mean={mean:7.3f}")
    if "original" in by_variant and "distorted" in by_variant:
        delta = (sum(by_variant["distorted"]) / len(by_variant["distorted"])
                 - sum(by_variant["original"]) / len(by_variant["original"]))
        print(f"  ΔHPSv3 (distorted - original)         = {delta:+7.3f}")
    print()


def main() -> None:
    args = parse_args()

    device_index = int(args.cuda_device)
    if not torch.cuda.is_available():
        sys.exit("CUDA required for HPSv3")
    torch.cuda.set_device(device_index)

    try:
        from hpsv3 import HPSv3RewardInferencer
    except ImportError:
        sys.exit("hpsv3 not installed — `pip install hpsv3`")
    inferencer = HPSv3RewardInferencer(device=f"cuda:{device_index}")

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        sys.exit(f"input dir not found: {input_dir}")

    for model in args.models:
        model_dir = input_dir / model
        if not model_dir.is_dir():
            print(f"[skip] {model}: no directory at {model_dir}")
            continue
        score_model(inferencer, model_dir, args.batch_size)


if __name__ == "__main__":
    main()
