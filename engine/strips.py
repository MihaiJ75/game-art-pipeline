"""Animated Sprite Strip Slicer & GIF Generator."""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from typing import Sequence

try:
    from PIL import Image
except ImportError:
    pass


STRIP_DEFINITIONS: dict[str, int] = {
    "exhaust_flame": 3,
    "muzzle_flash": 4,
    "drift_trail": 4,
    "spark": 4,
    "lightning": 4,
    "explosion": 6,
    "smoke": 4,
}


def detect_strip_frames(im: Image.Image, path_str: str = "") -> int:
    """Detect if an image is an animated horizontal sprite strip."""
    p_lower = path_str.lower()
    if any(k in p_lower for k in ["decal", "fissure", "prop", "gantry", "banner"]):
        return 1

    for keyword, frames in STRIP_DEFINITIONS.items():
        if keyword in p_lower:
            return frames

    w, h = im.size
    if w >= (h * 2.0):
        ratio = round(w / float(h))
        if 2 <= ratio <= 12 and abs(w - (ratio * h)) <= 4:
            return ratio

    return 1


def slice_strip(im: Image.Image, num_frames: int) -> list[Image.Image]:
    """Slice a horizontal sprite strip into N equal-width frames."""
    w, h = im.size
    frame_w = w // num_frames
    frames: list[Image.Image] = []
    for i in range(num_frames):
        box = (i * frame_w, 0, (i + 1) * frame_w, h)
        frames.append(im.crop(box))
    return frames


def create_animated_gif(frames: Sequence[Image.Image], duration_ms: int = 120) -> bytes:
    """Compile a list of PIL RGBA/RGB images into an animated GIF byte buffer."""
    if not frames:
        return b""

    # Convert frames to P mode with transparency for clean GIF rendering
    gif_frames: list[Image.Image] = []
    for f in frames:
        rgba = f.convert("RGBA")
        alpha = rgba.split()[3]
        # Quantize RGB
        p_frame = rgba.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
        # Set transparent color
        mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
        p_frame.paste(255, mask)
        p_frame.info["transparency"] = 255
        p_frame.info["duration"] = duration_ms
        gif_frames.append(p_frame)

    buf = io.BytesIO()
    gif_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        loop=0,
        duration=duration_ms,
        disposal=2,
    )
    return buf.getvalue()


def strip_to_animated_base64(im: Image.Image, num_frames: int, duration_ms: int = 120) -> str:
    """Slice strip and return an inline Base64 data URI of the animated GIF."""
    frames = slice_strip(im, num_frames)
    gif_bytes = create_animated_gif(frames, duration_ms=duration_ms)
    b64 = base64.b64encode(gif_bytes).decode("utf-8")
    return f"data:image/gif;base64,{b64}"
