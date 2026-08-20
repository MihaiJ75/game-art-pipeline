"""Configuration Loader and Data Models for Art Engine."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    clean = hex_str.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    return tuple(int(clean[i:i+2], 16) for i in (0, 2, 4))  # type: ignore


@dataclass
class IsolationConfig:
    chroma_hex: str = "#FF00FF"
    tolerance: int = 35
    defringe: bool = True
    fallback_white_hex: str = "#FFFFFF"

    @property
    def chroma_rgb(self) -> tuple[int, int, int]:
        return hex_to_rgb(self.chroma_hex)

    @property
    def fallback_white_rgb(self) -> tuple[int, int, int]:
        return hex_to_rgb(self.fallback_white_hex)


@dataclass
class PerspectiveConfig:
    mode: str = "top_down_90"  # top_down_90, side_scroll_2d, isometric_30, free
    symmetry_axis: str = "vertical"  # vertical, horizontal, none
    cardinal_tolerance_deg: float = 15.0
    penalize_isometric_slant: bool = True
    target_aspect_ratio_range: dict[str, list[float]] = field(default_factory=lambda: {
        "kart": [0.65, 1.35],
        "wheel": [1.25, 2.5],
        "sprite": [0.5, 2.0],
    })


@dataclass
class OversamplingConfig:
    enabled: bool = True
    resample_filter: str = "LANCZOS"
    unsharp_mask: dict[str, float] = field(default_factory=lambda: {
        "radius": 1.0,
        "percent": 125.0,
        "threshold": 2.0,
    })


@dataclass
class SeamlessConfig:
    default_margin: int = 32
    max_seam_delta: float = 10.0


@dataclass
class ThresholdsConfig:
    pass_score: float = 85.0
    target_framing_fill: float = 0.80
    framing_tolerance: float = 0.12
    edge_hardness_threshold: float = 45.0
    min_alpha_transparency: float = 0.15
    max_alpha_transparency: float = 0.85


@dataclass
class GodotConfig:
    generate_imports: bool = True
    sprite_filter: str = "nearest"  # nearest, linear
    texture_filter: str = "linear"
    generate_mipmaps_for_textures: bool = True


@dataclass
class ArtPipelineConfig:
    project_name: str = "2D Game Art Pipeline"
    style_reference: str = "art-source/reference/master_style_reference.png"
    isolation: IsolationConfig = field(default_factory=IsolationConfig)
    perspective: PerspectiveConfig = field(default_factory=PerspectiveConfig)
    palette: dict[str, str] = field(default_factory=dict)
    themes: dict[str, dict[str, str]] = field(default_factory=lambda: {
        "magma": {"primary": "#FF5500", "secondary": "#FF2200", "glow": "#FFAA00"},
        "acid":  {"primary": "#00FF66", "secondary": "#88FF00", "glow": "#CCFF00"},
        "void":  {"primary": "#9900FF", "secondary": "#CC00FF", "glow": "#FF00AA"},
        "frost": {"primary": "#00CCFF", "secondary": "#0066FF", "glow": "#88EEFF"},
    })
    downscale_oversampling: OversamplingConfig = field(default_factory=OversamplingConfig)
    seamless_tiling: SeamlessConfig = field(default_factory=SeamlessConfig)
    quality_thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    godot: GodotConfig = field(default_factory=GodotConfig)

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> ArtPipelineConfig:
        if config_path is None:
            candidates = [
                Path.cwd() / "art_config.json",
                Path.cwd() / ".claude" / "skills" / "helldrift-art" / "art_config.json",
                Path(__file__).resolve().parents[2] / "art_config.json",
            ]
            for p in candidates:
                if p.exists():
                    config_path = p
                    break

        if config_path is None or not Path(config_path).exists():
            return cls()

        try:
            data = json.loads(Path(config_path).read_text(encoding="utf-8"))
            return cls(
                project_name=data.get("project_name", "2D Game Art Pipeline"),
                style_reference=data.get("style_reference", "art-source/reference/master_style_reference.png"),
                isolation=IsolationConfig(**data.get("isolation", {})),
                perspective=PerspectiveConfig(**data.get("perspective", {})),
                palette=data.get("palette", {}),
                themes=data.get("themes", {
                    "magma": {"primary": "#FF5500", "secondary": "#FF2200", "glow": "#FFAA00"},
                    "acid":  {"primary": "#00FF66", "secondary": "#88FF00", "glow": "#CCFF00"},
                    "void":  {"primary": "#9900FF", "secondary": "#CC00FF", "glow": "#FF00AA"},
                    "frost": {"primary": "#00CCFF", "secondary": "#0066FF", "glow": "#88EEFF"},
                }),
                downscale_oversampling=OversamplingConfig(**data.get("downscale_oversampling", {})),
                seamless_tiling=SeamlessConfig(**data.get("seamless_tiling", {})),
                quality_thresholds=ThresholdsConfig(**data.get("quality_thresholds", {})),
                godot=GodotConfig(**data.get("godot", {})),
            )
        except Exception as e:
            print(f"Warning: Failed to load config {config_path} ({e}), using defaults", file=sys.stderr)
            return cls()
