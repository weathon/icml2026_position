# Evaluation Code

This directory contains the scripts and notebooks used for the benchmark
generation, reward-model scoring, rater training, and figure-level analyses.
Most paths are local and relative, so run scripts from the subdirectory where
they live unless the script says otherwise.

## Code Layout

```text
benchmarks/
  benchmark.py              Main image-generation sweep.
  benchmark_emotion.py      Emotion-bias generation sweep.
  benchmark_post_paper.py   Extra post-submission generation sweep.
  prompts.json              Prompt set used by the benchmark scripts.
  config.json               FluxTransformer2DModel config.
  run2.sh                   Driver script for the original sweep.
  run_post_paper.sh         Driver script for later model additions.

reward_models/
  run_hpsv2.py              HPSv2 scoring.
  eval_later.py             HPSv3 scoring used in earlier runs.
  score_post_paper_hpsv3.py HPSv3 scoring for post-paper additions.
  run_image_reward.py       ImageReward scoring.
  pick_score.py             PickScore helper.
  *_rewards.*               Cached reward outputs.

dataset_construction/
  ds.py                     AAS benchmark prompt construction.
  ds_emotion.py             Emotion split construction.
  convert_base64_dataset.py Decode base64 image records into a HF dataset.
  *.ipynb                   Dataset assembly and inspection notebooks.

rater/
  train.py                  BLIP-based aesthetic rater training.
  eval.py                   Held-out rater evaluation.
  main.py                   End-to-end BLIP/HPS/PickScore evaluation pipeline.
  human_eval.py             Human-evaluation utilities.
  rules.csv                 Distortion rules for training/evaluation.
  gen_rules.csv             Generation-time rule list.

rater_training/
  train.py                  Earlier rater-training path.
  train_sigmoid.py          Sigmoid-head BLIP training experiment.
  qwen.py                   Qwen3-VL rater utilities.
  infer.py, infer_vsf.py    Inference helpers.
  llm_select.py             LLM-based selection helper.
  prompts.json, rules.csv   Prompt and rule inputs.

studies/
  anti_physics/             Anti-physics case study.
  attn_map/                 Attention-map visualization.
  emotion_bias/             Emotion-bias analysis.

data/
  vsf.py, vsf_krea.py       VSF inference utilities.
  nag.py                    NAG reference script.
  reward_model_deltas.csv   Shared reward-model delta table.

notebooks/
  *.ipynb                   Exploratory and analysis notebooks.
```

## Typical Entry Points

Run a generation benchmark:

```bash
cd eval/benchmarks
python benchmark.py --models flux_dev --cuda-device 0
```

Score benchmark outputs with reward models:

```bash
cd eval/reward_models
python run_hpsv2.py
python run_image_reward.py
python eval_later.py
```

Train or evaluate the BLIP-based rater:

```bash
cd eval/rater
python train.py
python eval.py
```

Build prompt/image datasets:

```bash
cd eval/dataset_construction
python ds.py
python ds_emotion.py
```

## Inputs

- `benchmarks/prompts.json` contains the prompt set used by the generation
  benchmark scripts.
- `dataset_construction/` contains scripts used to build the prompt/image
  datasets before publishing to Hugging Face.
- `rater/rules.csv` and `rater/gen_rules.csv` define the distortion and
  generation rules used by the rater pipeline.
- `benchmark.py` expects a Flux checkpoint at
  `eval/benchmarks/flux/flux/transformer/diffusion_pytorch_model.safetensors`.
  This path is gitignored because the checkpoint is large.

## Outputs

- Reward-model scripts write cached score files under `reward_models/`.
- Benchmark scripts may write generated image folders and intermediate dataset
  exports in their working directories.
- Rater training writes checkpoints and run artifacts locally.
- Notebooks under `studies/` and `notebooks/` produce the analysis plots and
  intermediate tables used during paper development.

## Environment Notes

The exact package environment is experiment-dependent. The code uses common
image-generation and evaluation libraries such as PyTorch, diffusers,
transformers, datasets, and reward-model-specific packages. Several scripts
download model weights from Hugging Face on first run.

The following are intentionally not tracked:

- `wandb/`
- `flux/`
- `aas_benchmark_2_with_blip*/`
- `*.pth`, `*.ckpt`, `*.hf`
- `__pycache__/`, `.ipynb_checkpoints/`

## Raw Analysis Data

The public benchmark dataset on Hugging Face includes the prompt/image pairs
and raw analysis data used for downstream evaluation:

<https://huggingface.co/datasets/weathon/aas_benchmark_final>

