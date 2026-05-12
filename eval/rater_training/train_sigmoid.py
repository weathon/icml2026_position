# %%

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"
import torch
import requests
from PIL import Image
from transformers import BlipProcessor, BlipForImageTextRetrieval

processor = BlipProcessor.from_pretrained("Salesforce/blip-itm-large-coco")
model = BlipForImageTextRetrieval.from_pretrained("Salesforce/blip-itm-large-coco")
processor.image_processor.size = {'height': 768, 'width': 768}

model = model.cuda()
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

import json
with open("prompts.json", "r") as f:
    prompt_dict = json.load(f)



# %%


# %% 

def format_data(sample):
    images = []
    dims_selected = []
    # print(len(sample["image"]), len(sample["annotation"]))
    for image in range(len(sample['image'])):
        images.append(sample['image'][image])
        try:
            if random.random()>0.5:
                # sample a dim with score>=0 
                dims_selected.append(random.choice(list([i for i in dims if sample['annotation'][image][i]==0])))
            else:
                # sample a dim with score<0
                dims_selected.append(random.choice(list([i for i in dims if sample['annotation'][image][i]!=0])))
        except IndexError:
            dims_selected.append(random.choice(dims))
            

    prompts = [prompt_dict[dim] for i, dim in enumerate(dims_selected)]
    images = list(sample['image'])
    n_images = len(images)
    n_prompts = len(prompts) 
    inputs = processor(images=images, text=prompts, return_tensors="pt", padding=True)
    answers = [1 if i[dim]<0 else (0.5 if i[dim]==0 else 0) for i, dim in zip(sample["annotation"], dims_selected)]
    labels = torch.tensor(answers)
    inputs['labels'] = labels
    inputs['dim'] = [dims.index(dim) for dim in dims_selected]
    inputs['n_images'] = [n_images] * len(inputs['input_ids'])
    return {
        'pixel_values': inputs['pixel_values'],
        'input_ids': inputs['input_ids'],
        'attention_mask': inputs['attention_mask'],
        'labels': inputs['labels'], 
        'dims': dims_selected,
        'n_images': inputs['n_images'],
        # "annotation": [i[dim] for i, dim in zip(sample["annotation"], dims_selected)],
    } 



# %%
train_ds = train_ds.with_transform(format_data)
test_ds = test_ds.with_transform(format_data)

# %%
# train_ds[0:7]["labels"]

# %%

import wandb

import torch
from transformers import PreTrainedModel, PretrainedConfig

class Rater(PreTrainedModel):
    def __init__(self, backbone):
      super().__init__(PretrainedConfig())
      self.backbone = backbone
      self.head = torch.nn.Linear(768, 1)

    def forward(self, pixel_values, input_ids, attention_mask, n_images, labels=None):
      n_images = n_images[0]
      outputs = self.backbone(pixel_values=pixel_values, input_ids=input_ids, attention_mask=attention_mask, interpolate_pos_encoding=True)
      itm_scores = self.head(outputs.question_embeds[:,0,:]).squeeze(-1)

      if labels is not None:
        assert itm_scores.shape == labels.shape, f"{itm_scores.shape} {labels.shape}"
        assert itm_scores.shape[0] == n_images
        bce_loss = torch.nn.functional.binary_cross_entropy_with_logits(itm_scores, labels)
        mae_loss = torch.nn.functional.l1_loss(torch.sigmoid(itm_scores), labels)
        loss = bce_loss + mae_loss

        try: 
          wandb.log({"bce_loss": bce_loss, "acc": ((itm_scores>0) == (labels>0.5)).float().mean(), "mae_loss": mae_loss})
        except:
          pass
        outputs['loss'] = loss

      return outputs

my_rater = Rater(model)




# %%
# my_rater = my_rater.cpu()
# with torch.no_grad():
#     my_rater(**train_ds[0:2]) 

# %%

from transformers import TrainingArguments
import os
training_args = TrainingArguments( 
    output_dir="BLIP-Reward-Long",
    learning_rate=8e-5, 
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    gradient_accumulation_steps=1,
    num_train_epochs=20,
    weight_decay=0.001,
    eval_strategy="steps",
    save_strategy="steps",
    eval_steps=500,
    save_steps=500,
    logging_steps=1,
    load_best_model_at_end=True,
    push_to_hub=True,
    max_grad_norm=1.0,
    remove_unused_columns=False,
    dataloader_num_workers=min(os.cpu_count(), 32),
    fp16=True,
    warmup_ratio=0.02,
    lr_scheduler_type="cosine",
    # lr_scheduler_kwargs={"num_decay_steps": 500},
    report_to="wandb"
)


from peft import get_peft_model, LoraConfig, TaskType
lora_config = LoraConfig(
    r=16,
    lora_alpha=16,
    lora_dropout=0.01,
    # target_modules=["all-linear", "position_embeddings"], # all linear has less trainable?``
    target_modules=["qkv", "query", "key", "value", "dense", "projection", "fc1", "fc2", "text_proj", "visual_proj", "position_embeddings"],
    modules_to_save=["head"] 
)
my_rater = get_peft_model(my_rater, lora_config)  
my_rater = my_rater.to("cuda")
my_rater.print_trainable_parameters()
from transformers import Trainer 

trainer = Trainer(
    model=my_rater,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=test_ds,
    processing_class=processor,
)

# %%
trainer.train() 



