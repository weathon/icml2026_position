#!/usr/bin/env bash
# Precompute VAE latents + Qwen text embeddings to disk so the training
# script can run without loading the VAE or text encoder.
set -euo pipefail

cd "$(dirname "$0")"

export MODEL_NAME="black-forest-labs/FLUX.2-klein-base-9B"
export DATASET_NAME="weathon/merged_aa_recaptioned"
export CACHE_DIR="./cache_aa"

mkdir -p "$CACHE_DIR"

python3 precompute_cache.py \
  --pretrained_model_name_or_path="$MODEL_NAME" \
  --dataset_name="$DATASET_NAME" \
  --cache_dir="$CACHE_DIR" \
  --aspect_ratio_buckets="1024,1024" \
  --num_validation=20 \
  --validation_seed=0 \
  --dtype=bf16 \
  --device=cuda \
  "$@"
