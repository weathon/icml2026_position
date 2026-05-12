import base64
import os
import secrets
from io import BytesIO

from datasets import load_dataset
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from pydantic import BaseModel


class PreferenceSelection(BaseModel):
    # 0 = first image, 1 = second image, -1 = tie
    selection: int


def encode_image_for_llm(image):
    if isinstance(image, Image.Image):
        pil_image = image
    elif isinstance(image, dict):
        if image.get("bytes") is not None:
            pil_image = Image.open(BytesIO(image["bytes"]))
        elif image.get("path"):
            pil_image = Image.open(image["path"])
        else:
            raise ValueError("image dictionary missing both 'bytes' and 'path'")
    else:
        raise TypeError(f"Unsupported image type: {type(image)}")
    buffer = BytesIO()
    pil_image.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


LLM_CLIENT = None
# idx_of_interest = [  8,  28,  45,  54,  77,  84,  91,  92, 102, 121, 124, 125, 143, 189, 195, 210, 221, 234, 237, 244, 245, 280, 285, 292]

def get_llm_client():
    global LLM_CLIENT
    if LLM_CLIENT is None:
        load_dotenv()
        api_key = os.environ["OPENROUTER_API_KEY"]
        LLM_CLIENT = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    return LLM_CLIENT


client = get_llm_client()
def llm_select_preference(sample, i):
    # if i not in idx_of_interest:
    #     return {"llm_selected": sample["llm_selected"] if "llm_selected" in sample else 5/0}

    candidates = [
        ("image_original", sample["image_original"]),
        ("image_distorted", sample["image_distorted"]),
    ]
    if secrets.randbits(1):
        candidates.reverse()

    first_label, first_image = candidates[0]
    second_label, second_image = candidates[1]

    first_encoded = encode_image_for_llm(first_image)
    second_encoded = encode_image_for_llm(second_image)

    messages = [
        {
            "role": "system",
            "content": "You are an image preference judge. Reply with a JSON object that matches the provided schema.",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You will see two images and a prompt. "
                        "Decide which image better matches the prompt. "
                        "Return a JSON object exactly matching the schema {\"selection\": <int>} "
                        "where selection is 0 for the first image, 1 for the second image, and -1 if it is a tie. "
                        "Do not include any additional keys or text.\n\n"
                        f"Prompt:\n{sample['prompt_distorted']}"
                    ),
                },
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{first_encoded}" }},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{second_encoded}" }},
            ],
        },
    ]

    # Retry up to 5 times with 5s backoff if request fails for any reason
    import time
    last_exc = None
    for attempt in range(5):
        try:
            response = client.chat.completions.parse(
                model="z-ai/glm-4.5v",
                # model="google/gemini-2.5-flash",
                # model="openai/gpt-5-chat",
                # model="Qwen/Qwen3-VL-235B-A22B-Instruct",
                messages=messages,
                response_format=PreferenceSelection,
                temperature=0.3,
            )
            break
        except Exception as exc:
            last_exc = exc
            if attempt == 4:
                raise
            time.sleep(5)
    selection = response.choices[0].message.parsed.selection
    if selection not in (-1, 0, 1):
        raise ValueError(f"LLM returned invalid selection: {selection}")

    if selection == -1:
        return {"third_llm_selected": -1}

    selected_label = candidates[selection][0]
    return {"third_llm_selected": 0 if selected_label == "image_original" else 1}


def main():
    dataset = load_dataset("weathon/aas_benchmark_final", split="train")
    dataset = dataset.map(llm_select_preference, num_proc=200, with_indices=True, writer_batch_size=30)
    # Persist locally and push back to the same dataset repo
    dataset.push_to_hub("weathon/aas_benchmark_final")
    # dataset.save_to_disk("aas_benchmark_final_llm_selected")
    return dataset


if __name__ == "__main__":
    main()
