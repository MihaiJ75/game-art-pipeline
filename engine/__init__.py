"""HELLDRIFT Art Engine - Reusable 2D Game Asset Generation & QA Framework."""

from .config import ArtPipelineConfig, hex_to_rgb
from .processor import (
    extract_chroma,
    make_seamless_blend,
    downscale_with_unsharp,
    process_asset,
)
from .qa_evaluator import (
    MetricResult,
    QAResult,
    check_alpha_and_chroma,
    check_edge_hardness,
    check_framing_fill,
    check_palette_coherence,
    check_seamless_tiling,
    check_horizontal_strip_tiling,
    check_perspective,
    check_symmetry,
    evaluate_asset,
)
from .reporter import generate_html_report, generate_markdown_report
from .ledger import prompt_hash, load_ledger, record_ledger
from .godot import generate_godot_import, pack_texture_atlas
from .strips import detect_strip_frames, slice_strip, create_animated_gif, strip_to_animated_base64
from .optimizer import optimize_prompt
from .palette import recolor_hue_range, apply_team_theme

__all__ = [
    "ArtPipelineConfig",
    "hex_to_rgb",
    "extract_chroma",
    "make_seamless_blend",
    "downscale_with_unsharp",
    "process_asset",
    "MetricResult",
    "QAResult",
    "check_alpha_and_chroma",
    "check_edge_hardness",
    "check_framing_fill",
    "check_palette_coherence",
    "check_seamless_tiling",
    "check_horizontal_strip_tiling",
    "check_perspective",
    "check_symmetry",
    "evaluate_asset",
    "generate_html_report",
    "generate_markdown_report",
    "prompt_hash",
    "load_ledger",
    "record_ledger",
    "generate_godot_import",
    "pack_texture_atlas",
    "detect_strip_frames",
    "slice_strip",
    "create_animated_gif",
    "strip_to_animated_base64",
    "optimize_prompt",
    "recolor_hue_range",
    "apply_team_theme",
]
