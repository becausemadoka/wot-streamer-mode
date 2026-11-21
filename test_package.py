# -*- coding: utf-8 -*-
"""Replicate the game package loader's checks to prove the package is loadable.

The client logged: "load error: compression not supported".  Its loader (per the
official package doc) is a ZIP reader that:
  * rejects any entry whose compression method is not STORED
  * needs meta.xml at the package root
  * relies on ZIPDIRENTRY/ZIPFILERECORD structures
  * then mounts res/ and executes res/scripts/client/gui/mods/mod_*.pyc

We check the first three here, and compare against a mod the game demonstrably
loads ('...wotmod loaded' in game.log).
"""
import os
import struct
import zipfile

# Optional: a real client install, used only to compare against third-party
# packages the game already loads.  Set WOT_GAME to enable that comparison; the
# main checks below run without it, so this test works on a clean checkout.
GAME = os.environ.get("WOT_GAME")
HERE = os.path.dirname(os.path.abspath(__file__))

# Default target: the package we just built.  Deliberately NOT the copy installed
# into the game, so this test runs on a clean checkout without installing
# anything.  Override with WOT_MOD=<path> to check a specific file.
DEFAULT_MINE = os.path.join(HERE, "build", "akemi.streamermode_1.0.3.wotmod")


def _mine():
    return os.environ.get("WOT_MOD") or DEFAULT_MINE


def _known_good_samples():
    """Any third-party .wotmod already present in the game, as reference points.

    The mods folder is named after the client version, so look for whatever
    public-ip-* directory exists instead of hardcoding one (it changed once
    already: rjvbjboi -> gmhujdqi).
    """
    samples = []
    if not GAME:
        return samples
    mods_root = os.path.join(GAME, "mods")
    if not os.path.isdir(mods_root):
        return samples
    for entry in sorted(os.listdir(mods_root)):
        folder = os.path.join(mods_root, entry)
        if not os.path.isdir(folder) or not entry.startswith("public-ip-"):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".wotmod") and not name.startswith("akemi.streamermode"):
                samples.append(("working: %s" % name, os.path.join(folder, name)))
                if len(samples) >= 2:
                    return samples
    return samples


CANDIDATES = [("MINE", _mine())] + _known_good_samples()

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + repr(detail)) if detail and not cond else ''))


def raw_local_headers(path):
    """Scan local file headers (PK\\x03\\x04) and report compression methods."""
    methods = []
    with open(path, 'rb') as fh:
        data = fh.read()
    i = 0
    while True:
        i = data.find(b'PK\x03\x04', i)
        if i < 0:
            break
        # local header: sig(4) ver(2) flags(2) method(2) ...
        method = struct.unpack_from('<H', data, i + 8)[0]
        nlen = struct.unpack_from('<H', data, i + 26)[0]
        name = data[i + 30:i + 30 + nlen].decode('utf-8', 'replace')
        methods.append((name, method))
        i += 4
    return methods


print('=' * 72)
print('comparison of on-disk package structure')
print('=' * 72)

for label, path in CANDIDATES:
    if not os.path.isfile(path):
        print('%-40s MISSING' % label)
        continue
    print()
    print('%s' % label)
    print('  file: %s' % os.path.basename(path))
    methods = raw_local_headers(path)
    nonstored = [(n, m) for n, m in methods if m != 0]
    print('  entries: %d   non-STORED: %d' % (len(methods), len(nonstored)))
    if nonstored:
        for n, m in nonstored:
            print('     !! %s method=%d' % (n, m))

print()
print('=' * 72)
print('assertions on MY package')
print('=' * 72)
mine = CANDIDATES[0][1]
with zipfile.ZipFile(mine) as z:
    infos = z.infolist()

    check('every entry is ZIP_STORED (else "compression not supported")',
          all(i.compress_type == zipfile.ZIP_STORED for i in infos),
          [(i.filename, i.compress_type) for i in infos
           if i.compress_type != zipfile.ZIP_STORED])

    check('no data-descriptor flag on entries (loader reads sizes up front)',
          all(not (i.flag_bits & 0x08) for i in infos),
          [(i.filename, hex(i.flag_bits)) for i in infos if i.flag_bits & 0x08])

    check('meta.xml at package root', 'meta.xml' in z.namelist())

    mod_pyc = [n for n in z.namelist()
               if n.startswith('res/scripts/client/gui/mods/mod_')
               and n.endswith('.pyc')]
    check('exactly one gui/mods/mod_*.pyc', len(mod_pyc) == 1, mod_pyc)

    check('parent directories present as explicit entries',
          all(p + '/' in z.namelist() for p in
              ['res', 'res/scripts', 'res/scripts/client', 'res/scripts/client/gui',
               'res/scripts/client/gui/mods']),
          [n for n in z.namelist() if n.endswith('/')])

    import binascii
    raw = z.read(mod_pyc[0])
    magic = raw[:4]
    if not isinstance(magic, bytes):
        magic = magic.encode('latin-1')
    magic_hex = binascii.hexlify(magic).decode('ascii')
    check('pyc magic is Python 2.7 (03f30d0a)', magic_hex == '03f30d0a', magic_hex)

    # the class-body check: make sure it loads the way the game would
    import marshal
    try:
        code = marshal.loads(raw[8:])
        entry = {c.co_name for c in code.co_consts if hasattr(c, 'co_code')}
        check('loads and defines init/fini',
              'init' in entry and 'fini' in entry, sorted(entry)[:10])
    except Exception as e:
        check('loads and defines init/fini', False, e)

    check('meta.xml mentions the mod id',
          b'akemi.streamermode' in z.read('meta.xml'))

print()
print('=' * 72)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
