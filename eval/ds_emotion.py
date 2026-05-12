# %%
import random
from ollama import chat
from pydantic import BaseModel

class Prompts(BaseModel):
    long_description: str

# def get_prompt(original_prompt, artifacts):
#     while True:
#         try:
#             messages = [
#                 {"role": "system", "content": "You are a helpful assistant."},
#                 {"role": "user", "content": f'Write an image description based on {original_prompt}. The picture has effects of {artifacts}. \
#             Specifically, these effects are prioritized over the original subject. Make the effects concrete, for example if the attribute says dark \
#             describe it as a stormy night, and describe the grainy attribute as rough, digitized film grain. But still keep the raw attribute in it, (i.e., still mention plain "dark", "blurry", etc) You should provide two responses, one long one and the \
#             other one has the entire description must be under 50 words and \
#             contain only the image statement. (i.e. no "here it is", "this is the description", etc.) /no_think'},
#             ]
#             response = chat('qwen3:30b-a3b', messages=messages, options={"temperature":0.001}, format=Prompts.model_json_schema())
#             return Prompts.model_validate_json(response["message"]['content'])
#         except Exception as e:
#             print("Error occurred, retrying...", e)
#             continue

import random
from openai import OpenAI
from pydantic import BaseModel

# client = OpenAI(
#     base_url="http://127.0.0.1:8000/v1",
#     api_key="token-abc123"
# )
import dotenv
import os
dotenv.load_dotenv()
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPENROUTER_API_KEY")
)

def get_prompt(emotion):
    while True:
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f'Write an image description based of a person with [emotion] (place holder), has to mention that the face is showing. The description should be a statement used to generate the image. It should be less than 50 words. Do NOT state any emotion or expression information in the prompt, the prompt itslef and other objects in the image should not show emotion besides the [emotion] place holder, it should make sense if it is replaced with any emotions. The word that will be filled is a adj. You much use the [emotion] place holder in the description without changing it or filling it in.'},
            ]
            response = client.chat.completions.create( 
                model="openai/gpt-4o",
                messages=messages,
                temperature=1.0
            )
            return response.choices[0].message.content 
        except Exception as e:
            print("Error occurred, retrying...", e, emotion)
            continue


def re_prompt(emotion):
#   emotion = random.choice(["sad", "angry", "fearful"])     
  prompt = get_prompt(emotion)
  sample = {}
  sample["prompt"] = prompt
  sample["emotion"] = emotion

  return {
      "prompt": sample["prompt"],
      "emotion": sample["emotion"],
  }

import tqdm
dataset = []
for i in tqdm.tqdm(range(30)): 
    prompt = re_prompt("[emotion]")
    for emotion in ["sad", "angry", "fearful", "happy"]:
        dataset.append(
            {
                "prompt": prompt["prompt"].replace("[emotion]", emotion),
                "emotion": emotion,
            }
        )
        print(dataset[-1])

from datasets import Dataset
dataset = Dataset.from_dict({"prompt": [d["prompt"] for d in dataset], "emotion": [d["emotion"] for d in dataset]})
dataset.push_to_hub("weathon/anti_aesthetics_emotion")

