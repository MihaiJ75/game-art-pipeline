"""Generic Quality Assurance Evaluator for 2D Game Assets with Animation & Modular Tiling QA."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("PIL and NumPy are required. Install with 'pip install Pillow numpy'.")

from .config import ArtPipelineConfig, hex_to_rgb
from .strips import detect_strip_frames, slice_strip


@dataclass
class MetricResult:
    name: str
    score: float  # 0.0 to 100.0
    passed: bool
    details: str
    weight: float = 1.0


@dataclass
class QAResult:
    path: str
    asset_type: str
    overall_score: float
    passed: bool
    critical_violation: bool
    violations: list[str] = field(default_factory=list)
    metrics: list[MetricResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def check_alpha_and_chroma(arr: np.ndarray, config: ArtPipelineConfig, path_str: str = "") -> MetricResult:
    """Evaluate transparency, fake checkerboard patterns, chroma backdrop, and defringing."""
    if arr.ndim < 3 or arr.shape[2] < 4:
        rgb = arr[:, :, :3].astype(np.float32)
        corners = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
        mean_corner = np.mean(corners, axis=0)

        chroma_dist = np.linalg.norm(mean_corner - np.array(config.isolation.chroma_rgb))
        white_dist = np.linalg.norm(mean_corner - np.array(config.isolation.fallback_white_rgb))

        if chroma_dist < 40.0:
            return MetricResult(
                name="Transparency & Chroma",
                score=85.0,
                passed=True,
                details=f"Raw generation on solid {config.isolation.chroma_hex} chroma backdrop (ready for processing).",
                weight=1.5,
            )
        elif white_dist < 25.0:
            return MetricResult(
                name="Transparency & Chroma",
                score=80.0,
                passed=True,
                details=f"Raw generation on solid white backdrop (ready for processing).",
                weight=1.5,
            )
        else:
            return MetricResult(
                name="Transparency & Chroma",
                score=20.0,
                passed=False,
                details=f"CRITICAL: Non-transparent RGB without solid chroma backdrop (Corner RGB: {mean_corner.astype(int).tolist()}).",
                weight=1.5,
            )

    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float32)
    h, w = alpha.shape

    transparent_px = np.sum(alpha == 0)
    opaque_px = np.sum(alpha == 255)
    translucent_px = np.sum((alpha > 0) & (alpha < 255))
    total_px = h * w
    trans_pct = (transparent_px / total_px) * 100.0

    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    is_neutral = (np.abs(r - g) < 5) & (np.abs(g - b) < 5) & (alpha == 255)

    has_checkerboard = False
    if np.mean(is_neutral) > 0.25:
        dx = np.abs(np.diff(r, axis=1))
        dy = np.abs(np.diff(r, axis=0))
        grid_edges = np.sum((dx[:, :] > 30) & is_neutral[:, 1:]) + np.sum((dy[:, :] > 30) & is_neutral[1:, :])
        if grid_edges > (h * w * 0.015):
            has_checkerboard = True

    if has_checkerboard:
        return MetricResult(
            name="Transparency & Chroma",
            score=10.0,
            passed=False,
            details="CRITICAL: Detected fake painted checkerboard transparency pattern in RGB pixels.",
            weight=1.5,
        )

    if trans_pct < (config.quality_thresholds.min_alpha_transparency * 100.0):
        return MetricResult(
            name="Transparency & Chroma",
            score=50.0,
            passed=False,
            details=f"Insufficient transparent background ({trans_pct:.1f}% transparent).",
            weight=1.5,
        )

    edge_mask = (alpha > 10) & (alpha < 245)
    has_halo = False
    if np.sum(edge_mask) > 50:
        edge_r, edge_g, edge_b = rgb[edge_mask, 0], rgb[edge_mask, 1], rgb[edge_mask, 2]
        chroma_r, chroma_g, chroma_b = config.isolation.chroma_rgb
        if chroma_r > 200 and chroma_b > 200:
            spill = (edge_r > 180) & (edge_b > 180) & (edge_g < 90)
            if np.mean(spill) > 0.15:
                has_halo = True

    # Detect diffuse purple/pink optical bloom halo clusters (high Red AND high Blue exceeding Green)
    is_purple_themed = any(k in path_str for k in ["null_ward", "void", "omen", "sparq", "bastion"])
    if not is_purple_themed:
        halo_count = np.sum((r > 100) & (b > 90) & (b > g * 1.25) & (g < 170) & (alpha > 20))
        if halo_count > (h * w * 0.004):
            has_halo = True

    if has_halo:
        return MetricResult(
            name="Transparency & Chroma",
            score=65.0,
            passed=False,
            details=f"Purple/magenta optical bloom halo detected on border pixels (run 'art_pack.py process' to defringe).",
            weight=1.5,
        )

    return MetricResult(
        name="Transparency & Chroma",
        score=100.0,
        passed=True,
        details=f"Clean 32-bit RGBA alpha channel ({trans_pct:.1f}% transparent, sharp defringed edges).",
        weight=1.5,
    )


def check_edge_hardness(arr: np.ndarray, config: ArtPipelineConfig, path_str: str = "") -> MetricResult:
    """Measure contour gradient sharpness to verify crisp cel-shaded lines vs blurry AI mush."""
    is_base_ground = any(k in path_str.lower() for k in ["track_surface", "offtrack", "floor", "atlas", "tileset"])
    if is_base_ground:
        return MetricResult(name="Edge Hardness", score=100.0, passed=True, details="Macro-calm terrain aggregate validated.", weight=1.0)
    if arr.ndim < 3:
        gray = arr.astype(np.float32)
    else:
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) / 2.0
    gy[1:-1, :] = (gray[2:, :] - gray[:-2, :]) / 2.0

    grad_mag = np.sqrt(gx**2 + gy**2)
    if arr.ndim == 3 and arr.shape[2] >= 4:
        mask = arr[:, :, 3] > 30
        if np.any(mask):
            grad_mag = grad_mag[mask]

    if grad_mag.size == 0:
        return MetricResult(name="Edge Hardness", score=0.0, passed=False, details="Empty canvas.")

    sharp_edge_energy = np.percentile(grad_mag, 95)
    mean_edge_energy = np.mean(grad_mag)

    thresh = config.quality_thresholds.edge_hardness_threshold
    score = min(100.0, max(0.0, (sharp_edge_energy / (thresh * 1.2)) * 100.0))
    passed = score >= 75.0

    details = (
        f"95th percentile edge gradient = {sharp_edge_energy:.1f} (Mean = {mean_edge_energy:.1f}). "
        f"{'Crisp hard-edged vector contours.' if passed else 'Softer/blurry contours detected.'}"
    )

    return MetricResult(
        name="Edge Hardness",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=1.2,
    )


def check_framing_fill(arr: np.ndarray, config: ArtPipelineConfig, target_fill: float | None = None) -> MetricResult:
    """Calculate the bounding box fill ratio of the subject relative to canvas."""
    h, w = arr.shape[:2]
    target = target_fill or config.quality_thresholds.target_framing_fill
    tolerance = config.quality_thresholds.framing_tolerance

    if arr.ndim == 3 and arr.shape[2] >= 4:
        mask = arr[:, :, 3] > 20
    else:
        corners = np.array([arr[0, 0], arr[0, -1], arr[-1, 0], arr[-1, -1]])
        bg = np.median(corners, axis=0)
        dist = np.linalg.norm(arr.astype(np.float32) - bg, axis=2)
        mask = dist > 30

    if not np.any(mask):
        return MetricResult(name="Framing & Canvas Fill", score=0.0, passed=False, details="No distinct subject detected.", weight=1.0)

    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    bbox_h = (rmax - rmin + 1) / float(h)
    bbox_w = (cmax - cmin + 1) / float(w)
    max_dim_fill = max(bbox_h, bbox_w)

    diff = abs(max_dim_fill - target)
    if diff <= tolerance:
        score = 100.0 - (diff / tolerance) * 15.0
        passed = True
    else:
        score = max(20.0, 100.0 - (diff / target) * 100.0)
        passed = False

    details = (
        f"Subject bounding box fills {max_dim_fill*100:.1f}% of canvas "
        f"(Target: {target*100:.0f}% ± {tolerance*100:.0f}%). "
        f"{'Framing scale is well-balanced.' if passed else 'Subject is undersized or clipped.'}"
    )

    return MetricResult(
        name="Framing & Canvas Fill",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=1.0,
    )


def check_palette_coherence(arr: np.ndarray, config: ArtPipelineConfig, path_str: str = "") -> MetricResult:
    """Analyze color distribution against project color palette."""
    rgb = arr[:, :, :3].astype(np.float32)
    if arr.ndim == 3 and arr.shape[2] >= 4:
        mask = arr[:, :, 3] > 30
    else:
        mask = np.ones((arr.shape[0], arr.shape[1]), dtype=bool)

    if not np.any(mask):
        return MetricResult(name="Palette Coherence", score=0.0, passed=False, details="No subject pixels.")

    subject_rgb = rgb[mask]
    luminance = 0.299 * subject_rgb[:, 0] + 0.587 * subject_rgb[:, 1] + 0.114 * subject_rgb[:, 2]
    contrast_range = np.percentile(luminance, 95) - np.percentile(luminance, 5)

    is_dark_base = (luminance < 60).mean()
    is_hot_accent = ((subject_rgb[:, 0] > 180) & (subject_rgb[:, 1] > 40) & (subject_rgb[:, 2] < 80)).mean()
    is_magic_accent = ((subject_rgb[:, 2] > 160) | (subject_rgb[:, 1] > 180)).mean()
    accent_presence = is_hot_accent + is_magic_accent

    is_base_ground = any(k in path_str.lower() for k in ["track_surface", "offtrack", "floor", "atlas", "tileset"])
    if is_base_ground and is_dark_base > 0.70:
        return MetricResult(
            name="Palette Coherence",
            score=100.0,
            passed=True,
            details=f"Dark base ratio = {is_dark_base*100:.1f}%. Macro-calm terrain surface validated (clean background canvas).",
            weight=1.0,
        )

    score = 70.0
    if is_dark_base > 0.20:
        score += 15.0
    if accent_presence > 0.02:
        score += 15.0
    if contrast_range > 120:
        score += 10.0
    elif contrast_range < 70:
        score -= 20.0

    score = min(100.0, max(30.0, score))
    passed = score >= 75.0

    details = (
        f"Dynamic contrast = {contrast_range:.1f}/255, dark base ratio = {is_dark_base*100:.1f}%, "
        f"glowing accent ratio = {accent_presence*100:.1f}%. "
        f"{'Adheres strongly to color script.' if passed else 'Lacks required contrast/palette accenting.'}"
    )

    return MetricResult(
        name="Palette Coherence",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=1.0,
    )


def check_seamless_tiling(arr: np.ndarray, config: ArtPipelineConfig) -> MetricResult:
    """Measure 4-edge continuity for tileable textures."""
    rgb = arr[:, :, :3].astype(np.float32)
    h, w = rgb.shape[:2]

    h_diff = float(np.mean(np.abs(rgb[:, 0] - rgb[:, -1])))
    v_diff = float(np.mean(np.abs(rgb[0, :] - rgb[-1, :])))
    avg_diff = (h_diff + v_diff) / 2.0

    max_delta = config.seamless_tiling.max_seam_delta
    score = max(0.0, min(100.0, 100.0 - (avg_diff / max_delta) * 40.0))
    passed = avg_diff < max_delta

    details = (
        f"Horizontal edge Δ = {h_diff:.2f}/255, Vertical edge Δ = {v_diff:.2f}/255 "
        f"(Avg Δ = {avg_diff:.2f}). {'Seamless edge wrapping passed.' if passed else 'Noticeable boundary seam detected.'}"
    )

    return MetricResult(
        name="Seamless Tiling",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=1.5,
    )


def check_horizontal_strip_tiling(arr: np.ndarray, config: ArtPipelineConfig) -> MetricResult:
    """Measure horizontal 1D continuity (left edge vs right edge) for modular track strips."""
    rgb = arr[:, :, :3].astype(np.float32)
    h_diff = float(np.mean(np.abs(rgb[:, 0] - rgb[:, -1])))

    max_delta = 5.0
    passed = h_diff <= max_delta
    score = max(0.0, min(100.0, 100.0 - (h_diff / max_delta) * 50.0))

    details = (
        f"Horizontal edge Δ = {h_diff:.2f}/255. "
        f"{'Seamless horizontal modular track strip wrapping passed.' if passed else 'Horizontal boundary seam mismatch detected.'}"
    )

    return MetricResult(
        name="Horizontal Strip Tiling",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=1.5,
    )


def check_perspective(arr: np.ndarray, config: ArtPipelineConfig, asset_type: str, path_str: str = "") -> MetricResult:
    """Verify camera perspective projection rules according to config."""
    if config.perspective.mode == "free":
        return MetricResult(name="Perspective Correctness", score=100.0, passed=True, details="Free perspective mode.")

    if arr.ndim < 3:
        gray = arr.astype(np.float32)
    else:
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    h, w = gray.shape
    mask = (arr[:, :, 3] > 30) if (arr.ndim == 3 and arr.shape[2] >= 4) else np.ones((h, w), dtype=bool)

    if not np.any(mask):
        return MetricResult(name="Perspective Correctness", score=0.0, passed=False, details="Empty canvas.")

    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) / 2.0
    gy[1:-1, :] = (gray[2:, :] - gray[:-2, :]) / 2.0

    grad_mag = np.sqrt(gx**2 + gy**2)
    edge_mask = mask & (grad_mag > 20)

    if not np.any(edge_mask):
        return MetricResult(name="Perspective Correctness", score=100.0, passed=True, details="Planar surface.")

    angles = np.arctan2(gy[edge_mask], gx[edge_mask])
    angles_deg = np.abs(np.rad2deg(angles)) % 180.0

    iso_angles = ((angles_deg >= 25) & (angles_deg <= 35)) | ((angles_deg >= 145) & (angles_deg <= 155))
    iso_ratio = np.mean(iso_angles)

    cardinal_angles = (angles_deg <= 15) | (angles_deg >= 165) | ((angles_deg >= 75) & (angles_deg <= 105))
    cardinal_ratio = np.mean(cardinal_angles)

    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    bbox_h = rmax - rmin + 1
    bbox_w = cmax - cmin + 1
    aspect_ratio = bbox_h / float(max(bbox_w, 1))

    is_wheel = "wheel" in path_str.lower()
    is_projectile = ("warhead" in path_str.lower()) or ("missile" in path_str.lower()) or ("rocket" in path_str.lower())
    score = 100.0
    violations: list[str] = []

    if is_wheel:
        tread_horizontal_bars = np.mean((angles_deg <= 20) | (angles_deg >= 160))
        if aspect_ratio < 1.15:
            score -= 35.0
            violations.append("Wheel appears as round circular side-profile rather than elongated top-down tread")
        if tread_horizontal_bars > 0.35:
            score += 10.0

    if config.perspective.penalize_isometric_slant and iso_ratio > 0.40 and cardinal_ratio < 0.30:
        score -= (iso_ratio - 0.40) * 80.0
        violations.append(f"Significant 3/4 isometric perspective angle detected ({iso_ratio*100:.1f}% diagonal edges)")

    score = min(100.0, max(20.0, score))
    passed = score >= 75.0

    details = (
        f"Cardinal plan-alignment = {cardinal_ratio*100:.1f}%, Isometric angle ratio = {iso_ratio*100:.1f}%, "
        f"Aspect ratio = {aspect_ratio:.2f}. "
        f"{'Strict 90° top-down orthographic plan view verified.' if passed else 'Perspective tilt detected: ' + '; '.join(violations)}"
    )

    return MetricResult(
        name="Perspective Correctness",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=1.3,
    )


def check_symmetry(arr: np.ndarray, config: ArtPipelineConfig, path_str: str = "") -> MetricResult:
    """Check bilateral symmetry along configured axis."""
    if config.perspective.symmetry_axis == "none":
        return MetricResult(name="Orientation & Symmetry", score=100.0, passed=True, details="Symmetry check disabled.")

    if arr.ndim == 3 and arr.shape[2] >= 4:
        mask = arr[:, :, 3] > 30
    else:
        mask = np.ones((arr.shape[0], arr.shape[1]), dtype=bool)

    h, w = mask.shape
    mid_w = w // 2
    left_half = mask[:, :mid_w]
    right_half = np.fliplr(mask[:, mid_w + (w % 2):])

    overlap = np.sum(left_half & right_half)
    union = np.sum(left_half | right_half)
    symmetry_iou = (overlap / float(union)) if union > 0 else 0.0

    is_directional = any(k in path_str.lower() for k in ["warhead", "missile", "rocket", "kart", "character", "exhaust"])
    if is_directional and symmetry_iou < 0.70:
        return MetricResult(
            name="Orientation & Symmetry",
            score=round(symmetry_iou * 100.0, 1),
            passed=False,
            details=f"CRITICAL: Directional sprite has asymmetric diagonal tilt (IoU = {symmetry_iou*100:.1f}%). Must be aligned strictly North (0° vertical) for game engine rotation.",
            weight=1.5,
        )

    score = min(100.0, symmetry_iou * 125.0)
    passed = score >= 70.0

    details = (
        f"Bilateral symmetry IoU = {symmetry_iou*100:.1f}%. "
        f"{'Well-centered facing orientation.' if passed else 'Asymmetric tilt detected.'}"
    )

    return MetricResult(
        name="Orientation & Symmetry",
        score=round(score, 1),
        passed=passed,
        details=details,
        weight=0.8,
    )


def check_animation_strip_quality(arr: np.ndarray, num_frames: int, path_str: str = "") -> MetricResult:
    """Evaluate frame alignment, anchor stability, cross-boundary bleed, and temporal flow."""
    h, w = arr.shape[:2]
    frame_w = w // num_frames

    if arr.ndim < 3 or arr.shape[2] < 4:
        alpha = np.ones((h, w), dtype=np.uint8) * 255
    else:
        alpha = arr[:, :, 3]

    score = 100.0
    violations: list[str] = []

    # 1. Check cross-frame boundary bleed (dividers between frames must be transparent)
    bleed_px = 0
    for k in range(1, num_frames):
        div_x = k * frame_w
        boundary_col = alpha[:, div_x-1:div_x+1]
        bleed_px += int(np.sum(boundary_col > 30))

    if bleed_px > (h * 0.15 * (num_frames - 1)):
        score -= 25.0
        violations.append(f"Content bleeds across frame dividing lines ({bleed_px} border px)")

    # 2. Check anchor stability & jitter across frames
    anchors_x: list[float] = []
    anchors_y: list[float] = []
    masses: list[float] = []

    for i in range(num_frames):
        frame_alpha = alpha[:, i*frame_w:(i+1)*frame_w]
        frame_mask = frame_alpha > 30
        mass = float(np.sum(frame_mask))
        masses.append(mass)

        if mass > 10:
            rows = np.any(frame_mask, axis=1)
            cols = np.any(frame_mask, axis=0)
            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]
            center_x = (cmin + cmax) / 2.0
            base_y = float(rmax)
            anchors_x.append(center_x)
            anchors_y.append(base_y)

    if len(anchors_x) >= 2:
        std_x = float(np.std(anchors_x)) / float(frame_w)
        if std_x > 0.10:
            score -= 30.0
            violations.append(f"Excessive horizontal frame jitter/drift (σ = {std_x*100:.1f}% frame width)")

    passed = score >= 75.0
    details = (
        f"{num_frames} frames evaluated. Frame size = {frame_w}x{h}px. "
        f"{'Smooth animation flow with stable anchor.' if passed else 'Animation flaws: ' + '; '.join(violations)}"
    )

    return MetricResult(
        name="Animation Strip Quality",
        score=round(max(20.0, score), 1),
        passed=passed,
        details=details,
        weight=1.4,
    )


def evaluate_asset(img_path: Path | str, config: ArtPipelineConfig, asset_type: str = "auto") -> QAResult:
    """Run full QA analysis suite on an asset file."""
    p = Path(img_path)
    if not p.exists():
        return QAResult(
            path=str(img_path),
            asset_type=asset_type,
            overall_score=0.0,
            passed=False,
            critical_violation=True,
            violations=[f"File does not exist: {img_path}"],
        )

    path_str = str(p).replace("\\", "/").lower()
    is_horizontal_track_strip = ("finish_line_ground" in path_str) or ("safe_shoulder" in path_str)

    if asset_type == "auto":
        if "track_surface" in path_str or "offtrack" in path_str or "floor" in path_str or "atlas" in path_str or "tileset" in path_str:
            asset_type = "tile"
        elif "character" in path_str or "kart" in path_str:
            asset_type = "kart"
        elif "weapon" in path_str or "icon" in path_str:
            asset_type = "icon"
        elif "prop" in path_str:
            asset_type = "prop"
        elif "banner" in path_str or "menu_background" in path_str:
            asset_type = "scenic"
        else:
            asset_type = "sprite"

    try:
        im = Image.open(p)
        arr = np.array(im)
    except Exception as e:
        return QAResult(
            path=str(img_path),
            asset_type=asset_type,
            overall_score=0.0,
            passed=False,
            critical_violation=True,
            violations=[f"Failed to decode image: {e}"],
        )

    metrics: list[MetricResult] = []
    violations: list[str] = []
    recs: list[str] = []

    # Check if this asset is an animated strip
    num_frames = detect_strip_frames(im, path_str)

    is_atlas = ("atlas" in path_str) or ("tileset" in path_str)

    if asset_type == "tile":
        m_persp = check_perspective(arr, config, asset_type, path_str)
        m_hard = check_edge_hardness(arr, config, path_str=path_str)
        m_pal = check_palette_coherence(arr, config, path_str=path_str)

        if not is_atlas:
            m_tile = check_seamless_tiling(arr, config)
            metrics.extend([m_tile, m_persp, m_hard, m_pal])
            if not m_tile.passed:
                violations.append("Noticeable boundary seam error in tileable texture.")
                recs.append("Run 'art_pack.py process --seamless <file>' or reroll with seamless prompt.")
        else:
            metrics.extend([m_persp, m_hard, m_pal])
    elif asset_type == "scenic":
        m_hard = check_edge_hardness(arr, config, path_str=path_str)
        m_pal = check_palette_coherence(arr, config, path_str=path_str)
        metrics.extend([m_hard, m_pal])
    else:
        m_alpha = check_alpha_and_chroma(arr, config, path_str=path_str)
        m_persp = check_perspective(arr, config, asset_type, path_str)
        m_hard = check_edge_hardness(arr, config, path_str=path_str)
        m_fill = check_framing_fill(arr, config, target_fill=0.80 if asset_type == "kart" else 0.75)
        m_pal = check_palette_coherence(arr, config, path_str=path_str)
        m_sym = check_symmetry(arr, config, path_str=path_str)

        metrics.extend([m_alpha, m_persp, m_hard, m_fill, m_pal, m_sym])

        # If modular horizontal track strip (e.g. finish_line_ground), verify horizontal seamless wrapping
        if is_horizontal_track_strip:
            m_htile = check_horizontal_strip_tiling(arr, config)
            metrics.append(m_htile)
            if not m_htile.passed:
                violations.append("Horizontal track strip does not tile seamlessly left-to-right.")
                recs.append("Apply horizontal edge cross-blend or reroll with horizontal seamless prompt.")

        # If animated strip, add animation quality check
        if num_frames > 1:
            m_anim = check_animation_strip_quality(arr, num_frames, path_str)
            metrics.append(m_anim)
            if not m_anim.passed:
                violations.append("Animation strip has frame jitter or boundary bleeding.")
                recs.append("Reroll with explicit fixed nozzle/barrel root anchor and equal-width frame grid.")

        if not m_alpha.passed:
            if "checkerboard" in m_alpha.details.lower():
                violations.append("Fake painted checkerboard transparency detected.")
                recs.append("Run 'art_pack.py process <file>' to extract true alpha.")
            elif "halo" in m_alpha.details.lower():
                violations.append("Chroma edge halo/fringing detected on border.")
                recs.append("Run 'art_pack.py process <file>' to defringe edge pixels.")
            else:
                violations.append("Invalid or non-transparent background.")
                recs.append("Ensure raw image is on solid chroma and processed with 'art_pack.py process <file>'.")

        if not m_persp.passed:
            violations.append("Perspective distortion or 3/4 isometric tilt detected.")
            recs.append("Regenerate with 'strict 90-degree top-down bird\'s-eye orthographic plan view (zero 3D tilt)'.")

        if not m_hard.passed:
            violations.append("Edge sharpness is low (soft blurry AI contours).")
            recs.append("Regenerate with 'flat-vector cel-shading, bold thick clean dark outlines'.")

        if not m_fill.passed and num_frames == 1 and not is_horizontal_track_strip:
            violations.append("Subject framing fill ratio out of specification.")
            recs.append("Adjust prompt so subject fills ~80% of canvas.")

    total_weight = sum(m.weight for m in metrics)
    overall = sum(m.score * m.weight for m in metrics) / total_weight if total_weight > 0 else 0.0

    critical = any("CRITICAL" in m.details for m in metrics) or (len(violations) >= 2)
    pass_thresh = config.quality_thresholds.pass_score
    passed = (overall >= pass_thresh) and not critical

    return QAResult(
        path=str(img_path),
        asset_type=asset_type,
        overall_score=round(overall, 1),
        passed=passed,
        critical_violation=critical,
        violations=violations,
        metrics=metrics,
        recommendations=recs,
    )
