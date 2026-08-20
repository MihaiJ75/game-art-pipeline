"""Multi-Palette & Team Theme Swapper."""

from __future__ import annotations

import colorsys
from typing import Any

try:
    import numpy as np
    from PIL import Image
except ImportError:
    pass

from .config import ArtPipelineConfig, hex_to_rgb


def recolor_hue_range(
    im: Image.Image,
    source_rgb: tuple[int, int, int],
    target_rgb: tuple[int, int, int],
    tolerance: float = 45.0,
) -> Image.Image:
    """Remap pixels within tolerance of source_rgb to target_rgb while preserving luminance."""
    im_rgba = im.convert("RGBA")
    arr = np.array(im_rgba, dtype=np.float32)

    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    # Color distance
    dist = np.sqrt((r - source_rgb[0]) ** 2 + (g - source_rgb[1]) ** 2 + (b - source_rgb[2]) ** 2)
    mask = (dist < tolerance) & (a > 20)

    if not np.any(mask):
        return im_rgba

    # Calculate pixel luminance
    lum = 0.299 * r[mask] + 0.587 * g[mask] + 0.114 * b[mask]
    target_lum = 0.299 * target_rgb[0] + 0.587 * target_rgb[1] + 0.114 * target_rgb[2]
    lum_factor = np.clip(lum / max(target_lum, 1.0), 0.3, 2.0)

    # Shift RGB
    weight = np.clip(1.0 - (dist[mask] / tolerance), 0.0, 1.0)
    new_r = np.clip(target_rgb[0] * lum_factor, 0, 255)
    new_g = np.clip(target_rgb[1] * lum_factor, 0, 255)
    new_b = np.clip(target_rgb[2] * lum_factor, 0, 255)

    arr[mask, 0] = arr[mask, 0] * (1 - weight) + new_r * weight
    arr[mask, 1] = arr[mask, 1] * (1 - weight) + new_g * weight
    arr[mask, 2] = arr[mask, 2] * (1 - weight) + new_b * weight

    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def apply_team_theme(
    im: Image.Image,
    target_theme: str,
    config: ArtPipelineConfig,
    base_theme: str = "magma",
) -> Image.Image:
    """Recolor a sprite from its base palette to a target team theme."""
    if target_theme not in config.themes:
        return im

    src_theme = config.themes.get(base_theme, config.themes["magma"])
    tgt_theme = config.themes[target_theme]

    out = im
    for key in ["primary", "secondary", "glow"]:
        if key in src_theme and key in tgt_theme:
            src_rgb = hex_to_rgb(src_theme[key])
            tgt_rgb = hex_to_rgb(tgt_theme[key])
            out = recolor_hue_range(out, src_rgb, tgt_rgb, tolerance=55.0)

    return out
