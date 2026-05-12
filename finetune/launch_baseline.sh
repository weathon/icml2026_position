#!/usr/bin/env bash
# Generate the 10 validation images using the unmodified base FLUX 2 Klein
# model (no LoRA). Outputs to ./baseline_validation/.
set -euo pipefail

cd "$(dirname "$0")"

export MODEL_NAME="black-forest-labs/FLUX.2-klein-base-9B"
export CACHE_DIR="./cache_aa"
export OUTPUT_DIR="./baseline_validation"

python3 generate_baseline_validation.py \
  --pretrained_model_name_or_path="$MODEL_NAME" \
  --cache_dir="$CACHE_DIR" \
  --output_dir="$OUTPUT_DIR" \
  --num_inference_steps=28 \
  --guidance_scale=3.5 \
  --height=1024 \
  --width=1024 \
  --seed=42 \
  "$@"
