
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import torch
import requests
from PIL import Image
from transformers import BlipProcessor, BlipForImageTextRetrieval
import hpsv2


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


raw_blip = BlipForImageTextRetrieval.from_pretrained("Salesforce/blip-itm-base-coco", torch_dtype=torch.float16)
raw_blip = raw_blip.cuda()

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


dims = {k: v for k, v in guide.items() if k not in ["unsafe type", "hands", "face", "body", "safety", "lighting aesthetic", "symmetry"]}.keys()
dims = list(dims)
dim_min = {i:min(guide[i].keys()) for i in guide.keys()}

import json
with open("prompts.json", "r") as f:
    prompt_dict = json.load(f)

# import trackio as wandb
import wandb
space_id="weathon/trackio"

import torch
from diffusers import StableDiffusion3Pipeline, FluxPipeline



# pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-dev", torch_dtype=torch.bfloat16)
# pipe = pipe.to("cuda:1")
pipe = StableDiffusion3Pipeline.from_pretrained("stabilityai/stable-diffusion-3.5-large", torch_dtype=torch.bfloat16)
pipe = pipe.to("cuda:0")

def get_original_sd(sample, seed):
    image_original_sd = pipe(
        sample["original_prompt"],
        num_inference_steps=32,
        generator=torch.Generator("cuda").manual_seed(seed),
        guidance_scale=7.0,
    ).images[0]
    return image_original_sd
    
def get_distorted_sd(sample, seed):
    image_distorted_sd = pipe(
        prompt=sample["disorted_short_prompt"],
        prompt_2=sample["disorted_short_prompt"],
        prompt_3=sample["disorted_long_prompt"],
        negative_prompt=sample["negative_prompt"],
        num_inference_steps=32,
        guidance_scale=random.uniform(3.0, 9.0),
        generator=torch.Generator("cuda").manual_seed(seed)
    ).images[0] 
    return image_distorted_sd

def get_distorted_flux(sample, seed):
    image_distorted_flux = pipe(
        prompt=sample["disorted_short_prompt"],
        prompt_2=sample["disorted_long_prompt"],
        num_inference_steps=32,
        guidance_scale=7.0,
        generator=torch.Generator("cuda").manual_seed(seed)
    ).images[0]
    return image_distorted_flux

def get_original_flux(sample, seed):
    image_distorted_strong_sd = pipe(
        prompt=sample["original_prompt"],
        num_inference_steps=32,
        guidance_scale=7.0,
        generator=torch.Generator("cuda").manual_seed(seed)
    ).images[0] 
    return image_distorted_strong_sd


from datasets import load_dataset

ds = load_dataset("weathon/anti_aesthetics_dataset")


os.makedirs("images", exist_ok=True)

deltas = {dim:[] for dim in dims}
wandb.init(project="eval")
# wandb.init(project="eval", space_id="weathon/trackio")
base = 865679875645

hps_scores = []
anti_aesthetics_scores = []
for i, sample in enumerate(ds['train'].select(range(1000))):

    image1 = get_original_sd(sample, seed=i + base)
    image2 = get_distorted_sd(sample, seed=i + base)
    images = [image1, image2]
  
    large_image = Image.new('RGB', (images[0].size[0] + images[1].size[0], images[0].size[1]))
    large_image.paste(images[0], (0, 0))
    large_image.paste(images[1], (images[0].size[0], 0))

    dims_applied = sample["selected"]#[key for key in dims if sample["selected"][key] is not None and key != "lighting aesthetic"]
    original_scores = []
    distorted_scores = []
    # for dim in dims_applied:
    for dim in dims: # use dims applied when benchmark use all when compare with hpsv2
        inputs = processor(images=images, text=[prompt_dict[dim]] * 2, return_tensors="pt", padding=True).to("cuda")
        with torch.no_grad():
            outputs = model(**inputs, n_images=[2]) 
        score = torch.nn.functional.softmax(outputs['itm_score'], dim=-1)[:,1]
        print(f"{dim}: {list(score.cpu().detach().numpy())}") 
        delta = (score[1] - score[0]).cpu().detach().numpy()
        deltas[dim].append(delta)
        original_scores.append(score[0].cpu().detach().numpy())
        distorted_scores.append(score[1].cpu().detach().numpy())
 
    original_hpsv2_result = hpsv2.score(image1, sample["original_prompt"], hps_version="v2.1") 
    original_hpsv2_distorted_prompt = hpsv2.score(image1, sample["disorted_long_prompt"], hps_version="v2.1") 
    distorted_hpsv2_result = hpsv2.score(image2, sample["disorted_long_prompt"], hps_version="v2.1")
    
    hpsv2_delta = distorted_hpsv2_result[0] - original_hpsv2_result[0]
    hpsv2_delta_2 = distorted_hpsv2_result[0] - original_hpsv2_distorted_prompt[0]

    # cannot do delta as that will be use original prompt. wait that is fine for this calculation right? this is not benchmark but just score coorelation
    hps_scores.append(distorted_hpsv2_result[0] -  original_hpsv2_distorted_prompt[0])
    anti_aesthetics_scores.append(np.mean(distorted_scores) - np.mean(original_scores))

    # calculate r^2 and p for the regression
    import numpy as np
    from scipy.stats import linregress
    slope, intercept, r_value, p_value, std_err = linregress(hps_scores, anti_aesthetics_scores)
    print(f"R: {r_value}")


    data = [[x, y] for (x, y) in zip(hps_scores, anti_aesthetics_scores)]
    # data = [[x, y] for (x, y) in zip(hps_scores, anti_aesthetics_scores)]
    table = wandb.Table(data=data, columns = ["hps_scores", "anti_aesthetics_scores"])

           
    print(f"hpsv2: {hps_scores}\n anti_aesthetics: {anti_aesthetics_scores}")

    with torch.no_grad():
        with torch.autocast("cuda"):
            original_blip_inputs = processor(images=image1, text=[sample["disorted_long_prompt"]], return_tensors="pt", padding=True).to("cuda", torch.float16)
            original_blip_outputs = raw_blip(**original_blip_inputs)
            original_blip_score = torch.nn.functional.softmax(original_blip_outputs['itm_score'], dim=-1)[:,1]

            distorted_blip_inputs = processor(images=image2, text=[sample["disorted_long_prompt"]], return_tensors="pt", padding=True).to("cuda", torch.float16)
            distorted_blip_outputs = raw_blip(**distorted_blip_inputs)
            distorted_blip_score = torch.nn.functional.softmax(distorted_blip_outputs['itm_score'], dim=-1)[:,1]
            blip_delta = distorted_blip_score - original_blip_score
            print(f"blip delta: {blip_delta}")

    logs = {f"delta_{dim}": np.mean(deltas[dim]) for dim in deltas.keys()}
    logs = logs | { 
       "image": wandb.Image(large_image, caption=", ".join([f"{dim}: {deltas[dim][-1]:.2f}" for dim in dims_applied])),
        "hpsv2_delta": hpsv2_delta,
        "hpsv2_delta_2": hpsv2_delta_2,
        "blip_delta": blip_delta.cpu().detach().numpy()[0],
        "anti_aesthetics_score vs hpsv2" : wandb.plot.scatter(table, "hps_scores", "anti_aesthetics_scores", title="hpsv2 vs anti_aesthetics"),
        "r": r_value,
    }

    wandb.log(logs) 