"""Runs the printfins.com fin engine inside Fusion.

The fins come from the website's own engine (web/*.js, unmodified), bundled by
plugins/shared/bundle.py and run in an embedded V8 (mini-racer), exactly as the
Orca plugin does. There is no Python port of the fin geometry to drift from the
site: a fix on the site reaches Fusion the next time the add-in is built.

Pure Python, no adsk imports, so the tests run it without Fusion.

    engine/fins_engine.js   the bundle (plugins/fusion/build.py writes it)
    lib/<platform>/         mini-racer, vendored per platform by build.py, because
                            Fusion's Python has no pip. A mini-racer already on
                            sys.path (a dev machine, CI) is used first.
"""

import atexit
import base64
import json
import os
import platform
import sys
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(HERE, 'engine', 'fins_engine.js')
LIB = os.path.join(HERE, 'lib')

# What the website starts with (plugins/shared/engine/fins_entry.js ENGINE_DEFAULTS).
DEFAULTS = {
    'mode': 'auto',
    'bedPad': True,
    'tines': True,
    'tineDensity': 0.0,
    'coverage': 0.5,
    'layerHeight': 0.2,
}

# One engine run should take well under a few seconds. Past this, give up rather
# than leave Fusion frozen on the main thread.
TIMEOUT_S = 60.0


class EngineError(Exception):
    """The engine couldn't start or run, worded for the readout."""


def platform_tag():
    """The lib/ subfolder that holds this machine's mini-racer build."""
    machine = platform.machine().lower()
    if sys.platform == 'win32':
        return 'win_amd64'
    if sys.platform == 'darwin':
        return 'macosx_arm64' if machine in ('arm64', 'aarch64') else 'macosx_x86_64'
    return 'linux_x86_64'


def _import_mini_racer():
    import importlib.util
    if importlib.util.find_spec('py_mini_racer') is None:   # a dev machine or CI has it
        vendored = os.path.join(LIB, platform_tag())
        if not os.path.isdir(os.path.join(vendored, 'py_mini_racer')):
            raise EngineError(
                'The fin engine’s JavaScript runtime (mini-racer) isn’t in this copy of the '
                'add-in for %s. Install the Support Fins build for this platform, or run '
                'plugins/fusion/build.py.' % platform_tag())
        if vendored not in sys.path:
            sys.path.insert(0, vendored)
    from py_mini_racer import MiniRacer, init_mini_racer
    return MiniRacer, init_mini_racer


_ctx = None


def _engine():
    """One V8 context for the whole Fusion session (loading the bundle takes ms)."""
    global _ctx
    if _ctx is None:
        if not os.path.isfile(BUNDLE):
            raise EngineError('The fin engine bundle is missing (engine/fins_engine.js). '
                              'Run plugins/fusion/build.py, or install a packaged build.')
        MiniRacer, init_mini_racer = _import_mini_racer()
        flags = ['--single-threaded']
        if sys.platform == 'darwin':
            # macOS: mini-racer's JIT hits SIGTRAP, and a hardened app like Fusion may
            # refuse JIT memory anyway (the Orca plugin learned this first).
            flags.append('--jitless')
        init_mini_racer(flags=flags, ignore_duplicate_init=True)
        ctx = MiniRacer()
        with open(BUNDLE, encoding='utf-8') as fh:
            ctx.eval(fh.read())
        # mini-racer never tears V8 down on its own; without this, exit can hang.
        atexit.register(ctx.close)
        # Fusion's Stop/Run reimports this module; close the last run's context
        # (kept on sys, which outlives the reimport) instead of leaking its thread.
        old = getattr(sys, '_support_fins_v8', None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        sys._support_fins_v8 = ctx
        _ctx = ctx
    return _ctx


def reset():
    """Drop this module's V8 context; the next call starts a new one."""
    global _ctx
    ctx, _ctx = _ctx, None
    if ctx is not None:
        try:
            ctx.close()
        except Exception:
            pass
    if getattr(sys, '_support_fins_v8', None) is ctx:
        sys._support_fins_v8 = None


def available():
    """(True, None) if the engine can run here, else (False, why)."""
    try:
        _engine()
        return True, None
    except EngineError as e:
        return False, str(e)
    except Exception as e:  # a broken DLL, an unsupported OS...
        return False, 'The fin engine couldn’t start: %s' % e


def compute_fins(soup, options=None):
    """Run the website's fin engine on a posed part.

    soup    flat sequence of floats, 9 per triangle: the part in PRINT SPACE (mm,
            z up, the bed at z = 0), wound outward.
    options overrides for DEFAULTS (mode, bedPad, tines, tineDensity, coverage,
            layerHeight).

    Returns (fins, stats): fins is an array('d') triangle soup in the SAME frame as
    `soup` (the engine seats the part itself; its offset is undone here), and
    stats is the engine's dict (overhangRegions, finTriangles, padTriangles, tines...).
    """
    data = array('d', soup)
    if not len(data) or len(data) % 9:
        raise EngineError('The part has no triangles to fit fins to.')
    if sys.byteorder != 'little':       # the bridge reads little-endian bytes
        data.byteswap()
    opts = dict(DEFAULTS)
    opts.update({k: v for k, v in (options or {}).items() if k in DEFAULTS})
    payload = (base64.b64encode(data.tobytes()).decode('ascii'), json.dumps(opts))
    raw = None
    for attempt in (1, 2):
        try:
            raw = _engine().call('SupportFinsEngine.computeFinsB64', *payload,
                                 timeout_sec=TIMEOUT_S)
            break
        except EngineError:
            raise
        except Exception as e:
            # A context that was closed under us (another copy of this module
            # reloaded, as Fusion's Stop/Run does) fails every call: start a fresh
            # one and try once more before giving up.
            reset()
            if attempt == 2:
                raise EngineError('The fin engine failed on this part (%s: %s).'
                                  % (type(e).__name__, e or 'no message'))
    out = json.loads(raw)
    seated = array('f')
    seated.frombytes(base64.b64decode(out['triangles']))
    if sys.byteorder != 'little':
        seated.byteswap()
    off = out['offset']                 # seated = input + offset
    ox, oy, oz = off['x'], off['y'], off['z']
    fins = array('d', seated)
    for i in range(0, len(fins), 3):
        fins[i] -= ox
        fins[i + 1] -= oy
        fins[i + 2] -= oz
    return fins, out['stats']
