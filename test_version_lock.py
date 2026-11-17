# -*- coding: utf-8 -*-
"""Verify the version-lock MACHINERY.

Requirement: the internal build must work ONLY on 2.4.1.0, and go inert if the
client moves to 2.4.1.1.

Note on how this is tested.  The shipped source has TARGET_VERSION = '' (no
lock) so the normal public build and the behaviour suites stay unlocked; the
internal build is the only artifact with a pin, injected by build_internal.py.
So here we drive the machinery by ASSIGNING mod.TARGET_VERSION, which is exactly
what the pinned bytecode does by construction.  test_internal_artifact.py
separately proves the shipped artifact really carries the pin.

The client already refuses to load packages from mods/<other version>/, but that
is a property of the FOLDER.  A user who unzips the .wotmod into a newer
mods/2.4.1.1/ directory, or into res_mods by hand, would still have it imported.
So the lock lives in init(): on a mismatch we return before installing a hook.

Python 2.7.
"""
import os
import sys
import types
import imp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + repr(detail)) if detail and not cond else ''))


# ------------------------------------------------------------------ stubs --
def boom(force=False):
    raise RuntimeError('version.xml unavailable')


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
        self._prefixBadge = 101
        self._suffixBadge = 202

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


arena_vos = types.ModuleType('gui.battle_control.arena_info.arena_vos')
arena_vos.PlayerInfoVO = PlayerInfoVO
arena_vos.VehicleArenaInfoVO = VehicleArenaInfoVO
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
sys.modules['gui.battle_control.arena_info.arena_vos'] = arena_vos
sys.modules['gui.battle_control.arena_info.player_format'] = pformat
sys.modules['gui.battle_control.arena_info'].arena_vos = arena_vos
sys.modules['gui.battle_control.arena_info'].player_format = pformat

bl = types.ModuleType('gui.doc_loaders.badges_loader')
bl.getSelectedByLayout = lambda ids: (101, 202) if ids else (0, 0)
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

av = types.ModuleType('gui.battle_results.reusable.avatars')
av.AvatarInfo = type('AI', (object,), {})
av.AvatarsInfo = type('AV', (object,), {})
sys.modules[av.__name__] = av
sys.modules['gui.battle_results.reusable'].avatars = av

veh = types.ModuleType('gui.battle_results.components.vehicles')
veh.BadgeBlock = type('BB', (object,), {'setRecord': lambda self, r, u: None})
veh.RegularVehicleStatsBlock = type(
    'RV', (object,), {'setRecord': lambda self, r, u: None})
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

# `helpers` -- the client's own version accessor.  getClientVersion() returns the
# RAW string from version.xml, spaces and build number included.
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

# ------------------------------------------------------------------- load --
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))

print()
print('=== the shipped source is UNLOCKED by default ===')
check('TARGET_VERSION is empty in the public build',
      mod.TARGET_VERSION == '', mod.TARGET_VERSION)
ok, running = mod.versionIsSupported()
check('empty pin means "no lock"', ok is True, running)

print()
print('=== a matching client runs ===')
# turn the pin on, which is what build_internal.py bakes into the artifact
mod.TARGET_VERSION = '2.4.1.0'
check('pinned to 2.4.1.0', mod.TARGET_VERSION == '2.4.1.0', mod.TARGET_VERSION)

print()
print('=== version string parsing ===')
cases = [
    # (raw, expected)
    (' v.2.4.1.0 #975 ', (2, 4, 1, 0)),
    ('v.2.4.1.0 #975', (2, 4, 1, 0)),
    ('2.4.1.0', (2, 4, 1, 0)),
    (' v.2.4.1.1 #976 ', (2, 4, 1, 1)),
    ('v.2.4.2 #1000', (2, 4, 2)),
    ('v2.5', (2, 5)),
    ('  v.2.4.1.0  ', (2, 4, 1, 0)),
    ('', None),
    ('garbage', None),
    (None, None),
]
for raw, expected in cases:
    got = mod.parseClientVersion(raw)
    check('parse %r -> %r' % (raw, expected), got == expected, got)

print()
print('=== a matching client runs ===')
mod.CONFIG._values.update({'enable': True, 'mode': 'label', 'namePrefix': 'Player_',
                           'botMode': 'botLabel', 'botPrefix': 'Bot_',
                           'hideClanTag': True, 'hideBotClanTag': True,
                           'hideResultsClanTag': True, 'hideBadges': True,
                           'hideBotBadges': True, 'badges.exemptKnown': True,
                           'showRealNamesInProfile': True,
                           'scope.inBattle': True, 'scope.battleResults': True})
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set()
mod.IDENTITY.ownClanAbbrev = 'MYCLAN'
mod.IDENTITY.squadmateDBIDs = set()

ok, running = mod.versionIsSupported()
check('2.4.1.0 is supported', ok is True, running)
check('running version parsed', running == (2, 4, 1, 0), running)

logs[:] = []
mod.init()
check('mod became active', mod._ACTIVE is True, mod._ACTIVE)
check('hooks were installed', mod.INSTALLER._installed is True,
      mod.INSTALLER._installed)
check('hooks list is non-empty', len(mod.INSTALLER._undos) > 0,
      len(mod.INSTALLER._undos))
hooked = len(mod.INSTALLER._undos)

print()
print('=== 2.4.1.1 must be refused, and install NOTHING ===')
mod.fini()
check('clean uninstall', mod._ACTIVE is False and len(mod.INSTALLER._undos) == 0,
      (mod._ACTIVE, len(mod.INSTALLER._undos)))

helpers.getClientVersion = lambda force=False: ' v.2.4.1.1 #976 '
ok, running = mod.versionIsSupported()
check('2.4.1.1 is not supported', ok is False, running)
check('running version is 2.4.1.1', running == (2, 4, 1, 1), running)

logs[:] = []
mod.init()
check('mod stayed inactive', mod._ACTIVE is False, mod._ACTIVE)
check('no hooks installed', mod.INSTALLER._installed is False,
      mod.INSTALLER._installed)
check('no undo callables', len(mod.INSTALLER._undos) == 0,
      len(mod.INSTALLER._undos))
check('a REFUSED line was logged', any(l[0] == 'error' for l in logs),
      logs)
refused = ''.join(str(l[1]) for l in logs)
check('log names both versions',
      '2.4.1.0' in refused and '2.4.1.1' in refused, refused)

print()
print('=== other versions are also refused ===')
for raw, label in ((' v.2.4.2.0 #1000 ', '2.4.2.0'),
                   (' v.2.5.0.0 #1 ', '2.5.0.0'),
                   (' v.2.4.0.2 #900 ', '2.4.0.2 (older)')):
    helpers.getClientVersion = lambda force=False, r=raw: r
    ok, running = mod.versionIsSupported()
    check('%s refused' % label, ok is False, running)

print()
print('=== an unreadable version is refused (fail closed) ===')
# NOTE: runningClientVersion() deliberately tries several accessors, so all of
# them have to be broken for the version to be genuinely unknown.
helpers.getClientVersion = lambda force=False: 'nonsense'
helpers.getShortClientVersion = lambda: 'nonsense'
helpers.getFullClientVersion = lambda: 'nonsense'
ok, running = mod.versionIsSupported()
check('unparseable version refused', ok is False, running)

helpers.getClientVersion = lambda force=False: None
helpers.getShortClientVersion = lambda: None
helpers.getFullClientVersion = lambda: None
ok, running = mod.versionIsSupported()
check('missing version refused', ok is False, running)

print()
print('=== a fallback accessor still pins correctly ===')
# getClientVersion broken but the short form fine -> must still gate correctly
helpers.getClientVersion = lambda force=False: 'nonsense'
helpers.getShortClientVersion = lambda: ' v.2.4.1.0 '
helpers.getFullClientVersion = lambda: 'nonsense'
ok, running = mod.versionIsSupported()
check('falls back to the short accessor', ok is True and running == (2, 4, 1, 0),
      (ok, running))

helpers.getShortClientVersion = lambda: ' v.2.4.1.1 '
ok, running = mod.versionIsSupported()
check('fallback also refuses a newer client', ok is False, running)

helpers.getClientVersion = boom
helpers.getShortClientVersion = boom
helpers.getFullClientVersion = boom
ok, running = mod.versionIsSupported()
check('raising version accessor refused', ok is False, running)

print()
print('=== every entry point is inert while disabled ===')
# still pointing at a raising accessor; _ACTIVE must remain False
mod._ACTIVE = False
before = len(logs)
mod.onAvatarBecomePlayer()
mod.onAvatarBecomeNonPlayer()
mod.onAccountBecomePlayer()
mod.fini()
check('battle events did not activate anything', mod._ACTIVE is False,
      mod._ACTIVE)
check('no hooks after battle events', len(mod.INSTALLER._undos) == 0,
      len(mod.INSTALLER._undos))

print()
print('=== and 2.4.1.0 works again afterwards ===')
helpers.getClientVersion = lambda force=False: ' v.2.4.1.0 #975 '
mod.init()
check('re-activates on the pinned version', mod._ACTIVE is True, mod._ACTIVE)
check('installs the same hook count', len(mod.INSTALLER._undos) == hooked,
      (len(mod.INSTALLER._undos), hooked))
mod.fini()

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)