"""Agent SDK runner for dataset curation. Loops through classes.json with checkpointing."""

import os
import json
import shutil
import argparse
import datetime
from pathlib import Path

import anyio

from claude_agent_sdk import (
    create_sdk_mcp_server, ClaudeSDKClient, ClaudeAgentOptions,
    AssistantMessage, TextBlock, ToolUseBlock, ToolResultBlock,
)

from agent_sdk_tools import ALL_TOOLS, load_existing_commits, TMP_DIR, pop_tool_returns

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).parent
CHECKPOINT_FILE = REPO_DIR / "checkpoint.json"
CLASSES_FILE = REPO_DIR / "classes_new.json"
LOGS_DIR = REPO_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def load_checkpoint() -> set:
    try:
        return set(json.loads(CHECKPOINT_FILE.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_checkpoint(completed: set) -> None:
    CHECKPOINT_FILE.write_text(json.dumps(sorted(completed), indent=2))


# ---------------------------------------------------------------------------
# Markdown logger
# ---------------------------------------------------------------------------

class MarkdownLogger:
    def __init__(self, key: str):
        safe_name = key.replace(":", "_").replace(" ", "_")
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = LOGS_DIR / f"{safe_name}_{ts}.md"
        self.img_dir = LOGS_DIR / f"{safe_name}_{ts}_images"
        self.img_dir.mkdir(exist_ok=True)
        self.img_count = 0
        self._write(f"# {key}\n\n*Started: {datetime.datetime.now().isoformat()}*\n\n")

    def _write(self, text: str):
        with open(self.log_path, "a") as f:
            f.write(text)

    def log_task(self, task: str):
        self._write(f"## Task\n\n```\n{task}\n```\n\n")

    def log_text(self, text: str):
        self._write(f"{text}\n\n")

    def log_tool_use(self, name: str, args: dict):
        self._write(f"### 🔧 `{name}`\n\n```json\n{json.dumps(args, indent=2, ensure_ascii=False)}\n```\n\n")

    def log_tool_result(self, text: str):
        self._write(f"**Result:**\n\n{text}\n\n")

    def log_image(self, src_path: str):
        src = Path(src_path)
        if not src.exists():
            return
        self.img_count += 1
        dst = self.img_dir / f"img_{self.img_count}{src.suffix}"
        shutil.copy2(src, dst)
        rel = dst.relative_to(self.log_path.parent)
        self._write(f"![grid]({rel})\n\n")

    def finish(self):
        self._write(f"\n---\n*Finished: {datetime.datetime.now().isoformat()}*\n")


def _extract_image_paths(text: str) -> list[str]:
    """Find tmp grid image paths mentioned in text."""
    paths = []
    for word in text.split():
        if word.startswith(TMP_DIR) or (os.sep in word and word.endswith((".jpg", ".png", ".webp"))):
            clean = word.rstrip(".,;)")
            if os.path.exists(clean):
                paths.append(clean)
    return paths


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_one(main_type: str, sub_type: str, methods: dict, system_prompt: str, server, model_id: str = "claude-opus-4-7"):
    key = f"{main_type}:{sub_type}"
    print(f"\n{'='*60}")
    print(f"[runner] Starting: {key}")
    print(f"{'='*60}\n")

    load_existing_commits()
    logger = MarkdownLogger(key)

    task = (
        f"main_type: {main_type}, "
        f"sub_type: {sub_type} - {json.dumps(methods, ensure_ascii=False)}"
    )
    logger.log_task(task)

    options = ClaudeAgentOptions(
        cwd=str(REPO_DIR),
        model=model_id,
        mcp_servers={"dataset-curation": server},
        allowed_tools=["Read"],
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        max_turns=200,
        thinking={"type": "adaptive"},
        effort="xhigh",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for ret in pop_tool_returns():
                    logger.log_tool_result(ret)
                    for img_path in _extract_image_paths(ret):
                        logger.log_image(img_path)
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                        logger.log_text(block.text)
                        for img_path in _extract_image_paths(block.text):
                            logger.log_image(img_path)
                    elif isinstance(block, ToolUseBlock):
                        if block.name == "mcp__dataset-curation__log_actions":
                            msg = block.input.get("msg", "") if isinstance(block.input, dict) else ""
                            logger.log_text(f"> **Agent Log:** {msg}")
                        else:
                            logger.log_tool_use(block.name, block.input)
                    elif isinstance(block, ToolResultBlock):
                        text = str(block.content) if block.content else ""
                        logger.log_tool_result(text)
                        for img_path in _extract_image_paths(text):
                            logger.log_image(img_path)

    logger.finish()
    print(f"\n[runner] Finished: {key} — log: {logger.log_path}\n")


async def main():
    parser = argparse.ArgumentParser(description="Run dataset curation agent.")
    parser.add_argument("filter_type", nargs="?", default=None, help="Filter by main_type (e.g. anti_aesthetics)")
    parser.add_argument("--model", default="claude-opus-4-7",
                        help="Model ID (default: claude-opus-4-7). e.g. claude-sonnet-4-6")
    args = parser.parse_args()

    classes = json.loads(CLASSES_FILE.read_text())
    completed = load_checkpoint()
    print(f"[CHECKPOINT] {len(completed)} tasks already completed, resuming.")
    print(f"[MODEL] {args.model}")

    prompt_path = REPO_DIR / "system_prompt.md"
    system_prompt = prompt_path.read_text()

    server = create_sdk_mcp_server("dataset-curation", tools=ALL_TOOLS)

    for main_type in classes:
        if args.filter_type and main_type != args.filter_type:
            continue
        for sub_type in classes[main_type]:
            key = f"{main_type}:{sub_type}"
            if key in completed:
                print(f"[SKIP] {key}")
                continue

            await run_one(main_type, sub_type, classes[main_type][sub_type], system_prompt, server, model_id=args.model)
            completed.add(key)
            save_checkpoint(completed)
            print(f"[CHECKPOINT] Saved: {key}")


if __name__ == "__main__":
    anyio.run(main)
