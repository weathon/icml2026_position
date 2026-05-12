#!/usr/bin/env bash
# Run all post-paper image generation models that don't have results yet.
# Scoring (HPSv3) is handled separately by reward_models/score_post_paper_hpsv3.py.
#
# Run from this directory:
#     cd eval/benchmarks
#     bash run_post_paper.sh
#
# Env / requirements:
#     - .env with OPENAI_API_KEY (gpt-image-1.5) and REPLICATE_API_TOKEN
#       (qwen_image, seeddream4). If you don't have these, just comment those
#       lines out below.
#     - Recent diffusers from main for FLUX.2 / Z-Image / GLM-Image / LongCat:
#         pip install -U "git+https://github.com/huggingface/diffusers.git"
#     - hf auth login   (gated repos: FLUX.2-klein-9B)

set -euo pipefail

# --- knobs ----------------------------------------------------------------
CUDA_DEVICE="${CUDA_DEVICE:-0}"
OUTPUT_DIR="${OUTPUT_DIR:-post_paper_images}"
NUM_PROMPTS="${NUM_PROMPTS:-300}"
# Models that still need to be run. gpt-image-1.5 / qwen_image / seeddream4
# are already done — keep them out of this list. Order is smallest-VRAM
# first so an OOM doesn't waste earlier work.
MODELS=(
  z_image_turbo
  longcat_image
  z_image
  alchemist
  glm_image
  flux2_klein_9b
)
# --------------------------------------------------------------------------

mkdir -p "$OUTPUT_DIR"
echo "→ output dir: $OUTPUT_DIR"
echo "→ cuda device: $CUDA_DEVICE"
echo "→ prompts: first $NUM_PROMPTS from weathon/anti_aesthetics_dataset"
echo

for model in "${MODELS[@]}"; do
  model_dir="$OUTPUT_DIR/$model"

  # Skip a model when both variants exist for every prompt.
  # benchmark_post_paper.py also skips per-file when --skip-existing is on,
  # so partial runs resume on the next launch.
  if [[ -d "$model_dir" ]]; then
    have=$(find "$model_dir" -maxdepth 1 -name '*.png' | wc -l | tr -d ' ')
    expected=$(( NUM_PROMPTS * 2 ))
    if (( have >= expected )); then
      echo "=== $model — already complete ($have / $expected PNGs) — skipping"
      continue
    fi
    echo "=== $model — resuming ($have / $expected PNGs done)"
  else
    echo "=== $model — starting fresh"
  fi

  python3 benchmark_post_paper.py \
    --models "$model" \
    --output-dir "$OUTPUT_DIR" \
    --cuda-device "$CUDA_DEVICE" \
    --num-prompts "$NUM_PROMPTS" \
    --skip-existing

  echo
done

echo "✓ all models attempted. Score next with:"
echo "  cd ../reward_models && python3 score_post_paper_hpsv3.py \\"
echo "      --input-dir ../benchmarks/$OUTPUT_DIR \\"
echo "      --models ${MODELS[*]} --cuda-device $CUDA_DEVICE"
