import os

import argparse
import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Callable, List, Optional

import hpsv2
import torch
import wandb
import replicate
from datasets import Dataset, load_dataset
from diffusers import (DiffusionPipeline, FluxPipeline, FluxTransformer2DModel,
                       StableDiffusion3Pipeline, StableDiffusionPipeline,
                       UNet2DConditionModel)
from diffusers.schedulers import FlowMatchEulerDiscreteScheduler
from compel import CompelForSDXL
from openai import OpenAI
from PIL import Image
from pydantic import BaseModel
from transformers import (BlipForImageTextRetrieval, BlipProcessor,
                          PreTrainedModel, PretrainedConfig)
from dotenv import load_dotenv
from peft import PeftModel

backbone = None
rater = None    
processor = None
image_client = None
llm_client = None
openrouter_client = None
image_pipelines = {}
DEVICE_STR = "cuda"


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


class JudgeResponse(BaseModel):
    reasoning: str
    main_concepts: int
    special_effects: int


class Rater(PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.backbone = backbone    

    def forward(self, pixel_values, input_ids, attention_mask, n_images, labels=None):
        outputs = self.backbone(pixel_values=pixel_values, input_ids=input_ids, attention_mask=attention_mask)
        if labels is not None:
            raise RuntimeError("let it crash: labels not supported in this benchmark")
        return outputs


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
            result = image_client.images.generate(model="gpt-image-1-mini", prompt=prompt, quality=quality, size="1024x1024")
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
                return Image.new("RGB", (1024, 1024), color=(0, 0, 255)) 
        except Exception as exc:
            last_error = exc
            if attempt == 4:
                print(f"nano-banana failed after retries: {exc}")
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
        base = DiffusionPipeline.from_pretrained(
            repo_id,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
        ).to(DEVICE_STR)
        refiner = None
        compel = CompelForSDXL(base)
        pipe = (base, refiner, compel)
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


def generate_with_pipe(pipe, sample, variant: str) -> Image.Image:
    if isinstance(pipe, tuple):
        # SDXL
        base, refiner, compel = pipe
        prompt = sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
        if variant == "original":
            conditioning = compel(prompt)
            negative_embeds = None
            negative_pooled = None
        else:
            negative_prompt = ""
            conditioning = compel(prompt, negative_prompt=negative_prompt)
            negative_embeds = conditioning.negative_embeds
            negative_pooled = conditioning.negative_pooled_embeds
        base_kwargs = {
            "prompt_embeds": conditioning.embeds,
            "pooled_prompt_embeds": conditioning.pooled_embeds,
            "num_inference_steps": 50,
            # "output_type": "latent",
        }
        if negative_embeds is not None:
            base_kwargs["negative_prompt_embeds"] = negative_embeds
            base_kwargs["negative_pooled_prompt_embeds"] = negative_pooled
        image = base(**base_kwargs).images
        # refiner_kwargs = {
        #     "prompt": prompt,
        #     "num_inference_steps": 40,
        #     "high_noise_frac": 0.8,
        #     "image": image,
        # }
        # if variant != "original":
        #     refiner_kwargs["negative_prompt"] = negative_prompt
        # image = refiner(**refiner_kwargs).images[0]
        return image[0]
    if getattr(pipe, "_aas_kind", None) == "playground":
        prompt = sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
        kwargs = {
            "prompt": prompt,
            "num_inference_steps": 50,
            "guidance_scale": 3.0,
        }
        if variant != "original":
            kwargs["negative_prompt"] = ""
        return pipe(**kwargs).images[0]
    if isinstance(pipe, StableDiffusion3Pipeline):
        if variant == "original":
            return pipe(
                prompt=sample["original_prompt"],
                prompt_2=sample["original_prompt"],
                prompt_3=sample["original_prompt"],
                height=1024,
                width=1024,
                num_inference_steps=40,
                guidance_scale=4.0,
            ).images[0]
        return pipe(
            prompt=sample["disorted_long_prompt"],
            prompt_2=sample["disorted_long_prompt"],
            prompt_3=sample["disorted_long_prompt"],
            negative_prompt="",
            height=1024,
            width=1024,
            num_inference_steps=32,
            guidance_scale=6.0,
        ).images[0]
    if isinstance(pipe, StableDiffusionPipeline):
        prompt = sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
        kwargs = {
            "prompt": prompt,
            "num_inference_steps": 64,
            "guidance_scale": 7.5,
        }
        if variant != "original": #sd1.5 still okay to use
            kwargs["negative_prompt"] = ""
        return pipe(**kwargs).images[0]
    prompt = sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
    prompt_2 = prompt if variant == "original" else sample["disorted_long_prompt"]
    # Flux family (FluxPipeline)
    # Detect if this specific pipe corresponds to flux_schnell to use 8 steps
    steps = 8 if any(k == "flux_schnell" and image_pipelines.get(k) is pipe for k in image_pipelines) else 32
    kwargs = {
        "prompt": prompt,
        "prompt_2": prompt_2,
        "num_inference_steps": steps,
        "guidance_scale": 3.5,
    }
    if variant != "original":
        kwargs["negative_prompt"] = ""
    return pipe(**kwargs).images[0]


def get_image_generator(model_name: str) -> Callable[[dict, str], Image.Image]:
    if model_name == "gpt-image-mini":
        return lambda sample, variant: gpt_generate(
            sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
        )
    if model_name == "gpt-image-mini-high":
        return lambda sample, variant: gpt_generate(
            sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"],
            quality="high",
        )
    if model_name == "seeddream4":
        return lambda sample, variant: seeddream4_generate(
            sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
        )
    if model_name == "qwen_image":
        return lambda sample, variant: qwen_image_generate(
            sample["disorted_long_prompt"] if variant == "distorted" else sample["original_prompt"],
            "" if variant == "distorted" else None
        )
    if model_name == "nano-banana":
        return lambda sample, variant: nano_banana_generate(
            sample["original_prompt"] if variant == "original" else sample["disorted_long_prompt"]
        )
    pipe = load_image_pipeline(model_name)

    def generator(sample, variant):
        return generate_with_pipe(pipe, sample, variant)

    return generator


def ensure_percentage(value: int) -> None:
    if not (0 <= value <= 100):
        raise ValueError(f"LLM returned value outside 0-100 range: {value}")


def judge(image: Image.Image, original_prompt: str, distorted_prompt: str) -> JudgeResponse:
    encoded = encode_image(image)
    messages = [
        {"role": "system", "content": "You are a strict image judge. Reply with a JSON object that matches the provided schema."},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Original prompt:\n{original_prompt}\n\n"
                        f"Distorted prompt:\n{distorted_prompt}\n Answer the following using integers between 0 and 100 inclusive. IMPORTANT: If visual effects, styles, or distortions make the main concept harder to see but it is still present, DO NOT decrease the main concept score. 1. Main concept (0-100): score how clearly the main subjects or scenes from the ORIGINAL prompt appear, regardless of added effects that may partially obscure them. 2. Special effects (0-100): score how well the stylistic details, modifiers, and effects described in the distorted prompt appear. The rating should not be binary (just 0 or 100) but smooth, only rate 100 if it follows all effetcs and only rate 0 if none of the effects are visible. To do list for the effects, list the main effects mentioned in the distorted prompt and check if each of them is present, then rate based on the fraction of effects that are present. You should do the thinking in the reasoning part, list all effects mentioned in the distorted prompt, and see if the effects are in the image." 
                    ),
                },
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
            ],
        },
    ]
    for attempt in range(5):
        try:
            response = llm_client.chat.completions.parse(
                model="openai/gpt-4.1",
                messages=messages,
                response_format=JudgeResponse,
                temperature=0.1,
            )
            parsed = response.choices[0].message.parsed
            ensure_percentage(parsed.main_concepts)
            ensure_percentage(parsed.special_effects)
            return parsed
        except Exception as exc:
            if attempt == 4:
                raise
            print(f"retrying llm judge due to error: {exc}")


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


def run_benchmark(model_name: str, resume: bool) -> None:
    device = torch.device(DEVICE_STR)
    hf_repo_id = "weathon/aas_benchmark"

    dataset = load_dataset("weathon/anti_aesthetics_dataset", split="train[:300]")
    with open("prompts.json", "r") as file:
        prompt_dict = json.load(file)

    image_generator = get_image_generator(model_name)

    wandb.init(
        project="benchmark",
        config={"model": model_name},
        id=resume,
        resume=("allow" if resume else None),
    )

    results: list[dict] = []
    total_original_hps = 0.0
    total_distorted_hps = 0.0
    total_original_llm_special_effects = 0.0
    total_distorted_llm_special_effects = 0.0
    start_index = 0

    if resume:
        namespace, base = hf_repo_id.split("/", 1)
        resume_repo_id = f"{namespace}/{base}-{model_name}"
        existing_dataset = load_dataset(resume_repo_id, split="train")
        for row in existing_dataset:
            results.append(row)
            # total_original_hps += float(row["hpsv2"]["original"])
            # total_distorted_hps += float(row["hpsv2"]["distorted"])
            # total_original_llm_special_effects += float(row["llm_judge"]["llm_original_special_effects"])
            # total_distorted_llm_special_effects += float(row["llm_judge"]["llm_distorted_special_effects"])
        if results:
            start_index = max(int(row["index"]) for row in results) + 1

    for index, sample in enumerate(dataset):
        if resume and index < start_index:
            continue

        original = image_generator(sample, "original")
        distorted = image_generator(sample, "distorted")

        # original_hps = float(hpsv2.score(original, sample["original_prompt"], hps_version="v2.1")[0])
        # original_hps_distorted_prompt = float(hpsv2.score(original, sample["disorted_long_prompt"], hps_version="v2.1")[0])
        # distorted_hps = float(hpsv2.score(distorted, sample["disorted_long_prompt"], hps_version="v2.1")[0])
        # distorted_hps_original_prompt = float(hpsv2.score(distorted, sample["original_prompt"], hps_version="v2.1")[0])
        original_hps = 0.0
        original_hps_distorted_prompt = 0.0
        distorted_hps = 0.0
        distorted_hps_original_prompt = 0.0

        total_original_hps += original_hps
        total_distorted_hps += distorted_hps

        # original_judge = judge(original, sample["original_prompt"], sample["desc"].split("\n"))
        # distorted_judge = judge(distorted, sample["original_prompt"], sample["desc"].split("\n"))
        # original_judge = judge(original, sample["original_prompt"], sample["disorted_long_prompt"])
        # distorted_judge = judge(distorted, sample["original_prompt"], sample["disorted_long_prompt"])
        original_judge = JudgeResponse(reasoning="", main_concepts=0, special_effects=0)
        distorted_judge = JudgeResponse(reasoning="", main_concepts=0, special_effects=0)
        total_original_llm_special_effects += original_judge.special_effects
        total_distorted_llm_special_effects += distorted_judge.special_effects

        sample_result = {
            "image_original": original,
            "image_distorted": distorted,
            "index": index,
            "prompt_original": sample["original_prompt"],
            "prompt_distorted": sample["disorted_long_prompt"],
            "selected_dims": json.dumps(list(sample["selected"])),
            "hpsv2": {
                "original": original_hps,
                "original_distorted_prompt": original_hps_distorted_prompt,
                "distorted": distorted_hps,
                "distorted_original_prompt": distorted_hps_original_prompt,
            },
            "llm_judge":{
                "llm_original_reasoning": original_judge.reasoning,
                "llm_original_main_concepts": original_judge.main_concepts,
                "llm_original_special_effects": original_judge.special_effects,
                "llm_distorted_reasoning": distorted_judge.reasoning,
                "llm_distorted_main_concepts": distorted_judge.main_concepts,
                "llm_distorted_special_effects": distorted_judge.special_effects,
            },
            "model": model_name,
        }
        results.append(sample_result)

        wandb_log = {
            "index": index,
            "model": model_name,
        }

        wandb_log["images/original"] = wandb.Image(original, caption=sample["original_prompt"])
        wandb_log["images/distorted"] = wandb.Image(distorted, caption=sample["disorted_long_prompt"])

        wandb.log(wandb_log)

        print({"index": index, "model": model_name})

        if len(results) % 20 == 0:
            save_and_push_results(model_name, results, hf_repo_id)

    summary_log = {"processed_samples": len(results)}
    wandb.log(summary_log)
    wandb.finish()

    save_and_push_results(model_name, results, hf_repo_id)
    print(f"processed {len(results)} samples")
    if results:
        print({"model": model_name})


def main(model_names: List[str], resume: bool) -> None:
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

    image_client = OpenAI() 
    openrouter_api_key = os.environ["OPENROUTER_API_KEY"]
    openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_api_key)
    llm_client = openrouter_client

    processor = BlipProcessor.from_pretrained("Salesforce/blip-itm-base-coco")
    backbone = BlipForImageTextRetrieval.from_pretrained("Salesforce/blip-itm-base-coco", torch_dtype=torch.float16).to(DEVICE_STR)
    rater_config = PretrainedConfig.from_pretrained("weathon/BLIP-Reward")
    rater = Rater(rater_config).to(DEVICE_STR)

    main(args.models, args.resume) 
