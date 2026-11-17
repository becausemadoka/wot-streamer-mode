"""Build akemi.streamermode.wotmod.

Usage: python build.py
"""
import json
import os
import py_compile
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, 'src')
BUILD = os.path.join(HERE, 'build')
MOD_NAME = 'akemi.streamermode'
# The mod's own version, used only in the package filename
# (<id>_<version>.wotmod).  It is NOT the game version and has nothing to do
# with where the file is installed: the client loads a package from whatever
# mods/<client version>/ folder the player puts it in, and reads the identity
# from meta.xml, not from the filename.
MOD_VERSION = '1.0'

# CPython 2.7 is required for bytecode compatibility (magic 03f30d0a).  Located
# by py27_env.py so this is not tied to C:\Python27 (that path broke once
# already).  PY27_CMD is a command PREFIX, e.g. ['py', '-2.7'].
import py27_env
PY27_CMD = py27_env.require()

# Modules that go into res/scripts/client/gui/mods/.
# The client auto-imports and runs every 'mod_*.pyc' it finds there, so only the
# entry point uses that prefix; the settings page is a plain module the entry
# point imports on demand.
SOURCES = ['mod_streamer_mode.py', 'streamer_mode_settings.py']

META_XML = """<root>
    <id>{mod}</id>
    <version>{ver}</version>
    <name>Streamer Mode</name>
    <description>Anonymises strangers' nicknames in battle. Friends, clanmates, platoon mates and yourself keep real names.</description>
</root>
"""


def clean():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD)


def compile_mod(src_name):
    """Compile one source with real Python 2.7 so the bytecode matches the client."""
    src = os.path.join(SRC_DIR, src_name)
    out = os.path.join(BUILD, src_name.replace('.py', '.pyc'))
    if not os.path.isfile(src):
        raise SystemExit('missing source %s' % src)
    r = subprocess.run(PY27_CMD + ['-c',
                                   'import py_compile,sys;'
                                   'py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)',
                                   src, out],
                       capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout.decode('utf-8', 'replace'))
        sys.stderr.write(r.stderr.decode('utf-8', 'replace'))
        raise SystemExit('compile failed: %s' % src_name)
    return out


def check_bytecode(path):
    """Confirm the magic number and that CPython 2.7 can actually load it.

    The build runs under Python 3, whose `marshal` cannot read 2.7 bytecode, so
    the deserialisation check is done in a 2.7 subprocess -- the same interpreter
    that compiled the file.  This keeps the verification real without depending
    on any external tooling.
    """
    raw = open(path, 'rb').read()
    magic = raw[:4].hex()
    if magic != '03f30d0a':
        raise SystemExit('unexpected magic %s (want 03f30d0a = Python 2.7)' % magic)

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
        raise SystemExit('%s cannot be loaded under Python 2.7: %s'
                         % (os.path.basename(path),
                            r.stderr.decode('utf-8', 'replace').strip()))
    names = [n for n in r.stdout.decode('utf-8', 'replace').splitlines() if n]
    return magic, 8, names


def default_config():
    return {
        "enable": True,
        "mode": "label",
        # Empty: the mod picks Player_ or 玩家_ from the client language.
        # Writing a concrete prefix here would pin every client to one language.
        "namePrefix": "",
        "botMode": "botLabel",
        "botPrefix": "Bot_",
        "hideBotClanTag": True,
        "exclude.ownName": True,
        "exclude.friendName": True,
        "exclude.clanmateName": True,
        "exclude.divmateName": True,
        "hideClanTag": True,
        "hideResultsClanTag": True,
        "hideBadges": True,
        "hideBotBadges": True,
        "badges.exemptKnown": True,
        "showRealNamesInProfile": True,
        "scope.inBattle": True,
        "scope.battleResults": True,
        "scope.playersPanel": True,
        "scope.minimap": True,
        "scope.messages": True,
        "scope.markers": True,
        "scope.postmortem": True
    }


def package(pyc_paths):
    """Build the .wotmod exactly as the game's loader requires.

    The WoT package loader REJECTS any deflate-compressed entry and logs
    "compression not supported" (verified against a real client).  Official
    docs are explicit: "a zip-archive ... no compression ... set the compression
    level to 'without compression' when creating archives".  Every working mod
    in a real mods folder is stored uncompressed.

    We therefore write every member with ZIP_STORED, and emit explicit
    directory entries the way 7-Zip does, since the loader is documented to
    rely on ZIPDIRENTRY/ZIPFILERECORD structures.
    """
    out = os.path.join(BUILD, '%s_%s.wotmod' % (MOD_NAME, MOD_VERSION))

    members = [('meta.xml',
                META_XML.format(mod=MOD_NAME, ver=MOD_VERSION).encode('utf-8'))]
    for pyc in pyc_paths:
        members.append(('res/scripts/client/gui/mods/' + os.path.basename(pyc),
                        open(pyc, 'rb').read()))
    members.append(('res/mods/%s/text/en.yml' % MOD_NAME,
                    ('mod.%s.name: Streamer Mode\n' % MOD_NAME).encode('utf-8')))

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
        seen_dirs = set()
        for name, data in members:
            # explicit directory entries for every parent, in order
            parts = name.split('/')[:-1]
            for i in range(len(parts)):
                d = '/'.join(parts[:i + 1]) + '/'
                if d not in seen_dirs:
                    seen_dirs.add(d)
                    zi = zipfile.ZipInfo(d)
                    zi.compress_type = zipfile.ZIP_STORED
                    zi.external_attr = 0o40755 << 16 | 0x10   # dir
                    z.writestr(zi, b'')
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, data)
    return out


def verify_package(path):
    """Assert the package can actually be loaded by the game."""
    problems = []
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            if i.compress_type != zipfile.ZIP_STORED:
                problems.append('%s is compressed (method=%d)'
                                % (i.filename, i.compress_type))
        names = z.namelist()
        if 'meta.xml' not in names:
            problems.append('meta.xml missing from package root')
        if not any(n.endswith('.pyc') and '/gui/mods/mod_' in n for n in names):
            problems.append('no res/scripts/client/gui/mods/mod_*.pyc')
        # the loader reads meta.xml first; bad XML would break the package
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(z.read('meta.xml').decode('utf-8'))
        except Exception as e:
            problems.append('meta.xml is not valid XML: %s' % e)
        # every stored pyc must be readable bytecode
        for i in z.infolist():
            if i.filename.endswith('.pyc'):
                raw = z.read(i.filename)
                if raw[:4].hex() != '03f30d0a':
                    problems.append('%s has wrong magic %s'
                                    % (i.filename, raw[:4].hex()))
    return problems


def main():
    clean()
    pycs = []
    for src_name in SOURCES:
        pyc = compile_mod(src_name)
        magic, off, names = check_bytecode(pyc)
        pycs.append(pyc)
        print('compiled %s' % os.path.basename(pyc))
        print('  magic=%s header=%d code_objects=%d' % (magic, off, len(names)))
        if src_name == 'mod_streamer_mode.py':
            print('  entry points present: %s'
                  % [n for n in ('init', 'fini', 'onAvatarBecomePlayer',
                                 'onAvatarBecomeNonPlayer') if n in names])
            missing = [n for n in ('init', 'fini') if n not in names]
            if missing:
                raise SystemExit('missing entry points: %s' % missing)

    # ship a default config as documentation of the knobs
    cfg_dir = os.path.join(BUILD, 'configs', MOD_NAME)
    os.makedirs(cfg_dir)
    with open(os.path.join(cfg_dir, 'config.json'), 'w') as fh:
        fh.write(json.dumps(default_config(), indent=2, sort_keys=True))

    wotmod = package(pycs)
    print('packaged %s (%d bytes)' % (os.path.basename(wotmod),
                                      os.path.getsize(wotmod)))

    problems = verify_package(wotmod)
    if problems:
        for p in problems:
            print('  PACKAGE PROBLEM: %s' % p)
        raise SystemExit('package would not load in game')

    with zipfile.ZipFile(wotmod) as z:
        print('  all entries ZIP_STORED, meta.xml valid, bytecode magic ok')
        for n in z.namelist():
            print('   %-58s %d' % (n, z.getinfo(n).file_size))
    return 0


if __name__ == '__main__':
    sys.exit(main())
