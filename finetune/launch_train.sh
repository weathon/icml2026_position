#!/usr/bin/env bash
# Launch multi-LoRA anti-aesthetics training for FLUX 2 Klein.
set -euo pipefail

cd "$(dirname "$0")"

export MODEL_NAME="black-forest-labs/FLUX.2-klein-base-9B"
export DATASET_NAME="weathon/merged_aa_recaptioned"
export OUTPUT_DIR="./multi_lora_aa"
export CACHE_DIR="./cache_aa"
export CUDA_VISIBLE_DEVICES="2"

mkdir -p "$OUTPUT_DIR"

accelerate launch \
  --mixed_precision=bf16 \
  train_multilora_anti_aesthetics.py \
    --pretrained_model_name_or_path="$MODEL_NAME" \
    --dataset_name="$DATASET_NAME" \
    --output_dir="$OUTPUT_DIR" \
    --precomputed_cache_dir="$CACHE_DIR" \
    --mixed_precision=bf16 \
    --rank=64 \
    --lora_alpha=64 \
    --train_batch_size=1 \
    --gradient_accumulation_steps=4 \
    --gradient_checkpointing \
    --learning_rate=1e-4 \
    --lr_scheduler=constant \
    --lr_warmup_steps=100 \
    --num_train_epochs=3 \
    --aspect_ratio_buckets="1024,1024" \
    --weighting_scheme=none \
    --guidance_scale=1.0 \
    --checkpointing_steps=500 \
    --num_validation_samples=10 \
    --validation_epochs=1 \
    --validation_steps=28 \
    --validation_guidance=3.5 \
    --report_to=wandb \
    --seed=42 \
    "$@"
