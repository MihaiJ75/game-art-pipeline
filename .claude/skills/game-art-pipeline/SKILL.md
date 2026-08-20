---
name: game-art-pipeline
description: Generate, process, verify, and track 2D/2.5D game assets using the modular Art Pipeline Engine. Use whenever art, sprites, textures, icons, weapons, tracks, or UI elements are needed for any game - to check missing assets, process generated raw images into clean 32-bit RGBA sprites, run Computer Vision QA scoring, and export to Godot, Unity, or Texture Atlases. Triggers: 'generate art', 'process sprites', 'run art qa', 'evaluate sprite quality', 'next art tier', 'missing assets'.
---

# Generic Game Art Pipeline & Computer Vision QA Engine

A modular, configuration-driven pipeline for generating, post-processing, and rigorously validating 2D game assets using quantitative Computer Vision metrics.

---

## 1. Core Invariants & Rules

1. **Always Attach the Style Reference**: Attach `art-source/reference/master_style_reference.png` as context to every generation call.
2. **Solid Pure Chroma Backdrop**: Always generate against flat `#FF00FF` magenta (or configured chroma color).
3. **Oversampling & Sharpening**: Generate at high resolution (1024x1024), downscale to gameplay target with Lanczos + unsharp masking.
4. **Clean 32-Bit RGBA Alpha**: Run `python art_pack.py process <path>` for automated chroma cutout and exterior flood-fill defringing.
5. **QA Scoring Threshold**: Every asset must achieve a QA score >= 85.0/100 and pass all critical invariant checks.
6. **Strict Quota Policy (Zero Geometric Substitutes)**: When image generation rate limits (`429 RESOURCE_EXHAUSTED`) are reached, NEVER generate simplistic code drawings. Stop, report the exact reset timestamp, and pause until quota resets.

---

## 2. Standard Commands Reference

```bash
# 1. Fetch work order for next milestone tier
python art_pack.py order next

# 2. Post-process sprite (alpha cutout, defringing, unsharp mask)
python art_pack.py process <path>

# 3. Post-process seamless tileable texture (4-edge margin cross-blend)
python art_pack.py process <path> --seamless

# 4. Measure tiling seam delta (0.00 is target)
python art_pack.py test-tile <path> --save-preview

# 5. Evaluate asset with Computer Vision QA
python art_qa.py score <path>

# 6. Batch QA evaluation & update interactive HTML dashboard
python art_pack.py qa

# 7. Record asset fingerprint to ledger
python art_pack.py record <path>

# 8. Audit prompt pack completeness vs disk vs ledger
python art_pack.py audit
```

---

## 3. End-to-End Asset Generation Workflow

For each asset in the work order:
1. **Generate**: Call image generation with the exact prompt from the spec and attach `master_style_reference.png`.
   - *If 429 quota limit is encountered*: STOP immediately and report the reset timestamp.
2. **Process**: Run `python art_pack.py process <path>` (add `--seamless` for tileable textures).
3. **Score**: Run `python art_qa.py score <path>`.
   - If Score < 85%, check the recommendations and refine the prompt.
4. **Record**: Run `python art_pack.py record <path>`.
5. **Dashboard**: Run `python art_pack.py qa` to refresh `art-source/qa_report.html`.
