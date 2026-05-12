# anti_aesthetics_agent

Dataset curation agent built on the Claude Agent SDK. Loops through a
class taxonomy in `classes_new.json` and uses an MCP tool server backed
by Qwen3-VL embeddings to search, sample, and commit image batches.

## Layout

```
agent_sdk_runner.py    Entry point — driver loop with checkpointing
agent_sdk_tools.py     MCP tool definitions (init/search/sample/commit/...)
dataset_loader.py      Loads HF embeddings + Qwen3-VL embedder
qwen3_vl_embedding.py  Qwen3-VL embedder model wrapper
image_utils.py         Grid/stack helpers for tool image returns
system_prompt.md       System prompt for the agent
classes_new.json       Class taxonomy to iterate over
logs/                  Per-run markdown logs (gitignored)
tmp/                   Tool-generated grid images (gitignored)
```

Runtime artifacts (`checkpoint.json`, `dataset.json`, `agent_log.txt`,
`logs/`, `tmp/`) are created on first run and gitignored.

## Setup

```bash
pip install -r requirements.txt
export DATASET_ROOT=/path/to/your/image/dataset   # default: /home/wg25r/Downloads/ds/train
```

The dataset loader pulls embeddings from HuggingFace
(`weathon/ava_embeddings`) and downloads `Qwen/Qwen3-VL-Embedding-8B`,
so you also need an authenticated HF environment if those gates apply.

## Run

```bash
python agent_sdk_runner.py                       # iterate every main_type
python agent_sdk_runner.py anti_aesthetics       # filter to one main_type
python agent_sdk_runner.py --model claude-opus-4-7
```

Progress is checkpointed to `checkpoint.json`; rerunning resumes where
it left off. Per-task markdown transcripts (with embedded grid images)
are written to `logs/`.
