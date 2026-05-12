# Universal Aesthetic Alignment Narrows Artistic Expression

ICML 2026 position paper, project website, and supporting code.

This repo bundles three pieces:

- The project **website** (`index.html` + `site/`) — the mode-selector splash
  and the two paired landing pages (polished vs anti-aesthetic).
- An **evaluation suite** (`eval/`) — benchmarks, reward-model scorers, the
  BLIP-based rater, and the case-study notebooks behind the paper's figures.
- A **dataset-curation agent** (`anti_aesthetics_agent/`) — Claude Agent SDK
  driver that walks a class taxonomy and uses Qwen3-VL embeddings to sample
  candidate images for the anti-aesthetic dataset.

The paper source (`main.tex`, `sec/*.tex`) lives in a separate repo, so this
one is just the website + the code that produced the numbers and the dataset.

## Layout

```
index.html                 Mode-selector splash for the project site
site/                      Polished + anti-aesthetic landing pages, CSS, JS
scripts/                   Helpers for building website assets and pushing
                           the real-image dataset to HuggingFace
design_guide.md            Visual design notes for the two website modes
CHANGELOG.md               Website changelog

eval/                      Evaluation code (see eval/README.md)
anti_aesthetics_agent/     Dataset curation agent (see its own README)
```

## Website

The site is plain HTML/CSS/JS, no build step. Open `index.html` directly, or
serve the repo root with any static server, e.g.:

```bash
python -m http.server 8000
# then visit http://localhost:8000/
```

The splash routes to `site/normal.html` (research-page layout) or
`site/anti.html` (the deliberately ugly version). The chosen mode is
remembered in `localStorage`.

See `CHANGELOG.md` for the site history and `design_guide.md` for the visual
spec behind each mode.

## Evaluation

All evaluation code is in [`eval/`](eval/). The README there describes the
sub-folder layout (benchmarks, reward models, rater training, case studies)
and how to run each piece.

## Dataset agent

The Claude Agent SDK driver that curates the anti-aesthetic dataset lives in
[`anti_aesthetics_agent/`](anti_aesthetics_agent/). Its README covers setup,
the MCP tool layout, and how to resume from a checkpoint.

## Publishing checklist

Before pushing this repo publicly:

- Strip any HuggingFace / OpenAI / Replicate tokens from local `.env` files
  (they are gitignored, but double-check).
- Confirm `eval/wandb/`, `eval/**/flux/`, `eval/**/*.pth`, `eval/**/*.ckpt`,
  `anti_aesthetics_agent/tmp/`, and `anti_aesthetics_agent/embeddings/` are
  not tracked — `.gitignore` files in each subdir already cover these.
- Bump the paper link in `index.html` / `site/normal.html` once the camera-ready
  arXiv id is final.
