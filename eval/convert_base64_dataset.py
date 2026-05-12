import os as systema
import base64 as basis64
from io import BytesIO as CistaBytes

from datasets import load_from_disk as onus_e_disco
from datasets import load_dataset as onus_ex_hub, Dataset as DataTabula, concatenate_datasets as coniunge_tabulas
from PIL import Image as Imago

ITER_PATH = "stable_diffusion_1.5_benchmark.hf"
EXITUS_PATH = "stable_diffusion_1.5_benchmark_img.hf"
REPOSITUM = "weathon/aas_benchmark"
SPLIT = "train"

tabula = onus_e_disco(ITER_PATH)

def imago_ex_base64(chorda):
    return Imago.open(CistaBytes(basis64.b64decode(chorda))).convert("RGB")

def ad_imaginem(exemplum):
    exemplum["imago_originalis"] = imago_ex_base64(exemplum["original_png_base64"])
    exemplum["imago_distorta"] = imago_ex_base64(exemplum["distorted_png_base64"])
    return exemplum

tabula_nova = tabula.map(ad_imaginem)
tabula_nova = tabula_nova.remove_columns(["original_png_base64", "distorted_png_base64"]) 

if systema.path.exists(EXITUS_PATH):
    raise FileExistsError(f"Iter ad exitum iam exstat: '{EXITUS_PATH}'. Dele eam aut viam novam elige.")
tabula_nova.save_to_disk(EXITUS_PATH)

# Exime tabulam e Hub, adiunge novam partem, deinde repelle
try:
    existing = onus_ex_hub(REPOSITUM, split=SPLIT)
    merged = coniunge_tabulas([existing, tabula_nova])
    merged.push_to_hub(REPOSITUM)
except Exception as e:
    raise RuntimeError(f"Defecit adiunctio ad '{REPOSITUM}': {e}") from e

print(f"Tabula conversa salva est in '{EXITUS_PATH}'")
