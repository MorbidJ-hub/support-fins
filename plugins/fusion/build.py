#!/usr/bin/env python3
"""Bundle the printfins.com engine into the Fusion add-in.

  python3 plugins/fusion/build.py      # -> SupportFins/palette/fins_engine.js

The add-in runs the website's engine (web/*.js, untouched, bundled with the
shared bridge by plugins/shared/bundle.py, as Orca does) in a hidden Fusion
palette, so this bundle is all it needs: nothing native, one set of files for
Windows and macOS. Copy or link SupportFins/ into Fusion's AddIns folder and Run.

Needs esbuild (see plugins/shared/bundle.py).
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ADDIN = HERE / 'SupportFins'
BUNDLE = ADDIN / 'palette' / 'fins_engine.js'

sys.path.insert(0, str(HERE.parent / 'shared'))
from bundle import bundle_engine  # noqa: E402


def main():
    js = bundle_engine(BUNDLE)
    print('engine bundle: SupportFins/palette/fins_engine.js (%.0f KB)' % (len(js) / 1024))


if __name__ == '__main__':
    main()
