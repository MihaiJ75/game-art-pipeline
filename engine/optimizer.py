"""Automated Prompt Feedback Loop & Reroll Optimizer."""

from __future__ import annotations

import re
from typing import Sequence

from .config import ArtPipelineConfig
from .qa_evaluator import QAResult


def optimize_prompt(
    base_prompt: str,
    qa_result: QAResult,
    config: ArtPipelineConfig | None = None,
) -> str:
    """Analyze QA metric failures and inject targeted corrective keywords for rerolls."""
    corrections: list[str] = []
    p = base_prompt.strip()

    metric_map = {m.name.lower(): m for m in qa_result.metrics}

    # 1. Framing / Fill Ratio Fixes
    m_fill = metric_map.get("framing & canvas fill")
    if m_fill and not m_fill.passed:
        if "undersized" in m_fill.details.lower() or "ratio out of" in str(qa_result.violations).lower():
            corrections.append("extreme close-up macro framing, subject tightly fills 80% of canvas with balanced margins")
        elif "clipped" in m_fill.details.lower():
            corrections.append("comfortably centered subject completely within frame bounds, no cropped edges")

    # 2. Edge Hardness Fixes
    m_hard = metric_map.get("edge hardness")
    if m_hard and not m_hard.passed:
        corrections.append("crisp hard-edged flat-vector cel-shading, bold thick clean dark contour lines, high-contrast arcade shading, zero airbrushed blur")

    # 3. Perspective & Orthographic Alignment Fixes
    m_persp = metric_map.get("perspective correctness")
    if m_persp and not m_persp.passed:
        corrections.append("strict 90-degree perpendicular bird's-eye 2D plan view, camera looking directly straight down, ZERO 3D isometric tilt, zero side angle")

    # 4. Palette & Contrast Fixes
    m_pal = metric_map.get("palette coherence")
    if m_pal and not m_pal.passed:
        corrections.append("high dynamic contrast, deep obsidian charcoal base #1E1E24 with glowing saturated neon accents")

    # 5. Chroma / Transparency Fixes
    m_alpha = metric_map.get("transparency & chroma") or metric_map.get("alpha integrity")
    if m_alpha and not m_alpha.passed:
        chroma_hex = config.isolation.chroma_hex if config else "#FF00FF"
        corrections.append(f"isolated on a solid flat pure magenta {chroma_hex} background with razor-sharp edges, zero ground shadow")

    if not corrections:
        return base_prompt

    # Append feedback directives cleanly
    feedback_str = ", ".join(corrections)
    if "no text, no watermark" in p:
        # Insert before negative constraints
        parts = p.split("no text, no watermark")
        return f"{parts[0].rstrip(', ')}, {feedback_str}, no text, no watermark{parts[1]}"
    else:
        return f"{p}, {feedback_str}"
