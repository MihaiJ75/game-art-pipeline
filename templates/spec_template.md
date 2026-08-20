# Game Art Specification & Generation Prompts

This document is the single source of truth for all 2D game assets in the project.

---

## 1. Master Style Anchor

### 1.1 Master Style Reference Sheet
**Path:** `art-source/reference/master_style_reference.png`
```
Create a master concept art style reference sheet for [GAME_TITLE] depicting the overall visual DNA: [GENRE / THEME / COLOR_SCRIPT / LIGHTING_MOOD]. High contrast, bold cel-shaded vector game art, clean dark outlines, vibrant emissive accents, isolated on a solid flat pure magenta #FF00FF background.
```

---

## 2. Characters & Entities

- **Path pattern:** `res://assets/sprites/characters/<id>_<name>.png`
- **Tips:** 90° top-down / side-scroller orthographic view. Generate at 1024x1024, downscale in-engine. Frame filling ~75-80% with generous margins on all four sides.

### 2.1 Main Character
**Path:** `res://assets/sprites/characters/00_hero.png`
```
Using the attached master style reference, generate a strict [PERSPECTIVE: 90-degree top-down / side-view] illustration of [CHARACTER_DESCRIPTION]. [LANDMARKS & ANATOMY]. The entire character is comfortably contained within the central 75% of the frame with generous margins on all four sides (no element touches the canvas border). Flat vector cel-shaded comic-arcade game art, bold clean dark outlines, vibrant accent lighting. Isolated on a solid flat pure magenta #FF00FF background with sharp edges, zero ground shadow, no text, no watermark, no logos, no checkerboard pattern. Square image.
```

---

## 3. Environment & Terrain

### 3.1 Seamless Ground Surface
**Path:** `res://assets/sprites/environment/ground_surface.png`
```
Using the attached master style reference, generate a seamless tileable texture of [TERRAIN_DESCRIPTION] from a perpendicular 90-degree top-down bird's-eye view. Flat ground plane, smooth matte texture with fine micro-grain aggregate and zero high-contrast repeating landmarks. Flat vector cel-shaded arcade game art, no text, no watermark, perfectly square image.
```
