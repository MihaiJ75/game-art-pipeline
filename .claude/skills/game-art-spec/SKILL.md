---
name: game-art-spec
description: Architect, structure, and generate production-grade 2D Game Art Specifications, milestone tiers, and deterministic generative prompts from Game Design Documents (GDDs), game mechanics, or art style references. Use when starting a new game, defining new characters, weapons, terrain, props, or UI, or structuring art roadmaps for AI image generation. Triggers: 'create art spec', 'write art prompts', 'generate art roadmap', 'plan game assets', 'asset specification'.
---

# Game Art Specification & Prompt Architecture Skill

This skill guides AI agents in converting Game Design Documents (GDDs) and game concepts into **deterministic, production-ready Game Art Specifications** (`specs/art-prompts.md`) and milestone roadmaps (`art-source/tiers.json`).

---

## 1. Core Principles of Game Art Specification

1. **Deterministic Style Anchoring**:
   - Every prompt pack MUST begin with a **Tier 0 Master Style Reference** (`art-source/reference/master_style_reference.png`) defining the visual DNA (color script, cel-shading weight, lighting, mood).
   - All downstream prompts MUST open with: `"Using the attached master style reference, generate..."`.

2. **Strict Camera Perspective Locking**:
   - Explicitly specify the exact camera angle to eliminate 3D isometric hallucinations:
     - **Top-Down 2D**: `"strict 90-degree perpendicular top-down bird's-eye plan view, zero perspective tilt, zero 3D vanishing lines"`.
     - **Side-Scroller / Platformer**: `"strict 90-degree true side-scroller orthographic profile view, facing East/right, flat horizontal ground plane"`.
     - **Isometric**: `"strict 2:1 dimetric isometric view (true 26.565° camera angle)"`.

3. **Solid Chroma Isolation Backdrop**:
   - NEVER request a "transparent background" in generative prompts (causes fake checkered pattern hallucinations).
   - ALWAYS specify: `"isolated on a solid flat pure magenta #FF00FF background with razor-sharp edges, zero ground shadow"`.

4. **Modular Layered Component Decomposition**:
   - **Verticality (Z-Index)**: Objects characters pass *under* (bridges, gates, arches) MUST be split into `<name>_ground.png` (Z < 0) and `<name>_overhead.png` (Z > 0 with transparent archway).
   - **Modular Nodes**: Dynamic or rotating parts (wheels, turrets, weapons) MUST NOT be drawn on the base body. Specify empty sockets/wells with bare mounting hubs.
   - **Unbaked VFX**: Continuous effects (thruster fire, muzzle flash, glowing hazard auras) MUST be specified as separate sprite overlay nodes or sequential animation strips.

5. **Anti-Hallucination Framing & Padding**:
   - Specify canvas fill and margins: `"The entire subject is comfortably contained within the central 75% of the frame with generous margins on all four sides (no element touches the canvas border)..."`.

---

## 2. Specification File Templates

### A. The Master Prompt Pack (`specs/art-prompts.md`)
Organize assets by category with explicit IDs, relative paths, and fenced prompt blocks:

```markdown
# [GAME_NAME] Art Specification & Prompt Pack

## 1. Master Style Anchor
### 1.1 Master Style Reference
**Path:** `art-source/reference/master_style_reference.png`
```
[Prompt text]
```

## 2. Characters & Entities
### 2.1 Player Character
**Path:** `res://assets/sprites/player/hero.png`
```
[Prompt text]
```
```

### B. The Milestone Tiers Roadmap (`art-source/tiers.json`)
```json
{
  "style_reference": "art-source/reference/master_style_reference.png",
  "tiers": {
    "t0-style": {
      "name": "Master Style Anchor",
      "gate": "Hard gate for all downstream generation.",
      "blocks_everything": true,
      "assets": ["art-source/reference/master_style_reference.png"]
    },
    "t1-prototype": {
      "name": "Core Playable Prototype",
      "gate": "Minimum assets required for playable build.",
      "assets": [
        "res://assets/sprites/player/hero.png",
        "res://assets/sprites/environment/ground.png"
      ]
    }
  }
}
```

---

## 3. Workflow for Creating a New Art Spec

1. Analyze the Game Design Document to list all required visual entities.
2. Define the Master Style Reference prompt capturing the core aesthetic.
3. Write modular, perspective-locked prompts for all characters, terrain, weapons, and UI.
4. Structure the assets into dependency tiers (`t0-style`, `t1-prototype`, `t2-vertical-slice`, etc.) in `tiers.json`.
5. Run `python art_pack.py audit` to verify 100% prompt-path consistency before generation.
