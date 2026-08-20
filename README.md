# 🎨 Game Art Pipeline & Computer Vision QA Engine

[![CI](https://github.com/MihaiJ75/game-art-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/MihaiJ75/game-art-pipeline/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Engine: Godot 4](https://img.shields.io/badge/Godot-4.x-478CBF?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Engine: Unity](https://img.shields.io/badge/Unity-2D-000000?logo=unity&logoColor=white)](https://unity.com/)
[![AI: Claude Code & Gemini](https://img.shields.io/badge/AI-Claude%20Code%20%7C%20Gemini-7B2CBF)](https://claude.ai)

> **The production-grade, zero-dependency 2D game asset engine for autonomous AI agents and technical artists.**  
> Engineer game art specs from GDDs, orchestrate generative image models with style consistency, strip chroma backgrounds with flood-fill defringing, and validate game sprites with quantitative Computer Vision quality assurance.

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

## 🤖 Inter-Agent & Multi-Model Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    1. SPEC ENGINEERING                      │
│   (Claude Code / Antigravity via 'game-art-spec' skill)     │
│   • Reads Game Design Doc & Camera Perspectives             │
│   • Writes specs/art-prompts.md & art-source/tiers.json     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    2. IMAGE GENERATION                      │
│        (Gemini 3.7 / Antigravity / Midjourney / SDXL)       │
│   • Generates on solid #FF00FF magenta chroma               │
│   • Conditioned on art-source/master_style_reference.png    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 3. AUTOMATED POST-PROCESSING                │
│                   (art_pack.py process)                     │
│   • Sub-pixel chroma cutout & interior pocket excision      │
│   • Exterior flood-fill defringing & unsharp masking        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 4. COMPUTER VISION QA GATE                  │
│                     (art_qa.py score)                       │
│   • Transparency, Perspective, Edges, Fill, Palette, Sym    │
│   • Pass (>=85%) -> SHA-256 Ledger & HTML Dashboard         │
│   • Fail (<85%)  -> Smart Prompt Refinement Recommendations │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ CLI Command Cheatsheet

| Command | Purpose |
| :--- | :--- |
| `python art_pack.py audit` | Audit prompt specs vs milestone tiers vs disk files |
| `python art_pack.py status` | Show roadmap milestone completion percentages |
| `python art_pack.py order <tier\|path>` | Output exact prompts and context attachments |
| `python art_pack.py process <file>` | Clean alpha, excise chroma, defringe, and sharpen |
| `python art_pack.py process <file> --seamless` | Apply 4-edge cosine cross-blending for textures |
| `python art_pack.py test-tile <file>` | Measure seam delta & output 2x2 preview |
| `python art_qa.py score <file>` | Run 6-metric Computer Vision QA evaluation |
| `python art_pack.py qa` | Batch evaluate entire project & render HTML dashboard |
| `python art_pack.py record <file>` | Record prompt SHA-256 fingerprint in ledger |

---

## 📁 Repository Structure

```
├── .claude/skills/
│   ├── game-art-spec/SKILL.md      # Skill: Prompt pack architecture
│   └── game-art-pipeline/SKILL.md  # Skill: Execution & QA workflows
├── engine/                         # Core Python CV Engine
│   ├── processor.py                # Chroma & seamless processing
│   ├── qa_evaluator.py             # 6-Metric Computer Vision QA
│   ├── reporter.py                 # HTML dashboard & markdown reporter
│   ├── ledger.py                   # SHA-256 prompt hashing
│   ├── work_order.py               # Tier milestone scheduling
│   ├── strips.py                   # Animation strip slicing
│   ├── palette.py                  # Dynamic theme recoloring
│   └── godot.py                    # Engine import presets & atlas packer
├── templates/                      # Ready-to-use config & spec templates
├── tests/                          # Automated unit test suite
├── art_pack.py                     # Main CLI entrypoint
├── art_qa.py                       # Standalone QA entrypoint
├── pyproject.toml                  # Python package configuration
└── LICENSE                         # MIT License
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

## 🌟 Star & Support

If you find this pipeline useful for your game development or AI workflows, give the repo a ⭐! Contributions and PRs are welcome.
