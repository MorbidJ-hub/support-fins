#!/usr/bin/env python3
"""Build the single-file OrcaSlicer plugin.

  python3 plugins/orca/build.py            # -> plugins/orca/build/support_fins_orca.py

1. Bundles the printfins.com engine (web/*.js, untouched) plus the Orca bridge
   (panel/engine_bridge.js) into one IIFE with esbuild.
2. Inlines that bundle into src/support_fins_orca.py as ENGINE_JS.

The result is ONE .py file: drop it into OrcaSlicer (Plugins > Install local
plugin, or <data_dir>/orca_plugins/). Orca installs numpy and mini-racer itself
from the PEP 723 header on first load (it bundles uv for that).

Needs esbuild: `npx esbuild` (fetched on demand) or ESBUILD=/path/to/esbuild.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "build"
PLACEHOLDER = '"__FINS_ENGINE_JS__"'


def esbuild_cmd():
    if os.environ.get("ESBUILD"):
        return [os.environ["ESBUILD"]]
    if shutil.which("esbuild"):
        return ["esbuild"]
    # shutil.which finds npx.cmd on Windows, where a bare "npx" isn't executable
    return [shutil.which("npx") or "npx", "--yes", "esbuild@0.28"]


def main():
    OUT.mkdir(exist_ok=True)
    bundle = OUT / "fins_engine.js"
    subprocess.run(esbuild_cmd() + [
        str(HERE / "panel" / "engine_bridge.js"), "--bundle", "--format=iife",
        "--global-name=SupportFinsEngine", "--target=es2022", "--minify",
        f"--outfile={bundle}", "--log-level=warning",
    ], check=True)
    js = bundle.read_text(encoding="utf-8")
    src = (HERE / "src" / "support_fins_orca.py").read_text(encoding="utf-8")
    if src.count(PLACEHOLDER) != 1:
        sys.exit("placeholder for the engine bundle not found exactly once in src/support_fins_orca.py")
    # json.dumps yields a valid Python string literal (ASCII, escaped).
    out = src.replace(PLACEHOLDER, json.dumps(js))
    target = OUT / "support_fins_orca.py"
    target.write_text(out, encoding="utf-8")
    print(f"built {target.relative_to(HERE.parent.parent)} "
          f"({target.stat().st_size / 1024:.0f} KB, engine {len(js) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
