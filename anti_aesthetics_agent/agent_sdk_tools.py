"""MCP tools for dataset curation, used by the Agent SDK agent."""

import os
import sys
import json
import uuid
import time
import random
import datetime
import contextlib

import torch
import numpy as np
from PIL import Image as PILImage

from claude_agent_sdk import tool

from image_utils import grid_stack

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(REPO_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

dataset_commits: dict = {}
LOG_FILE = os.path.join(REPO_DIR, "agent_log.txt")
DATASET_JSON = os.path.join(REPO_DIR, "dataset.json")
DATASET_ROOT = "/home/wg25r/Downloads/ds/train"
_IS_INITIALIZED = False
_INIT_REQUIRED_MSG = "Server resources are not initialized. You need to call `init` first."

# Lazy-loaded resources
model = None
ava_embeddings_tensor = None
ls_embeddings_tensor = None
lapis_embeddings_tensor = None
ava_names_list = None
ls_names_list = None
lapis_names_list = None
dataset_map = {"photos": "ava", "dreamcore": "ls", "artwork": "lapis"}
_loader_summary: dict = {}
_img_counter = 0
_tool_returns: list[str] = []


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _make_result(text: str) -> dict:
    _tool_returns.append(text)
    return {"content": [{"type": "text", "text": text}]}


def _make_result_with_image(img_path: str, text: str) -> dict:
    full_text = f"Grid image saved at: {img_path}\nUse the Read tool to view it.\n{text}"
    _tool_returns.append(full_text)
    return {"content": [{"type": "text", "text": full_text}]}


def pop_tool_returns() -> list[str]:
    results = list(_tool_returns)
    _tool_returns.clear()
    return results


def _coerce_list(val) -> list[str]:
    if val is None or val == "":
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("["):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [val] if val else []
    return []


def _coerce_float(val, default: float) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _coerce_int(val, default: int) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _require_init() -> str | None:
    if _IS_INITIALIZED:
        return None
    return _INIT_REQUIRED_MSG


def _save_grid_to_tmp(pil_image: PILImage.Image) -> str:
    global _img_counter
    _img_counter += 1
    path = os.path.join(TMP_DIR, f"grid_{_img_counter}.jpg")
    pil_image.save(path, format="JPEG", quality=90)
    return path


def _get_embeddings_and_names(dataset: str):
    if dataset == "photos":
        return ava_embeddings_tensor, ava_names_list
    elif dataset == "dreamcore":
        return ls_embeddings_tensor, ls_names_list
    else:
        return lapis_embeddings_tensor, lapis_names_list


def _name_at(names, i):
    n = names[i]
    return n.item() if hasattr(n, "item") else n


def _apply_negative_filter(embeddings, names, negative_prompts, negative_threshold):
    if not negative_prompts:
        return set()
    combined_mask = torch.zeros(len(embeddings), dtype=torch.bool)
    for neg in negative_prompts:
        q_emb = model.process([{"text": neg}]).cpu().float()
        sim = torch.nn.functional.cosine_similarity(embeddings, q_emb)
        combined_mask |= sim > negative_threshold
    target_indices = torch.where(combined_mask)[0].tolist()
    return {_name_at(names, i) for i in target_indices}


def _search_impl(query, dataset, negative_prompts, negative_threshold, t, return_paths=False):
    _log(f"[LOG] Searching for '{query}' in dataset '{dataset}' ...")
    embeddings, names = _get_embeddings_and_names(dataset)
    excluded = _apply_negative_filter(embeddings, names, negative_prompts, negative_threshold)

    query_embedding = model.process([{"text": query}]).cpu()
    res = torch.nn.functional.cosine_similarity(embeddings, query_embedding.float())

    excluded_indices = {i for i in range(len(names)) if _name_at(names, i) in excluded}
    valid_mask = torch.ones(len(res), dtype=torch.bool)
    for idx in excluded_indices:
        valid_mask[idx] = False
    valid_scores = res[valid_mask].numpy()
    hist = np.histogram(valid_scores, bins=10)
    sim_distribution = f"Similarity distribution: counts={hist[0].tolist()}, bins=[{', '.join(f'{b:.3f}' for b in hist[1].tolist())}]"

    selected_images, top_scores = [], []
    for idx in torch.argsort(res, descending=True):
        idx_int = int(idx.item())
        name = _name_at(names, idx_int)
        if name not in excluded:
            selected_images.append(name)
            top_scores.append(f"{res[idx_int].item():.4f}")
        if len(selected_images) >= t:
            break

    paths = []
    for name in selected_images:
        path = f"{DATASET_ROOT}/{dataset_map[dataset]}/{name}"
        if os.path.exists(path):
            paths.append(path)

    score_info = f"Top-{len(top_scores)} scores: [{', '.join(top_scores)}]\n{sim_distribution}"

    if return_paths:
        return paths, score_info
    if not paths:
        return None, score_info
    return grid_stack(paths, row_size=5), score_info


def _sample_impl(query, dataset, min_threshold, max_threshold, negative_prompts, negative_threshold):
    embeddings, names = _get_embeddings_and_names(dataset)
    excluded = _apply_negative_filter(embeddings, names, negative_prompts, negative_threshold)

    query_embedding = model.process([{"text": query}]).cpu()
    res = torch.nn.functional.cosine_similarity(embeddings, query_embedding.float())

    mask = torch.logical_and(res >= min_threshold, res <= max_threshold)
    candidate_indices = torch.where(mask)[0].tolist()
    selected = [_name_at(names, i) for i in candidate_indices if _name_at(names, i) not in excluded]

    paths = []
    for name in selected:
        path = f"{DATASET_ROOT}/{dataset_map[dataset]}/{name}"
        if os.path.exists(path):
            paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@tool("init", "Initialize embeddings and models. Call once before using any other tool.", {})
async def tool_init(args):
    try:
        global _IS_INITIALIZED, model
        global ava_embeddings_tensor, ls_embeddings_tensor, lapis_embeddings_tensor
        global ava_names_list, ls_names_list, lapis_names_list
        global dataset_map, _loader_summary

        if _IS_INITIALIZED:
            return _make_result("Already initialized.")

        start = time.time()
        with contextlib.redirect_stdout(sys.stderr):
            from dataset_loader import (
                model as m, ava_embeddings_tensor as a_e, ls_embeddings_tensor as l_e,
                lapis_embeddings_tensor as la_e, ava_names_list as a_n, ls_names_list as l_n,
                lapis_names_list as la_n, dataset_map as dm, dataset_loader_summary,
            )
        model = m
        ava_embeddings_tensor, ls_embeddings_tensor, lapis_embeddings_tensor = a_e, l_e, la_e
        ava_names_list, ls_names_list, lapis_names_list = a_n, l_n, la_n
        dataset_map = dm
        _loader_summary = dataset_loader_summary()
        _IS_INITIALIZED = True
        elapsed = round(time.time() - start, 2)
        return _make_result(f"Initialization complete in {elapsed}s. rows={_loader_summary.get('total_rows', 'n/a')}, embedding_dim={_loader_summary.get('embedding_dim', 'n/a')}.")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] init failed: {tb}")
        return _make_result(f"ERROR in init: {e}\n{tb}")


@tool("search", "Search for top-k images matching a query.", {
    "query": {"type": "string", "description": "Text query for semantic image search."},
    "negative_prompts": {"type": "array", "items": {"type": "string"}, "description": "Negative text prompts to filter out (3-5 max)."},
    "negative_threshold": {"type": "number", "description": "Cosine similarity threshold for negative filtering. You must choose this value based on inspecting the returned images, not a default."},
    "t": {"type": "integer", "description": "Number of top results. Default 10."},
})
async def tool_search(args):
    try:
        err = _require_init()
        if err:
            return _make_result(err)

        query = args["query"]
        dataset = "photos"
        negative_prompts = _coerce_list(args.get("negative_prompts"))
        if negative_prompts and args.get("negative_threshold") in (None, ""):
            return _make_result("ERROR: negative_threshold is required when negative_prompts is set. Pick it based on the images you have observed, not a default.")
        negative_threshold = _coerce_float(args.get("negative_threshold"), 0.3)
        t = _coerce_int(args.get("t"), 10)

        result, score_info = _search_impl(query, dataset, negative_prompts, negative_threshold, t)
        if result is None:
            return _make_result(f"No Image Found\n{score_info}")

        img_path = _save_grid_to_tmp(result)
        return _make_result_with_image(img_path, f"Showing top {t} results for '{query}' in {dataset}.\n{score_info}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] search failed: {tb}")
        return _make_result(f"ERROR in search: {e}\n{tb}")


@tool("sample", "Sample random images within a similarity score range.", {
    "query": {"type": "string", "description": "Text query."},
    "min_threshold": {"type": "number", "description": "Minimum cosine similarity. You must choose this based on inspecting search results for this query, not a default."},
    "max_threshold": {"type": "number", "description": "Maximum cosine similarity. You must choose this based on inspecting search results for this query, not a default."},
    "count": {"type": "integer", "description": "Number of images to sample. Default 5."},
    "negative_prompts": {"type": "array", "items": {"type": "string"}, "description": "Negative text prompts."},
    "negative_threshold": {"type": "number", "description": "Threshold for negative filtering. Required when negative_prompts is set; pick from observation."},
})
async def tool_sample(args):
    try:
        err = _require_init()
        if err:
            return _make_result(err)

        query = args["query"]
        dataset = "photos"
        if args.get("min_threshold") in (None, "") or args.get("max_threshold") in (None, ""):
            return _make_result("ERROR: min_threshold and max_threshold are required. Run search first and pick values based on the observed similarity distribution.")
        min_t = _coerce_float(args.get("min_threshold"), 0.0)
        max_t = _coerce_float(args.get("max_threshold"), 1.0)
        count = _coerce_int(args.get("count"), 5)
        negative_prompts = _coerce_list(args.get("negative_prompts"))
        if negative_prompts and args.get("negative_threshold") in (None, ""):
            return _make_result("ERROR: negative_threshold is required when negative_prompts is set.")
        negative_threshold = _coerce_float(args.get("negative_threshold"), 0.2)

        paths = _sample_impl(query, dataset, min_t, max_t, negative_prompts, negative_threshold)
        if not paths:
            return _make_result("No Image Found")

        sampled = random.sample(paths, min(count, len(paths)))
        grid = grid_stack(sampled, row_size=5)
        img_path = _save_grid_to_tmp(grid)
        return _make_result_with_image(img_path, f"Sampled {len(sampled)} from {len(paths)} candidates.")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] sample failed: {tb}")
        return _make_result(f"ERROR in sample: {e}\n{tb}")


@tool("commit", "Commit images with similarity >= threshold to the dataset.", {
    "query": {"type": "string", "description": "Text query used for the search."},
    "threshold": {"type": "number", "description": "Minimum cosine similarity threshold (0.0-1.0). You must choose this based on inspecting search results for this query, not a default."},
    "negative_prompts": {"type": "array", "items": {"type": "string"}, "description": "Negative text prompts."},
    "negative_threshold": {"type": "number", "description": "Threshold for negative filtering. Required when negative_prompts is set; pick from observation."},
    "message": {"type": "string", "description": "Descriptive tags for this commit."},
})
async def tool_commit(args):
    try:
        err = _require_init()
        if err:
            return _make_result(err)

        query = args["query"]
        dataset = "photos"
        if args.get("threshold") in (None, ""):
            return _make_result("ERROR: threshold is required. Run search first and pick a value based on the observed similarity distribution.")
        threshold = _coerce_float(args.get("threshold"), 0.3)
        negative_prompts = _coerce_list(args.get("negative_prompts"))
        if negative_prompts and args.get("negative_threshold") in (None, ""):
            return _make_result("ERROR: negative_threshold is required when negative_prompts is set.")
        negative_threshold = _coerce_float(args.get("negative_threshold"), 0.2)
        message = args.get("message", "")

        embeddings, names = _get_embeddings_and_names(dataset)
        excluded = _apply_negative_filter(embeddings, names, negative_prompts, negative_threshold)

        query_embedding = model.process([{"text": query}]).cpu()
        res = torch.nn.functional.cosine_similarity(embeddings, query_embedding.float())

        mask = res >= threshold
        candidate_indices = torch.where(mask)[0].tolist()
        selected = [_name_at(names, i) for i in candidate_indices if _name_at(names, i) not in excluded]

        images = []
        for name in selected:
            path = f"{DATASET_ROOT}/{dataset_map[dataset]}/{name}"
            if os.path.exists(path):
                images.append(path)

        commit_id = str(uuid.uuid4())[:8]
        dataset_commits[commit_id] = {
            "query": query, "dataset": dataset, "threshold": threshold,
            "negative_prompts": negative_prompts, "negative_threshold": negative_threshold,
            "message": message, "images": images, "size": len(images),
        }
        with open(DATASET_JSON, "w") as f:
            json.dump(dataset_commits, f, indent=2)

        return _make_result(f"Committed with ID: {commit_id}, message: {message} with {len(images)} images.")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] commit failed: {tb}")
        return _make_result(f"ERROR in commit: {e}\n{tb}")


@tool("undo_commit", "Remove a commit from the dataset.", {
    "commit_id": {"type": "string", "description": "The 8-character commit ID to remove."},
})
async def tool_undo_commit(args):
    try:
        err = _require_init()
        if err:
            return _make_result(err)

        commit_id = args["commit_id"]
        if commit_id not in dataset_commits:
            return _make_result(f"Commit ID {commit_id} not found.")

        removed = dataset_commits.pop(commit_id)
        with open(DATASET_JSON, "w") as f:
            json.dump(dataset_commits, f, indent=2)
        return _make_result(f"Removed commit {commit_id}: {removed['message']} with {removed['size']} images.")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] undo_commit failed: {tb}")
        return _make_result(f"ERROR in undo_commit: {e}\n{tb}")


@tool("status", "Show all commit history.", {})
async def tool_status(args):
    try:
        err = _require_init()
        if err:
            return _make_result(err)

        if not dataset_commits:
            return _make_result("No commits yet.")

        total = sum(c["size"] for c in dataset_commits.values())
        lines = [f"Total commits: {len(dataset_commits)}, Total images: {total}\n\nCommit History:"]
        for cid, info in dataset_commits.items():
            lines.append(f"- [{cid}] {info['message']} ({info['size']} images)")
        return _make_result("\n".join(lines))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] status failed: {tb}")
        return _make_result(f"ERROR in status: {e}\n{tb}")


@tool("sample_from_committed", "Sample images from a committed batch.", {
    "commit_id": {"type": "string", "description": "The 8-character commit ID."},
    "n": {"type": "integer", "description": "Number of images to sample. Default 20."},
})
async def tool_sample_from_committed(args):
    try:
        err = _require_init()
        if err:
            return _make_result(err)

        commit_id = args["commit_id"]
        n = _coerce_int(args.get("n"), 20)
        if commit_id not in dataset_commits:
            return _make_result(f"Commit ID {commit_id} not found.")

        images = [p for p in dataset_commits[commit_id]["images"] if os.path.exists(p)]
        if not images:
            return _make_result("No images found on disk for this commit.")

        sampled = random.sample(images, min(n, len(images)))
        grid = grid_stack(sampled, row_size=5)
        img_path = _save_grid_to_tmp(grid)
        return _make_result_with_image(img_path, f"Sampled {len(sampled)} images from commit {commit_id}.")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] sample_from_committed failed: {tb}")
        return _make_result(f"ERROR in sample_from_committed: {e}\n{tb}")


@tool("log_actions", "Log the agent's thoughts and reasoning.", {
    "msg": {"type": "string", "description": "The message to log."},
})
async def tool_log_actions(args):
    try:
        msg = args.get("msg", "")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {msg}\n")
        _log(f"[LOG] {msg}")
        return _make_result("Logged.")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"[ERROR] log_actions failed: {tb}")
        return _make_result(f"ERROR in log_actions: {e}\n{tb}")


ALL_TOOLS = [
    tool_init, tool_search, tool_sample, tool_commit,
    tool_undo_commit, tool_status, tool_sample_from_committed, tool_log_actions,
]


def load_existing_commits():
    """Load existing dataset commits from disk."""
    if os.path.exists(DATASET_JSON):
        try:
            with open(DATASET_JSON, "r") as f:
                dataset_commits.update(json.load(f))
        except json.JSONDecodeError:
            dataset_commits.clear()
