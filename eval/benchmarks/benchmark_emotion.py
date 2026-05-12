import os
import random

import argparse
import base64
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional

import torch
import replicate
from datasets import Dataset, load_dataset
import wandb
from diffusers import (DiffusionPipeline, FluxPipeline, FluxTransformer2DModel,
                       StableDiffusion3Pipeline, StableDiffusionPipeline,
                       UNet2DConditionModel)
from diffusers.schedulers import FlowMatchEulerDiscreteScheduler
from openai import OpenAI
from PIL import Image
from dotenv import load_dotenv
from peft import PeftModel

image_client = None
openrouter_client = None
image_pipelines: Dict[str, DiffusionPipeline] = {}
DEVICE_STR = "cuda"
# Fixed seed for local pipeline generation
SEED = int(os.environ.get("AAS_SEED", "42"))


PIPE_CONFIG = {
    "flux_dev": ("flux", "black-forest-labs/FLUX.1-dev"),
    "flux_schnell": ("flux", "black-forest-labs/FLUX.1-schnell"),
    "flux_krea": ("flux", "black-forest-labs/FLUX.1-Krea-dev"),
    "grpo_flux": ("flux_bf16", "CodeGoat24/FLUX.1-dev-PrefGRPO"), 
    "stable_diffusion_3.5_large": ("sd3", "stabilityai/stable-diffusion-3.5-large"),
    "stable_diffusion_3.5_medium": ("sd3", "stabilityai/stable-diffusion-3.5-medium"),
    "sd3_medium_grpo": ("sd3_grop_pickscore", "stabilityai/stable-diffusion-3.5-medium"),
    "sd3_medium_grpo_geneval": ("sd3_grop_geneval", "stabilityai/stable-diffusion-3.5-medium"),
    "stable_diffusion_1.5": ("sd15", "sd-legacy/stable-diffusion-v1-5"),
    "stable_diffusion_xl": ("sdxl", "stabilityai/stable-diffusion-xl-base-1.0"),
    "dpo-sd1.5": ("sd15_dpo", "runwayml/stable-diffusion-v1-5"),
    "playground": ("playground", "playgroundai/playground-v2.5-1024px-aesthetic"),
    "dance_flux": ("dance_flux", "black-forest-labs/FLUX.1-dev"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    # Build a dynamic help string listing available models
    available_models = [
        "gpt-image-mini",
        "gpt-image-mini-high",
        "seeddream4",
        "qwen_image",
        "nano-banana",
        *list(PIPE_CONFIG.keys()),
    ]
    models_help = (
        "image model(s) to benchmark. Multiple allowed (space or comma separated). "
        + "Available: " 
        + ", ".join(sorted(available_models))
    )
    parser.add_argument(
        "--models",
        "-m",
        dest="models",
        nargs="+",
        default=["gpt-image-mini"],
        help=models_help,
    )
    parser.add_argument(
        "--continue",
        dest="resume",
        type=str,
        default=None,
        help="W&B run ID to resume logging to (also resumes HF results).",
    )
    parser.add_argument("--cuda-device", default="1", help="CUDA_VISIBLE_DEVICES value")
    return parser.parse_args()


def encode_image(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def gpt_generate(prompt: str, quality: str = "low") -> Image.Image:
    last_error = None
    for attempt in range(5):
        try:
            result = image_client.images.generate(
                model="gpt-image-1-mini",
                prompt=prompt,
                quality=quality,
                size="1024x1024",
            )
            image_bytes = base64.b64decode(result.data[0].b64_json)
            return Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            last_error = exc
            if attempt == 4:
                print(f"gpt-image-mini failed after retries: {exc}")
                return Image.new("RGB", (1024, 1024), color=(0, 0, 255))
            print(f"retrying gpt-image-mini due to error: {exc}")
    return Image.new("RGB", (1024, 1024), color=(0, 0, 255))

# cross model correlation cannot be done, only delta
def nano_banana_generate(prompt: str) -> Image.Image:
    last_error = None
    for attempt in range(5):
        try:
            completion = openrouter_client.chat.completions.create(
                model="google/gemini-2.5-flash-image-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Generate an image with following prompt, return the image directly: {prompt}",
                            },
                        ],
                    }
                ],
            )
            message = completion.choices[0].message
            try:
                image_url = message.images[0]["image_url"]["url"]
                image_bytes = base64.b64decode(image_url.split(",")[1].replace("\x00", ""))
                return Image.open(BytesIO(image_bytes)).convert("RGB")
            except AttributeError:
                text_response = getattr(message, "content", "")
                print(f"nano-banana returned text-only response: {text_response}")
                raise ValueError("nano-banana did not return an image")
        except Exception as exc:
            last_error = exc
            if attempt == 4:
                print(f"FUCK! nano-banana failed after retries: {exc}")
                return Image.new("RGB", (1024, 1024), color=(0, 0, 255))
            print(f"retrying nano-banana due to error: {exc}")
    return Image.new("RGB", (1024, 1024), color=(0, 0, 255))


def seeddream4_generate(prompt: str) -> Image.Image:
    output = replicate.run(
        "bytedance/seedream-4",
        input={
            "size": "1K", 
            "width": 1024,
            "height": 1024,
            "prompt": prompt,
            "max_images": 1,
            "image_input": [],
            "aspect_ratio": "1:1",
            "sequential_image_generation": "disabled",
        },
    )
    image_bytes = output[0].read()
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def qwen_image_generate(prompt: str, negative_prompt: Optional[str]) -> Image.Image:
    payload = {
        "prompt": prompt,
        "go_fast": True,
        "guidance": 4,
        "image_size": "optimize_for_quality",
        "aspect_ratio": "1:1",
        "output_format": "png",
        "enhance_prompt": False,
        "num_inference_steps": 50,
    }
    if negative_prompt is not None:
        payload["negative_prompt"] = negative_prompt
    output = replicate.run(
        "qwen/qwen-image",
        input=payload,
    )
    image_bytes = output[0].read()
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def load_image_pipeline(model_name: str):
    if model_name in image_pipelines:
        return image_pipelines[model_name]
    if model_name not in PIPE_CONFIG:
        raise ValueError(f"Unsupported model: {model_name}")
    kind, repo_id = PIPE_CONFIG[model_name]
    if kind == "sd3":
        pipe = StableDiffusion3Pipeline.from_pretrained(repo_id, torch_dtype=torch.float16).to(DEVICE_STR)
    elif kind == "sd15":
        pipe = StableDiffusionPipeline.from_pretrained(repo_id, torch_dtype=torch.float16).to(DEVICE_STR)
    elif kind == "sd15_dpo":
        pipe = StableDiffusionPipeline.from_pretrained(repo_id, torch_dtype=torch.float16)
        unet = UNet2DConditionModel.from_pretrained(
            "mhdang/dpo-sd1.5-text2image-v1",
            subfolder="unet",
            torch_dtype=torch.float16,
        )
        pipe.unet = unet
        pipe = pipe.to(DEVICE_STR)
    elif kind == "sdxl":
        pipe = DiffusionPipeline.from_pretrained(
            repo_id,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
        ).to(DEVICE_STR)
    elif kind == "flux_bf16":
        pipe = FluxPipeline.from_pretrained(repo_id, torch_dtype=torch.bfloat16).to(DEVICE_STR)
    elif kind == "dance_flux":
        transformer_path = Path("flux/flux/transformer/diffusion_pytorch_model.safetensors")
        config_path = Path("flux/flux/transformer/config.json")
        model = FluxTransformer2DModel.from_single_file(
            str(transformer_path),
            config=str(config_path),
            torch_dtype=torch.bfloat16,
        )
        pipe = FluxPipeline.from_pretrained(
            repo_id,
            torch_dtype=torch.bfloat16,
            transformer=model,
        ).to(DEVICE_STR)
    elif kind == "playground":
        pipe = DiffusionPipeline.from_pretrained(
            repo_id,
            torch_dtype=torch.float16,
            variant="fp16",
        ).to(DEVICE_STR)
        pipe._aas_kind = "playground"
    elif kind == "sd3_grop_pickscore":
        pipe = StableDiffusion3Pipeline.from_pretrained(repo_id, torch_dtype=torch.float16)
        pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config)
        lora_repo_id = "jieliu/SD3.5M-FlowGRPO-PickScore"
        peft_model = PeftModel.from_pretrained(pipe.transformer, lora_repo_id)
        pipe.transformer = peft_model.merge_and_unload()
        pipe = pipe.to(DEVICE_STR)
    elif kind == "sd3_grop_geneval":
        pipe = StableDiffusion3Pipeline.from_pretrained(repo_id, torch_dtype=torch.float16)
        pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config(pipe.scheduler.config)
        lora_repo_id = "jieliu/SD3.5M-FlowGRPO-GenEval"
        peft_model = PeftModel.from_pretrained(pipe.transformer, lora_repo_id)
        pipe.transformer = peft_model.merge_and_unload()
        pipe = pipe.to(DEVICE_STR)
    else:
        pipe = FluxPipeline.from_pretrained(repo_id, torch_dtype=torch.float16).to(DEVICE_STR)
    image_pipelines[model_name] = pipe
    return pipe


def generate_with_pipe(pipe: DiffusionPipeline, prompt: str) -> Image.Image:
    # Use a fixed torch.Generator for deterministic outputs
    gen = torch.Generator(device=DEVICE_STR)
    gen.manual_seed(SEED)
    if isinstance(pipe, StableDiffusion3Pipeline):
        return pipe(
            prompt=prompt,
            prompt_2=prompt,
            prompt_3=prompt,
            # height=512,
            # width=512,
            num_inference_steps=32,
            guidance_scale=4.0,
            # guidance_scale=6.0,
            generator=gen,
        ).images[0]
    if isinstance(pipe, StableDiffusionPipeline):
        return pipe(
            prompt=prompt,
            num_inference_steps=64,
            guidance_scale=7.5,
            generator=gen,
        ).images[0]
    if isinstance(pipe, FluxPipeline):
        steps = 8 if any(
            key == "flux_schnell" and image_pipelines.get(key) is pipe
            for key in image_pipelines
        ) else 32
        return pipe(
            prompt=prompt,
            prompt_2=prompt,
            num_inference_steps=steps,
            guidance_scale=3.5,
            generator=gen,
        ).images[0]
    return pipe(
        prompt=prompt,
        num_inference_steps=50,
        guidance_scale=3.0,
        generator=gen,
    ).images[0]


def resolve_prompt(sample: dict) -> str:
    if "prompt" in sample and sample["prompt"]:
        return sample["prompt"]
    if "original_prompt" in sample and sample["original_prompt"]:
        return sample["original_prompt"]
    raise KeyError("Sample does not contain a usable prompt")


def get_image_generator(model_name: str) -> Callable[[dict], Image.Image]:
    if model_name == "gpt-image-mini":
        return lambda sample: gpt_generate(resolve_prompt(sample))
    if model_name == "gpt-image-mini-high":
        return lambda sample: gpt_generate(resolve_prompt(sample), quality="high")
    if model_name == "seeddream4":
        return lambda sample: seeddream4_generate(resolve_prompt(sample))
    if model_name == "qwen_image":
        return lambda sample: qwen_image_generate(resolve_prompt(sample), None)
    if model_name == "nano-banana":
        return lambda sample: nano_banana_generate(resolve_prompt(sample))
    pipe = load_image_pipeline(model_name)

    def generator(sample: dict) -> Image.Image:
        prompt = resolve_prompt(sample)
        return generate_with_pipe(pipe, prompt)

    return generator


def save_and_push_results(model_name: str, results: list[dict], hf_repo_id: str) -> None:
    if not results:
        print(f"no results to save for model {model_name}")
        return
    disk_path = Path(f"{model_name}_benchmark.hf")
    dataset = Dataset.from_list(results)
    dataset.save_to_disk(str(disk_path))
    # Build per-model repo id preserving the namespace
    namespace, base = hf_repo_id.split("/", 1)
    repo_id = f"{namespace}/{base}-{model_name}"
    dataset.push_to_hub(repo_id)


def run_benchmark(model_name: str, resume: Optional[str]) -> None:
    hf_repo_id = "weathon/ass_emotion"

    dataset = load_dataset("weathon/anti_aesthetics_emotion", split="train")
    image_generator = get_image_generator(model_name)

    results: list[dict] = []
    initial_count = 0
    start_index = 0

    # Initialize W&B for this model's run
    wandb.init(
        project="benchmark",
        config={"model": model_name},
        id=resume,
        resume=("allow" if resume else None),
    )

    if resume:
        namespace, base = hf_repo_id.split("/", 1)
        resume_repo_id = f"{namespace}/{base}-{model_name}"
        existing_dataset = load_dataset(resume_repo_id, split="train")
        for row in existing_dataset:
            results.append(
                {
                    "image": row["image"],
                    "emotion": row["emotion"],
                    "prompt": row["prompt"],
                    "model": row["model"],
                }
            )
        initial_count = len(results)
        start_index = len(existing_dataset)

    for index, sample in enumerate(dataset):
        if resume and index < start_index:
            continue

        prompt = resolve_prompt(sample)
        image = image_generator(sample)
        sample_result = {
            "image": image,
            "emotion": sample["emotion"],
            "prompt": prompt,
            "model": model_name,
        }
        results.append(sample_result)

        # Log to W&B: image with emotion as caption
        wandb.log({
            "index": index,
            "model": model_name,
            "image": wandb.Image(image, caption=str(sample["emotion"]))
        })

        print({"index": index, "model": model_name, "prompt": prompt})

    save_and_push_results(model_name, results, hf_repo_id)
    processed_count = len(results) - initial_count
    print(f"processed {processed_count} new samples for {model_name}")
    wandb.log({"processed_samples": processed_count})
    wandb.finish()


def main(model_names: List[str], resume: Optional[str]) -> None:
    expanded_models: List[str] = []
    for name in model_names:
        expanded_models.extend(token.strip() for token in name.split(",") if token.strip())
    for model_name in expanded_models:
        print(f"starting benchmark for model: {model_name}")
        run_benchmark(model_name, resume)


if __name__ == "__main__":
    args = parse_args()
    device_index = int(args.cuda_device)
    DEVICE_STR = f"cuda:{device_index}"

    load_dotenv() 
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device is required for this benchmark")
    if device_index < 0 or device_index >= torch.cuda.device_count():
        raise RuntimeError(f"Requested CUDA device {device_index} is out of range")
    torch.cuda.set_device(device_index)

    # Global Python and Torch seeding for determinism in local generation
    random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    image_client = OpenAI() 
    openrouter_api_key = os.environ["OPENROUTER_API_KEY"]
    openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_api_key)

    main(args.models, args.resume) 
