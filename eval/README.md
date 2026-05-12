# eval

Evaluation code for the ICML 2026 position paper. This directory holds the
scripts and notebooks used to generate the paper's benchmark numbers, train and
evaluate the BLIP-based aesthetic rater, and run the case studies.

The code has not been cleaned up beyond grouping into folders, so paths inside
scripts are still relative. Run each script from the folder it lives in.

## Layout

```
benchmarks/            Image-generation benchmark sweep
  benchmark.py           Main sweep over generation models (FLUX, SD3, etc.)
  benchmark_emotion.py   Emotion-bias sweep
  prompts.json           Prompt set used by the sweeps
  config.json            FluxTransformer2DModel config
  run2.sh                Driver shell script

reward_models/         Off-the-shelf reward-model scorers
  run_hpsv2.py           Score the AAS benchmark with HPSv2
  run_image_reward.py    Score with ImageReward
  eval_later.py          Score with HPSv3
  eval_later.ipynb       Same, exploratory notebook
  pick_score.py          PickScore helper used by main.py
  hpsv2_rewards.json     Cached HPSv2 scores
  hpsv3_rewards.pkl      Cached HPSv3 scores
  image_reward.json      Cached ImageReward scores

dataset_construction/  Building the prompt/image dataset
  ds.py                  Prompt generation for the AAS benchmark
  ds_emotion.py          Prompt generation for the emotion split
  convert_base64_dataset.py  Decode base64 images back into a HF dataset
  dataset_gen.ipynb      Dataset assembly notebook
  data.ipynb             Dataset inspection notebook

rater/                 BLIP-based aesthetic rater used by the paper
  train.py               Training loop
  eval.py                Held-out evaluation
  main.py                End-to-end pipeline (BLIP + HPSv2 + PickScore)
  human_eval.py          Human-eval helper
  rules.csv              Distortion rules used during training
  gen_rules.csv          Generation-time rule list
  gpt.png                Reference image for qualitative comparisons
  rater.ipynb, eval.ipynb, main.ipynb,
  binary.ipynb, blip_compare.ipynb   Exploratory notebooks

rater_training/        Earlier rater-training code (Qwen3-VL + LLM raters,
                       qualitative PDFs). Kept self-contained.

studies/               Case-study folders for individual figures
  anti_physics/          "Anti-physics" study
  attn_map/              Attention-map visualization
  emotion_bias/          Emotion-bias plots

data/                  Shared inference scripts and reference images
                       (VSF, NAG, img2img), referenced from notebooks.

notebooks/             Misc exploratory notebooks
  scratch.ipynb, qwen_image.ipynb, dance_grpo.ipynb
```

## Running things

Most scripts read their inputs from the working directory, so `cd` into the
right subfolder first. For example:

```bash
cd benchmarks
python benchmark.py --models flux_dev --cuda-device 0

cd ../reward_models
python run_hpsv2.py

cd ../rater
python train.py
```

`benchmark.py` expects a `flux/flux/transformer/diffusion_pytorch_model.safetensors`
checkpoint at `eval/benchmarks/flux/flux/transformer/` (gitignored). The Qwen
rater under `rater_training/` and the off-the-shelf reward models pull weights
from HuggingFace on first run.

## Notes

- `wandb/`, `flux/`, `aas_benchmark_2_with_blip*/`, `*.pth`, `*.ckpt`, and
  `*.hf` are gitignored — they are run artifacts or local checkpoints.
- The empty `eval` file and empty `HPSv3/` directory are leftovers from before
  the reorg and can be removed when convenient.
