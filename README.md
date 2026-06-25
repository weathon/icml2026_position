# Universal Aesthetic Alignment Narrows Artistic Expression

[![Project Page](https://img.shields.io/badge/project-page-blue)](https://weathon.github.io/icml2026_position)
[![OpenReview](https://img.shields.io/badge/OpenReview-1gQ4zc1Q8I-red)](https://openreview.net/forum?id=1gQ4zc1Q8I)
[![arXiv](https://img.shields.io/badge/arXiv-2512.11883-b31b1b.svg)](https://arxiv.org/abs/2512.11883)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Datasets-yellow.svg)](https://huggingface.co/datasets/weathon/aas_benchmark_final)

Code, evaluation scripts, datasets, and supporting artifacts for the ICML 2026
position paper **Universal Aesthetic Alignment Narrows Artistic Expression**.
If this repository is useful for your research, please consider starring it.

The project makes a critical argument about aesthetic alignment in image
generation and reward models. We show how optimization toward an averaged
aesthetic preference can override users who ask for anti-aesthetic, abstract,
distorted, negative-emotion, or otherwise non-mainstream visual outputs. The
paper's central concern is that this override is not a harmless quality
improvement: it is a form of aesthetic authoritarianism that constrains user
autonomy, narrows aesthetic pluralism, and turns a contestable artistic value
into an imposed default.

## Project Overview

Modern image generators are often optimized toward broad, averaged notions of
visual appeal: clean lighting, balanced composition, smooth detail, legible
subjects, and positive affect. Our experiments trace how this optimization
affects prompts that deliberately depart from that visual regime. The critical
question is whether systems should be allowed to treat the aesthetic mean as a
superior value when a user explicitly asks for images that are ugly, distorted,
abstract, low-fidelity, emotionally negative, or otherwise outside mainstream
commercial aesthetics.

We call this failure mode **reversed alignment**: instead of the model aligning
to the user's stated intent, the user is pushed back toward the model's learned
aesthetic preference. The empirical finding supports a normative objection: a
system that substitutes its own aesthetic preference for the user's request
reduces expressive freedom, makes non-mainstream visual language less
available, and quietly defines which forms of art and emotion are admissible.

The released artifacts support four parts of the analysis:

- A wide-spectrum aesthetic benchmark spanning conventional and anti-aesthetic
  instructions.
- Reward-model audits measuring whether scoring models prefer the image that
  actually follows the prompt.
- Real-image and artwork analyses testing whether the bias extends beyond
  synthetic benchmark pairs.
- Emotion-bias studies showing how negative affect is sanitized or penalized
  even when anger, fear, sadness, or critique is the requested content.
- Dataset-curation and fine-tuning code used for the paper's supporting
  experiments.

## Resources

- Paper: [OpenReview](https://openreview.net/forum?id=1gQ4zc1Q8I)
- Preprint: [arXiv:2512.11883](https://arxiv.org/abs/2512.11883)
- Project page: <https://weathon.github.io/icml2026_position>
- ICML page: <https://icml.cc/virtual/2026/poster/67242>
- Lay blog: [English](blog/README.md) | [中文](blog/README.zh-CN.md)

## Datasets

- [AAS benchmark](https://huggingface.co/datasets/weathon/aas_benchmark_final):
  wide-spectrum aesthetic prompt/image pairs and raw analysis data for
  evaluating whether generation and reward models respect anti-aesthetic
  instructions.
- [AAS real images](https://huggingface.co/datasets/weathon/aas_real_images):
  curated real-image anti-aesthetic dataset used for reward-model analysis.
- [LAPIS](https://huggingface.co/datasets/weathon/lapis): real artworks used to
  probe reward-model treatment of historically grounded non-mainstream
  aesthetics.
- [Critical comparison pairs](https://huggingface.co/datasets/weathon/critical_comparsion):
  social-critique image pairs used in the Image New Speak analysis.

## Repository Structure

```text
eval/                       Evaluation suite for benchmark, reward-model,
                            rater, and case-study experiments.
  benchmarks/               Image-generation benchmark sweeps.
  reward_models/            HPSv2, HPSv3, ImageReward, and PickScore scoring.
  dataset_construction/     Prompt and dataset construction scripts.
  rater/                    BLIP-based aesthetic rater training/evaluation.
  rater_training/           Earlier Qwen/LLM rater-training experiments.
  studies/                  Figure-level studies and analysis notebooks.
  data/                     Shared data-preparation and inference utilities.
  notebooks/                Exploratory notebooks.

finetune/                   Fine-tuning and validation scripts for model
                            variants used in the experiments.

anti_aesthetics_agent/      Agent-assisted dataset curation code using
                            Qwen3-VL embeddings and a class taxonomy.

scripts/                    Dataset publishing and asset-generation utilities.

blog/                       Public write-up drafts and related media.

index.html, site/           Project-page assets served by GitHub Pages.
poster.html, poster.pdf     Poster artifacts.
```

More detailed notes are available in [eval/README.md](eval/README.md) and
[anti_aesthetics_agent/README.md](anti_aesthetics_agent/README.md).

## Usage

The experimental code is organized by task. Most scripts assume they are run
from their own subdirectory because several paths are relative.

```bash
cd eval/benchmarks
python benchmark.py --models flux_dev --cuda-device 0

cd ../reward_models
python run_hpsv2.py

cd ../rater
python train.py
```

The fine-tuning code has separate dependencies:

```bash
pip install -r finetune/requirements_finetune.txt
```

The dataset-curation agent has its own environment:

```bash
cd anti_aesthetics_agent
pip install -r requirements.txt
python agent_sdk_runner.py
```

Large model weights, local checkpoints, generated datasets, and run logs are
not tracked in git. See the subdirectory READMEs for expected paths and setup
details.

## Citation

```bibtex
@inproceedings{guo2026universal,
  title = {Position: Universal Aesthetic Alignment Narrows Artistic Expression},
  author = {Guo, Wenqi Marshall and Qian, Qingyun and Hasan, Khalad and Du, Shan},
  booktitle = {Forty-third International Conference on Machine Learning},
  year = {2026},
  url = {https://openreview.net/forum?id=1gQ4zc1Q8I}
}
```



## Star History

<a href="https://www.star-history.com/?repos=weathon%2Ficml2026_position&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=weathon/icml2026_position&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=weathon/icml2026_position&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=weathon/icml2026_position&type=date&legend=top-left" />
 </picture>
</a>
