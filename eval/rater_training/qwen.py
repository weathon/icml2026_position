# %%
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
import torch

model = Qwen3VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen3-VL-4B-Instruct", dtype=torch.bfloat16, device_map="cuda"
)

processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-4B-Instruct")

# %%

# %%
import os
import torch
import requests
from PIL import Image
from transformers import BlipProcessor, BlipForImageTextRetrieval


from datasets import load_dataset

# Login using e.g. `huggingface-cli login` to access this dataset
train_ds = load_dataset("zai-org/VisionRewardDB-Image", split='train[:40000]')
test_ds = load_dataset("zai-org/VisionRewardDB-Image", split='train[40000:]')

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

# %%

# %%
processor.tokenizer.padding_side = "left"

# %%
import json
with open("prompts.json", "r") as f:
    prompt_dict = json.load(f)
    
def format_data(sample):
    images = []
    dims_selected = []
    # print(len(sample["image"]), len(sample["annotation"]))
    for image in range(len(sample['image'])):
        images.append(sample['image'][image])
        try:
            if random.random()>0.5:
                # sample a dim with score>=0 
                dims_selected.append(random.choice(list([i for i in dims if sample['annotation'][image][i]>=0])))
            else:
                # sample a dim with score<0
                dims_selected.append(random.choice(list([i for i in dims if sample['annotation'][image][i]<0])))
        except IndexError:
            dims_selected.append(random.choice(dims))
            

    prompts = [prompt_dict[dim] for i, dim in enumerate(dims_selected)]
    images = list(sample['image'])
    n_images = len(images) 
    n_prompts = len(prompts) 
    messages = [[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": images[i].convert("RGB").resize((512, 512)),
                },
                {"type": "text", "text": prompt},
            ],
        }
    ] for i, prompt in enumerate(prompts)]

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True, 
        return_dict=True,
        return_tensors="pt",
        padding=True,
        tokenize=True,
    ) 
    # inputs["pixel_values"] = torch.stack(inputs["pixel_values"].chunk(n_images, dim=0))
    answers = [1 if i[dim]<0 else (0 if i[dim]>0 else 0.5)for i, dim in zip(sample["annotation"], dims_selected)]
    labels = torch.tensor(answers)
    inputs['labels'] = labels
    inputs['dim'] = [dims.index(dim) for dim in dims_selected]
    return inputs

# %%
23552/23

# %%
train_ds = train_ds.with_transform(format_data)
test_ds = test_ds.with_transform(format_data)
train_ds[0:23].pixel_values.shape

# %%
# import torch
# with torch.no_grad(): 
#     print(model(**train_ds[0:2].to("cuda")).hidden_states.shape) 

# %%
# train_ds[0:2]["input_ids"][1]

# %%
from transformers import PreTrainedModel, PretrainedConfig

class Rater(PreTrainedModel):
    def __init__(self, backbone):
      super().__init__(PretrainedConfig())
      self.backbone = backbone
      self.head = torch.nn.Sequential(
         torch.nn.Linear(2560, 2560 * 4),
          torch.nn.ReLU(),
          torch.nn.Linear(2560 * 4, 1),
      )

    def forward(self, pixel_values, input_ids, attention_mask, image_grid_thw, dim, labels=None):
      hidden_states = self.backbone(
          pixel_values=pixel_values,
          input_ids=input_ids,
          attention_mask=attention_mask,
          image_grid_thw=image_grid_thw,
      ).hidden_states
      
      pooled_output = hidden_states[:, -1, :]
      logits = self.head(pooled_output)
      output = {'logits': logits.squeeze(-1)}
      if labels is not None: 
          bce_loss = torch.nn.functional.binary_cross_entropy_with_logits(
              logits.squeeze(-1), labels.float()
          )
          output['loss'] = bce_loss
      return output
my_rater = Rater(model).to("cuda", dtype=torch.bfloat16)

# %%
# lora
from peft import get_peft_model, LoraConfig, TaskType
lora_config = LoraConfig(
    r=32,
    lora_alpha=32,
    lora_dropout=0.01,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    modules_to_save=["head"]
)

# %%
my_rater = get_peft_model(my_rater, lora_config) 

# %%
my_rater = my_rater.to("cuda", dtype=torch.bfloat16)

# %%
with torch.no_grad():
    with torch.autocast("cuda", dtype=torch.bfloat16):
        inputs = train_ds[30:60] 
        inputs = inputs.to("cuda")    
        print(my_rater(**inputs))


from torch.utils.data import DataLoader
from torch.optim import AdamW
from tqdm import tqdm

batch_size = 32
num_epochs = 3
lr = 5e-5

train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(test_ds, batch_size=batch_size)

optimizer = AdamW(my_rater.parameters(), lr=lr)

step = 0
import wandb
wandb.init(project="qwen-vl-rater", name="qwen-vl-rater-lora")
for epoch in range(num_epochs):
    my_rater.train()
    total_loss = 0
    for batch in tqdm(train_loader):
        batch = {k: v.to("cuda") if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
        with torch.autocast("cuda", dtype=torch.bfloat16):
            output = my_rater(**batch)
            loss = output["loss"]
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        wandb.log({"train/loss": loss.item(), "step": step, "epoch": epoch})
        step += 1
    print(f"Epoch {epoch+1}/{num_epochs} Train Loss: {total_loss/len(train_loader):.4f}")

    my_rater.eval()
    eval_loss = 0
    with torch.no_grad():
        for batch in test_loader:
            batch = {k: v.to("cuda") if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.bfloat16):
                output = my_rater(**batch)
                eval_loss += output["loss"].item()
    eval_loss /= len(test_loader)
    wandb.log({"eval/loss": eval_loss, "epoch": epoch})
    print(f"Epoch {epoch+1}/{num_epochs} Eval Loss: {eval_loss:.4f}")

wandb.finish()
