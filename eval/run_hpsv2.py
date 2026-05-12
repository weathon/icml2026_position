from datasets import load_dataset, load_from_disk
# dataset = load_dataset("weathon/aas_benchmark", split="train")
dataset = load_dataset("weathon/aas_benchmark-stable_diffusion_3.5_large")["train"]
# dataset = load_from_disk("rater_training/aas_benchmark_2_with_blip")
import hpsv2

idx_of_interest = [8,  28,  45,  54,  77,  84,  91,  92, 102, 121, 124, 125, 143, 189, 195, 210, 221, 234, 237, 244, 245, 280, 285, 292]

import torch
def hpsv2_reward(sample, i):
    # if i not in idx_of_interest:
    #     return sample["hpsv2_reward"]
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
                reward = hpsv2.score(image, prompt, hps_version="v2.1") 
                rewards.append(reward)

    results = {
            "hpsv2_oiop": float(rewards[0][0]), # original image, original prompt
            "hpsv2_oidp": float(rewards[1][0]), # original image, distorted prompt
            "hpsv2_diop": float(rewards[2][0]), # distorted image, original prompt
            "hpsv2_didp": float(rewards[3][0]), # distorted image, distorted prompt 
    }
    print(results)
    return results


rewards = []
import tqdm
for i, sample in enumerate(tqdm.tqdm(dataset)):
    reward = hpsv2_reward(sample, i)
    rewards.append(reward)

with open("hpsv2_rewards.json", "w") as f:
    import json
    json.dump(rewards, f)
