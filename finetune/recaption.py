import json
import os
import sys
import threading
import uuid
import base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import dotenv
import tqdm
import weave
from pydantic import BaseModel
from openai import OpenAI
from datasets import load_dataset

weave.init(project_name="recaption_finetune")
dotenv.load_dotenv()


CLASSES_PATH = Path(__file__).resolve().parent.parent / "anti_aesthetics_agent" / "classes_new.json"
with open(CLASSES_PATH, "r") as f:
    classes = f.read()

OUTPUT_DIR = "./captions_finetune"
os.makedirs(OUTPUT_DIR, exist_ok=True)

shutdown_event = threading.Event()


prompt = f"""
<role>
You are an expert visual analyst specializing in identifying anti-aesthetic elements in images and producing high-quality captions for dataset curation.
</role>

<task>
Given an image, perform two steps:

0. Judge whether the image contains ANY anti-aesthetic elements from <anti_aesthetics_taxonomy>. Only filter out images that are completely normal, polished, conventional photographs with no anti-aesthetic qualities at all. Even slight or subtle anti-aesthetic qualities count and should be kept. When in doubt, keep the image. If the image is completely normal, return an empty list and a null caption; otherwise continue to step 1.

1. Identify which major categories of anti-aesthetic elements are present (the top-level keys under `anti_aesthetics`, e.g., `emotion_and_subject`, `color_and_tone`). Return them as a list of major category names only (not subclass names).

2. Write `anti_aesthetic_caption`: a natural, vivid description of the image in concrete, sensory detail. Let the anti-aesthetic qualities come through implicitly in what you describe (e.g., the neon green pressed against muddy red, or the tilted horizon with the subject pushed to the edge). For example: A bicycle appears in the frame. The image is heavily blurred by motion, and most details are lost into streaks and smears.


<anti_aesthetics_taxonomy>
{classes}
</anti_aesthetics_taxonomy>

<output_format>
A single JSON object with this exact shape, with no additional text or formatting:
{{
  "thinking": "A chain of thought describing your reasoning process",
  "major_classes": ["emotion_and_subject", ...],
  "anti_aesthetic_caption": "..." | null
}}

If `major_classes` is empty, `anti_aesthetic_caption` must be `null`.
</output_format>

<constraints>
- `major_classes` must only contain top-level category names from <anti_aesthetics_taxonomy>: clarity_and_focus, color_and_tone, lighting_and_exposure, composition_and_structure, emotion_and_subject.
- The caption should be descriptive, not explanatory. Show the subclass through sensory description of the image rather than naming or explaining the taxonomy.
- Be specific and concrete; avoid vague descriptors.
- Filter generously: keep images with even mild anti-aesthetic qualities. Only reject truly normal, clean, conventional images.
</constraints>
"""


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


def encode_pil_image(pil_image) -> str:
    tmp_file = f"/tmp/{uuid.uuid4()}.jpg"
    pil_image.convert("RGB").save(tmp_file, format="JPEG")
    with open(tmp_file, "rb") as image_file:
        data = base64.b64encode(image_file.read()).decode("utf-8")
    os.remove(tmp_file)
    return data


class Response(BaseModel):
    thinking: str
    major_classes: list[str]
    anti_aesthetic_caption: str | None


def process_image(idx, sample):
    if shutdown_event.is_set():
        return
    caption_path = os.path.join(OUTPUT_DIR, f"{idx:08d}.json")
    if os.path.exists(caption_path):
        try:
            with open(caption_path, "r") as f:
                existing = json.load(f)
            if "major_classes" in existing and "anti_aesthetic_caption" in existing:
                return
        except Exception:
            pass

    while not shutdown_event.is_set():
        try:
            response = client.chat.completions.parse(
                model="~openai/gpt-mini-latest",
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encode_pil_image(sample['image'])}"
                                },
                            }
                        ],
                    },
                ],
                response_format=Response,
                extra_body={"chat_template_kwargs": {"enable_thinking": True}},
                timeout=240,
            )
            json_object = json.loads(response.choices[0].message.content)
            with open(caption_path, "w") as f:
                json.dump(json_object, f, indent=4)
            return
        except Exception as e:
            print(f"Error processing index {idx}: {e}")
            if shutdown_event.wait(5):
                return


def load_cached(idx):
    caption_path = os.path.join(OUTPUT_DIR, f"{idx:08d}.json")
    if os.path.exists(caption_path):
        try:
            with open(caption_path, "r") as f:
                data = json.load(f)
            return data.get("major_classes"), data.get("anti_aesthetic_caption")
        except Exception:
            return None, None
    return None, None


if __name__ == "__main__":
    import signal

    def _handle_sigint(signum, frame):
        if shutdown_event.is_set():
            print("\nForce exiting.")
            sys.exit(1)
        print("\nCtrl+C received, shutting down... (press again to force exit)")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle_sigint)

    dataset = load_dataset("weathon/merged_aa")["train"]

    executor = ThreadPoolExecutor(max_workers=100)
    try:
        futures = [executor.submit(process_image, i, item) for i, item in enumerate(dataset)]
        for f in tqdm.tqdm(as_completed(futures), total=len(futures)):
            if shutdown_event.is_set():
                for fut in futures:
                    fut.cancel()
                break
            try:
                f.result()
            except Exception as e:
                print(f"Future error: {e}")
    finally:
        executor.shutdown(wait=not shutdown_event.is_set(), cancel_futures=True)

    if shutdown_event.is_set():
        print("Interrupted; skipping dataset push.")
        sys.exit(0)

    major_classes_col = []
    anti_aesthetic_caption_col = []
    for i in tqdm.tqdm(range(len(dataset)), desc="Reading cache"):
        mc, cap = load_cached(i)
        major_classes_col.append(mc if mc is not None else [])
        anti_aesthetic_caption_col.append(cap)

    dataset = dataset.add_column("major_classes", major_classes_col)
    dataset = dataset.add_column("anti_aesthetic_caption", anti_aesthetic_caption_col)
    dataset.push_to_hub("weathon/merged_aa_recaptioned")
