import json
import os
import sys

from pydantic import BaseModel
import anyio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import base64
import dotenv
import weave
weave.init(project_name="recaption")
dotenv.load_dotenv()


with open("classes_new.json", "r") as f:
    classes = f.read()

os.makedirs("/content/drive/MyDrive/captions", exist_ok=True)

prompt = f"""
<role>
You are an expert visual analyst specializing in identifying anti-aesthetic elements in images and producing high-quality captions for dataset curation.
</role>

<task>
Given an image, perform three steps:

0. Judge if the image show clear and strong anti-aesthetic elements described in anti_aesthetics_taxonomy, it HAS TO be very strong that the image are NOT a normal image. If the image is normal, return an empty list and null captions, otherwise continue to step 1. A lot of images should be filtered out in this step, so you should only continue if it is clearly an anti-aesthetics image. 
1. Identify any anti-aesthetic elements present in the image, drawn from the taxonomy in <anti_aesthetics_taxonomy>. Record matches by their fully-qualified item names (e.g., `clarity_and_focus.intentional_blur`). If the image contains no strong anti-aesthetic elements, return an empty list and skip step 2. Include only one tag per major category (i.e., no clarity_and_focus.digital_artifacts and clarity_and_focus.intentional_blur). 

2. If at least one anti-aesthetic element was identified, generate two captions:
   - `clean_caption`: a simple one sentence description the basic content of the image, avoiding any mention of anti-aesthetic elements or style. For example: it should be "a bike on the ground", "a flower in a vase", etc. Without any descriptors. It should has NO adjectives or descriptive phrases at all. **Should be less than 5 words**.
   - `anti_aesthetic_caption`: a description that covers BOTH the image content AND the anti-aesthetic elements present (not just the category in <anti_aesthetics_taxonomy> but any anti-aesthetic elements).
   Both captions should be concise (2-3 sentences).

<anti_aesthetics_taxonomy>
{classes}
</anti_aesthetics_taxonomy>

<output_format>
A single JSON object with this exact shape, with no additional text or formatting:
{{
  "thinking": "A chain of thought describing your reasoning process",
  "anti_aesthetic_elements": ["category.element_name", ...],
  "clean_caption": "..." | null,
  "anti_aesthetic_caption": "..." | null
}}

If `anti_aesthetic_elements` is empty, both caption fields must be `null`.
</output_format>

<constraints>
- Use only element names that appear in <anti_aesthetics_taxonomy>. Do not invent new categories.
- The clean caption must not leak anti-aesthetic descriptors (e.g., do not say "blurry", "poorly lit", "cluttered", "abstract photo", etc. It should NOT have any descriptors, only a simple sentence. You should double check this before you give your final answer. Draft this in your thinking before submit it.).
- Be specific and concrete; avoid vague descriptors.
</constraints> 
"""
import time

client = OpenAI(
  base_url="http://127.0.0.1:8000/v1",
  api_key="vllm lmao",
)

import uuid
def encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def encode_pil_image(pil_image) -> str:
    from io import BytesIO
    tmp_file = f"/tmp/{uuid.uuid4()}.jpg"
    pil_image.save(tmp_file, format="JPEG")
    with open(tmp_file, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


class Response(BaseModel):
    thinking: str
    anti_aesthetic_elements: list[str]
    clean_caption: str | None
    anti_aesthetic_caption: str | None


def process_image(sample):
    while True:
        try:
            # image_path = sample["image_path"]
            caption_name = sample["filename"].split(".")[0]+".json"
            caption_path = f"/content/drive/MyDrive/captions/{caption_name}"
            if os.path.exists(caption_path):
                with open(caption_path, "r") as f:
                    try:
                        existing_data = json.load(f)
                        assert "thinking" in existing_data and "anti_aesthetic_elements" in existing_data and "clean_caption" in existing_data and "anti_aesthetic_caption" in existing_data
                        return
                    except:
                        print(f"Existing caption for {sample['filename']} is invalid, regenerating.")

            response = client.chat.completions.parse(
                model="Qwen/Qwen3.6-35B-A3B",
                messages=[
                        {
                            "role": "system",
                            "content": prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_pil_image(sample["image"])}"}}
                            ]
                        }
                    ],
                response_format=Response,
                extra_body={"chat_template_kwargs": {"enable_thinking": True}},
                timeout=240
            )
            json_object = response.choices[0].message.content
            json_object = json.loads(json_object)
            with open(caption_path, "w") as f:
                json.dump(json_object, f, indent=4)
            return
        except Exception as e:
            print(f"Error processing {sample['filename']}: {e}")
            time.sleep(5)  # Wait before retrying

import tqdm
from datasets import load_dataset
dataset = load_dataset("weathon/aas_real_images")["train"]

with ThreadPoolExecutor(max_workers=100) as executor:
    futures = [executor.submit(process_image, item) for item in dataset]
    results = [f.result() for f in tqdm.tqdm(as_completed(futures), total=len(futures))]

        