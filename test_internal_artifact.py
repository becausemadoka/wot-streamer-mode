# -*- coding: utf-8 -*-
"""End-to-end check of the SHIPPED internal package.

test_version_lock.py works on the unlocked build (build/), which is the normal
public artifact.  This file does the opposite: it loads the bytecode that actually
sits inside dist_internal/*.wotmod and proves the lock is baked in and effective.

If this test passes, the artifact we hand out really does refuse to run on
2.4.1.1 -- it is not just "the source has a check somewhere".

Python 2.7.
"""
import os
import sys
import zipfile
import marshal
import struct
import types
import imp

HERE = os.path.dirname(os.path.abspath(__file__))
WOTMOD = os.path.join(HERE, 'dist_internal', 'mods', '2.4.1.0',
                      'akemi.streamermode_1.0.3.wotmod')

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + repr(detail)) if detail and not cond else ''))


if not os.path.isfile(WOTMOD):
    print('missing %s -- run build_internal.py first' % WOTMOD)
    sys.exit(1)

print()
print('=== artifact contents ===')
z = zipfile.ZipFile(WOTMOD)
names = z.namelist()
check('package exists', True)
check('meta.xml at root', 'meta.xml' in names)
check('exactly one mod_*.pyc',
      len([n for n in names
           if n.startswith('res/scripts/client/gui/mods/mod_')]) == 1, names)
check('every entry STORED',
      all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist()))

meta = z.read('meta.xml').decode('utf-8')
check('meta marks it internal', 'internal' in meta.lower(), meta)
check('meta names the pinned version', '2.4.1.0' in meta, meta)

print()
print('=== the lock is baked into the shipped bytecode ===')
raw = z.read('res/scripts/client/gui/mods/mod_streamer_mode.pyc')
# in Python 2 zipfile returns str, which has no .hex()
magic = struct.unpack('<I', raw[:4])[0]
check('pyc magic is 2.7', magic == 0x0a0df303, hex(magic))
module_code = marshal.loads(raw[8:])
strings = [c for c in module_code.co_consts if isinstance(c, str)]
check("TARGET_VERSION is '2.4.1.0' in the artifact", '2.4.1.0' in strings,
      [s for s in strings if s and '.' in s][:6])

# The refusal string is a constant of init(), not of the module body, so search
# the nested code objects too.
def all_consts(code, out):
    out.append(code)
    for k in code.co_consts:
        if hasattr(k, 'co_code'):
            all_consts(k, out)
    return out


every = []
for code in all_consts(module_code, []):
    every.extend([c for c in code.co_consts if isinstance(c, str)])
check('refusal message shipped',
      any('DISABLED: this build is locked' in s for s in every),
      [s for s in every if 'DISABLED' in s][:3])

print()
print('=== load the artifact module and exercise the gate ===')
# Minimal client stubs so the artifact can be imported.
class PlayerInfoVO(object):
    def __init__(self, accountDBID=None, avatarSessionID=None, name='',
                 clanAbbrev=''):
        self.accountDBID = accountDBID
        self.avatarSessionID = avatarSessionID
        self.name = name
        self.clanAbbrev = clanAbbrev

    @property
    def isBot(self):
        return not self.avatarSessionID

    def getPlayerLabel(self):
        return self.name or 'Unknown'

    def getPlayerFakeLabel(self):
        return ''


class VehicleArenaInfoVO(object):
    def __init__(self, vehicleID=0, player=None):
        self.vehicleID = vehicleID
        self.player = player
        self._prefixBadge = 0
        self._suffixBadge = 0

    @property
    def selectedBadge(self):
        return self._prefixBadge

    @property
    def selectedSuffixBadge(self):
        return self._suffixBadge

    def getBadgeExtraInfo(self):
        return ('', '')

    def getDisplayedName(self, name=None):
        return 'T-54' if name is None else name


class PlayerFullNameFormatter(object):
    def format(self, vInfoVO, playerName=None):
        import collections
        R = collections.namedtuple('R', 'playerFullName playerName '
                                        'playerFakeName clanAbbrev regionCode '
                                        'vehicleName')
        return R(playerName, playerName, '', '', '', '')


av = types.ModuleType('gui.battle_control.arena_info.arena_vos')
av.PlayerInfoVO = PlayerInfoVO
av.VehicleArenaInfoVO = VehicleArenaInfoVO
pformat = types.ModuleType('gui.battle_control.arena_info.player_format')
pformat.PlayerFullNameFormatter = PlayerFullNameFormatter
pformat._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16})
pformat._PLAYER_FULL_NAME_FORMATS = {}

for name in ('gui', 'gui.battle_control', 'gui.battle_control.arena_info',
             'gui.battle_results', 'gui.battle_results.reusable',
             'gui.battle_results.components',
             'gui.battle_results.presenters',
             'gui.battle_results.presenters.packers',
             'gui.impl', 'gui.impl.battle', 'gui.impl.battle.battle_page',
             'gui.doc_loaders', 'gui.shared',
             'gui.Scaleform', 'gui.Scaleform.daapi', 'gui.Scaleform.daapi.view',
             'gui.Scaleform.daapi.view.battle',
             'gui.Scaleform.daapi.view.battle.shared',
             'gui.Scaleform.daapi.view.battle.shared.stats_exchange',
             'gui.Scaleform.daapi.view.lobby',
             'gui.Scaleform.daapi.view.lobby.profile'):
    m = types.ModuleType(name)
    m.__path__ = []
    sys.modules[name] = m
sys.modules['gui.battle_control.arena_info.arena_vos'] = av
sys.modules['gui.battle_control.arena_info.player_format'] = pformat
sys.modules['gui.battle_control.arena_info'].arena_vos = av
sys.modules['gui.battle_control.arena_info'].player_format = pformat

bl = types.ModuleType('gui.doc_loaders.badges_loader')
bl.getSelectedByLayout = lambda ids: (0, 0)
bl.getAvailableBadges = lambda: {}
sys.modules['gui.doc_loaders.badges_loader'] = bl
sys.modules['gui.doc_loaders'].badges_loader = bl
sb = types.ModuleType('gui.shared.badges')
sb.buildBadge = lambda bid, extra=None: None
sys.modules['gui.shared.badges'] = sb
sys.modules['gui.shared'].badges = sb
brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = type('P', (object,), {'realName': property(lambda s: 'R')})
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp
rav = types.ModuleType('gui.battle_results.reusable.avatars')
rav.AvatarInfo = type('AI', (object,), {})
rav.AvatarsInfo = type('AV', (object,), {})
sys.modules[rav.__name__] = rav
sys.modules['gui.battle_results.reusable'].avatars = rav
veh = types.ModuleType('gui.battle_results.components.vehicles')
veh.BadgeBlock = type('BB', (object,), {'setRecord': lambda s, r, u: None})
veh.RegularVehicleStatsBlock = type(
    'RV', (object,), {'setRecord': lambda s, r, u: None})
sys.modules[veh.__name__] = veh
sys.modules['gui.battle_results.components'].vehicles = veh
pk = types.ModuleType('gui.battle_results.presenters.packers.user_info')
pk.UserNames = type('UN', (object,), {})
sys.modules[pk.__name__] = pk
sys.modules['gui.battle_results.presenters.packers'].user_info = pk
pm = types.ModuleType(
    'gui.Scaleform.daapi.view.battle.shared.postmortem_panel')
pm.PostmortemPanel = type('PM', (object,), {})
sys.modules[pm.__name__] = pm
sys.modules['gui.Scaleform.daapi.view.battle.shared'].postmortem_panel = pm
tv = types.ModuleType('gui.impl.battle.battle_page.tab_view')
tv.TabView = type('TV', (object,), {})
sys.modules[tv.__name__] = tv
sys.modules['gui.impl.battle.battle_page'].tab_view = tv
se = types.ModuleType(
    'gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle')
se.VehicleInfoComponent = type('C', (object,), {'_data': {}})
sys.modules[se.__name__] = se
sys.modules['gui.Scaleform.daapi.view.battle.shared.stats_exchange'].vehicle = se
lc = types.ModuleType('gui.lobby_context')
lc.LobbyContext = type('LC', (object,), {})
sys.modules['gui.lobby_context'] = lc
pw = types.ModuleType(
    'gui.Scaleform.daapi.view.lobby.profile.ProfileWindow')
pw.ProfileWindow = type('PW', (object,), {})
sys.modules[pw.__name__] = pw

helpers = types.ModuleType('helpers')
helpers.getClientVersion = lambda force=False: ' v.2.4.1.0 #975 '
helpers.getShortClientVersion = lambda: ' v.2.4.1.0 '
helpers.getFullClientVersion = lambda: 'v.2.4.1.0 #975'
sys.modules['helpers'] = helpers

logs = []
bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: logs.append(('info', a))
bw.logError = lambda *a: logs.append(('error', a))
sys.modules['BigWorld'] = bw

# Load the artifact's bytecode from the zip (not from build/).
tmp = os.path.join(HERE, 'build_internal', '_from_artifact_mod.pyc')
open(tmp, 'wb').write(raw)
shipped = imp.load_compiled('shipped_mod', tmp)

check('shipped TARGET_VERSION is pinned', shipped.TARGET_VERSION == '2.4.1.0',
      shipped.TARGET_VERSION)
ok, running = shipped.versionIsSupported()
check('shipped build accepts 2.4.1.0', ok is True, running)

shipped.CONFIG._values.update({'enable': True, 'mode': 'label',
                               'namePrefix': 'Player_', 'botMode': 'botLabel',
                               'botPrefix': 'Bot_', 'hideClanTag': True,
                               'hideBotClanTag': True, 'hideResultsClanTag': True,
                               'hideBadges': True, 'hideBotBadges': True,
                               'badges.exemptKnown': True,
                               'showRealNamesInProfile': True,
                               'scope.inBattle': True,
                               'scope.battleResults': True})
shipped.IDENTITY.ownDBID = 1
shipped.IDENTITY.friendDBIDs = set()
shipped.IDENTITY.ownClanAbbrev = 'MYCLAN'
shipped.IDENTITY.squadmateDBIDs = set()

logs[:] = []
shipped.init()
check('shipped build activates on 2.4.1.0', shipped._ACTIVE is True,
      shipped._ACTIVE)
hooks_on_ok = len(shipped.INSTALLER._undos)
check('hooks installed on the pinned version', hooks_on_ok > 0, hooks_on_ok)
shipped.fini()

print()
print('=== the shipped artifact refuses 2.4.1.1 ===')
helpers.getClientVersion = lambda force=False: ' v.2.4.1.1 #976 '
helpers.getShortClientVersion = lambda: ' v.2.4.1.1 '
helpers.getFullClientVersion = lambda: 'v.2.4.1.1 #976'
ok, running = shipped.versionIsSupported()
check('shipped build rejects 2.4.1.1', ok is False, running)

logs[:] = []
shipped.init()
check('stays inactive on 2.4.1.1', shipped._ACTIVE is False, shipped._ACTIVE)
check('installs ZERO hooks on 2.4.1.1', len(shipped.INSTALLER._undos) == 0,
      len(shipped.INSTALLER._undos))
check('logs a DISABLED line', any(l[0] == 'error' for l in logs), logs)
text = ''.join(str(l[1]) for l in logs)
check('the log names both versions',
      '2.4.1.0' in text and '2.4.1.1' in text, text)

# and it must stay inert through the battle lifecycle events
shipped.onAvatarBecomePlayer()
shipped.onAvatarBecomeNonPlayer()
shipped.onAccountBecomePlayer()
check('battle events do not revive it', len(shipped.INSTALLER._undos) == 0,
      len(shipped.INSTALLER._undos))

os.remove(tmp)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)
