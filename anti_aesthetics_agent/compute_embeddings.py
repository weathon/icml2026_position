import os
import sys
import time
import pickle
import argparse

import numpy as np
import dotenv

dotenv.load_dotenv()

from gemini_embedding import GeminiEmbedder, EMBED_DIM

DATASET_ROOT = "/home/wg25r/Downloads/ds/train"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings")
SOURCES = ["ava"]


def list_images(source):
    d = os.path.join(DATASET_ROOT, source)
    return sorted(f for f in os.listdir(d) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))


def _parts_dir(source):
    return os.path.join(OUT_DIR, source, "_parts")


def _part_path(source, image_name):
    return os.path.join(_parts_dir(source), os.path.splitext(image_name)[0] + ".pkl")


def _load_part(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _is_valid_part(path):
    try:
        arr = _load_part(path)
    except Exception:
        return False
    return isinstance(arr, np.ndarray) and arr.shape == (EMBED_DIM,) and arr.dtype == np.float32


def _atomic_save_part(path, vec):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(vec, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def _consolidate(source, names_all):
    names = []
    vecs = []
    for n in names_all:
        p = _part_path(source, n)
        if not _is_valid_part(p):
            print(f"[{source}] missing or bad part: {n}", file=sys.stderr)
            continue
        names.append(n)
        vecs.append(_load_part(p).astype(np.float32))
    if not vecs:
        print(f"[{source}] nothing to consolidate", file=sys.stderr)
        return

    out_path = os.path.join(OUT_DIR, f"{source}.pkl")
    tmp = out_path + ".tmp"
    payload = {"names": np.array(names, dtype=object),
               "embeddings": np.stack(vecs, axis=0).astype(np.float32)}
    with open(tmp, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, out_path)
    print(f"[{source}] consolidated {len(names)} embeddings -> {out_path}")


def compute_for_source(source, embedder):
    src_dir = os.path.join(DATASET_ROOT, source)
    parts = _parts_dir(source)
    os.makedirs(parts, exist_ok=True)

    names_all = list_images(source)
    print(f"[{source}] {len(names_all)} images")

    todo = [n for n in names_all if not _is_valid_part(_part_path(source, n))]
    skipped = len(names_all) - len(todo)
    if skipped:
        print(f"[{source}] resume: {skipped} already embedded, {len(todo)} remaining")

    if todo:
        chunk = embedder.batch_size * embedder.max_workers
        t0 = time.time()
        done = 0
        for i in range(0, len(todo), chunk):
            sub = todo[i:i + chunk]
            items = [{"image_path": os.path.join(src_dir, n)} for n in sub]
            try:
                embs = embedder.embed(items)
            except Exception as e:
                print(f"[{source}] chunk failed at offset {i}: {e}", file=sys.stderr)
                raise

            for name, vec in zip(sub, embs):
                _atomic_save_part(_part_path(source, name), vec.astype(np.float32))
            done += len(sub)

            elapsed = time.time() - t0
            rate = done / max(elapsed, 1e-6)
            eta = (len(todo) - done) / max(rate, 1e-6)
            total_done = skipped + done
            print(f"[{source}] {total_done}/{len(names_all)} ({rate:.1f} img/s, eta {eta/60:.1f} min)")
    else:
        print(f"[{source}] all parts present")

    _consolidate(source, names_all)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", nargs="+", default=SOURCES, choices=SOURCES)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--consolidate-only", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.consolidate_only:
        for s in args.sources:
            _consolidate(s, list_images(s))
        return

    embedder = GeminiEmbedder(batch_size=args.batch_size, max_workers=args.workers)
    for s in args.sources:
        compute_for_source(s, embedder)


if __name__ == "__main__":
    main()
