import os
import pickle

import dotenv
dotenv.load_dotenv()

import numpy as np
import torch

from gemini_embedding import GeminiEmbedder, EMBED_DIM

EMBED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings")


def _load(source):
    with open(os.path.join(EMBED_DIR, f"{source}.pkl"), "rb") as f:
        d = pickle.load(f)
    return d["names"], d["embeddings"].astype(np.float32)


ava_names_list, ava_embeddings = _load("ava")

ls_names_list = np.array([], dtype=object)
ls_embeddings = np.zeros((0, EMBED_DIM), dtype=np.float32)
lapis_names_list = np.array([], dtype=object)
lapis_embeddings = np.zeros((0, EMBED_DIM), dtype=np.float32)

model_name_or_path = "google/gemini-embedding-2-preview"
model = GeminiEmbedder(model=model_name_or_path)

ava_embeddings_tensor = torch.tensor(ava_embeddings).float()
ls_embeddings_tensor = torch.tensor(ls_embeddings).float()
lapis_embeddings_tensor = torch.tensor(lapis_embeddings).float()

dataset_map = {
    "photos": "ava",
}


def dataset_loader_summary():
    return {
        "model_name_or_path": model_name_or_path,
        "total_rows": int(len(ava_names_list)),
        "ava_count": int(len(ava_names_list)),
        "embedding_dim": int(ava_embeddings_tensor.shape[1]) if len(ava_embeddings_tensor.shape) > 1 else 0,
    }
