#!/usr/bin/env python3
"""Read the HELLDRIFT art prompt pack and answer five questions:

  status              what is done, what is pending, per tier
  order  <tier|path>  the exact generation work order for a tier or one asset
  audit               pack vs tiers vs disk, and what art the pack still owes
  process <paths...>  clean alpha (remove magenta/white/checkerboard), defringe, downscale, unsharp mask, seamless blend
  test-tile <path>    verify 2x2 seamless tiling and measure edge seam error
  qa [<paths...>]     run automated quality assurance scoring and generate HTML dashboard

specs/helldrift-art-prompts-with-paths.md is the single source of truth for
prompts and paths. This script holds no prompt text of its own; it extracts
them. tiers.json decides ORDER ONLY, never content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# Add script directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from engine import ArtPipelineConfig
except ImportError:
    from art_engine import ArtPipelineConfig, process_asset as engine_process_asset

# Python block-buffers stdout whenever it is not a terminal, which on Windows
# cmd.exe means a backgrounded or piped run appears to produce nothing until
# the process exits or the 8KB block fills. Line buffering plus write_through
# makes output stream as it is produced, so callers never need `python -u`.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(  # type: ignore[attr-defined]
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
            write_through=True,
        )

PACK_REL = Path("specs") / "helldrift-art-prompts-with-paths.md"


def find_repo() -> Path:
    """The repo is wherever the art pack is. Walk up from the env override,
    then the cwd, then this script, so the skill works whether it is checked
    into the repo or installed into a global skills directory."""
    candidates: list[Path] = []
    if os.environ.get("HELLDRIFT_REPO"):
        candidates.append(Path(os.environ["HELLDRIFT_REPO"]).expanduser())
    candidates.extend([Path.cwd(), *Path.cwd().parents])
    candidates.extend(Path(__file__).resolve().parents)

    for base in candidates:
        if (base / PACK_REL).exists():
            return base
    sys.exit(
        f"cannot find {PACK_REL.as_posix()}.\n"
        "Run this from inside the HELLDRIFT repo, or set HELLDRIFT_REPO."
    )


REPO = find_repo()
PACK = REPO / PACK_REL
TIERS = Path(__file__).resolve().parents[1] / "assets" / "tiers.json"
LEDGER = REPO / "art-source" / "ledger.json"

HEADING = re.compile(r"^(#{2,3})\s+(.*)$")
FENCE = re.compile(r"^```")
PATHISH = re.compile(r"`?((?:res://|docs/|art-source/)[A-Za-z0-9_./<>*-]+\.png)`?")
BARE_PNG = re.compile(r"`(?:\.\.\./)?([A-Za-z0-9_-]+\.png)`")
DECLARES = re.compile(r"Paths?(?:\s*pattern)?:")


class Entry:
    """One asset declaration in the pack, with the prompts that follow it."""

    def __init__(self, section: str, section_line: int, line: int):
        self.section = section
        self.section_line = section_line
        self.line = line
        self.paths: list[str] = []
        self.prompts: list[str] = []
        self.notes: list[str] = []

    @property
    def ref(self) -> str:
        m = re.match(r"^(\d+(?:\.\d+)?)\.?\s", self.section)
        return f"§{m.group(1)}" if m else f"'{self.section}'"

    @property
    def label(self) -> str:
        return re.sub(r"^\d+(?:\.\d+)?\.?\s+", "", self.section)


def parse_pack() -> list[Entry]:
    if not PACK.exists():
        sys.exit(f"art pack not found at {PACK}")

    lines = PACK.read_text(encoding="utf-8").splitlines()
    entries: list[Entry] = []
    section, section_line = "(preamble)", 0
    current: Entry | None = None
    in_fence = False
    fence_buf: list[str] = []
    fence_owner: Entry | None = None

    for n, raw in enumerate(lines, 1):
        if FENCE.match(raw):
            if in_fence:
                if fence_owner is not None:
                    fence_owner.prompts.append("\n".join(fence_buf).strip())
                fence_buf = []
            else:
                fence_owner = current
            in_fence = not in_fence
            continue
        if in_fence:
            fence_buf.append(raw)
            continue

        h = HEADING.match(raw)
        if h:
            section, section_line = h.group(2).strip(), n
            current = None
            continue

        found = PATHISH.findall(raw)
        if DECLARES.search(raw):
            # A declaration may put its path on the next line (art pack §1).
            current = Entry(section, section_line, n)
            entries.append(current)
            for p in found:
                if p not in current.paths:
                    current.paths.append(p)
            continue

        if current is None:
            continue

        # Continuation of a multi-path declaration, or a prose sibling.
        for p in found:
            if p not in current.paths:
                current.paths.append(p)
        if not found:
            for stem in BARE_PNG.findall(raw):
                # Already declared with a full path somewhere in this entry?
                if any(p.endswith("/" + stem) for p in current.paths):
                    continue
                base = current.paths[0].rsplit("/", 1)[0] if current.paths else ""
                sibling = f"{base}/{stem}" if base else stem
                if sibling not in current.paths:
                    current.paths.append(sibling)
        if raw.strip().startswith(("- ", "**")) and len(current.notes) < 8:
            current.notes.append(raw.strip())

    return entries


def build_index(entries: list[Entry]) -> dict[str, Entry]:
    idx: dict[str, Entry] = {}
    for e in entries:
        for p in e.paths:
            idx.setdefault(p, e)
    return idx


def template_to_regex(declared: str) -> str:
    pattern = re.escape(declared)
    for token, sub in (
        (r"<panel>", r"[a-z]+"),
        (r"<tier>", r"\d+"),
        (r"<id>", r"[0-9a-z_]+"),
        (r"<name>", r"[a-z0-9_]+"),
        (r"<track_id>", r"[0-9a-z_]+"),
        (r"<prop_name>", r"[a-z0-9_]+"),
        (r"<variant>", r"[a-z0-9_]+"),
        (r"<type>", r"[a-z0-9_]+"),
        (r"\*", r"[a-z0-9_]+"),
    ):
        pattern = pattern.replace(token, sub)
    return pattern


def resolve(path: str, idx: dict[str, Entry], derivations: list[dict]):
    """Return (entry, derivation) for a concrete path. Either may be None."""
    if path in idx and idx[path].prompts:
        return idx[path], None

    for declared, entry in idx.items():
        if ("<" in declared or "*" in declared) and entry.prompts:
            if re.fullmatch(template_to_regex(declared), path):
                return entry, None

    for d in derivations:
        if re.fullmatch(d["match"], path):
            src = idx.get(d["source"])
            if src is not None and src.prompts:
                return src, d

    return idx.get(path), None


def to_fs(path: str) -> Path:
    if path.startswith("res://"):
        return REPO / path[len("res://"):]
    return REPO / path


def prompt_fingerprint(entry: "Entry", deriv: dict | None) -> str:
    """Hash of the exact text that produced an asset. Changing a prompt in the
    pack changes this, which is what makes an existing file detectably stale.
    A derivation note is part of the instruction, so it is part of the hash."""
    material = "\n--\n".join(entry.prompts)
    if deriv:
        material += "\n--DERIVED--\n" + deriv["note"]
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def load_ledger() -> dict:
    if not LEDGER.exists():
        return {}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8")).get("assets", {})
    except (json.JSONDecodeError, OSError):
        print(f"warning: {LEDGER} is unreadable, treating every asset as untracked",
              file=sys.stderr)
        return {}


def save_ledger(assets: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "Which prompt generated which asset. Written by art_pack.py record. "
            "If a prompt in the art pack changes, the fingerprint stops matching "
            "and the asset is reported STALE. Delete an entry to force a reroll."
        ),
        "assets": dict(sorted(assets.items())),
    }
    LEDGER.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_tiers() -> dict:
    if not TIERS.exists():
        sys.exit(f"tiers.json not found at {TIERS}")
    return json.loads(TIERS.read_text(encoding="utf-8"))


def classify(paths, idx, derivations, ledger=None):
    """Four buckets:
      done  - on disk, and the prompt that made it has not changed
      stale - on disk, but the pack's prompt has changed since (or is untracked
              and the file predates the ledger, which we report but trust)
      ready - not on disk, prompt available
      owed  - not on disk, pack has no prompt
    """
    if ledger is None:
        ledger = load_ledger()

    done, stale, ready, owed = [], [], [], []
    for p in paths:
        entry, deriv = resolve(p, idx, derivations)
        exists = to_fs(p).exists()
        has_prompt = entry is not None and bool(entry.prompts)

        if exists:
            record = ledger.get(p)
            changed = (
                has_prompt
                and entry is not None
                and record is not None
                and record.get("prompt") != prompt_fingerprint(entry, deriv)
            )
            if changed:
                stale.append((p, entry, deriv, record))
            else:
                done.append(p)
        elif has_prompt:
            ready.append((p, entry, deriv))
        else:
            owed.append(p)
    return done, stale, ready, owed


def cmd_status(args) -> None:
    data = load_tiers()
    idx = build_index(parse_pack())
    derivations = data.get("derivations", [])
    ledger = load_ledger()

    print("HELLDRIFT art pipeline status")
    print(f"pack:   {PACK.relative_to(REPO).as_posix()}")
    print(f"ledger: {LEDGER.relative_to(REPO).as_posix()}"
          f"{'' if LEDGER.exists() else '  (not created yet)'}\n")

    blocked_by = None
    stale_total = 0
    for key, tier in data["tiers"].items():
        done, stale, ready, owed = classify(tier["assets"], idx, derivations, ledger)
        total = len(tier["assets"])
        complete = len(done) == total
        stale_total += len(stale)
        flag = "complete" if complete else f"{len(done)}/{total}"
        if stale:
            flag += f", {len(stale)} stale"
        if not complete and blocked_by is None and tier.get("blocks_everything"):
            blocked_by = key

        print(f"[{key}] {tier['name']} -- {flag}")
        print(f"      needed for: {tier['gate']}")
        if not complete or stale or args.verbose:
            for entry_stale in stale:
                p, _, _, record = entry_stale
                print(f"      STALE     {p}  <- prompt changed since "
                      f"{record.get('generated', 'unknown date')}")
            for p, entry, deriv in ready:
                tag = f" (derive from {entry.ref})" if deriv else f" ({entry.ref})"
                print(f"      TODO      {p}{tag}")
            for p in owed:
                print(f"      NO PROMPT {p}  <- pack owes a prompt, see §6")
            if args.verbose:
                for p in done:
                    mark = "done     " if p in ledger else "done (untracked)"
                    print(f"      {mark} {p}")
        print()

    if stale_total:
        print(f"{stale_total} asset(s) were generated from a prompt that has since")
        print("changed. 'order' includes them; each one will say REGENERATE and")
        print("show which fingerprint it was made from.")
    if blocked_by:
        print(f"BLOCKED: [{blocked_by}] is not complete and everything downstream")
        print("depends on it. Generate that tier before any other.")


def emit_reference_header(ref: str | None) -> None:
    if not ref:
        return
    print("-" * 74)
    print("STYLE REFERENCE (attach to every asset in this order):")
    print(f"  {ref}")
    print()
    print("Attach it once per image-generation session if that tool keeps images")
    print("in context across turns. If each call is stateless (an API call per")
    print("asset), attach it on every call. Either way the reference must be in")
    print("context for every asset below, because every prompt in the pack opens")
    print("with 'Using the attached style reference'.")
    print("-" * 74)
    print()


def emit_rules(ref: str | None) -> None:
    print("# Every call obeys these. They come from the pack's 'General tricks'")
    print("# and industry best practices for high-hardness, coherent game art:")
    if ref:
        print("#  1. The style reference above is in context for every asset here.")
        print("#     If the session drops it, or you start a new one, re-attach.")
    else:
        print("#  1. ATTACH the master style reference on EVERY call. It does not")
        print("#     exist yet, which is why this order is the one that makes it.")
    print("#  2. Oversampling: Generate 1024x1024 square, then downscale with")
    print("#     Lanczos + unsharp mask sharpening via `art_pack.py process`.")
    print("#  3. Camera: Strict 90° top-down bird's-eye orthographic plan view.")
    print("#  4. Karts: chassis & rider ONLY with empty wheel wells. No wheels.")
    print("#  5. Isolation: Solid pure magenta (#FF00FF) backdrop, zero shadows.")
    print("#     Never prompt 'transparent background' (causes fake checkerboard).")
    print("#  6. Clean alpha & defringe with `art_pack.py process <file>`.")
    print("#  7. Textures: Make seamless with `art_pack.py process --seamless <file>`")
    print("#     and verify with `art_pack.py test-tile <file>`.")
    print("#  8. Quality check: verify score with `art_pack.py qa <file>`.")
    print()


def emit_order(paths, idx, derivations, label: str, data: dict, force=False) -> None:
    done, stale, ready, owed = classify(paths, idx, derivations)
    work = [(p, e, d, None) for p, e, d in ready] + \
           [(p, e, d, r) for p, e, d, r in stale]

    ref_rel = data.get("style_reference")
    ref_fs = to_fs(ref_rel) if ref_rel else None
    ref_exists = bool(ref_fs and ref_fs.exists())
    ref_abs = str(ref_fs) if ref_exists else None

    # Anything other than the reference itself needs the reference attached.
    needs_ref = [p for p, *_ in work if p != ref_rel]
    if needs_ref and not ref_exists:
        print("#" * 74)
        print("# STOP. The master style reference does not exist:")
        print(f"#   {ref_fs}")
        print("#")
        print("# Every prompt in the pack begins 'Using the attached style")
        print("# reference'. Generating any of these without it produces art that")
        print("# will not match anything made later, and the mismatch is not")
        print("# fixable without regenerating everything around it.")
        print("#")
        print("# Run this first:")
        print("#   python .claude/skills/helldrift-art/scripts/art_pack.py order t0-style")
        print("#")
        print("# Override with --force only if you know the reference is elsewhere.")
        print("#" * 74)
        if not force:
            sys.exit(2)
        print()

    print(f"# Generation work order: {label}")
    print(f"# {len(ready)} to generate, {len(stale)} to REGENERATE (prompt changed), "
          f"{len(done)} up to date, {len(owed)} blocked")
    print()
    emit_reference_header(ref_abs)
    emit_rules(ref_abs)

    for i, (p, entry, deriv, record) in enumerate(work, 1):
        print("=" * 74)
        verb = "REGENERATE" if record else "ASSET"
        print(f"{verb} {i}/{len(work)}: {p}")
        print(f"WRITE TO:  {to_fs(p)}")
        print(f"SOURCE:    art pack {entry.ref} {entry.label} (line {entry.line})")
        if p == ref_rel:
            print("ATTACH:    nothing. This call CREATES the style reference that")
            print("           every other call in the project attaches.")
        elif ref_abs:
            print("ATTACH:    the style reference from the header above")
        else:
            print("ATTACH:    MISSING - the style reference does not exist. See above.")
        if record:
            print(f"WHY:       the file exists, but the prompt changed since it was")
            print(f"           generated on {record.get('generated', 'an unknown date')}.")
            print(f"           was {record.get('prompt')}, now "
                  f"{prompt_fingerprint(entry, deriv)}. Overwrite it.")
        if deriv:
            print(f"DERIVED:   reusing the {entry.ref} prompt. {deriv['note']}")
        if entry.notes:
            print("PACK NOTES:")
            for note in entry.notes:
                print(f"  {note}")
        for j, prompt in enumerate(entry.prompts, 1):
            tag = f"PROMPT {j}/{len(entry.prompts)}" if len(entry.prompts) > 1 else "PROMPT"
            print(f"{tag}:")
            print(prompt)
        print()
        print(f"AFTER SAVING: python .claude/skills/helldrift-art/scripts/"
              f"art_pack.py process {to_fs(p)}")
        print(f"              python .claude/skills/helldrift-art/scripts/"
              f"art_pack.py record {p}")
        print()

    if owed:
        print("=" * 74)
        print("BLOCKED - the pack has no prompt for these. Do NOT improvise one:")
        for p in owed:
            print(f"  {p}")
        print("Add a prompt to the art pack first, then re-run. The pack is the")
        print("source of truth precisely so nothing gets generated off-spec.")
        print()

    if done:
        print(f"Skipped {len(done)} asset(s) that already exist on disk.")
    if not ready and not owed:
        print("Nothing to do. This tier is complete.")


def first_incomplete(data, idx, derivations) -> str | None:
    """Earliest tier with anything missing or stale."""
    for key, tier in data["tiers"].items():
        done, stale, _, _ = classify(tier["assets"], idx, derivations)
        if len(done) != len(tier["assets"]) or stale:
            return key
    return None


def cmd_order(args) -> None:
    data = load_tiers()
    idx = build_index(parse_pack())
    derivations = data.get("derivations", [])

    if args.target == "next":
        key = first_incomplete(data, idx, derivations)
        if key is None:
            print("Every tier is complete. Nothing to generate.")
            return
        tier = data["tiers"][key]
        print(f"# 'next' resolved to [{key}] {tier['name']}")
        print(f"# unblocks: {tier['gate']}")
        print()
        emit_order(tier["assets"], idx, derivations, f"[{key}] {tier['name']}",
                   data, args.force)
        return

    if args.target in data["tiers"]:
        tier = data["tiers"][args.target]
        emit_order(tier["assets"], idx, derivations,
                   f"[{args.target}] {tier['name']}", data, args.force)
        return

    hits = [p for t in data["tiers"].values() for p in t["assets"] if args.target in p]
    if not hits:
        hits = [p for p in idx if args.target in p and "<" not in p and "*" not in p]
    if not hits:
        sys.exit(
            f"no tier key and no asset path matches '{args.target}'.\n"
            f"tiers: {', '.join(data['tiers'])}"
        )
    emit_order(hits, idx, derivations, args.target, data, args.force)


def cmd_record(args) -> None:
    """Stamp the ledger with the prompt that produced an asset. Run this right
    after saving a generated file, or the tooling cannot tell later whether a
    prompt edit invalidated it."""
    data = load_tiers()
    idx = build_index(parse_pack())
    derivations = data.get("derivations", [])
    ledger = load_ledger()
    stamp = time.strftime("%Y-%m-%d")

    if args.all:
        targets = [
            p for t in data["tiers"].values() for p in t["assets"]
            if to_fs(p).exists()
        ]
    else:
        targets = args.paths

    if not targets:
        sys.exit("nothing to record. Pass one or more paths, or --all.")

    recorded, skipped = 0, []
    for raw in targets:
        matches = [p for p in idx if raw == p] or \
                  [p for t in data["tiers"].values() for p in t["assets"] if raw in p]
        if not matches:
            skipped.append(f"{raw}: no such asset in the pack or the tiers")
            continue
        for p in dict.fromkeys(matches):
            if not to_fs(p).exists():
                skipped.append(f"{p}: not on disk yet")
                continue
            entry, deriv = resolve(p, idx, derivations)
            if entry is None or not entry.prompts:
                skipped.append(f"{p}: the pack has no prompt, nothing to fingerprint")
                continue
            ledger[p] = {
                "prompt": prompt_fingerprint(entry, deriv),
                "source": f"art pack {entry.ref}",
                "generated": stamp,
            }
            recorded += 1
            print(f"recorded {p}  ({ledger[p]['prompt']}, {entry.ref})")

    if recorded:
        save_ledger(ledger)
        print(f"\n{recorded} entry/entries written to "
              f"{LEDGER.relative_to(REPO).as_posix()}")
    for line in skipped:
        print(f"skipped  {line}")


def cmd_audit(args) -> None:
    del args
    data = load_tiers()
    entries = parse_pack()
    idx = build_index(entries)
    derivations = data.get("derivations", [])
    tiered = {p for t in data["tiers"].values() for p in t["assets"]}

    print("== Declared in the pack but scheduled in no tier")
    print("   (these will never be generated by any milestone)")
    never_shipped = set(data.get("umbrella_paths", []))
    orphans = [
        p for p in sorted(idx)
        if p not in tiered
        and "<" not in p and "*" not in p
        and not p.startswith("art-source/")
        and p not in never_shipped
    ]
    for p in orphans:
        print(f"   {p}  ({idx[p].ref})")
    if not orphans:
        print("   none")

    print("\n== Scheduled in a tier but the pack owes a prompt")
    missing = []
    for p in sorted(tiered):
        entry, _ = resolve(p, idx, derivations)
        if entry is None or not entry.prompts:
            missing.append(p)
    for p in missing:
        print(f"   {p}")
    if not missing:
        print("   none")

    print("\n== On disk but scheduled in no tier")
    root = REPO / "assets" / "sprites"
    stray = []
    if root.exists():
        for f in sorted(root.rglob("*.png")):
            rel = "res://" + f.relative_to(REPO).as_posix()
            if rel not in tiered:
                stray.append(rel)
    for p in stray:
        print(f"   {p}")
    if not stray:
        print("   none")

    ledger = load_ledger()
    print("\n== In the ledger but the file is gone")
    print("   (deleted for a reroll, so they read as not-yet-generated)")
    ghosts = [p for p in sorted(ledger) if not to_fs(p).exists()]
    for p in ghosts:
        print(f"   {p}  (was {ledger[p].get('prompt')})")
    if not ghosts:
        print("   none")

    print("\n== On disk with no ledger entry")
    print("   (generated before the ledger existed, or made by hand; trusted,")
    print("    but a prompt change will not be detected until recorded)")
    untracked = [
        p for p in sorted(tiered)
        if to_fs(p).exists() and p not in ledger
    ]
    for p in untracked:
        print(f"   {p}")
    if not untracked:
        print("   none")

    print(f"\n{len(entries)} declarations parsed, {len(idx)} distinct paths, "
          f"{len(tiered)} scheduled across {len(data['tiers'])} tiers, "
          f"{len(ledger)} recorded in the ledger.")


# =========================================================================
# Image Processing & Seam Verification Utilities
# =========================================================================

def make_seamless_blend(arr: np.ndarray, margin: int = 32) -> np.ndarray:
    """Apply linear alpha margin cross-blend on 4 edges to produce perfect 0.0 seam delta."""
    out = arr.copy().astype(np.float32)
    h, w = out.shape[:2]
    m = min(margin, w // 4, h // 4)

    for i in range(m):
        alpha = i / float(m)
        # Left and Right blend
        blended_x = out[:, i] * (1 - alpha) + out[:, w - 1 - i] * alpha
        out[:, i] = blended_x
        out[:, w - 1 - i] = blended_x

    for j in range(m):
        alpha = j / float(m)
        # Top and Bottom blend
        blended_y = out[j, :] * (1 - alpha) + out[h - 1 - j, :] * alpha
        out[j, :] = blended_y
        out[h - 1 - j, :] = blended_y

    return out.astype(np.uint8)


def process_image(img_path: Path, bg_color: str | None, tolerance: int,
                  downscale: tuple[int, int] | None, sharpen: bool = True,
                  make_seamless: bool = False, seamless_margin: int = 32) -> None:
    try:
        from PIL import Image, ImageFilter
        import numpy as np
    except ImportError:
        sys.exit("Pillow and numpy are required for image processing. Run 'pip install Pillow numpy'.")

    if not img_path.exists():
        print(f"Error: {img_path} does not exist", file=sys.stderr)
        return

    im = Image.open(img_path)
    
    # If image is a tileable ground texture or make_seamless is requested
    if make_seamless or "track_surface" in img_path.as_posix() or "offtrack" in img_path.as_posix() or "floor" in img_path.as_posix():
        rgb_arr = np.array(im.convert("RGB"))
        blended = make_seamless_blend(rgb_arr, margin=seamless_margin)
        im = Image.fromarray(blended)
        if downscale:
            im = im.resize(downscale, Image.Resampling.LANCZOS)
        if sharpen:
            im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        im.save(img_path, "PNG", optimize=True)
        print(f"Processed Texture (Seamless, {im.size[0]}x{im.size[1]}): {img_path}")
        return

    # Standard isolated sprite processing
    im = im.convert("RGBA")
    arr = np.array(im, dtype=np.float32)

    # Determine target background color
    target_rgb: tuple[float, float, float]
    if bg_color:
        hex_clean = bg_color.lstrip("#")
        target_rgb = tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    else:
        # Auto-detect background from corners (top-left, top-right, bottom-left, bottom-right)
        corners = np.array([arr[0, 0, :3], arr[0, -1, :3], arr[-1, 0, :3], arr[-1, -1, :3]])
        mean_corner = np.mean(corners, axis=0)
        if mean_corner[0] > 180 and mean_corner[1] < 80 and mean_corner[2] > 180:
            target_rgb = (255.0, 0.0, 255.0)
        elif mean_corner[0] > 235 and mean_corner[1] > 235 and mean_corner[2] > 235:
            target_rgb = (255.0, 255.0, 255.0)
        else:
            target_rgb = (255.0, 0.0, 255.0)

    # Calculate Euclidean color distance to target background
    diff = np.sqrt(
        (arr[:, :, 0] - target_rgb[0]) ** 2 +
        (arr[:, :, 1] - target_rgb[1]) ** 2 +
        (arr[:, :, 2] - target_rgb[2]) ** 2
    )

    alpha = np.clip((diff - tolerance) / max(tolerance, 1.0) * 255.0, 0, 255)
    
    if target_rgb == (255.0, 0.0, 255.0):
        arr[:, :, 3] = alpha
        # Despill / defringing: remove magenta spill on edge pixels
        edge_mask = (arr[:, :, 3] > 0) & (arr[:, :, 3] < 240)
        arr[edge_mask, 0] = np.minimum(arr[edge_mask, 0], arr[edge_mask, 1] + 30)
        arr[edge_mask, 2] = np.minimum(arr[edge_mask, 2], arr[edge_mask, 1] + 30)
    else:
        arr[:, :, 3] = np.minimum(arr[:, :, 3], alpha)

    result = Image.fromarray(arr.astype(np.uint8), "RGBA")

    if downscale:
        result = result.resize(downscale, Image.Resampling.LANCZOS)
        if sharpen:
            # Unsharp mask sharpening to preserve crisp vector contours after downsampling
            result = result.filter(ImageFilter.UnsharpMask(radius=1.0, percent=125, threshold=2))

    img_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(img_path, "PNG", optimize=True)
    print(f"Processed Sprite (RGBA, {result.size[0]}x{result.size[1]}): {img_path}")


def cmd_process(args) -> None:
    downscale = tuple(args.downscale) if args.downscale else None
    config = ArtPipelineConfig.load()
    if args.bg:
        config.isolation.chroma_hex = args.bg
    if args.tolerance:
        config.isolation.tolerance = args.tolerance

    for p_str in args.paths:
        p = to_fs(p_str)
        if p.is_dir():
            for f in sorted(p.rglob("*.png")):
                engine_process_asset(f, config, downscale=downscale,
                                     sharpen=not args.no_sharpen,
                                     make_seamless=args.seamless,
                                     seamless_margin=args.seamless_margin)
        else:
            engine_process_asset(p, config, downscale=downscale,
                                 sharpen=not args.no_sharpen,
                                 make_seamless=args.seamless,
                                 seamless_margin=args.seamless_margin)


def cmd_test_tile(args) -> None:
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        sys.exit("Pillow and numpy are required. Run 'pip install Pillow numpy'.")

    img_path = to_fs(args.path)
    if not img_path.exists():
        sys.exit(f"File not found: {img_path}")

    im = Image.open(img_path).convert("RGB")
    arr = np.array(im, dtype=np.float32)
    h, w, _ = arr.shape

    h_diff = float(np.mean(np.abs(arr[:, 0] - arr[:, -1])))
    v_diff = float(np.mean(np.abs(arr[0, :] - arr[-1, :])))
    avg_diff = (h_diff + v_diff) / 2.0

    print(f"Seam Analysis for: {img_path.relative_to(REPO).as_posix()}")
    print(f"Dimensions:        {w}x{h} px")
    print(f"Horizontal Seam Δ: {h_diff:.2f} / 255")
    print(f"Vertical Seam Δ:   {v_diff:.2f} / 255")
    print(f"Average Seam Δ:    {avg_diff:.2f} / 255")

    if avg_diff < 3.0:
        print("Rating:            EXCELLENT (Seamless wrap is virtually invisible)")
    elif avg_diff < 8.0:
        print("Rating:            GOOD (Minor seam difference, usually imperceptible in motion)")
    elif avg_diff < 15.0:
        print("Rating:            NOTICEABLE (Visible seam line at borders - consider blending or rerolling)")
    else:
        print("Rating:            POOR (Harsh visible boundary mismatch - reroll with seamless prompt)")

    if args.save_preview:
        preview = Image.new("RGB", (w * 2, h * 2))
        preview.paste(im, (0, 0))
        preview.paste(im, (w, 0))
        preview.paste(im, (0, h))
        preview.paste(im, (w, h))
        out_preview = img_path.parent / f"{img_path.stem}_2x2_preview.png"
        preview.save(out_preview, "PNG")
        print(f"2x2 Preview Saved: {out_preview.relative_to(REPO).as_posix()}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="art_pack.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="per-tier progress")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_status)

    o = sub.add_parser(
        "order",
        help="work order for 'next', a tier key, or a path fragment",
    )
    o.add_argument("target", nargs="?", default="next")
    o.add_argument("--force", action="store_true",
                   help="emit the order even if the master style reference is missing")
    o.set_defaults(func=cmd_order)

    r = sub.add_parser(
        "record",
        help="stamp the ledger with the prompt that generated an asset",
    )
    r.add_argument("paths", nargs="*", help="asset paths or path fragments")
    r.add_argument("--all", action="store_true",
                   help="record every scheduled asset that exists on disk")
    r.set_defaults(func=cmd_record)

    a = sub.add_parser("audit", help="cross-check pack, tiers, ledger and disk")
    a.set_defaults(func=cmd_audit)

    p = sub.add_parser("process", help="extract alpha from solid backdrop, defringe, downscale, sharpen")
    p.add_argument("paths", nargs="+", help="image file(s) or directories to process")
    p.add_argument("--bg", default="#FF00FF", help="hex color of solid backdrop (default: #FF00FF magenta)")
    p.add_argument("--tolerance", type=int, default=35, help="color distance tolerance (default: 35)")
    p.add_argument("--downscale", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"),
                   help="downscale image to WIDTH HEIGHT using Lanczos")
    p.add_argument("--no-sharpen", action="store_true", help="disable unsharp mask sharpening")
    p.add_argument("--seamless", action="store_true", help="apply 4-edge margin blending for tileable textures")
    p.add_argument("--seamless-margin", type=int, default=32, help="margin size in pixels for seamless blend")
    p.set_defaults(func=cmd_process)

    t = sub.add_parser("test-tile", help="verify 2x2 seamless tiling and edge seam error")
    t.add_argument("path", help="path to tileable texture image")
    t.add_argument("--save-preview", action="store_true", help="save a 2x2 repeating grid preview")
    t.set_defaults(func=cmd_test_tile)

    q = sub.add_parser("qa", help="run automated QA evaluation and scoring on assets")
    q.add_argument("paths", nargs="*", help="asset paths or directory (leave empty to check all)")
    q.add_argument("--report", default="art-source/qa_report.html", help="HTML report output path")
    def cmd_qa(args):
        qa_script = Path(__file__).parent / "art_qa.py"
        if not args.paths:
            os.system(f"python3 {qa_script} verify-all --report {args.report}")
        else:
            for p in args.paths:
                os.system(f"python3 {qa_script} score {p}")
    q.set_defaults(func=cmd_qa)

    args = ap.parse_args()
    args.func(args)


def flush_quietly() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (BrokenPipeError, ValueError, OSError):
            pass


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        sys.exit(0)
    except KeyboardInterrupt:
        flush_quietly()
        sys.exit(130)
    finally:
        flush_quietly()
