"""Freeze each registered protocol, verbatim, from the commit that registered it.

    python scripts/freeze_protocols.py           # write protocols/*.md
    python scripts/freeze_protocols.py --check   # confirm the files still match git

Each protocol was registered by committing its text to PROJECT_BRIEF.md before
any model was fitted to the data it governs. The brief has since been rewritten
as a readable project record, so this script copies each section out of the
brief as it stood at its registering commit, unchanged, original punctuation
included, and records a SHA-256 of the copied text. Needs the repository's git
history.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "protocols"
BRIEF = "PROJECT_BRIEF.md"

# file, title, registering commit, start of the section's heading, what it governs
PROTOCOLS = [
    ("01_phase2_band_ratio.md", "Phase 2 protocol: the band ratio at Jervis Bay", "8332154",
     "## Phase 2 protocol", "the Stumpf band ratio at Jervis Bay: calibration, blocked validation, "
     "statistics and the CATZOC breakdown depth; later runs at every site follow it"),
    ("02_substrate_addendum.md", "Substrate addendum", "73d02ce",
     "### Substrate addendum", "how pixels are classed by seabed type and how classes are compared"),
    ("03_v2_gradient_boosting.md", "v2 protocol: gradient boosting", "c2baa44",
     "## v2 protocol", "the gradient-boosting model, its features, its comparison with the band "
     "ratio and the coordinate model kept as a leakage demonstration"),
    ("04_phase4_three_sites.md", "Phase 4 protocol: three sites", "a5b5f5d",
     "## Phase 4 protocol", "site eligibility, scene and gauge rules, the clarity metric, "
     "the within-site block test, four predictions and the sensitivity runs"),
    ("05_phase4_amendment.md", "Phase 4 amendment: Northern Beaches open coast only", "2cd2f53",
     "### Phase 4 amendment", "the open-sea rule at Northern Beaches, made before any fit at the new sites"),
    ("06_exploratory_depth_standardised.md", "Exploratory addendum: depth-standardised block test",
     "884dce1", "### Exploratory addendum", "an exploratory test defined after the registered "
     "Phase 4 result was seen, with its reading rule fixed before it was run"),
]


def git(*args: str) -> str:
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return out.stdout


def section(text: str, heading: str) -> str:
    """The section starting at the heading, up to the next heading outside a code fence."""
    lines = text.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(heading))
    fence = False
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].lstrip().startswith("```"):
            fence = not fence
        elif not fence and lines[i].startswith("#"):
            end = i
            break
    return "\n".join(lines[start:end]).rstrip("\n") + "\n"


def frozen(name: str, title: str, short: str, heading: str, governs: str) -> tuple[str, str, str, str]:
    full, date = git("log", "-1", "--format=%H %cI", short).split()
    text = section(git("show", f"{full}:{BRIEF}"), heading)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    page = (f"# {title}\n\n"
            f"Governs {governs}.\n\n"
            f"Registered in commit `{full}` ({date}). The text below the rule is copied "
            f"unchanged from `{BRIEF}` as it stood at that commit, including its original "
            f"punctuation and its working voice. To see it in place:\n\n"
            f"```\ngit show {short}:{BRIEF}\n```\n\n"
            f"SHA-256 of the copied text: `{digest}`\n\n---\n\n{text}")
    return page, full, date, digest


def index(rows: list[tuple[str, str, str, str, str]]) -> str:
    lines = ["# Registered protocols", "",
             "Each analysis in this project was registered before it was run: its protocol, "
             "predictions and decision gate were committed to `PROJECT_BRIEF.md` before any "
             "model was fitted to the data it governs. That file has since been rewritten as a "
             "readable project record, so the registered texts are kept here, each copied "
             "verbatim from the commit that registered it by `scripts/freeze_protocols.py`.", "",
             "`python scripts/freeze_protocols.py --check` confirms that every file still "
             "matches git history. The code finds the same commits independently: each output "
             "record under `outputs/` names the commit that introduced its protocol.", "",
             "| File | Protocol | Registered | Commit |", "|:--|:--|:--|:--|"]
    for name, title, full, date, _ in rows:
        lines.append(f"| [`{name}`]({name}) | {title} | {date[:10]} | `{full[:7]}` |")
    lines += ["", "Changes made after a protocol was registered are listed, with their reasons, "
              "in the decisions register of `PROJECT_BRIEF.md` and in Table 4 of the paper.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="compare with the files instead of writing")
    a = p.parse_args(argv)
    OUT.mkdir(exist_ok=True)
    rows, bad = [], 0
    for name, title, short, heading, governs in PROTOCOLS:
        page, full, date, digest = frozen(name, title, short, heading, governs)
        rows.append((name, title, full, date, digest))
        path = OUT / name
        if a.check:
            same = path.exists() and path.read_text(encoding="utf-8") == page
            bad += not same
            print(f"{'ok  ' if same else 'DIFF'} {name}  {digest[:16]}")
        else:
            path.write_text(page, encoding="utf-8", newline="\n")
            print(f"wrote {name}  {digest[:16]}")
    idx = index(rows)
    if a.check:
        same = (OUT / "README.md").exists() and (OUT / "README.md").read_text(encoding="utf-8") == idx
        bad += not same
        print(f"{'ok  ' if same else 'DIFF'} README.md")
    else:
        (OUT / "README.md").write_text(idx, encoding="utf-8", newline="\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
