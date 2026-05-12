import os
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import torch
import numpy as np

OPENROUTER_URL = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_MODEL = "google/gemini-embedding-2-preview"
EMBED_DIM = 3072


def _read_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _build_item(item: dict) -> dict:
    if "text" in item and item["text"] is not None:
        return {"content": [{"type": "text", "text": item["text"]}]}
    if "image_path" in item:
        b64 = _read_b64(item["image_path"])
        return {"content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}
    if "image_b64" in item:
        return {"content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{item['image_b64']}"}}]}
    if "image_url" in item:
        return {"content": [{"type": "image_url", "image_url": {"url": item["image_url"]}}]}
    raise ValueError(f"Unsupported item: {list(item.keys())}")


class GeminiEmbedder:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 batch_size: int = 32, max_workers: int = 6,
                 max_retries: int = 5, timeout: int = 120):
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.timeout = timeout

    def _post(self, inputs: list[dict]) -> list[list[float]]:
        payload = {"model": self.model, "input": inputs, "encoding_format": "float"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_err = None
        for attempt in range(self.max_retries):
            try:
                r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=self.timeout)
                if r.status_code == 200:
                    j = r.json()
                    if "data" in j:
                        return [d["embedding"] for d in j["data"]]
                    last_err = f"missing data: {j}"
                else:
                    last_err = f"http {r.status_code}: {r.text[:300]}"
            except Exception as e:
                last_err = str(e)
            time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"OpenRouter request failed after {self.max_retries} retries: {last_err}")

    def embed(self, items: list[dict]) -> np.ndarray:
        if not items:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)

        batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
        results: list[list[list[float]] | None] = [None] * len(batches)

        def worker(idx: int):
            built = [_build_item(it) for it in batches[idx]]
            return idx, self._post(built)

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(worker, i) for i in range(len(batches))]
            for f in as_completed(futures):
                idx, embs = f.result()
                results[idx] = embs

        flat = [e for batch in results for e in batch]
        return np.array(flat, dtype=np.float32)

    def process(self, items: list[dict]) -> torch.Tensor:
        embs = self.embed(items)
        return torch.from_numpy(embs)
