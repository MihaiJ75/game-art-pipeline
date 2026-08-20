#!/usr/bin/env python3
"""HELLDRIFT Art Quality Assurance & Verification CLI

Wraps the reusable art_engine QA Evaluator and Reporter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from engine import (
    ArtPipelineConfig,
    MetricResult,
    QAResult,
    evaluate_asset,
    generate_html_report,
    generate_markdown_report,
    check_alpha_and_chroma,
    check_edge_hardness,
    check_framing_fill,
    check_palette_coherence,
    check_seamless_tiling,
    check_perspective,
    check_symmetry,
)


def find_repo() -> Path:
    candidates = [Path.cwd(), *Path.cwd().parents]
    candidates.extend(Path(__file__).resolve().parents)
    for base in candidates:
        if (base / "specs" / "helldrift-art-prompts-with-paths.md").exists():
            return base
    return Path.cwd()


REPO = find_repo()


def to_fs(path: str | Path) -> Path:
    p_str = str(path)
    if p_str.startswith("res://"):
        return REPO / p_str[len("res://"):]
    p = Path(p_str)
    if p.is_absolute():
        return p
    return REPO / p


# Backward-compatibility alias functions for existing tests / scripts
_default_config = ArtPipelineConfig.load()

def check_alpha_integrity(arr):
    return check_alpha_and_chroma(arr, _default_config)

def check_orientation_symmetry(arr):
    return check_symmetry(arr, _default_config)

def check_perspective_correctness(arr, asset_type="sprite", path_str=""):
    return check_perspective(arr, _default_config, asset_type, path_str)


def main() -> None:
    ap = argparse.ArgumentParser(prog="art_qa.py", description="HellDrift Art QA & Verification Engine")
    ap.add_argument("--config", help="path to custom art_config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="evaluate a single image asset")
    s.add_argument("path", help="path to image file")
    s.add_argument("--type", default="auto", choices=["auto", "kart", "tile", "icon", "prop", "scenic", "sprite"])
    s.add_argument("--json", action="store_true", help="output JSON format")

    v = sub.add_parser("verify-all", help="scan and evaluate all generated project sprites")
    v.add_argument("--dir", default="assets/sprites", help="directory to scan")
    v.add_argument("--report", default="art-source/qa_report.html", help="path to export HTML report")
    v.add_argument("--md", default="art-source/qa_report.md", help="path to export Markdown report")

    args = ap.parse_args()
    config = ArtPipelineConfig.load(args.config) if args.config else ArtPipelineConfig.load()

    if args.cmd == "score":
        fs_path = to_fs(args.path)
        res = evaluate_asset(fs_path, config, args.type)
        if args.json:
            print(json.dumps(asdict(res), indent=2))
        else:
            print("=" * 60)
            print(f"{config.project_name.upper()} ART QA: {res.path}")
            print(f"Asset Type:     {res.asset_type.upper()}")
            print(f"Overall Score:  {res.overall_score:.1f} / 100")
            print(f"Verdict:        {'PASSED' if res.passed else 'NEEDS REROLL'}")
            print("-" * 60)
            print("METRIC BREAKDOWN:")
            for m in res.metrics:
                status = "PASS" if m.passed else "FAIL"
                print(f"  [{status}] {m.name:<24}: {m.score:>5.1f}%  ({m.details})")
            if res.violations:
                print("-" * 60)
                print("VIOLATIONS:")
                for viol in res.violations:
                    print(f"  - {viol}")
            if res.recommendations:
                print("RECOMMENDATIONS:")
                for rec in res.recommendations:
                    print(f"  - {rec}")
            print("=" * 60)

    elif args.cmd == "verify-all":
        target_dir = to_fs(args.dir)
        files: list[Path] = []
        if target_dir.exists():
            files.extend(sorted(target_dir.rglob("*.png")))
        banner_file = to_fs("docs/banner.png")
        if banner_file.exists():
            files.append(banner_file)
        ref_dir = to_fs("art-source/reference")
        if ref_dir.exists():
            files.extend(sorted(ref_dir.glob("*.png")))

        results = []
        print("=" * 74)
        print(f"{config.project_name.upper()} ART QA BATCH EVALUATION ({len(files)} assets)")
        print("=" * 74)
        print(f"{'STATUS':<8} {'SCORE':<8} {'ASSET PATH'}")
        print("-" * 74)

        for f in files:
            res = evaluate_asset(f, config)
            # Make path display clean relative
            if f.is_relative_to(REPO):
                res.path = f.relative_to(REPO).as_posix()
            results.append(res)
            mark = "PASS" if res.passed else "FAIL"
            print(f"[{mark}]    {res.overall_score:>5.1f}%   {res.path}")

        print("-" * 74)

        if args.report:
            generate_html_report(results, to_fs(args.report), config)
        if args.md:
            generate_markdown_report(results, to_fs(args.md), config)


if __name__ == "__main__":
    main()
