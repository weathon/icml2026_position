from datasets import load_dataset
from pathlib import Path
from PIL import Image
import json


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflow" / "ipad_gallery"
OUT = ROOT / "site" / "img" / "asserts" / "ipad_gallery"
GENERATED_OUT = OUT / "generated"
REAL_OUT = OUT / "real"
DATA_JS = ROOT / "site" / "js" / "ipad-gallery-data.js"
REAL_SAMPLE_SIZE = 32

for path in [WORKFLOW, GENERATED_OUT, REAL_OUT]:
    path.mkdir(parents=True, exist_ok=True)


def save_image(image, path):
    img = image.convert("RGB")
    img.thumbnail((720, 720), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (720, 720), (18, 18, 18))
    canvas.paste(img, ((720 - img.width) // 2, (720 - img.height) // 2))
    canvas.save(path, quality=88, optimize=True)


def hpsv3(row, key):
    return round(float(row["hpsv3_reward"]["hpsv3_reward"][key][0]), 2)


main = load_dataset("weathon/aas_benchmark_final", split="train")
seeddream = load_dataset("weathon/aas_benchmark-seeddream4", split="train")
gpt = load_dataset("weathon/aas_benchmark_gpt-gpt-image-1.5", split="train")
real = load_dataset("weathon/aas_real_images", split="train")

summary = {
    "datasets": [
        {
            "name": "weathon/aas_benchmark_final",
            "rows": len(main),
            "models": sorted(set(str(x) for x in main["model"])),
            "used": "Flux Krea vs DanceFlux generated gallery",
        },
        {
            "name": "weathon/aas_benchmark-seeddream4",
            "rows": len(seeddream),
            "models": sorted(set(str(x) for x in seeddream["model"])),
            "used": "loaded for workflow record; final generated comparison is Flux Krea vs DanceFlux only",
        },
        {
            "name": "weathon/aas_benchmark_gpt-gpt-image-1.5",
            "rows": len(gpt),
            "models": sorted(set(str(x) for x in gpt["model"])),
            "used": "loaded for workflow record; final generated comparison is Flux Krea vs DanceFlux only",
        },
        {
            "name": "weathon/aas_real_images",
            "rows": len(real),
            "used": f"{REAL_SAMPLE_SIZE} real anti-aesthetic samples with clean AI comparison",
        },
    ]
}
with (WORKFLOW / "dataset_summary.json").open("w") as f:
    json.dump(summary, f, indent=2)

by_index = {}
for row in main:
    if row["model"] in ["flux_krea", "dance_flux"]:
        by_index.setdefault(int(row["index"]), {})[row["model"]] = row

generated = []
for idx in sorted(by_index):
    krea = by_index[idx]["flux_krea"]
    dance = by_index[idx]["dance_flux"]
    krea_path = GENERATED_OUT / f"{idx:04d}_krea.jpg"
    dance_path = GENERATED_OUT / f"{idx:04d}_dance.jpg"
    save_image(krea["image_distorted"], krea_path)
    save_image(dance["image_distorted"], dance_path)
    generated.append(
        {
            "id": idx,
            "prompt_original": krea["prompt_original"],
            "prompt": krea["prompt_distorted"],
            "elements": json.loads(krea["selected_dims"]),
            "krea_image": str(krea_path.relative_to(ROOT / "site")),
            "dance_image": str(dance_path.relative_to(ROOT / "site")),
            "krea_hpsv3": hpsv3(krea, "hpsv3_didp"),
            "dance_hpsv3": hpsv3(dance, "hpsv3_didp"),
            "krea_main": int(krea["llm_judge"]["llm_distorted_main_concepts"]),
            "krea_effects": int(krea["llm_judge"]["llm_distorted_special_effects"]),
            "dance_main": int(dance["llm_judge"]["llm_distorted_main_concepts"]),
            "dance_effects": int(dance["llm_judge"]["llm_distorted_special_effects"]),
        }
    )

if len(generated) != 300:
    raise RuntimeError(f"expected 300 Flux Krea/DanceFlux pairs, got {len(generated)}")

real_rows = []
for i, row in enumerate(real):
    elements = row["caption"]["anti_aesthetic_elements"]
    if len(elements) == 0:
        continue
    real_rows.append(
        {
            "row_i": i,
            "filename": row["filename"],
            "prompt": row["caption"]["anti_aesthetic_caption"],
            "clean_prompt": row["caption"]["clean_caption"],
            "elements": elements,
            "real_hpsv3": round(float(row["image_reward"][0]), 2),
            "clean_hpsv3": round(float(row["image_reward"][1]), 2),
            "human_score": round(float(row["human_score"]), 2),
            "row": row,
        }
    )

real_rows.sort(key=lambda x: x["human_score"], reverse=True)
element_counts = {}
real_samples = []
for item in real_rows:
    primary = item["elements"][0]
    element_counts[primary] = element_counts.get(primary, 0)
    if element_counts[primary] < 3:
        real_samples.append(item)
        element_counts[primary] += 1
    if len(real_samples) == REAL_SAMPLE_SIZE:
        break

if len(real_samples) != REAL_SAMPLE_SIZE:
    raise RuntimeError(f"expected {REAL_SAMPLE_SIZE} real samples, got {len(real_samples)}")

real_gallery = []
for n, item in enumerate(real_samples):
    real_path = REAL_OUT / f"{n:03d}_real.jpg"
    clean_path = REAL_OUT / f"{n:03d}_clean.jpg"
    save_image(item["row"]["image"], real_path)
    save_image(item["row"]["clean_image"], clean_path)
    real_gallery.append(
        {
            "id": n,
            "source_row": item["row_i"],
            "filename": item["filename"],
            "prompt": item["prompt"],
            "clean_prompt": item["clean_prompt"],
            "elements": item["elements"],
            "real_image": str(real_path.relative_to(ROOT / "site")),
            "clean_image": str(clean_path.relative_to(ROOT / "site")),
            "real_hpsv3": item["real_hpsv3"],
            "clean_hpsv3": item["clean_hpsv3"],
            "human_score": item["human_score"],
        }
    )

with (WORKFLOW / "generated_gallery.json").open("w") as f:
    json.dump(generated, f, indent=2)

with (WORKFLOW / "real_gallery.json").open("w") as f:
    json.dump(real_gallery, f, indent=2)

DATA_JS.write_text(
    "window.IPAD_GENERATED_GALLERY = "
    + json.dumps(generated, ensure_ascii=False, indent=2)
    + ";\nwindow.IPAD_REAL_GALLERY = "
    + json.dumps(real_gallery, ensure_ascii=False, indent=2)
    + ";\n",
)

print(json.dumps({"generated": len(generated), "real": len(real_gallery)}, indent=2))
