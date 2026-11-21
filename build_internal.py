# -*- coding: utf-8 -*-
"""Build the VERSION-LOCKED internal test package.

Differences from build.py (the normal build):

  * The package is pinned to exactly one client version.  init() refuses to run
    on anything else, so the lock travels with the file instead of relying on
    which mods/<version>/ folder the user unzipped into.  See TARGET_VERSION in
    the source.
  * Output lands in `dist_internal/` next to this script -- deliberately NOT in
    the game folder.  Nothing here writes to World_of_Tanks_CN.
  * meta.xml is marked as an internal test build so it is obvious in a log or a
    mod list which artifact someone is running.

Usage:
    python build_internal.py
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, 'src')
WORK = os.path.join(HERE, 'build_internal')
DIST = os.path.join(HERE, 'dist_internal')
MOD_NAME = 'akemi.streamermode'
# Package filename version (<id>_<version>.wotmod).  Cosmetic only.
MOD_VERSION = '1.0.3'
# The CLIENT version this internal build is pinned to.  Unlike MOD_VERSION this
# IS functional: it is baked into the bytecode and init() refuses to run on any
# other client version.
PINNED_VERSION = '2.4.1.0'

# CPython 2.7 is a hard requirement (magic 03f30d0a); located via py27_env.py.
import py27_env
PY27_CMD = py27_env.require()

SOURCES = ['mod_streamer_mode.py', 'streamer_mode_settings.py']

# Internal builds get a distinct id suffix in meta.xml, so a log line or a mod
# manager entry makes it obvious this is not the public package.
META_XML = """<root>
    <id>{mod}</id>
    <version>{modver}-internal</version>
    <name>Streamer Mode (internal test, {ver} only)</name>
    <description>INTERNAL TEST BUILD. Works ONLY on World of Tanks {ver}. On any other client version the mod disables itself completely. Anonymises strangers' nicknames, clan tags and badges in battle; friends, clanmates, platoon mates and yourself keep real names.</description>
</root>
"""

README_MARKER = """INTERNAL TEST BUILD -- pinned to World of Tanks {ver}
================================================================

This package REFUSES to run on any other client version.  If the game updates
(e.g. to {ver_next}) the mod stays completely inert: it installs no hooks and
prints one line to the client log:

    [StreamerMode] DISABLED: this build is locked to client {ver}, running <x.y.z>

Install (only on {ver}):
    copy  mods\\{ver}\\{name}   ->  <game>\\mods\\{ver}\\

The version folder alone is not what enforces the lock -- the check runs inside
init(), so copying this file into a newer mods/ folder still will not activate
it.  Delete the file (or the whole folder) to remove it.
"""


def fail(message):
    sys.stderr.write('ERROR: %s\n' % message)
    raise SystemExit(1)


def clean():
    for path in (WORK, DIST):
        if os.path.isdir(path):
            shutil.rmtree(path)
    os.makedirs(WORK)
    os.makedirs(DIST)


def check_source_is_pinned():
    """The gate machinery has to exist in the source before we pin anything."""
    src = open(os.path.join(SRC_DIR, 'mod_streamer_mode.py'), 'rb').read()
    missing = []
    for needle in (b"TARGET_VERSION = ''",
                   b'def versionIsSupported(',
                   b'def runningClientVersion(',
                   b'def parseClientVersion('):
        if needle not in src:
            missing.append(needle.decode())
    if missing:
        fail('version lock machinery absent from source: %s'
             % ', '.join(missing))


def write_pinned_source(src_name, out_src):
    """Copy a source file, injecting the pinned TARGET_VERSION.

    The source ships with TARGET_VERSION = '' (no lock) so the normal build and
    the regular test suites stay unlocked.  The internal build is the only thing
    that turns the lock on, by rewriting that one constant in a TEMPORARY copy --
    the checked-in source is never modified.
    """
    src_path = os.path.join(SRC_DIR, src_name)
    text = open(src_path, 'rb').read()
    if src_name == 'mod_streamer_mode.py':
        needle = b"TARGET_VERSION = ''"
        if needle not in text:
            fail("cannot find the TARGET_VERSION placeholder in %s" % src_name)
        text = text.replace(needle,
                            b"TARGET_VERSION = '" +
                            PINNED_VERSION.encode('ascii') + b"'", 1)
    with open(out_src, 'wb') as fh:
        fh.write(text)
    return out_src


def compile_mod(src_name):
    """Compile the PINNED copy, so the lock is baked into the bytecode."""
    out = os.path.join(WORK, src_name.replace('.py', '.pyc'))
    if not os.path.isfile(os.path.join(SRC_DIR, src_name)):
        fail('missing source %s' % src_name)

    pinned_src = write_pinned_source(
        src_name, os.path.join(WORK, '_pinned_' + src_name))
    proc = subprocess.run(
        PY27_CMD + ['-c',
                    'import py_compile,sys;'
                    'py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)',
                    pinned_src, out],
        capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout.decode('utf-8', 'replace'))
        sys.stderr.write(proc.stderr.decode('utf-8', 'replace'))
        fail('compile failed: %s' % src_name)
    return out


def check_bytecode(path):
    """Confirm the magic number and that CPython 2.7 can actually load it.

    The build runs under Python 3, whose `marshal` cannot read 2.7 bytecode, so
    the deserialisation check runs in a 2.7 subprocess -- the interpreter that
    just compiled the file.
    """
    raw = open(path, 'rb').read()
    magic = raw[:4].hex()
    if magic != '03f30d0a':
        fail('unexpected magic %s (want 03f30d0a = Python 2.7)' % magic)

    probe = (
        'import marshal, sys, types\n'
        'raw = open(sys.argv[1], "rb").read()\n'
        'code = marshal.loads(raw[8:])\n'
        'assert isinstance(code, types.CodeType), "not a code object"\n'
        'names = []\n'
        'def walk(c):\n'
        '    names.append(c.co_name)\n'
        '    for k in c.co_consts:\n'
        '        if isinstance(k, types.CodeType):\n'
        '            walk(k)\n'
        'walk(code)\n'
        'sys.stdout.write("\\n".join(names))\n'
    )
    r = subprocess.run(PY27_CMD + ['-c', probe, path], capture_output=True)
    if r.returncode != 0:
        fail('%s cannot be loaded under Python 2.7: %s'
             % (os.path.basename(path),
                r.stderr.decode('utf-8', 'replace').strip()))
    names = [n for n in r.stdout.decode('utf-8', 'replace').splitlines() if n]
    return magic, 8, names


def package(pyc_paths, out_path):
    """Write the .wotmod: every entry ZIP_STORED, with explicit dir records."""
    members = [('meta.xml',
                META_XML.format(mod=MOD_NAME, modver=MOD_VERSION,
                                ver=PINNED_VERSION).encode('utf-8'))]
    for pyc in pyc_paths:
        members.append(('res/scripts/client/gui/mods/' + os.path.basename(pyc),
                        open(pyc, 'rb').read()))
    members.append(('res/mods/%s/text/en.yml' % MOD_NAME,
                    ('mod.%s.name: Streamer Mode\n' % MOD_NAME).encode('utf-8')))

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_STORED) as z:
        seen = set()
        for name, data in members:
            parts = name.split('/')[:-1]
            for i in range(len(parts)):
                d = '/'.join(parts[:i + 1]) + '/'
                if d not in seen:
                    seen.add(d)
                    zi = zipfile.ZipInfo(d)
                    zi.compress_type = zipfile.ZIP_STORED
                    zi.external_attr = 0o40755 << 16 | 0x10
                    z.writestr(zi, b'')
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, data)
    return out_path


def verify_package(path):
    """Everything the game's loader demands, plus the version-lock markers."""
    problems = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                problems.append('%s is compressed' % info.filename)
        names = z.namelist()
        if 'meta.xml' not in names:
            problems.append('meta.xml missing from package root')
        mods = [n for n in names
                if n.startswith('res/scripts/client/gui/mods/mod_')
                and n.endswith('.pyc')]
        if len(mods) != 1:
            problems.append('expected exactly one mod_*.pyc, found %d' % len(mods))
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(z.read('meta.xml').decode('utf-8'))
        except Exception as exc:
            problems.append('meta.xml invalid: %s' % exc)

        for info in z.infolist():
            if info.filename.endswith('.pyc'):
                raw = z.read(info.filename)
                if raw[:4].hex() != '03f30d0a':
                    problems.append('%s wrong magic %s'
                                    % (info.filename, raw[:4].hex()))
                # the pin must be INSIDE the shipped bytecode
                if info.filename.endswith('mod_streamer_mode.pyc'):
                    for needle in (b'2.4.1.0', b'DISABLED: this build is locked'):
                        if needle not in raw:
                            problems.append(
                                'version lock string missing from shipped pyc: %r'
                                % needle)
    return problems


def write_readme(dist_dir):
    path = os.path.join(dist_dir, 'READ-ME-FIRST.txt')
    with open(path, 'w') as fh:
        fh.write(README_MARKER.format(
            ver=PINNED_VERSION,
            ver_next='2.4.1.1',
            name='%s_%s.wotmod' % (MOD_NAME, MOD_VERSION)))
        fh.write('\nFile list\n---------\n')
        for entry in sorted(os.listdir(dist_dir)):
            fh.write('  %s\n' % entry)
    return path


def main():
    clean()
    check_source_is_pinned()

    pycs = []
    for src_name in SOURCES:
        pyc = compile_mod(src_name)
        magic, off, names = check_bytecode(pyc)
        pycs.append(pyc)
        print('compiled %s  magic=%s code_objects=%d'
              % (os.path.basename(pyc), magic, len(names)))
        if src_name == 'mod_streamer_mode.py':
            for needed in ('init', 'fini', 'onAvatarBecomePlayer',
                           'onAvatarBecomeNonPlayer', 'versionIsSupported'):
                if needed not in names:
                    fail('missing code object %s' % needed)

    mod_dir = os.path.join(DIST, 'mods', PINNED_VERSION)
    os.makedirs(mod_dir)
    wotmod = os.path.join(mod_dir, '%s_%s.wotmod' % (MOD_NAME, MOD_VERSION))
    package(pycs, wotmod)

    problems = verify_package(wotmod)
    if problems:
        for p in problems:
            print('  PACKAGE PROBLEM: %s' % p)
        fail('package would not load, or the lock is not embedded')

    cfg_dir = os.path.join(DIST, 'mods', 'configs', MOD_NAME)
    os.makedirs(cfg_dir)
    import importlib.util as _u
    spec = _u.spec_from_file_location('b', os.path.join(HERE, 'build.py'))
    build_mod = _u.module_from_spec(spec)
    spec.loader.exec_module(build_mod)
    with open(os.path.join(cfg_dir, 'config.json'), 'w') as fh:
        fh.write(json.dumps(build_mod.default_config(), indent=2,
                            sort_keys=True))

    readme = write_readme(DIST)

    print()
    print('INTERNAL BUILD (pinned to %s) written to:' % PINNED_VERSION)
    for root, _dirs, files in os.walk(DIST):
        for f in sorted(files):
            full = os.path.join(root, f)
            print('  %-56s %7d  %s'
                  % (os.path.relpath(full, DIST), os.path.getsize(full),
                     os.path.basename(readme) if f.startswith('READ-') else ''))
    print()
    print('Nothing was written to the game directory.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
