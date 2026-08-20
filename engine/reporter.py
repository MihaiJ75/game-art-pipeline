"""Interactive HTML and Markdown QA Dashboard Reporter with Filtering & Animations."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image

from .config import ArtPipelineConfig
from .qa_evaluator import QAResult
from .strips import detect_strip_frames, slice_strip, strip_to_animated_base64
from .optimizer import optimize_prompt


def image_to_base64_thumbnail(fs_path: Path, max_size: int = 140) -> str:
    """Read an image and convert it to a self-contained Base64 data URI."""
    try:
        im = Image.open(fs_path)
        im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"
    except Exception:
        return ""


def generate_html_report(results: list[QAResult], output_path: Path, config: ArtPipelineConfig) -> None:
    """Generate an interactive, zero-dependency visual HTML dashboard report."""
    total = len(results)
    passed_cnt = sum(1 for r in results if r.passed)
    failed_cnt = total - passed_cnt
    avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0.0

    cards_html = []
    for r in results:
        p = Path(r.path)
        status_badge = (
            '<span class="badge pass">PASSED</span>'
            if r.passed
            else '<span class="badge fail">NEEDS REROLL</span>'
        )

        metrics_html = "".join([
            f"""
            <div class="metric-row">
                <span class="metric-name">{m.name}</span>
                <div class="bar-bg"><div class="bar-fill {'green' if m.passed else 'red'}" style="width: {m.score}%"></div></div>
                <span class="metric-val">{m.score:.0f}%</span>
            </div>
            """
            for m in r.metrics
        ])

        violations_html = (
            "".join([f'<li class="violation-item">⚠️ {v}</li>' for v in r.violations])
            if r.violations
            else '<li class="clean-item">✅ Zero violations detected</li>'
        )

        recs_html = (
            "".join([f'<li class="rec-item">💡 {rec}</li>' for rec in r.recommendations])
            if r.recommendations
            else ""
        )

        # Check for animated strip
        fs_img = Path(r.path)
        if not fs_img.is_absolute():
            fs_img = output_path.parent.parent / fs_img

        animated_gif_html = ""
        b64_src = image_to_base64_thumbnail(fs_img)

        if fs_img.exists():
            try:
                raw_im = Image.open(fs_img)
                num_frames = detect_strip_frames(raw_im, r.path)
                if num_frames > 1:
                    gif_b64 = strip_to_animated_base64(raw_im, num_frames, duration_ms=120)
                    animated_gif_html = f"""
                    <div class="anim-badge">▶ {num_frames} FRAMES</div>
                    <img src="{gif_b64}" alt="Animated Preview" class="anim-preview-overlay" />
                    """
            except Exception:
                pass

        sample_prompt = f"Using style reference, generate 90-degree top-down {p.stem} on magenta #FF00FF backdrop."
        opt_prompt = optimize_prompt(sample_prompt, r, config).replace('"', '&quot;').replace("'", "\\'")

        reroll_button = (
            f"""<button class="btn-reroll" onclick="copyPrompt('{opt_prompt}')">📋 Copy Reroll Prompt</button>"""
            if not r.passed
            else ""
        )

        cards_html.append(f"""
        <div class="card {'card-pass' if r.passed else 'card-fail'}" data-category="{r.asset_type}" data-status="{'pass' if r.passed else 'fail'}">
            <div class="card-header">
                <h3>{p.name}</h3>
                <div class="header-right">
                    <span class="score-badge">{r.overall_score:.0f}/100</span>
                    {status_badge}
                </div>
            </div>
            <div class="card-body">
                <div class="img-preview-box">
                    <img src="{b64_src}" alt="{p.name}" class="preview-img" />
                    {animated_gif_html}
                    <span class="type-tag">{r.asset_type.upper()}</span>
                </div>
                <div class="card-details">
                    <div class="metrics-container">
                        {metrics_html}
                    </div>
                    <ul class="issues-list">
                        {violations_html}
                        {recs_html}
                    </ul>
                    <div class="card-actions">
                        {reroll_button}
                    </div>
                </div>
            </div>
        </div>
        """)

    cards_joined = "\n".join(cards_html)
    proj_name = config.project_name.upper()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{config.project_name} Art QA & Verification Report</title>
<style>
    :root {{
        --bg: #0F0F14;
        --card-bg: #1B1B24;
        --border: #2A2A38;
        --text: #E5E5EB;
        --text-muted: #8E8E9E;
        --accent-orange: #FF5500;
        --accent-green: #00FF66;
        --accent-purple: #9900FF;
        --accent-red: #FF3344;
        --accent-cyan: #00CCFF;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: var(--bg);
        color: var(--text);
        margin: 0;
        padding: 30px;
    }}
    header {{
        border-bottom: 1px solid var(--border);
        padding-bottom: 20px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 15px;
    }}
    h1 {{
        color: var(--accent-orange);
        margin: 0 0 6px 0;
        font-size: 24px;
        letter-spacing: 0.5px;
    }}
    .stats-bar {{
        display: flex;
        gap: 14px;
    }}
    .stat-pill {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        padding: 8px 16px;
        border-radius: 8px;
        text-align: center;
    }}
    .stat-num {{
        font-size: 18px;
        font-weight: bold;
        color: #FFF;
    }}
    .stat-label {{
        font-size: 10px;
        color: var(--text-muted);
        text-transform: uppercase;
    }}
    .filter-bar {{
        display: flex;
        gap: 10px;
        margin-bottom: 25px;
        flex-wrap: wrap;
        align-items: center;
    }}
    .filter-btn {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        color: var(--text-muted);
        padding: 6px 14px;
        border-radius: 6px;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    .filter-btn:hover, .filter-btn.active {{
        background: var(--accent-orange);
        color: #FFF;
        border-color: var(--accent-orange);
        font-weight: bold;
    }}
    .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(520px, 1fr));
        gap: 20px;
    }}
    .card {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        transition: transform 0.15s ease;
    }}
    .card-pass {{ border-top: 3px solid var(--accent-green); }}
    .card-fail {{ border-top: 3px solid var(--accent-red); }}
    .card-header {{
        padding: 12px 16px;
        background: rgba(0,0,0,0.25);
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid var(--border);
    }}
    .card-header h3 {{
        margin: 0;
        font-size: 14px;
        font-family: monospace;
    }}
    .header-right {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .score-badge {{
        font-weight: bold;
        font-size: 14px;
    }}
    .badge {{
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 0.5px;
    }}
    .badge.pass {{ background: rgba(0,255,102,0.15); color: var(--accent-green); border: 1px solid var(--accent-green); }}
    .badge.fail {{ background: rgba(255,51,68,0.15); color: var(--accent-red); border: 1px solid var(--accent-red); }}
    .card-body {{
        padding: 16px;
        display: flex;
        gap: 16px;
    }}
    .img-preview-box {{
        width: 140px;
        height: 140px;
        background: #0A0A0E;
        background-image: linear-gradient(45deg, #16161E 25%, transparent 25%),
                          linear-gradient(-45deg, #16161E 25%, transparent 25%),
                          linear-gradient(45deg, transparent 75%, #16161E 75%),
                          linear-gradient(-45deg, transparent 75%, #16161E 75%);
        background-size: 16px 16px;
        background-position: 0 0, 0 8px, 8px -8px, -8px 0px;
        border: 1px solid var(--border);
        border-radius: 6px;
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        overflow: hidden;
    }}
    .preview-img {{
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }}
    .anim-badge {{
        position: absolute;
        top: 4px;
        left: 4px;
        background: rgba(153, 0, 255, 0.85);
        color: #FFF;
        font-size: 8px;
        font-weight: bold;
        padding: 2px 5px;
        border-radius: 3px;
        letter-spacing: 0.5px;
    }}
    .anim-preview-overlay {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
        opacity: 0;
        transition: opacity 0.2s ease;
    }}
    .img-preview-box:hover .anim-preview-overlay {{
        opacity: 1;
    }}
    .type-tag {{
        position: absolute;
        bottom: 4px;
        right: 4px;
        background: rgba(0,0,0,0.75);
        font-size: 9px;
        padding: 2px 5px;
        border-radius: 3px;
        color: var(--text-muted);
    }}
    .card-details {{
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }}
    .metrics-container {{
        display: flex;
        flex-direction: column;
        gap: 4px;
    }}
    .metric-row {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
    }}
    .metric-name {{
        width: 150px;
        color: var(--text-muted);
    }}
    .bar-bg {{
        flex: 1;
        height: 6px;
        background: #252533;
        border-radius: 3px;
        overflow: hidden;
    }}
    .bar-fill {{
        height: 100%;
        border-radius: 3px;
    }}
    .bar-fill.green {{ background: var(--accent-green); }}
    .bar-fill.red {{ background: var(--accent-red); }}
    .metric-val {{
        width: 32px;
        text-align: right;
        font-family: monospace;
        font-size: 10px;
    }}
    .issues-list {{
        margin: 0;
        padding-left: 0;
        list-style: none;
        font-size: 11px;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }}
    .violation-item {{ color: #FFB347; }}
    .rec-item {{ color: #72B9FF; }}
    .clean-item {{ color: var(--accent-green); }}
    .card-actions {{
        margin-top: 4px;
    }}
    .btn-reroll {{
        background: rgba(255, 85, 0, 0.15);
        color: var(--accent-orange);
        border: 1px solid var(--accent-orange);
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    .btn-reroll:hover {{
        background: var(--accent-orange);
        color: #FFF;
    }}
    .toast {{
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: var(--accent-green);
        color: #000;
        padding: 10px 20px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 12px;
        opacity: 0;
        transition: opacity 0.3s ease;
        pointer-events: none;
    }}
    .toast.show {{
        opacity: 1;
    }}
</style>
</head>
<body>
<header>
    <div>
        <h1>{proj_name} ART DASHBOARD</h1>
        <div style="color: var(--text-muted); font-size: 13px;">Computer Vision QA & Interactive Sprite Review</div>
    </div>
    <div class="stats-bar">
        <div class="stat-pill">
            <div class="stat-num">{total}</div>
            <div class="stat-label">Total Assets</div>
        </div>
        <div class="stat-pill">
            <div class="stat-num" style="color: var(--accent-green);">{passed_cnt}</div>
            <div class="stat-label">Passed QA</div>
        </div>
        <div class="stat-pill">
            <div class="stat-num" style="color: var(--accent-red);">{failed_cnt}</div>
            <div class="stat-label">Needs Reroll</div>
        </div>
        <div class="stat-pill">
            <div class="stat-num">{avg_score:.1f}%</div>
            <div class="stat-label">Avg Quality</div>
        </div>
    </div>
</header>

<div class="filter-bar">
    <span style="color: var(--text-muted); font-size: 12px; margin-right: 5px;">FILTER:</span>
    <button class="filter-btn active" onclick="filterCards('all', event)">All ({total})</button>
    <button class="filter-btn" onclick="filterCards('pass', event)">Passed ({passed_cnt})</button>
    <button class="filter-btn" onclick="filterCards('fail', event)">Needs Reroll ({failed_cnt})</button>
    <button class="filter-btn" onclick="filterCards('kart', event)">Karts</button>
    <button class="filter-btn" onclick="filterCards('tile', event)">Tracks & Tiles</button>
    <button class="filter-btn" onclick="filterCards('icon', event)">Weapons & Icons</button>
    <button class="filter-btn" onclick="filterCards('prop', event)">Props</button>
    <button class="filter-btn" onclick="filterCards('scenic', event)">Scenic & Banner</button>
</div>

<div class="grid" id="assetGrid">
    {cards_joined}
</div>

<div id="toast" class="toast">Prompt copied to clipboard!</div>

<script>
function filterCards(type, evt) {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    if (evt && evt.target) {{ evt.target.classList.add('active'); }}
    var cards = document.querySelectorAll('.card');
    cards.forEach(function(card) {{
        if (type === 'all') {{
            card.style.display = 'flex';
        }} else if (type === 'pass' || type === 'fail') {{
            card.style.display = (card.getAttribute('data-status') === type) ? 'flex' : 'none';
        }} else {{
            card.style.display = (card.getAttribute('data-category') === type) ? 'flex' : 'none';
        }}
    }});
}}

function copyPrompt(text) {{
    navigator.clipboard.writeText(text).then(function() {{
        var t = document.getElementById('toast');
        t.classList.add('show');
        setTimeout(function() {{ t.classList.remove('show'); }}, 2000);
    }});
}}
</script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nInteractive QA Dashboard generated: file://{output_path.resolve().as_posix()}")


def generate_markdown_report(results: list[QAResult], output_path: Path, config: ArtPipelineConfig) -> None:
    """Export a clean Markdown QA summary table."""
    total = len(results)
    passed_cnt = sum(1 for r in results if r.passed)
    failed_cnt = total - passed_cnt
    avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0.0

    lines = [
        f"# {config.project_name} Art QA Verification Summary",
        f"**Total Assets:** {total} | **Passed:** {passed_cnt} | **Needs Reroll:** {failed_cnt} | **Average Score:** {avg_score:.1f}%\n",
        "| Status | Score | Asset Path | Type | Key Issues |",
        "| :--- | :---: | :--- | :--- | :--- |",
    ]

    for r in results:
        status_icon = "✅ PASS" if r.passed else "❌ FAIL"
        issues = "; ".join(r.violations) if r.violations else "None (Clean)"
        lines.append(f"| {status_icon} | **{r.overall_score:.1f}%** | `{r.path}` | `{r.asset_type}` | {issues} |")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Markdown report generated:    file://{output_path.resolve().as_posix()}")
