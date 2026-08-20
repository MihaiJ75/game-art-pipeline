"""Godot 4 .import Preset Automation & Texture Atlas Generator."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

try:
    from PIL import Image
except ImportError:
    pass

from .config import ArtPipelineConfig


GODOT_SPRITE_IMPORT_TEMPLATE = """[remap]

importer="texture"
type="CompressedTexture2D"
uid="uid://helldrift_{stem}"
path="res://.godot/imported/{filename}-{stem}.ctex"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://{rel_path}"
dest_files=["res://.godot/imported/{filename}-{stem}.ctex"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=false
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=1
svg/scale=1.0
editor/scale_with_editor_scale=false
editor/convert_colors_with_editor_theme=false
flags/filter=false
"""

GODOT_TEXTURE_IMPORT_TEMPLATE = """[remap]

importer="texture"
type="CompressedTexture2D"
uid="uid://helldrift_{stem}"
path="res://.godot/imported/{filename}-{stem}.ctex"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://{rel_path}"
dest_files=["res://.godot/imported/{filename}-{stem}.ctex"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=1
svg/scale=1.0
editor/scale_with_editor_scale=false
editor/convert_colors_with_editor_theme=false
flags/filter=true
flags/repeat=1
"""


def generate_godot_import(png_path: Path, repo_root: Path | None = None, is_texture: bool = False) -> Path:
    """Generate or update Godot 4 .import file for an image asset."""
    import_file = png_path.parent / f"{png_path.name}.import"
    root = repo_root or png_path.parent
    try:
        rel_path = png_path.relative_to(root).as_posix()
    except Exception:
        rel_path = png_path.name

    template = GODOT_TEXTURE_IMPORT_TEMPLATE if is_texture else GODOT_SPRITE_IMPORT_TEMPLATE
    content = template.format(
        filename=png_path.name,
        stem=png_path.stem.replace("-", "_"),
        rel_path=rel_path,
    )
    import_file.write_text(content, encoding="utf-8")
    return import_file


def pack_texture_atlas(
    image_paths: Sequence[Path],
    output_png: Path,
    output_tres: Path | None = None,
    padding: int = 2,
    max_width: int = 1024,
) -> dict[str, tuple[int, int, int, int]]:
    """Pack multiple sprites into a texture atlas and generate Godot .tres resources."""
    images: list[tuple[str, Image.Image]] = []
    for p in sorted(image_paths):
        if p.exists() and p.suffix.lower() == ".png":
            images.append((p.stem, Image.open(p).convert("RGBA")))

    if not images:
        return {}

    # Sort images by height descending (Simple Shelf Packing)
    images.sort(key=lambda item: item[1].size[1], reverse=True)

    # Shelf packing algorithm
    shelves: list[dict] = []
    positions: dict[str, tuple[int, int, int, int]] = {}

    current_shelf_y = padding
    current_shelf_h = 0
    current_shelf_x = padding

    atlas_w = 0
    atlas_h = 0

    for name, im in images:
        w, h = im.size
        if (current_shelf_x + w + padding) > max_width and current_shelf_x > padding:
            # New shelf
            current_shelf_y += current_shelf_h + padding
            current_shelf_x = padding
            current_shelf_h = 0

        pos_x = current_shelf_x
        pos_y = current_shelf_y
        positions[name] = (pos_x, pos_y, w, h)

        current_shelf_x += w + padding
        current_shelf_h = max(current_shelf_h, h)

        atlas_w = max(atlas_w, current_shelf_x)
        atlas_h = max(atlas_h, current_shelf_y + current_shelf_h + padding)

    # Power of two dimensions
    pot_w = 2 ** math.ceil(math.log2(max(atlas_w, 32)))
    pot_h = 2 ** math.ceil(math.log2(max(atlas_h, 32)))

    atlas_im = Image.new("RGBA", (pot_w, pot_h), (0, 0, 0, 0))
    for name, im in images:
        x, y, w, h = positions[name]
        atlas_im.paste(im, (x, y), im)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    atlas_im.save(output_png, "PNG", optimize=True)

    # Generate Godot .tres if requested
    if output_tres:
        tres_lines = [
            '[gd_resource type="AtlasTexture" load_steps=2 format=3]',
            '',
            f'[ext_resource type="Texture2D" path="res://{output_png.as_posix()}" id="1_atlas"]',
            '',
            '[resource]',
            'atlas = ExtResource("1_atlas")',
        ]
        # First entry default
        if positions:
            first_name, (fx, fy, fw, fh) = next(iter(positions.items()))
            tres_lines.append(f'region = Rect2({fx}, {fy}, {fw}, {fh})')
        output_tres.write_text("\n".join(tres_lines) + "\n", encoding="utf-8")

    return positions
