from datasets import load_dataset, load_from_disk
# dataset = load_from_disk("rater_training/aas_benchmark_2_with_blip")
# dataset = load_from_disk("rater_training/aas_benchmark_2_with_blip")
dataset = load_dataset("weathon/aas_benchmark-stable_diffusion_3.5_large", split="train")

from hpsv3 import HPSv3RewardInferencer

inferencer = HPSv3RewardInferencer(device='cuda:1')
# idx_of_interest = [  8,  28,  45,  54,  77,  84,  91,  92, 102, 121, 124, 125, 143, 189, 195, 210, 221, 234, 237, 244, 245, 280, 285, 292]
import torch
def hpsv3_reward(sample, i):
    # if i not in idx_of_interest:
    #     return {"hpsv3_reward": sample["hpsv3_reward"] if "hpsv3_reward" in sample else 5/0}
    images_part = [sample["image_original"], sample["image_original"], sample["image_distorted"],  sample["image_distorted"]]
    prompts_part = [
        sample["prompt_original"],
        sample["prompt_distorted"],
        sample["prompt_original"],
        sample["prompt_distorted"]
    ] 
    with torch.no_grad(): 
        with torch.cuda.amp.autocast():
            rewards = inferencer.reward(prompts=prompts_part, image_paths=images_part)
    results = {
        "hpsv3_oiop": rewards[0], # original image, original prompt
        "hpsv3_oidp": rewards[1], # original image, distorted prompt
        "hpsv3_diop": rewards[2], # distorted image, original prompt
        "hpsv3_didp": rewards[3], # distorted image, distorted prompt 
    }
    return results 
  
rewards = []
import tqdm
for i, sample in enumerate(tqdm.tqdm(dataset)):
    reward = hpsv3_reward(sample, i)
    rewards.append(reward)

with open("hpsv3_rewards.pkl", "wb") as f:
    import pickle
    pickle.dump(rewards, f)

# hpsv3_reward(dataset[0])   
# dataset = dataset.map(hpsv3_reward)
# dataset.push_to_hub("weathon/aas_benchmark", private=True)