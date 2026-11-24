# -*- coding: utf-8 -*-
"""Simulate the client's gui.mods loader against the packaged .wotmod.

Replicates scripts/client/gui/mods/__init__.pyc:
  * scan gui/mods for 'mod_*' + '.pyc'
  * importlib.import_module('gui.mods.' + name)
  * call init(); send events; call fini()
"""
import os
import shutil
import sys
import types
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WOTMOD = os.path.join(HERE, 'build', 'akemi.streamermode_1.0.4.wotmod')
STAGE = os.path.join(HERE, 'build', '_install_sim')

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + repr(detail)) if detail and not cond else ''))


# --- stage the .wotmod as the game would mount it -------------------------
if os.path.isdir(STAGE):
    shutil.rmtree(STAGE)
os.makedirs(STAGE)
with zipfile.ZipFile(WOTMOD) as z:
    for n in z.namelist():
        # skip explicit directory entries (the package now ships them)
        if n.endswith('/'):
            continue
        if n.startswith('res/'):
            dest = os.path.join(STAGE, n[4:])
            d = os.path.dirname(dest)
            if not os.path.isdir(d):
                os.makedirs(d)
            with open(dest, 'wb') as fh:
                fh.write(z.read(n))
        elif n == 'meta.xml':
            with open(os.path.join(STAGE, 'meta.xml'), 'wb') as fh:
                fh.write(z.read(n))

MODS_DIR = os.path.join(STAGE, 'scripts', 'client', 'gui', 'mods')
check('mod_*.pyc staged under gui/mods',
      os.path.isfile(os.path.join(MODS_DIR, 'mod_streamer_mode.pyc')))

# --- stub the client so the mod can import -------------------------------
class _ArenaVos(object):
    class PlayerInfoVO(object):
        def getPlayerLabel(self):
            return 'Real'

        def getPlayerFakeLabel(self):
            return ''

    class VehicleArenaInfoVO(object):
        def getDisplayedName(self, name=None):
            return name


class _PlayerFormat(object):
    class PlayerFullNameFormatter(object):
        def format(self, vInfoVO, playerName=None):
            return playerName


class _BrPlayers(object):
    class PlayerInfo(object):
        @property
        def realName(self):
            return 'Real'

# place stubs on the path so the mod's imports resolve
pkg_root = os.path.join(STAGE, 'scripts', 'client')
sys.path.insert(0, pkg_root)

import imp  # noqa: E402

for name, obj in (
        ('gui', types.ModuleType('gui')),
        ('gui.battle_control', types.ModuleType('gui.battle_control')),
        ('gui.battle_control.arena_info', types.ModuleType('gui.battle_control.arena_info')),
        ('gui.battle_results', types.ModuleType('gui.battle_results')),
        ('gui.battle_results.reusable', types.ModuleType('gui.battle_results.reusable')),
):
    obj.__path__ = []
    sys.modules[name] = obj

av = types.ModuleType('gui.battle_control.arena_info.arena_vos')
av.PlayerInfoVO = _ArenaVos.PlayerInfoVO
av.VehicleArenaInfoVO = _ArenaVos.VehicleArenaInfoVO
sys.modules[av.__name__] = av

pf = types.ModuleType('gui.battle_control.arena_info.player_format')
pf.PlayerFullNameFormatter = _PlayerFormat.PlayerFullNameFormatter
pf._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16,
                                 'REGION': 256})
pf._PLAYER_FULL_NAME_FORMATS = {}
sys.modules[pf.__name__] = pf

brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = _BrPlayers.PlayerInfo
sys.modules[brp.__name__] = brp

bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

# --- replicate gui.mods loader -------------------------------------------
import importlib  # noqa: E402


def is_valid_mod(script_name, postfix='.pyc'):
    return script_name.startswith('mod_') and script_name.endswith(postfix)


found = [f for f in os.listdir(MODS_DIR) if is_valid_mod(f.lower())]
check('client loader would find exactly 1 mod', len(found) == 1, found)

gui = sys.modules['gui']
gui.__path__ = [os.path.join(pkg_root, 'gui')]
mods_pkg = types.ModuleType('gui.mods')
mods_pkg.__path__ = [MODS_DIR]
mods_pkg.__package__ = 'gui.mods'
sys.modules['gui.mods'] = mods_pkg
gui.mods = mods_pkg

loaded = {}
for script_name in found:
    moduleName = '%s.%s' % ('gui.mods', script_name.replace('.pyc', ''))
    try:
        loaded[moduleName] = importlib.import_module(moduleName)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check('import %s' % moduleName, False, e)

check('module imported', len(loaded) == 1, list(loaded))

if loaded:
    mod = list(loaded.values())[0]
    check('has init()', callable(getattr(mod, 'init', None)))
    check('has fini()', callable(getattr(mod, 'fini', None)))
    try:
        mod.init()
        check('init() ran without raising', True)
        # send the event the game fires on battle entry
        for ev in ('onAvatarBecomePlayer',):
            fn = getattr(mod, ev, None)
            if fn:
                fn()
        check('onAvatarBecomePlayer ran without raising', True)
        # and the anonymiser actually masks a name
        vo = _ArenaVos.PlayerInfoVO()
        vo.accountDBID = 4242
        vo.avatarSessionID = 'sess'
        vo.name = 'SomeStranger'
        vo.clanAbbrev = ''
        vo.fakeName = ''
        label = vo.getPlayerLabel()
        check('name anonymised after loader init', label != 'SomeStranger', label)
        mod.fini()
        check('fini() ran without raising', True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check('lifecycle ran cleanly', False, e)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)
