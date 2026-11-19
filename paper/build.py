"""Build the web page and the PDF from paper/paper.md.

    python paper/build.py              # page and PDF from the figures in docs/figures
    python paper/build.py --figures    # regenerate the figures first

Writes docs/index.html (served by GitHub Pages from /docs) and
docs/sdbNSW_paper.pdf. Needs pandoc 3.1 or later on the PATH and the typst
Python package (pip install typst). The PDF uses Libertinus Serif, which typst
embeds, and Inter for headings and tables if it is installed.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
DOCS = ROOT / "docs"
BUILD = PAPER / "_build"


def pandoc(fmt: str, template: Path, out: Path, *extra: str) -> None:
    cmd = ["pandoc", str(PAPER / "paper.md"), "--from", "markdown", "--to", fmt,
           "--citeproc", "--lua-filter", str(PAPER / "build.lua"),
           "--template", str(template), "--resource-path", str(PAPER),
           "--output", str(out), *extra]
    subprocess.run(cmd, check=True, cwd=PAPER)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--figures", action="store_true", help="run scripts/figures.py first")
    a = p.parse_args(argv)
    if shutil.which("pandoc") is None:
        sys.exit("pandoc not found on the PATH")
    if a.figures:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "figures.py"), "--root", str(ROOT),
                        "--out", str(DOCS / "figures")], check=True)
    DOCS.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)

    pandoc("html5", PAPER / "web.html", DOCS / "index.html", "--toc", "--toc-depth=2")
    (DOCS / ".nojekyll").touch()

    typ = BUILD / "paper.typ"
    pandoc("typst-citations", PAPER / "paper.typ", typ, "--metadata", "link-citations=false", "--wrap=none")
    # pandoc 3.1's Typst writer leaves "#emph[48](4)", which Typst reads as a
    # call with extra arguments; escape the parenthesis.
    src = typ.read_text(encoding="utf-8")
    typ.write_text(re.sub(r"(#(?:emph|strong)\[[^\]]*\])\(", r"\1\\(", src), encoding="utf-8")
    import typst  # imported late so the page can be built without it

    fonts = [d for d in ("/usr/share/fonts/opentype/inter", "C:/Windows/Fonts") if Path(d).exists()]
    typst.compile(str(typ), output=str(DOCS / "sdbNSW_paper.pdf"), root=str(ROOT), font_paths=fonts)
    print(DOCS / "index.html")
    print(DOCS / "sdbNSW_paper.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
