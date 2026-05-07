from datasets import Dataset, Features, Image, Sequence, Value
from huggingface_hub import HfApi
from pathlib import Path
import argparse
import json
import os
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default="weathon/aas_real_images")
    parser.add_argument("--source", default="/home/wg25r/aas2/AAv2/dataset.json")
    args = parser.parse_args()

    token = os.environ["HF_TOKEN"]
    source = Path(args.source)
    with source.open() as f:
        data = json.load(f)

    by_image = {}
    for class_key, item in data.items():
        for image_path in item["images"]:
            path = Path(image_path)
            if not path.exists():
                raise FileNotFoundError(image_path)
            record = by_image.setdefault(
                str(path),
                {
                    "image": str(path),
                    "original_path": str(path),
                    "file_name": path.name,
                    "class_keys": [],
                    "queries": [],
                    "source_datasets": [],
                    "messages": [],
                    "annotations_json": [],
                },
            )
            record["class_keys"].append(class_key)
            record["queries"].append(item["query"])
            record["source_datasets"].append(item["dataset"])
            record["messages"].append(item["message"])
            record["annotations_json"].append(
                json.dumps(
                    {
                        "class_key": class_key,
                        "query": item["query"],
                        "dataset": item["dataset"],
                        "threshold": item["threshold"],
                        "negative_prompts": item["negative_prompts"],
                        "negative_threshold": item["negative_threshold"],
                        "message": item["message"],
                        "class_size": item["size"],
                    },
                    ensure_ascii=False,
                )
            )

    rows = list(by_image.values())
    if not rows:
        raise RuntimeError("No image rows were created")

    features = Features(
        {
            "image": Image(),
            "original_path": Value("string"),
            "file_name": Value("string"),
            "class_keys": Sequence(Value("string")),
            "queries": Sequence(Value("string")),
            "source_datasets": Sequence(Value("string")),
            "messages": Sequence(Value("string")),
            "annotations_json": Sequence(Value("string")),
        }
    )
    dataset = Dataset.from_list(rows, features=features)
    dataset.push_to_hub(args.repo_id, token=token, private=False, max_shard_size="500MB")

    readme = f"""---
pretty_name: AAS Real Images
task_categories:
- image-classification
- image-to-text
tags:
- anti-aesthetics
- aesthetic-alignment
- image-generation
- visual-preference
---

# AAS Real Images

This dataset packages the real-image metadata from `~/aas2/AAv2/dataset.json` as a Hugging Face image dataset.

Each row is one distinct image. Images that were retrieved by multiple anti-aesthetic queries are deduplicated, and their query/class metadata is stored as arrays.

## Fields

- `image`: the image file.
- `original_path`: local source path used when packaging the dataset.
- `file_name`: source filename.
- `class_keys`: retrieval class IDs from the source JSON.
- `queries`: retrieval queries associated with the image.
- `source_datasets`: source bucket labels from the JSON, such as `photos`, `artwork`, or `dreamcore`.
- `messages`: human-readable anti-aesthetic subelement descriptions.
- `annotations_json`: per-class annotation records including thresholds and negative prompts.

## Intended Use

This dataset supports analysis of non-mainstream, wide-spectrum, and anti-aesthetic visual preferences, including deliberately degraded, disharmonious, gloomy, cluttered, surreal, or otherwise non-polished imagery.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(readme)
        readme_path = f.name

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=readme_path,
        path_in_repo="README.md",
        repo_id=args.repo_id,
        repo_type="dataset",
    )
    print(f"https://huggingface.co/datasets/{args.repo_id}")
    print(f"rows {len(rows)}")


if __name__ == "__main__":
    main()
