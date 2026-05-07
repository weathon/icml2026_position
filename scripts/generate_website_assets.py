from datasets import load_dataset
from PIL import Image
from pathlib import Path
import json
import os
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "website" / "assets"


def save_img(img, path, size=900):
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    img.save(path, quality=84, optimize=True)


def build_ai_examples():
    ds = load_dataset("weathon/aas_benchmark_final", split="train", streaming=True)
    want_rows = {0, 1, 2, 4}
    examples = []

    for row in ds:
        idx = int(row["index"])
        if idx not in want_rows:
            if idx > max(want_rows):
                break
            continue

        base = f"row_{idx:03d}"
        failed = OUT / "ai" / f"{base}_failed.jpg"
        success = OUT / "ai" / f"{base}_success.jpg"
        save_img(row["image_original"], failed)
        save_img(row["image_distorted"], success)
        examples.append(
            {
                "index": idx,
                "model": row["model"],
                "dims": row["selected_dims"],
                "failed": str(failed.relative_to(ROOT / "website")),
                "success": str(success.relative_to(ROOT / "website")),
                "prompt_original": row["prompt_original"],
                "prompt_distorted": row["prompt_distorted"],
                "llm_selected": row["llm_selected"],
            }
        )

    if len(examples) != len(want_rows):
        raise RuntimeError(f"Expected {len(want_rows)} AI rows, got {len(examples)}")

    return examples


def build_real_examples():
    data_path = Path("/home/wg25r/aas2/AAv2/dataset.json")
    with data_path.open() as f:
        data = json.load(f)

    keys = ["ba8cb8c5", "72f7caf4", "384e8d9b", "a93a1fb5", "63dffe73", "8897bf05"]
    examples = []
    for key in keys:
        item = data[key]
        src = next((Path(p) for p in item["images"] if Path(p).exists()), None)
        if src is None:
            raise FileNotFoundError(f"No existing image for {key}")

        dest = OUT / "real" / f"{key}{src.suffix.lower() if src.suffix else '.jpg'}"
        save_img(Image.open(src), dest)
        examples.append(
            {
                "key": key,
                "query": item["query"],
                "dataset": item["dataset"],
                "message": item["message"],
                "size": item["size"],
                "image": str(dest.relative_to(ROOT / "website")),
            }
        )

    return examples


def main():
    (OUT / "ai").mkdir(parents=True, exist_ok=True)
    (OUT / "real").mkdir(parents=True, exist_ok=True)
    meta = {"ai": build_ai_examples(), "real": build_real_examples()}
    with (OUT / "gallery.json").open("w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps({"ai": len(meta["ai"]), "real": len(meta["real"])}, indent=2))


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
