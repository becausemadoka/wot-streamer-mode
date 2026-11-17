# -*- coding: utf-8 -*-
"""Locate a usable CPython 2.7 interpreter.

Why this exists: the client's bytecode is CPython 2.7 (magic 03f30d0a), so the
build MUST compile with a real 2.7 -- a 3.x compile produces bytecode the game
cannot load.  The old build scripts hardcoded C:\\Python27\\python.exe, which
breaks as soon as the machine uses a different layout or the py launcher.

Resolution order (first hit wins):
  1. $WOT_PY27                      -- explicit override, full path to python.exe
  2. py -2.7                        -- the Windows py launcher
  3. a few conventional install paths

Exposes:
  PY27_CMD  -- list usable as a command prefix, e.g. ['py', '-2.7']
               or ['C:\\Python27\\python.exe']
  describe() -- human readable description for build logs

Import from build.py / build_internal.py.  Pure stdlib, works on py2 and py3.
"""
from __future__ import print_function

import os
import shutil
import subprocess

_CANDIDATE_FILES = [
    r'C:\Python27\python.exe',
    r'C:\Python27\pythonw.exe',
    r'D:\Python27\python.exe',
    r'C:\Python2.7\python.exe',
    r'C:\Program Files\Python27\python.exe',
    r'C:\Program Files (x86)\Python27\python.exe',
]


def _which(name):
    """shutil.which is 3.3+; implement a small py2/py3 compatible version."""
    try:
        from shutil import which as _w
        return _w(name)
    except Exception:
        pass
    exts = ['']
    if os.name == 'nt':
        exts = ['.exe', '.bat', '.cmd', '']
    for folder in os.environ.get('PATH', '').split(os.pathsep):
        if not folder:
            continue
        for ext in exts:
            candidate = os.path.join(folder, name + ext)
            if os.path.isfile(candidate):
                return candidate
    return None


def _works(cmd):
    """True when `cmd` runs and reports Python 2.7."""
    try:
        proc = subprocess.Popen(
            list(cmd) + ['-c', 'import sys; print(sys.version_info[0])'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _err = proc.communicate()
        if proc.returncode != 0:
            return False
        text = out.decode('ascii', 'replace').strip() if isinstance(out, bytes) else str(out).strip()
        return text.splitlines()[-1].strip() == '2'
    except Exception:
        return False


def _resolve():
    env = os.environ.get('WOT_PY27')
    if env:
        return [env], 'WOT_PY27=%s' % env

    launcher = _which('py')
    if launcher:
        if _works([launcher, '-2.7']):
            return [launcher, '-2.7'], 'py launcher (-2.7)'

    for path in _CANDIDATE_FILES:
        if os.path.isfile(path) and _works([path]):
            return [path], path

    return None, None


PY27_CMD, PY27_SOURCE = _resolve()
PY27_AVAILABLE = PY27_CMD is not None


def describe():
    if PY27_AVAILABLE:
        return 'CPython 2.7 via %s' % PY27_SOURCE
    return 'CPython 2.7 NOT FOUND (set WOT_PY27 to python.exe, or install 2.7)'


def require():
    """Exit with a clear message when 2.7 is missing."""
    if not PY27_AVAILABLE:
        raise SystemExit(
            'ERROR: %s\n'
            'The client runs CPython 2.7 bytecode, so a 2.7 interpreter is a hard\n'
            'requirement.  Install Python 2.7 and/or set WOT_PY27 to its python.exe.'
            % describe())
    return PY27_CMD


if __name__ == '__main__':
    print(describe())
    if PY27_AVAILABLE:
        subprocess.call(list(PY27_CMD) + ['-c', 'import sys; print(sys.version)'])
