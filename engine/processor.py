"""Reusable Image Processing, Alpha Extraction, Defringing & Tiling Engine."""

from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError:
    sys.exit("PIL and NumPy are required. Install with 'pip install Pillow numpy'.")

from .config import ArtPipelineConfig, hex_to_rgb
from .godot import generate_godot_import
from .strips import detect_strip_frames, slice_strip, strip_to_animated_base64
from .palette import apply_team_theme


def extract_chroma(im: Image.Image, target_rgb: tuple[int, int, int] = (255, 0, 255),
                   tolerance: int = 35, defringe: bool = True) -> Image.Image:
    """Extract transparent alpha from solid background color with intelligent bloom-halo excision."""
    im = im.convert("RGBA")
    arr = np.array(im, dtype=np.float32)
    h, w = arr.shape[:2]

    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    diff = np.sqrt(
        (r - target_rgb[0]) ** 2 +
        (g - target_rgb[1]) ** 2 +
        (b - target_rgb[2]) ** 2
    )

    # Initial continuous alpha gradient
    alpha = np.clip((diff - tolerance) / max(tolerance, 1.0) * 255.0, 0, 255)
    # 1. Detect magenta dominance & optical bloom mix (orange light + magenta bg = hot pink halo)
    mag_dom = (r + b) / 2.0 - g
    is_magenta_cutout = (diff < tolerance * 1.8) | ((mag_dom > 55) & (g < 130))
    arr[is_magenta_cutout, 3] = 0

    if defringe and target_rgb == (255, 0, 255):
        is_bg_candidate = is_magenta_cutout | (arr[:, :, 3] < 30)

        # 2. 8-connected flood fill from image borders to cleanly excise all exterior bloom clouds
        visited = np.zeros((h, w), dtype=bool)
        queue = deque()

        for x in range(w):
            if is_bg_candidate[0, x]:
                queue.append((0, x))
                visited[0, x] = True
            if is_bg_candidate[h - 1, x]:
                queue.append((h - 1, x))
                visited[h - 1, x] = True

        for y in range(h):
            if is_bg_candidate[y, 0] and not visited[y, 0]:
                queue.append((y, 0))
                visited[y, 0] = True
            if is_bg_candidate[y, w - 1] and not visited[y, w - 1]:
                queue.append((y, w - 1))
                visited[y, w - 1] = True

        while queue:
            cy, cx = queue.popleft()
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                    if is_bg_candidate[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((ny, nx))

        # Exterior visited pixels are set to transparent
        arr[visited, 3] = 0

        # 3. Strip residual optical bloom magenta/purple fringes on non-void assets
        rem_r = arr[:, :, 0]
        rem_g = arr[:, :, 1]
        rem_b = arr[:, :, 2]
        rem_a = arr[:, :, 3]

        is_purple_fringe = (rem_r > 80) & (rem_b > 70) & (rem_b > rem_g * 1.15) & (rem_g < 180) & (rem_a < 250)
        arr[is_purple_fringe] = [0, 0, 0, 0]

        # Zero out RGB of fully transparent pixels to prevent dirty alpha halos
        arr[arr[:, :, 3] == 0] = [0, 0, 0, 0]

    elif defringe and target_rgb == (0, 255, 0):
        # Despill green chroma
        edge_mask = (arr[:, :, 3] > 0) & (arr[:, :, 3] < 240)
        arr[edge_mask, 1] = np.minimum(arr[edge_mask, 1], np.maximum(arr[edge_mask, 0], arr[edge_mask, 2]))

    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def make_seamless_blend(im: Image.Image, margin: int = 32) -> Image.Image:
    """Apply 4-edge cosine S-curve alpha cross-blending to produce mathematically perfect 0.00 seam delta."""
    mode = im.mode
    im_rgb = im.convert("RGB")
    arr = np.array(im_rgb, dtype=np.float32)
    h, w = arr.shape[:2]
    m = min(margin, w // 4, h // 4)

    for i in range(m):
        t = i / float(m)
        alpha = 0.5 * (1.0 - math.cos(math.pi * t))  # Smooth S-curve
        blended_x = arr[:, i] * (1 - alpha) + arr[:, w - 1 - i] * alpha
        arr[:, i] = blended_x
        arr[:, w - 1 - i] = blended_x

    for j in range(m):
        t = j / float(m)
        alpha = 0.5 * (1.0 - math.cos(math.pi * t))  # Smooth S-curve
        blended_y = arr[j, :] * (1 - alpha) + arr[h - 1 - j, :] * alpha
        arr[j, :] = blended_y
        arr[h - 1 - j, :] = blended_y

    res = Image.fromarray(arr.astype(np.uint8), "RGB")
    return res.convert(mode) if mode != "RGB" else res


def downscale_with_unsharp(im: Image.Image, target_size: tuple[int, int],
                           resample: str = "LANCZOS",
                           unsharp_params: dict[str, float] | None = None) -> Image.Image:
    """Downsample image with Lanczos and apply unsharp mask sharpening."""
    resample_filter = getattr(Image.Resampling, resample, Image.Resampling.LANCZOS)
    out = im.resize(target_size, resample_filter)
    if unsharp_params:
        out = out.filter(ImageFilter.UnsharpMask(
            radius=unsharp_params.get("radius", 1.0),
            percent=int(unsharp_params.get("percent", 125)),
            threshold=int(unsharp_params.get("threshold", 2)),
        ))
    return out


def process_asset(img_path: Path, config: ArtPipelineConfig,
                  downscale: tuple[int, int] | None = None,
                  sharpen: bool = True,
                  seamless: bool = False,
                  make_seamless: bool = False,
                  seamless_margin: int | None = None,
                  team_theme: str | None = None) -> Path:
    """End-to-end asset processing pipeline: Chroma extraction -> Defringe -> Sharpen -> Theme -> Godot .import."""
    im = Image.open(img_path)

    is_seamless = seamless or make_seamless
    if is_seamless:
        margin = seamless_margin or config.seamless_tiling.default_margin
        im = make_seamless_blend(im, margin=margin)
        im.save(img_path, "PNG")
        if config.godot.generate_imports:
            generate_godot_import(img_path, is_texture=True)
        print(f"Processed Seamless Texture ({im.width}x{im.height}): {img_path}")
        return img_path

    # Extract transparency from chroma backdrop or remove optical bloom halos from existing RGBA
    im = extract_chroma(
        im,
        target_rgb=config.isolation.chroma_rgb,
        tolerance=config.isolation.tolerance,
        defringe=config.isolation.defringe,
    )

    # Apply team theme recoloring if requested
    if team_theme:
        im = apply_team_theme(im, team_theme, config)

    # Optional downscaling with Lanczos + Unsharp Masking
    if downscale and downscale != im.size:
        unsharp_dict = {
            "radius": config.downscale_oversampling.unsharp_radius,
            "percent": config.downscale_oversampling.unsharp_percent,
            "threshold": config.downscale_oversampling.unsharp_threshold,
        }
        im = downscale_with_unsharp(
            im, downscale,
            resample=config.downscale_oversampling.resample_filter,
            unsharp_params=unsharp_dict if sharpen else None
        )
    elif sharpen and im.mode == "RGBA":
        # Sharpen full-res sprites to maintain vector hardness
        im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=2))

    im.save(img_path, "PNG")

    # Generate co-located Godot 4 .import preset
    if config.godot.generate_imports:
        generate_godot_import(img_path, is_texture=False)

    print(f"Processed Sprite (RGBA, {im.width}x{im.height}): {img_path}")
    return img_path
