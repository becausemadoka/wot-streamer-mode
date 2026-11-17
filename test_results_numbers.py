# -*- coding: utf-8 -*-
"""Verify the battle-results personal scoreboard uses the SAME bot numbers.

Reported from a real battle: after TAB was fixed, the results screen's
"battle results -> personal scoreboard" still showed LARGER bot numbers.

Two causes, both ours:

1. The results hook keyed bots by NAME while every in-battle path keys by
   vehicleID.  Unrelated keys => a second numbering space, so results simply
   continued counting where battle stopped -- hence "larger".

2. onAvatarBecomeNonPlayer() called ANONYMISER.reset(), which wipes the
   numbering on leaving battle -- but the results screen is rendered AFTER
   that event.  Even a correct lookup would find an empty table.

The fix: keep the numbering alive until the NEXT battle starts (the reset in
onAvatarBecomePlayer already covers that), and resolve results bots through the
same name->identity binding the in-battle paths recorded.

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
        if name is None:
            return self.vehicleType.shortNameWithPrefix
        return name


class PlayerFullNameFormatter(object):
    def __init__(self):
        self._PlayerFullNameFormatter__isVehicleShortNameShown = True
        self._PlayerFullNameFormatter__isClanShown = True
        self._PlayerFullNameFormatter__isRegionShown = False

    def format(self, vInfoVO, playerName=None):
        import collections
        R = collections.namedtuple('PlayerFormatResult',
                                   'playerFullName playerName playerFakeName '
                                   'clanAbbrev regionCode vehicleName')
        p = vInfoVO.player
        if playerName is None:
            playerName = vInfoVO.getDisplayedName(p.getPlayerLabel())
        return R(playerName, playerName, '', p.clanAbbrev, '', 'T-54')


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
             'gui.Scaleform.daapi.view.battle.shared.stats_exchange'):
    m = types.ModuleType(name)
    m.__path__ = []
    sys.modules[name] = m
sys.modules['gui.battle_control.arena_info.arena_vos'] = arena_vos
sys.modules['gui.battle_control.arena_info.player_format'] = pf
sys.modules['gui.battle_control.arena_info'].arena_vos = arena_vos
sys.modules['gui.battle_control.arena_info'].player_format = pf


# --- battle_results PlayerInfo, mirroring the real __slots__ (no vehicleID!)
class BRPlayerInfo(object):
    __slots__ = ('_PlayerInfo__dbID', '_PlayerInfo__team',
                 '_PlayerInfo__fakeName', '_PlayerInfo__realName',
                 '_PlayerInfo__prebattleID', '_PlayerInfo__igrType',
                 '_PlayerInfo__clanInfo', '_PlayerInfo__isTeamKiller',
                 'squadIndex', '_PlayerInfo__tags', '_fullNameCalls')

    def __init__(self, dbID, realName, fakeName=''):
        self._PlayerInfo__dbID = dbID
        self._PlayerInfo__team = 1
        self._PlayerInfo__realName = realName
        self._PlayerInfo__fakeName = fakeName
        self._PlayerInfo__prebattleID = None
        self._PlayerInfo__igrType = 0
        self._PlayerInfo__clanInfo = None
        self._PlayerInfo__isTeamKiller = False
        self._PlayerInfo__tags = set()
        self.squadIndex = 0
        self._fullNameCalls = 0

    @property
    def realName(self):
        return self._PlayerInfo__realName

    @property
    def fakeName(self):
        return self._PlayerInfo__fakeName

    def getFullName(self):
        """Mirrors the real one: composes name + clan, bypassing realName."""
        self._fullNameCalls += 1
        return '%s [CLAN]' % (self._PlayerInfo__realName,)


brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = BRPlayerInfo
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp

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
                           'hideBotClanTag': True,
                           'scope.inBattle': True, 'scope.battleResults': True})
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set()
mod.IDENTITY.ownClanAbbrev = 'CLAN'
mod.IDENTITY.squadmateDBIDs = set()
mod.init()

fmt = PlayerFullNameFormatter()


def panelLabel(vid, name):
    """In-battle panel label for a bot."""
    vo = PlayerInfoVO(accountDBID=None, avatarSessionID=None, name=name)
    return fmt.format(VehicleArenaInfoVO(vehicleID=vid, player=vo), None).playerName


def resultsLabel(name):
    """Battle-results personal-scoreboard label for a bot (no dbID)."""
    return BRPlayerInfo(dbID=None, realName=name).realName


BOTS = [(':Ivan Petrov:', 101), (':Jan Kowalski:', 102), (':Boris Ivanov:', 103)]

print()
print('=== in battle, then in the results screen ===')
mod.ANONYMISER.reset()
panel = [panelLabel(vid, name) for name, vid in BOTS]
check('panel numbering', panel == ['Bot_001', 'Bot_002', 'Bot_003'], panel)

# the player leaves the battle: this used to wipe the numbering
mod.onAvatarBecomeNonPlayer()
check('numbering SURVIVES leaving the battle',
      mod.ANONYMISER._botNext == 3, mod.ANONYMISER._botNext)

results = [resultsLabel(name) for name, _vid in BOTS]
check('results labels are distinct', len(set(results)) == 3, results)
check('results reuse the in-battle numbers', results == panel,
      (results, panel))
check('results numbers are NOT larger than panel numbers',
      results == panel, (results, panel))

print()
print('=== results rendered twice must be stable ===')
again = [resultsLabel(name) for name, _vid in BOTS]
check('second render identical', again == results, (again, results))

print()
print('=== a bot seen ONLY in results still numbers sanely ===')
mod.ANONYMISER.reset()
only = [resultsLabel(':Only Bot %d:' % i) for i in range(3)]
check('results-only bots get distinct numbers', len(set(only)) == 3, only)
check('results-only numbering starts at Bot_001', only[0] == 'Bot_001', only)

print()
print('=== the next battle resets the numbering ===')
mod.ANONYMISER.reset()
panel2 = [panelLabel(vid, name) for name, vid in BOTS]
mod.onAvatarBecomePlayer()
panel3 = [panelLabel(vid, name) for name, vid in BOTS]
check('new battle starts from Bot_001 again',
      panel3[0] == 'Bot_001', (panel2, panel3))

print()
print('=== every accessor the scoreboard reads must be masked ===')
# components/shared.pyc PlayerNameBlock.setPlayerInfo reads ALL of these, so
# hooking only realName left fakeName / getFullName showing the original text.
mod.ANONYMISER.reset()
_b = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:')
_r = [panelLabel(vid, name) for name, vid in BOTS]
_rl = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:')
check('realName masked', _rl.realName.startswith('Bot_'), _rl.realName)
check('fakeName masked', _rl.fakeName.startswith('Bot_'), _rl.fakeName)
full = _rl.getFullName()
check('getFullName masked',
      'Ivan Petrov' not in full and full.split(' ')[0].startswith('Bot_'), full)
check('getFullName kept calling through to the original',
      _rl._fullNameCalls == 1, _rl._fullNameCalls)
check('all three agree on the number',
      _rl.realName == _rl.fakeName == full.split(' ')[0],
      (_rl.realName, _rl.fakeName, full))
check('they match the in-battle number for the first bot',
      _rl.realName == _r[0], (_rl.realName, _r[0]))

print()
print('=== humans unaffected in results ===')
mod.ANONYMISER.reset()
human = BRPlayerInfo(dbID=5000, realName='HumanGuy').realName
me = BRPlayerInfo(dbID=1, realName='MyOwnName').realName
check('stranger human anonymised', human == 'Player_001', human)
check('own name preserved', me == 'MyOwnName', me)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)