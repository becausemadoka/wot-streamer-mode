# -*- coding: utf-8 -*-
"""Verify the two newest fixes.

1. The battle-results personal scoreboard kept showing the real CLAN TAG.
   components/shared.pyc PlayerNameBlock.setPlayerInfo reads
       playerInfo.clanAbbrev -> clanLabel
   straight off the property -- it never goes through realName / fakeName /
   getFullName, so masking those three left the [TAG] visible.

2. The single-player profile / details window showed the ANONYMISED name.
   That window is fed by the context menu, whose user name is whatever the
   results screen handed it, so it inherited our label.  A new option
   (showRealNamesInProfile, default ON) restores the real name there.

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
                 clanAbbrev='', vehicleID=None):
        self.accountDBID = accountDBID
        self.avatarSessionID = avatarSessionID
        self.name = name
        self.clanAbbrev = clanAbbrev
        self.vehicleID = vehicleID

    @property
    def isBot(self):
        return not self.avatarSessionID

    def getPlayerLabel(self):
        return self.name if self.name else 'Unknown'

    def getPlayerFakeLabel(self):
        return ''


class _VehType(object):
    def __init__(self, short='T-54'):
        self.shortNameWithPrefix = short
        self.name = short


class VehicleArenaInfoVO(object):
    __slots__ = ('vehicleID', 'player', 'vehicleType')

    def __init__(self, vehicleID=0, player=None, vehicleType=None):
        self.vehicleID = vehicleID
        self.player = player or PlayerInfoVO()
        self.vehicleType = vehicleType if vehicleType is not None else _VehType()

    def getDisplayedName(self, name=None):
        return self.vehicleType.shortNameWithPrefix if name is None else name


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
pf = types.ModuleType('gui.battle_control.arena_info.player_format')
pf.PlayerFullNameFormatter = PlayerFullNameFormatter
pf._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16})
pf._PLAYER_FULL_NAME_FORMATS = {}

for name in ('gui', 'gui.battle_control', 'gui.battle_control.arena_info',
             'gui.battle_results', 'gui.battle_results.reusable',
             'gui.impl', 'gui.impl.battle', 'gui.impl.battle.battle_page',
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
sys.modules['gui.battle_control.arena_info.player_format'] = pf
sys.modules['gui.battle_control.arena_info'].arena_vos = arena_vos
sys.modules['gui.battle_control.arena_info'].player_format = pf


# --- battle_results PlayerInfo with the real __slots__ (clanInfo indirection)
class _ClanInfo(object):
    def __init__(self, clanAbbrev, clanDBID=0):
        self.clanAbbrev = clanAbbrev
        self.clanDBID = clanDBID


class BRPlayerInfo(object):
    __slots__ = ('_PlayerInfo__dbID', '_PlayerInfo__team',
                 '_PlayerInfo__fakeName', '_PlayerInfo__realName',
                 '_PlayerInfo__prebattleID', '_PlayerInfo__igrType',
                 '_PlayerInfo__clanInfo', '_PlayerInfo__isTeamKiller',
                 'squadIndex', '_PlayerInfo__tags')

    def __init__(self, dbID, realName, fakeName='', clanAbbrev=''):
        self._PlayerInfo__dbID = dbID
        self._PlayerInfo__team = 1
        self._PlayerInfo__realName = realName
        self._PlayerInfo__fakeName = fakeName
        self._PlayerInfo__prebattleID = None
        self._PlayerInfo__igrType = 0
        self._PlayerInfo__clanInfo = _ClanInfo(clanAbbrev)
        self._PlayerInfo__isTeamKiller = False
        self._PlayerInfo__tags = set()
        self.squadIndex = 0

    @property
    def realName(self):
        return self._PlayerInfo__realName

    @property
    def fakeName(self):
        return self._PlayerInfo__fakeName

    @property
    def clanAbbrev(self):
        return self._PlayerInfo__clanInfo.clanAbbrev

    def getFullName(self):
        return '%s [%s]' % (self._PlayerInfo__realName,
                            self._PlayerInfo__clanInfo.clanAbbrev)


brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = BRPlayerInfo
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp

# --- LobbyContext / ProfileWindow
lobby_context = types.ModuleType('gui.lobby_context')


class LobbyContext(object):
    def getPlayerFullName(self, pName, clanInfo=None, clanAbbrev=None,
                          regionCode=None, pDBID=None):
        """Mirrors the real composition (records what it was given)."""
        self.lastArgs = (pName, clanAbbrev, pDBID)
        return '%s [%s]' % (pName, clanAbbrev or '')

    def getRegionCode(self, dbID):
        return ''


lobby_context.LobbyContext = LobbyContext
sys.modules['gui.lobby_context'] = lobby_context


class ProfileWindow(object):
    def __init__(self, dbID, userName):
        self._ProfileWindow__databaseID = dbID
        self._ProfileWindow__userName = userName
        self.viewName = None

    def _ProfileWindow__updateUserInfo(self):
        """Mirrors the real one: name comes from __userName."""
        self.viewName = self._ProfileWindow__userName


profile_mod = types.ModuleType(
    'gui.Scaleform.daapi.view.lobby.profile.ProfileWindow')
profile_mod.ProfileWindow = ProfileWindow
sys.modules[profile_mod.__name__] = profile_mod
sys.modules['gui.Scaleform.daapi.view.lobby.profile'].ProfileWindow = profile_mod

tab_view = types.ModuleType('gui.impl.battle.battle_page.tab_view')
tab_view.TabView = type('TabView', (object,), {})
sys.modules['gui.impl.battle.battle_page.tab_view'] = tab_view
sys.modules['gui.impl.battle.battle_page'].tab_view = tab_view

se = types.ModuleType('gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle')
se.VehicleInfoComponent = type('C', (object,), {'_data': {}})
sys.modules[se.__name__] = se
sys.modules['gui.Scaleform.daapi.view.battle.shared.stats_exchange'].vehicle = se

bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

# ------------------------------------------------------------------- load --
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))
mod.CONFIG._values.update({'enable': True, 'mode': 'label',
                           'namePrefix': 'Player_', 'botMode': 'botLabel',
                           'botPrefix': 'Bot_', 'hideClanTag': True,
                           'hideBotClanTag': True, 'hideResultsClanTag': True,
                           'showRealNamesInProfile': True,
                           'scope.inBattle': True, 'scope.battleResults': True})
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set([2])
mod.IDENTITY.ownClanAbbrev = 'MYCLAN'
mod.IDENTITY.squadmateDBIDs = set()
mod.init()

print()
print('=== results screen: clan tag must be masked ===')
mod.ANONYMISER.reset()
stranger = BRPlayerInfo(dbID=7000, realName='EnemyGuy', clanAbbrev='ENEMY')
check('name masked', stranger.realName.startswith('Player_'), stranger.realName)
check('clan tag masked', stranger.clanAbbrev == '', repr(stranger.clanAbbrev))
full = stranger.getFullName()
check('getFullName has no clan tag', 'ENEMY' not in full, full)

print()
print('=== results: own clan and friends keep their tag ===')
mod.ANONYMISER.reset()
me = BRPlayerInfo(dbID=1, realName='MyOwnName', clanAbbrev='MYCLAN')
friend = BRPlayerInfo(dbID=2, realName='BuddyName', clanAbbrev='FRIENDCLAN')
check('own name kept', me.realName == 'MyOwnName', me.realName)
check('own clan kept', me.clanAbbrev == 'MYCLAN', repr(me.clanAbbrev))
check('friend name kept', friend.realName == 'BuddyName', friend.realName)
check('friend clan kept', friend.clanAbbrev == 'FRIENDCLAN',
      repr(friend.clanAbbrev))

print()
print('=== results clan switch can be turned off ===')
mod.CONFIG._values['hideResultsClanTag'] = False
mod.ANONYMISER.reset()
keep = BRPlayerInfo(dbID=7100, realName='Enemy2', clanAbbrev='SHOWME')
check('clan kept when switch off', keep.clanAbbrev == 'SHOWME',
      repr(keep.clanAbbrev))
check('name still masked', keep.realName.startswith('Player_'), keep.realName)
mod.CONFIG._values['hideResultsClanTag'] = True

print()
print('=== profile window: real name restored (option ON) ===')
mod.ANONYMISER.reset()
mod.CONFIG._values['showRealNamesInProfile'] = True
target = BRPlayerInfo(dbID=7200, realName='RealTarget', clanAbbrev='TGT')
masked = target.realName          # this is what the context menu carries
check('results name was masked first', masked.startswith('Player_'), masked)

ctx = LobbyContext()
# The restore happens on the WINDOW (narrow blast radius), which then feeds the
# name into lobbyContext.getPlayerFullName.  So drive it through the window.
win = ProfileWindow(7200, masked)
win._ProfileWindow__updateUserInfo()
out = ctx.getPlayerFullName(win._ProfileWindow__userName, None, 'TGT', '', 7200)
check('profile shows the real name', 'RealTarget' in out, out)
check('profile no longer shows the label', masked not in out, out)
check('window __userName restored', win.viewName == 'RealTarget',
      (win.viewName,))

print()
print('=== the global lobbyContext hook is NOT installed (blast radius) ===')
check('LobbyContext.getPlayerFullName left untouched',
      not getattr(LobbyContext.getPlayerFullName, '_streamerMode_hooked', False),
      LobbyContext.getPlayerFullName)

print()
print('=== profile switch OFF keeps it masked ===')
mod.CONFIG._values['showRealNamesInProfile'] = False
win2 = ProfileWindow(7200, masked)
win2._ProfileWindow__updateUserInfo()
out2 = LobbyContext().getPlayerFullName(win2._ProfileWindow__userName, None,
                                        'TGT', '', 7200)
check('profile stays masked when option off', out2.startswith('Player_'), out2)
check('window stays masked when option off',
      win2.viewName == masked, (win2.viewName, masked))
mod.CONFIG._values['showRealNamesInProfile'] = True

print()
print('=== unknown DBID is left alone ===')
win3 = ProfileWindow(999999, 'SomeoneElse')
win3._ProfileWindow__updateUserInfo()
out3 = LobbyContext().getPlayerFullName(win3._ProfileWindow__userName, None,
                                        'X', '', 999999)
check('unknown dbID untouched', out3.startswith('SomeoneElse'), out3)

print()
print('=== your own name is never "restored" from a label ===')
mod.ANONYMISER.reset()
me2 = BRPlayerInfo(dbID=1, realName='MyOwnName', clanAbbrev='MYCLAN')
win4 = ProfileWindow(1, me2.realName)
win4._ProfileWindow__updateUserInfo()
out4 = LobbyContext().getPlayerFullName(win4._ProfileWindow__userName, None,
                                        'MYCLAN', '', 1)
check('own profile shows own name', 'MyOwnName' in out4, out4)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)