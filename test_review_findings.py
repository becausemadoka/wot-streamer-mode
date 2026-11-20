# -*- coding: utf-8 -*-
"""Regression tests for the issues raised in the wgmods review.

Each block corresponds to one finding:

  1. results masking when realName != fakeName (native Anonymizer users)
  2. identity snapshots cleared/replaced at account and battle boundaries,
     including empty friend and platoon sets
  3. the current clan accessor (g_clanCache.clanAbbrev)
  4. the five per-surface switches actually gate their surface
  5. every badge path respects the master enable switch

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
        self._p = 101
        self._s = 202

    @property
    def selectedBadge(self):
        return self._p

    @property
    def selectedSuffixBadge(self):
        return self._s

    def getDisplayedName(self, name=None):
        return 'T-54' if name is None else name


class PlayerFullNameFormatter(object):
    def format(self, vInfoVO, playerName=None):
        import collections
        R = collections.namedtuple('R', 'playerFullName playerName '
                                        'playerFakeName clanAbbrev regionCode '
                                        'vehicleName')
        val = playerName or ''
        return R(val, val, '', '', '', '')


def _install(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


av = _install('gui.battle_control.arena_info.arena_vos',
              PlayerInfoVO=PlayerInfoVO,
              VehicleArenaInfoVO=VehicleArenaInfoVO)
pf = _install('gui.battle_control.arena_info.player_format',
              PlayerFullNameFormatter=PlayerFullNameFormatter,
              _FORMAT_MASK=type('M', (), {'NONE': 0, 'VEHICLE': 1, 'REGION': 2,
                                          'CLAN': 16, 'VEHICLE_REGION': 3}),
              _PLAYER_FULL_NAME_FORMATS={})
_ai = _install('gui.battle_control.arena_info', arena_vos=av, player_format=pf)
_bc = _install('gui.battle_control', arena_info=_ai)
_install('gui', battle_control=_bc)

class ClanInfo(object):
    __slots__ = ('clanAbbrev', 'clanDBID')

    def __init__(self, clanAbbrev='', clanDBID=0):
        self.clanAbbrev = clanAbbrev
        self.clanDBID = clanDBID


class BRPlayerInfo(object):
    __slots__ = ('_PlayerInfo__dbID', '_PlayerInfo__team', '_PlayerInfo__fakeName',
                 '_PlayerInfo__realName', '_PlayerInfo__prebattleID',
                 '_PlayerInfo__igrType', '_PlayerInfo__clanInfo',
                 '_PlayerInfo__isTeamKiller', 'squadIndex', '_PlayerInfo__tags',
                 '_PlayerInfo__vehicleID')

    def __init__(self, dbID, realName, fakeName='', vehicleID=None,
                 clanAbbrev=''):
        self._PlayerInfo__dbID = dbID
        self._PlayerInfo__team = 1
        self._PlayerInfo__realName = realName
        self._PlayerInfo__fakeName = fakeName
        self._PlayerInfo__prebattleID = None
        self._PlayerInfo__igrType = 0
        self._PlayerInfo__clanInfo = ClanInfo(clanAbbrev)
        self._PlayerInfo__isTeamKiller = False
        self._PlayerInfo__tags = set()
        self._PlayerInfo__vehicleID = vehicleID
        self.squadIndex = 0

    @property
    def realName(self):
        return self._PlayerInfo__realName

    @property
    def fakeName(self):
        return self._PlayerInfo__fakeName

    @property
    def clanAbbrev(self):
        info = self._PlayerInfo__clanInfo
        return info.clanAbbrev if info is not None else ''

    def getFullName(self):
        return '%s [TAG]' % self._PlayerInfo__realName


_install('gui.battle_results.reusable.players', PlayerInfo=BRPlayerInfo)
_install('gui.battle_results.reusable')
_install('gui.battle_results')
_install('gui.impl.battle.battle_page.tab_view',
         TabView=type('TabView', (object,), {}))
_install('gui.impl.battle.battle_page')
_install('gui.impl.battle')
_install('gui.impl')
_install('gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle',
         VehicleInfoComponent=type('VehicleInfoComponent', (object,), {
             '_data': {},
             'addVehicleInfo': lambda self, vInfoVO, overrides=None: None,
         }))
_install('gui.Scaleform.daapi.view.battle.shared.stats_exchange')
_install('gui.Scaleform.daapi.view.battle.shared')
_install('gui.Scaleform.daapi.view.battle')
_install('gui.Scaleform.daapi.view')
_install('gui.Scaleform.daapi')
_install('gui.Scaleform')
_install('gui.shared.badges', buildBadge=lambda *a, **k: 'badge')
_install('gui.shared')
_install('gui.doc_loaders.badges_loader', getSelectedByLayout=lambda ids: (1, 2))
_install('gui.doc_loaders')

bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

# clan cache stub -- the accessor the reviewer says is the real one
_clan_box = {'abbrev': None}


class _ClanCache(object):
    @property
    def clanAbbrev(self):
        return _clan_box['abbrev']


cc = _install('gui.clans.clan_cache', g_clanCache=_ClanCache())
_install('gui.clans', clan_cache=cc)

# ------------------------------------------------------------------- load --
# Same stub layout the other suites use: the parent packages must expose the
# child modules as attributes, or `from gui.battle_control.arena_info import
# arena_vos` fails and install() silently installs nothing.
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))

BASE = {'enable': True, 'mode': 'label', 'namePrefix': 'Player_',
        'botMode': 'botLabel', 'botPrefix': 'Bot_', 'hideClanTag': True,
        'hideBotClanTag': True, 'hideResultsClanTag': True,
        'scope.inBattle': True, 'scope.battleResults': True,
        'scope.playersPanel': True, 'scope.minimap': True,
        'scope.messages': True, 'scope.markers': True, 'scope.postmortem': True,
        'exclude.ownName': True, 'exclude.friendName': True,
        'exclude.clanmateName': True, 'exclude.divmateName': True,
        'hideBadges': True, 'hideBotBadges': True, 'badges.exemptKnown': True,
        'showRealNamesInProfile': True}


def reset_config(**over):
    mod.CONFIG._values = dict(BASE)
    mod.CONFIG._values.update(over)


reset_config()
mod.IDENTITY.ownDBID = 1000
mod.IDENTITY.friendDBIDs = set([2000])
mod.IDENTITY.ownClanAbbrev = 'MYCLAN'
mod.IDENTITY.squadmateDBIDs = set([4000])
mod.init()

panel_comp_cls = sys.modules[
    'gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle'
].VehicleInfoComponent

# `install()` walks the whole client and skips anything it cannot import, so in
# a stub environment not every hook lands.  Patch the classes this suite actually
# exercises explicitly, which is also what makes the assertions below precise.
mod.patch(BRPlayerInfo, 'realName', mod._hookResultsRealName, is_property=True)
mod.patch(BRPlayerInfo, 'fakeName', mod._hookResultsFakeName, is_property=True)
mod.patch(BRPlayerInfo, 'getFullName', mod._hookResultsFullName)
mod.patch(BRPlayerInfo, 'clanAbbrev', mod._hookResultsClanAbbrev,
          is_property=True)
mod.patch(panel_comp_cls, 'addVehicleInfo',
          mod._hookVehicleInfoComponentAdd)

# ===================================================================== 1 ===
print()
print('=== 1. results masking when realName != fakeName ===')

mod.ANONYMISER.reset()
stranger = BRPlayerInfo(dbID=5000, realName='RealNick', fakeName='FakeNick')
value = stranger.realName
check('native-anonymised stranger is masked',
      value not in ('RealNick', 'FakeNick') and value.startswith('Player_'), value)

full = stranger.getFullName()
check('getFullName is masked too', 'RealNick' not in full, full)

mod.ANONYMISER.reset()
buddy = BRPlayerInfo(dbID=2000, realName='BuddyReal', fakeName='BuddyFake')
check('friend keeps real name even when natively anonymised',
      buddy.realName == 'BuddyReal', buddy.realName)

mod.ANONYMISER.reset()
clanmate = BRPlayerInfo(dbID=3000, realName='ClanReal', fakeName='ClanFake',
                        clanAbbrev='MYCLAN')
check('clanmate keeps real name', clanmate.realName == 'ClanReal',
      clanmate.realName)

# Capture the real reader before any stub replaces it -- block 3 exercises it.
_real_clan_reader = mod.Identity._readOwnClanAbbrev

# --------------------------------------------------------------------- 2 ---
print()
print('=== 2. identity snapshots are replaced, not merged ===')

mod.IDENTITY.reset()
mod.IDENTITY.friendDBIDs = set([111, 222])
mod.IDENTITY.squadmateDBIDs = set([333])
mod._readFriendDBIDs = staticmethod(lambda: set())
mod._readSquadmateDBIDs = staticmethod(lambda: set())
mod.Identity._readFriendDBIDs = staticmethod(lambda: set())
mod.Identity._readSquadmateDBIDs = staticmethod(lambda: set())
mod.Identity._readOwnDBID = staticmethod(lambda: 999)
mod.IDENTITY.resolve()
check('empty friend list clears the old set',
      mod.IDENTITY.friendDBIDs == set(), mod.IDENTITY.friendDBIDs)
check('empty platoon clears the old set',
      mod.IDENTITY.squadmateDBIDs == set(), mod.IDENTITY.squadmateDBIDs)
check('own DBID is replaced', mod.IDENTITY.ownDBID == 999, mod.IDENTITY.ownDBID)

print()
print('=== 2b. account switch drops the previous account\'s exemptions ===')
mod.IDENTITY.friendDBIDs = set([2000])
mod.IDENTITY.squadmateDBIDs = set([4000])
mod.IDENTITY.ownClanAbbrev = 'OLDCLAN'
mod.Identity._readOwnDBID = staticmethod(lambda: None)
mod.Identity._readOwnClanAbbrev = staticmethod(lambda: None)
mod.onAccountBecomePlayer()
check('friends cleared on account change',
      mod.IDENTITY.friendDBIDs == set(), mod.IDENTITY.friendDBIDs)
check('platoon cleared on account change',
      mod.IDENTITY.squadmateDBIDs == set(), mod.IDENTITY.squadmateDBIDs)
check('clan cleared on account change',
      not mod.IDENTITY.ownClanAbbrev, mod.IDENTITY.ownClanAbbrev)

print()
print('=== 2c. next battle drops the previous platoon ===')
mod.IDENTITY.squadmateDBIDs = set([4000])
mod.Identity._readSquadmateDBIDs = staticmethod(lambda: set())
mod.onAvatarBecomePlayer()
check('platoon cleared when the next battle starts',
      mod.IDENTITY.squadmateDBIDs == set(), mod.IDENTITY.squadmateDBIDs)

# restore stubs used by later blocks
mod.Identity._readOwnDBID = staticmethod(lambda: 1000)
mod.Identity._readFriendDBIDs = staticmethod(lambda: set([2000]))
mod.Identity._readSquadmateDBIDs = staticmethod(lambda: set([4000]))
mod.IDENTITY.reset()
mod.IDENTITY.resolve()

# ===================================================================== 3 ===
print()
print('=== 3. clan accessor is g_clanCache.clanAbbrev ===')

_clan_box['abbrev'] = 'CACHECLAN'
got = _real_clan_reader()
check('reads g_clanCache.clanAbbrev', got == 'CACHECLAN', got)
_clan_box['abbrev'] = None
got = _real_clan_reader()
check('returns None when the cache is empty', got is None, got)

# ===================================================================== 4 ===
print()
print('=== 4. per-surface switches gate their own surface ===')


def results_label(dbID, realName, **kw):
    mod.ANONYMISER.reset()
    return BRPlayerInfo(dbID=dbID, realName=realName, **kw).realName


for key, label in (('scope.battleResults', 'battle results'),):
    reset_config(**{key: False})
    out = results_label(5000, 'Nick')
    check('%s OFF leaves the name alone' % label, out == 'Nick', out)
    reset_config()
    out = results_label(5000, 'Nick')
    check('%s ON masks the name' % label, out.startswith('Player_'), out)

# the panel hook and its switch
panel_comp = sys.modules[
    'gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle'].VehicleInfoComponent


def run_panel():
    comp = panel_comp()
    comp._data = {'clanAbbrev': 'STRANGER', 'playerName': 'Nick'}
    vo = VehicleArenaInfoVO(vehicleID=1,
                            player=PlayerInfoVO(accountDBID=5000,
                                                avatarSessionID=9,
                                                name='Nick',
                                                clanAbbrev='STRANGER'))
    comp.addVehicleInfo(vo)
    return comp._data


reset_config()
mod.ANONYMISER.reset()
data = run_panel()
check('playersPanel ON masks the row', data.get('clanAbbrev') == '', data)

reset_config(**{'scope.playersPanel': False})
mod.ANONYMISER.reset()
data = run_panel()
check('playersPanel OFF leaves the row alone',
      data.get('clanAbbrev') == 'STRANGER', data)
reset_config()

# Per-screen wiring is checked by rendering each screen with its switch both
# on and off in test_surface_switches.py, not by matching source spellings.

# ===================================================================== 5 ===
print()
print('=== 5. badge paths honour the master switch ===')

reset_config(enable=True)
mod.ANONYMISER.reset()
check('enabled: stranger badge is hidden',
      mod.ANONYMISER.shouldHideBadge(dbID=5000) is True, None)

reset_config(enable=False)
check('disabled: no badge is hidden',
      mod.ANONYMISER.shouldHideBadge(dbID=5000) is False, None)

# the two global wrappers must also stay inert with the mod off
badges_mod = sys.modules['gui.shared.badges']
loader_mod = sys.modules['gui.doc_loaders.badges_loader']
if hasattr(badges_mod, 'buildBadge') and hasattr(badges_mod, '_hooked'):
    pass
check('disabled: buildBadge wrapper returns the original',
      badges_mod.buildBadge(7) == 'badge', badges_mod.buildBadge(7))
check('disabled: getSelectedByLayout wrapper returns the original',
      loader_mod.getSelectedByLayout(['x']) == (1, 2),
      loader_mod.getSelectedByLayout(['x']))

reset_config(enable=False)
mod.ANONYMISER.reset()
check('disabled: strangers are not masked at all',
      mod.ANONYMISER.displayForID(5000, 'Nick') == 'Nick',
      mod.ANONYMISER.displayForID(5000, 'Nick'))

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)
