from datasets import load_dataset
# dataset = load_dataset("weathon/aas_benchmark", split="train")
dataset = load_dataset("weathon/aas_benchmark-stable_diffusion_3.5_large")["train"]


import ImageReward as RM
model = RM.load("ImageReward-v1.0")

import torch
def image_reward_reward(sample):
    images_part = [sample["image_original"], sample["image_original"], sample["image_distorted"],  sample["image_distorted"]]
    prompts_part = [
        sample["prompt_original"],
        sample["prompt_distorted"],
        sample["prompt_original"],
        sample["prompt_distorted"]
    ] 
    rewards = []

    with torch.no_grad():
        with torch.cuda.amp.autocast():
            for image, prompt in zip(images_part, prompts_part):
                reward = model.score(prompt, image)
                rewards.append(reward)

    results = {
            "image_reward_oiop": float(rewards[0]), # original image, original prompt
            "image_reward_oidp": float(rewards[1]), # original image, distorted prompt
            "image_reward_diop": float(rewards[2]), # distorted image, original prompt
            "image_reward_didp": float(rewards[3]), # distorted image, distorted prompt 
    }
    print(results)
    return results


rewards = []
import tqdm
for sample in tqdm.tqdm(dataset):
    reward = image_reward_reward(sample)
    rewards.append(reward)

with open("image_reward.json", "w") as f:
    import json
    json.dump(rewards, f)
