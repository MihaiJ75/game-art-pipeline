# 🎨 Game Art Pipeline & Computer Vision QA Engine

[![CI](https://github.com/MihaiJ75/game-art-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/MihaiJ75/game-art-pipeline/actions/workflows/ci.yml)
[![AI: Google Gemini 3.7](https://img.shields.io/badge/Optimized%20for-Google%20Gemini%203.7%20Flash%20Image-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![AI: Claude Code](https://img.shields.io/badge/Orchestrated%20with-Claude%20Code%20%7C%20Antigravity-7B2CBF)](https://claude.ai)
[![SEO: NanoBanana](https://img.shields.io/badge/SEO-nanobanana-yellow.svg)](https://github.com/MihaiJ75/game-art-pipeline)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Engine: Godot 4](https://img.shields.io/badge/Godot-4.x-478CBF?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Engine: Unity](https://img.shields.io/badge/Unity-2D-000000?logo=unity&logoColor=white)](https://unity.com/)

> **The production-grade 2D game asset engine specifically optimized for Google Gemini 3.7 Flash Image, Claude Code, NanoBanana, and autonomous AI agents.**  
> Engineer game art specs from GDDs, orchestrate generative vision models with style consistency, strip chroma backgrounds with flood-fill defringing, and validate game sprites with quantitative Computer Vision quality assurance.

---

## 🧠 How the Image Generation Architecture Works (Deep Dive)

Standard generative AI models often fail in game development pipelines because they hallucinate fake checkered transparency grids, cast unwanted ground shadows, tilt cameras into 3D isometric angles, and produce inconsistent art styles between assets.

This engine solves these problems through a **5-stage deterministic workflow**:

```
 1. STYLE ANCHORING       2. DETERMINISTIC PROMPT        3. GEMINI 3.7 GENERATION
┌──────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│ master_style_    │ ──> │ Prompt includes spatial│ ──> │ Generates raw 1024x1024│
│ reference.png    │     │ anchors, negative space│     │ on pure #FF00FF magenta│
└──────────────────┘     └────────────────────────┘     └───────────┬────────────┘
                                                                    │
 5. COMPUTER VISION QA    4. SUB-PIXEL PROCESSING                   │
┌──────────────────┐     ┌────────────────────────┐                 │
│ Scores 6 metrics │ <── │ Chroma cutout, defringe│ <───────────────┘
│ (Trans, Persp,   │     │ halo, Lanczos unsharp  │
│  Edges, Palette) │     │ downscaling (48x48)    │
└──────────────────┘     └────────────────────────┘
```

### Stage 1: Multimodal Style Reference Conditioning
Instead of relying on unstable text style keywords (e.g. "cyberpunk", "cel-shaded"), we generate **one** Master Style Sheet (`master_style_reference.png`) at Tier 0. Every subsequent generation call passes this image directly into Gemini 3.7's visual context window, ensuring identical outline weights, color saturation, and lighting across all sprites.

### Stage 2: Pure Chroma Isolation (No Fake Checkerboards)
Prompting generative AI for a "transparent background" frequently causes the AI to literally paint grey-and-white checkerboard squares into the sprite pixels. We force the AI to paint on a flat, solid, high-contrast `#FF00FF` magenta chroma backdrop with zero contact ground shadows.

### Stage 3: Spatial Coordinate Anchors (True North Heading)
In 2D game engines (Godot, Unity), directional sprites must point along a strict cardinal axis (typically North / $-Y$). Prompts specify strict coordinate landmarks:
- **TOP EDGE**: Front nosecone, front bumper, headlights.
- **CENTER**: Cockpit and driver facing upward.
- **BOTTOM EDGE**: Rear engine bay, exhaust pipes, spoiler.

### Stage 4: Negative Space & Modular Sockets
For game entities with moving sub-nodes (e.g. rotatable wheels, weapon turrets, animated booster flames), prompts explicitly demand empty cutouts with bare axle hubs, forbidding the model from baking in static wheels or permanent VFX.

### Stage 5: Sub-Pixel Defringing & Computer Vision QA
The raw generative image is passed to `art_pack.py process`:
- **Chroma Excision**: Calculates Euclidean color distance to strip magenta backdrops and interior cavities.
- **Defringing**: Uses boundary flood-fill to strip optical bloom spill without washing out intended purples or magentas.
- **Lanczos Downsampling & Unsharp Masking**: Downsamples to gameplay target (e.g. 1024x1024 → 48x48) while preserving sharp, hard-edged vector contours.
- **CV QA Evaluator**: Automatically scores the sprite across 6 quantitative metrics (Transparency, Perspective, Edge Hardness, Canvas Fill, Palette Coherence, Symmetry).

---

## ⚡ Key Highlights

- 📐 **Spec Architect Skill (`game-art-spec`)**: Turn any Game Design Document into deterministic, hallucination-resistant prompt packs with locked camera perspectives (90° top-down, side-scroller, isometric), solid chroma backdrops, and modular Z-index decomposition.
- 🔮 **Chroma & Defringe Processor**: Automated sub-pixel chroma extraction (`#FF00FF` magenta, `#00FF00` green) with boundary flood-fill halo excision and exterior alpha cleaning.
- 👁️ **Computer Vision QA Gate**: 6-metric quantitative evaluation with zero heavy ML dependencies (pure NumPy + Pillow):
  1. **Transparency & Chroma Purity** (0% halo spill)
  2. **Perspective Correctness** (Orthographic plan-alignment & tilt detection)
  3. **Cel-Shaded Edge Hardness** (95th-percentile gradient analysis)
  4. **Framing & Canvas Fill** (Target fill ratio & margin padding)
  5. **Palette Coherence** (Color script adherence & dynamic contrast)
  6. **Bilateral Symmetry & Cardinal Orientation** (IoU symmetry testing)
- 🔁 **Seamless Tiling Synthesizer**: 4-edge cosine S-curve cross-blending producing mathematically flawless `0.00` edge seam deltas for tilemaps and textures.
- 🎞️ **Animation Strip Slicing**: Slices sequential horizontal sprite sheets with automatic frame jitter and cross-frame bleed penalties.
- 📊 **Interactive HTML Dashboard**: Self-contained visual scoreboard with sprite previews, zoom modals, and failure recommendations.
- 🎮 **Multi-Engine Exporters**: Auto-generates Godot 4 `.import` presets (`Nearest, Mipmaps OFF` / `Linear, Repeat`) and Unity `.meta` settings.

---

## 🚀 Quickstart (60 Seconds)

### 1. Install Requirements
```bash
pip install -r requirements.txt
```

### 2. Initialize in Any Project
Copy the engine and templates into your game repository:
```bash
cp -r game-art-pipeline/* /path/to/your/game/
```

### 3. Check Work Order & Audit Assets
```bash
# Check roadmap status and missing assets
python art_pack.py audit

# Fetch next generation work order
python art_pack.py order next
```

### 4. Process Raw Art & Run Computer Vision QA
```bash
# Process raw generative image (cutout, defringe, unsharp mask)
python art_pack.py process assets/sprites/characters/hero.png

# Run CV QA scoring
python art_qa.py score assets/sprites/characters/hero.png

# Update the interactive HTML dashboard
python art_pack.py qa
```

---

## 🛠️ CLI Command Cheatsheet

| Command | Purpose |
| :--- | :--- |
| `python art_pack.py audit` | Audit prompt specs vs milestone tiers vs disk files |
| `python art_pack.py status` | Show roadmap milestone completion percentages |
| `python art_pack.py order <tier|path>` | Output exact prompts and context attachments |
| `python art_pack.py process <file>` | Clean alpha, excise chroma, defringe, and sharpen |
| `python art_pack.py process <file> --seamless` | Apply 4-edge cosine cross-blending for textures |
| `python art_pack.py test-tile <file>` | Measure seam delta & output 2x2 preview |
| `python art_qa.py score <file>` | Run 6-metric Computer Vision QA evaluation |
| `python art_pack.py qa` | Batch evaluate entire project & render HTML dashboard |
| `python art_pack.py record <file>` | Record prompt SHA-256 fingerprint in ledger |

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
