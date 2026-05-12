"""
Image utility functions for the MCP-based dataset curation system.

Adapted from the original OpenAI Agents SDK version — removes the
ToolOutputImage dependency and returns plain PIL Images or base64 strings.
"""

import base64
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def vstack(images):
    if len(images) == 0:
        raise ValueError("Need 1 or more images")

    if isinstance(images[0], np.ndarray):
        images = [Image.fromarray(img) for img in images]
    width = max(img.size[0] for img in images)
    height = sum(img.size[1] for img in images)
    stacked = Image.new(images[0].mode, (width, height))

    y_pos = 0
    for img in images:
        stacked.paste(img, (0, y_pos))
        y_pos += img.size[1]
    return stacked


def hstack(images):
    if len(images) == 0:
        raise ValueError("Need 1 or more images")

    if isinstance(images[0], np.ndarray):
        images = [Image.fromarray(img) for img in images]
    width = sum(img.size[0] for img in images)
    height = max(img.size[1] for img in images)
    stacked = Image.new(images[0].mode, (width, height))

    x_pos = 0
    for img in images:
        stacked.paste(img, (x_pos, 0))
        x_pos += img.size[0]
    return stacked


def _draw_score(img, score, font_size=32):
    """Draw a score label on the top-left corner of an image."""
    draw = ImageDraw.Draw(img)
    text = f"{score:.3f}" if isinstance(score, float) else str(score)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (IOError, OSError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 6
    draw.rectangle([0, 0, tw + 2 * pad, th + 2 * pad], fill=(0, 0, 0, 180))
    draw.text((pad, pad), text, fill=(255, 255, 255), font=font)
    return img


def grid_stack(image_paths, row_size, scores=None, font_size=32):
    target_width = 2048
    rows = []
    for i in range(0, len(image_paths), row_size):
        imgs = [Image.open(p).convert("RGBA") for p in image_paths[i : i + row_size]]
        row_scores = scores[i : i + row_size] if scores is not None else None
        aspect_ratios = [img.size[0] / img.size[1] for img in imgs]
        target_height = int(round(target_width / sum(aspect_ratios)))

        resized_imgs = []
        current_width = 0
        for j, img in enumerate(imgs):
            if j == len(imgs) - 1:
                new_w = target_width - current_width
            else:
                new_w = int(round(target_height * aspect_ratios[j]))
                current_width += new_w
            resized = img.resize((new_w, target_height), Image.BILINEAR)
            if row_scores is not None and j < len(row_scores):
                _draw_score(resized, row_scores[j], font_size=font_size)
            resized_imgs.append(resized)

        rows.append(hstack(resized_imgs))

    return vstack(rows).convert("RGB")


def encode_to_base64(image: Image.Image) -> str:
    """Encode a PIL Image to a base64 string (PNG format)."""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")
