import sys
import torch
sys.path.append("vsf")

import torch 
import sys
from diffusers import FluxTransformer2DModel
from pathlib import Path

from datasets import load_dataset

# Login using e.g. `huggingface-cli login` to access this dataset
ds = load_dataset("weathon/anti_aesthetics_dataset", split="train")

# from diffusers import FluxPipeline
from src.flux_pipeline import VSFFluxPipeline

dance_pipe = VSFFluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-Krea-dev",
    torch_dtype=torch.bfloat16,
)
dance_pipe = dance_pipe.to("cuda:1")
import wandb
wandb.init(project="vsf_generation")
gen = []
for sample in ds:
    image = dance_pipe( 
        sample["disorted_long_prompt"],
        negative_prompt=sample["negative_prompt"],
        guidance_scale=0.0,
        num_inference_steps=32,
        max_sequence_length=256, 
        scale=2.0, 
        generator=torch.Generator("cpu").manual_seed(54324)
    ).images[0]
    gen.append({
        "prompt": sample["disorted_long_prompt"],
        "negative_prompt": sample["negative_prompt"],
        "image": image,
        "method": "Flux Krea+VSF"
    })
    wandb.log({
        "generated_images": wandb.Image(image, caption=sample["disorted_long_prompt"])
    })

from datasets import Dataset
gen_ds = Dataset.from_list(gen)
gen_ds.push_to_hub("weathon/vsf_aa_krea", private=True)
    