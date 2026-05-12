
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1,2"

import torch
import requests
from PIL import Image
from transformers import BlipProcessor, BlipForImageTextRetrieval


from datasets import load_dataset

test_ds = load_dataset("zai-org/VisionRewardDB-Image", split='train[40000:]')


import torch
from transformers import PreTrainedModel, PretrainedConfig

processor = BlipProcessor.from_pretrained("Salesforce/blip-itm-base-coco")
backbone = BlipForImageTextRetrieval.from_pretrained("Salesforce/blip-itm-base-coco", torch_dtype=torch.float16)




class Rater(PreTrainedModel):
    def __init__(self, config):
      super().__init__(PretrainedConfig())
      self.backbone = backbone 
      # self.t_score = 0.2
      # self.t_ce = 0.2
      self.t = torch.nn.Parameter(torch.tensor(0.2))

    def forward(self, pixel_values, input_ids, attention_mask, n_images, labels=None):
      n_images = n_images[0]
      outputs = self.backbone(pixel_values=pixel_values, input_ids=input_ids, attention_mask=attention_mask)
      itm_scores = outputs[0]

      if labels is not None:
        assert itm_scores.shape[0] == labels.shape[0] == n_images, f"{itm_scores.shape[0]} {labels.shape[0]} {n_images}"
        assert itm_scores.shape[1] == labels.shape[1] == 2
        bce_loss = torch.nn.functional.cross_entropy(itm_scores, labels.argmax(-1)) 
        loss = bce_loss

        assert itm_scores.argmax(-1).shape == labels.argmax(-1).shape
        outputs['loss'] = loss

      return outputs
    
model = Rater.from_pretrained("weathon/BLIP-Reward", config=PretrainedConfig())
model = model.cuda()

from datasets import load_dataset

import io, math, random
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import pandas as pd

df = pd.read_csv("rules.csv")

import pandas as pd
import re

df.columns = df.columns.str.strip()
df['Dimension'] = df['Dimension'].ffill()

df['dim_key'] = df['Dimension'].apply(lambda x: re.search(r'\((.*?)\)', x).group(1) if re.search(r'\((.*?)\)', x) else x)

guide = {
    dim_key: {
        int(row['Score']): row['Option'] + ": " +str(row['Description']).strip()
        for _, row in group.iterrows()
    }
    for dim_key, group in df.groupby('dim_key')
}


dims = {k: v for k, v in guide.items() if k not in ["unsafe type", "hands", "face", "body", "safety", "lighting aesthetic"]}.keys()
dims = list(dims)
dim_min = {i:min(guide[i].keys()) for i in guide.keys()}

import json
with open("prompts.json", "r") as f:
    prompt_dict = json.load(f)

import wandb

import torch
from diffusers import StableDiffusion3Pipeline, FluxPipeline

pipe = StableDiffusion3Pipeline.from_pretrained("stabilityai/stable-diffusion-3.5-large", torch_dtype=torch.bfloat16)
pipe = pipe.to("cuda:0")

pipe2 = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe2 = pipe2.to("cuda:1")

from datasets import load_dataset

ds = load_dataset("weathon/anti_aesthetics_dataset")


dataset = []


def get_original_sd(sample):
    image_original_sd = pipe(
        sample["original_prompt"],
        num_inference_steps=32,
        guidance_scale=3.5,
    ).images[0]
    return image_original_sd
    
def get_distorted_sd(sample):
    image_distorted_sd = pipe(
        prompt=sample["disorted_short_prompt"],
        prompt_2=sample["disorted_short_prompt"],
        prompt_3=sample["disorted_long_prompt"],
        negative_prompt=sample["negative_prompt"],
        num_inference_steps=32,
        guidance_scale=3.5,
    ).images[0] 
    return image_distorted_sd


def get_distorted_flux(sample):
    image_distorted_flux = pipe2(
        prompt=sample["disorted_short_prompt"],
        prompt_2=sample["disorted_long_prompt"],
        num_inference_steps=8,
        guidance_scale=0.0,
    ).images[0]
    return image_distorted_flux

def get_distorted_strong_sd(sample):
    image_distorted_strong_sd = pipe(
        prompt=sample["disorted_short_prompt"],
        prompt_2=sample["disorted_short_prompt"],
        prompt_3=sample["disorted_long_prompt"],
        negative_prompt=sample["negative_prompt"],
        num_inference_steps=32,
        guidance_scale=5.0,
    ).images[0] 
    return image_distorted_strong_sd

functions = [get_original_sd, get_distorted_sd, get_distorted_flux, get_distorted_strong_sd]
os.makedirs("images", exist_ok=True)

for sample in ds['train'].select(range(100)):

    func = random.choices(functions, k=2)
    image1 = func[0](sample)
    image2 = func[1](sample)
    images = [image1, image2]
    
    shuffle_index = list(range(2))
    random.shuffle(shuffle_index)

    images = [images[i] for i in shuffle_index]
    images = images
    # concat
    large_image = Image.new('RGB', (images[0].size[0] + images[1].size[0], images[0].size[1]))
    large_image.paste(images[0], (0, 0))
    large_image.paste(images[1], (images[0].size[0], 0))

    dim = random.choice([i for i in sample['selected'].keys() if i is not None or dim == "lighting aesthetic"])
    inputs = processor(images=images, text=[prompt_dict[dim]] * 2, return_tensors="pt", padding=True).to("cuda")
    outputs = model(**inputs, n_images=[2]) 
    score = torch.nn.functional.softmax(outputs['itm_score'], dim=-1)[:,1]
    print(f"{dim}: {list(score.cpu().detach().numpy())}") 
    shuffled_scores = [score[i] for i in shuffle_index]
    image_name = random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=16)
    image_name = "".join(image_name) + ".png"
    large_image.save(os.path.join("images", image_name))

    dataset.append({
        "image_name": image_name,
        "image": large_image,
        "dimension": dim,
        "score": shuffled_scores,
        "shuffle_index": shuffle_index[:2],
    })

import datasets
dataset = datasets.Dataset.from_list(dataset)
dataset.push_to_hub("weathon/anti_aesthetic_human_eval", private=True)