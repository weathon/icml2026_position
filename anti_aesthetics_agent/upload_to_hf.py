import json
import os
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image
from datasets import load_dataset
from huggingface_hub import HfApi

DATASET_JSON = Path("/home/wg25r/anti_aesthetics_agent/dataset.json")
STAGING_ROOT = Path("/home/wg25r/anti_aesthetics_agent/tmp/hf_upload")
STAGING_TRAIN = STAGING_ROOT / "train"
REPO_ID = "weathon/aas_real_images"


def center_square_crop_and_save(args):
    src, dst = args
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            s = min(w, h)
            left = (w - s) // 2
            top = (h - s) // 2
            im = im.crop((left, top, left + s, top + s))
            im.save(dst, format="JPEG", quality=95)
        return (src, True, None)
    except Exception as e:
        return (src, False, str(e))


def main():
    HfApi().whoami()  # fail fast if not logged in

    data = json.loads(DATASET_JSON.read_text())

    per_image = defaultdict(lambda: {"query": [], "message": []})
    for entry in data.values():
        q = entry["query"]
        m = entry["message"]
        for path in entry["images"]:
            per_image[path]["query"].append(q)
            per_image[path]["message"].append(m)

    print(f"unique images: {len(per_image)}")

    if STAGING_ROOT.exists():
        shutil.rmtree(STAGING_ROOT)
    STAGING_TRAIN.mkdir(parents=True)

    tasks = []
    metadata_rows = []
    missing = 0
    for src_str in per_image:
        src = Path(src_str)
        if not src.exists():
            missing += 1
            continue
        fname = src.name
        dst = STAGING_TRAIN / fname
        tasks.append((str(src), str(dst)))
        metadata_rows.append({
            "file_name": fname,
            "filename": fname,
            "query": per_image[src_str]["query"],
            "message": per_image[src_str]["message"],
        })

    print(f"missing: {missing}, to crop: {len(tasks)}")

    fails = 0
    with ProcessPoolExecutor() as ex:
        futures = [ex.submit(center_square_crop_and_save, t) for t in tasks]
        for i, fut in enumerate(as_completed(futures), 1):
            src, ok, err = fut.result()
            if not ok:
                fails += 1
                print(f"FAIL {src}: {err}")
            if i % 500 == 0:
                print(f"cropped {i}/{len(tasks)}")
    print(f"crop done. failures: {fails}")

    valid_files = {p.name for p in STAGING_TRAIN.iterdir()}
    metadata_rows = [r for r in metadata_rows if r["file_name"] in valid_files]

    meta_path = STAGING_TRAIN / "metadata.jsonl"
    with meta_path.open("w") as f:
        for row in metadata_rows:
            f.write(json.dumps(row) + "\n")
    print(f"wrote metadata: {len(metadata_rows)} rows")

    ds = load_dataset("imagefolder", data_dir=str(STAGING_ROOT), split="train")
    print(ds)
    print("sample row:", {k: ds[0][k] for k in ds.column_names if k != "image"})
    print("image size:", ds[0]["image"].size)

    multi = next((r for r in metadata_rows if len(r["query"]) >= 2), None)
    if multi:
        print(f"multi-query sanity: {multi['file_name']} -> {len(multi['query'])} queries")

    ds.push_to_hub(REPO_ID, private=False)
    print(f"pushed to https://huggingface.co/datasets/{REPO_ID}")


if __name__ == "__main__":
    main()
