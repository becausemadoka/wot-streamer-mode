# -*- coding: utf-8 -*-
"""Offline verification of mod_streamer_mode.pyc against real client shapes.

Python 2.7.  Stubs only the few client names the mod touches at import time,
then drives the hooks with fake VOs that mirror the real 2.4.1.0 classes.
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + str(detail)) if detail and not cond else ''))


# --------------------------------------------------------------------------
# minimal client stubs
# --------------------------------------------------------------------------

class _Log(object):
    def logInfo(self, *a):
        pass

    def logError(self, *a):
        sys.stderr.write('  logError: %r\n' % (a,))


bigworld = types.ModuleType('BigWorld')
bigworld.logInfo = lambda *a: None
bigworld.logError = lambda *a: None
bigworld.player = None
sys.modules['BigWorld'] = bigworld

# gui.battle_control.arena_info.arena_vos with real-ish classes
arena_vos = types.ModuleType('gui.battle_control.arena_info.arena_vos')


class PlayerInfoVO(object):
    def __init__(self, accountDBID=None, avatarSessionID=None, name='',
                 clanAbbrev='', fakeName=''):
        self.accountDBID = accountDBID
        self.avatarSessionID = avatarSessionID
        self.name = name
        self.clanAbbrev = clanAbbrev
        self.fakeName = fakeName
        self.isTeamKiller = False

    def isBot(self):
        return not self.avatarSessionID

    def getPlayerLabel(self):
        return self.name if self.name else 'Unknown'

    def getPlayerFakeLabel(self):
        return self.fakeName or ''


class _VehType(object):
    """Mirrors VehicleTypeInfoVO: .name and .shortNameWithPrefix."""

    def __init__(self, short='T-34-85', full='T-34-85'):
        self.shortNameWithPrefix = short
        self.name = full


class VehicleArenaInfoVO(object):
    def __init__(self, vehicleID=0, team=1, player=None, prebattleID=None,
                 vehicleType=None):
        self.vehicleID = vehicleID
        self.team = team
        self.player = player or PlayerInfoVO()
        self.prebattleID = prebattleID
        self.vehicleType = vehicleType if vehicleType is not None else _VehType()

    def getDisplayedName(self, name=None):
        if name is None:
            # real client: vehicleType.shortNameWithPrefix
            return self.vehicleType.shortNameWithPrefix
        if self.player.isBot():
            return 'Bot'
        return name


arena_vos.PlayerInfoVO = PlayerInfoVO
arena_vos.VehicleArenaInfoVO = VehicleArenaInfoVO

# player_format with the real mask constants and formatter behaviour
player_format = types.ModuleType('gui.battle_control.arena_info.player_format')


class _PlayerFullNameFormatter(object):
    def __init__(self):
        self._PlayerFullNameFormatter__isVehicleShortNameShown = True
        self._PlayerFullNameFormatter__isClanShown = True
        self._PlayerFullNameFormatter__isRegionShown = False

    def format(self, vInfoVO, playerName=None):
        """Faithful to the client's mask-driven composition."""
        import collections
        R = collections.namedtuple('PlayerFormatResult',
                                   'playerFullName playerName playerFakeName '
                                   'clanAbbrev regionCode vehicleName')
        key = _Mask.NONE
        vehShortName = ''
        vehName = ''
        regionCode = ''
        vehType = vInfoVO.vehicleType
        if vehType is not None:
            if self._PlayerFullNameFormatter__isVehicleShortNameShown:
                vehName = vehShortName = vehType.shortNameWithPrefix
                key |= _Mask.VEHICLE
            else:
                vehName = vehType.name
        player = vInfoVO.player
        if playerName is None:
            playerName = vInfoVO.getDisplayedName(player.getPlayerLabel())
        fakePlayerName = player.getPlayerFakeLabel()
        clanAbbrev = ''
        if self._PlayerFullNameFormatter__isClanShown:
            clanAbbrev = player.clanAbbrev
            if clanAbbrev:
                key |= _Mask.CLAN
        if self._PlayerFullNameFormatter__isRegionShown:
            if regionCode:
                key |= _Mask.REGION
        if key == _Mask.NONE:
            fullName = playerName
        else:
            mask = player_format._PLAYER_FULL_NAME_FORMATS.get(key, '{0:>s}')
            fullName = mask.format(playerName, clanAbbrev, vehShortName, regionCode)
        return R(fullName, playerName, fakePlayerName, clanAbbrev, regionCode, vehName)


class _Mask(object):
    NONE = 0
    VEHICLE = 1
    CLAN = 16
    REGION = 256
    VEH_CLAN = 17
    VEH_REGION = 257
    REG_CLAN = 272
    ALL = 273


player_format._FORMAT_MASK = _Mask
player_format._PLAYER_FULL_NAME_FORMATS = {
    0: '{0:>s}', 1: '{0:>s} ({2:>s})', 16: '{0:>s}[{1:>s}]',
    17: '{0:>s}[{1:>s}] ({2:>s})', 256: '{0:>s} {3:>s}',
    257: '{0:>s} {3:>s} ({2:>s})', 272: '{0:>s}[{1:>s}] {3:>s}',
    273: '{0:>s}[{1:>s}] {3:>s} ({2:>s})',
}
player_format.PlayerFullNameFormatter = _PlayerFullNameFormatter

gui = types.ModuleType('gui')
gui.__path__ = []
bc = types.ModuleType('gui.battle_control')
bc.__path__ = []
ai = types.ModuleType('gui.battle_control.arena_info')
ai.__path__ = []
ai.arena_vos = arena_vos
ai.player_format = player_format
sys.modules['gui'] = gui
sys.modules['gui.battle_control'] = bc
sys.modules['gui.battle_control.arena_info'] = ai
sys.modules['gui.battle_control.arena_info.arena_vos'] = arena_vos
sys.modules['gui.battle_control.arena_info.player_format'] = player_format


# --------------------------------------------------------------------------
# load the compiled mod
# --------------------------------------------------------------------------
import imp
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))

print('--- mod loaded ---')
check('import ok', True)

# force a deterministic identity: self=1, friend=2, clanmate tag=CLAN
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set([2])
mod.IDENTITY.ownClanAbbrev = 'CLAN'
mod.IDENTITY.squadmateDBIDs = set([3])
mod.CONFIG._values['mode'] = 'label'
mod.CONFIG._values['namePrefix'] = 'Player_'
mod.CONFIG._values['exclude.ownName'] = True
mod.CONFIG._values['exclude.friendName'] = True
mod.CONFIG._values['exclude.clanmateName'] = True
mod.CONFIG._values['exclude.divmateName'] = True
mod.CONFIG._values['hideClanTag'] = True
mod.CONFIG._values['enable'] = True
mod.CONFIG._values['scope.inBattle'] = True
mod.CONFIG._values['scope.battleResults'] = True
# bots get their own prefix by default (see test_bots.py)
mod.CONFIG._values['botMode'] = 'botLabel'
mod.CONFIG._values['botPrefix'] = 'Bot_'

mod.init()
print('--- hooks installed ---')

# --------------------------------------------------------------------------
# behaviour
# --------------------------------------------------------------------------
stranger = PlayerInfoVO(accountDBID=99, avatarSessionID='s99', name='NoobKiller',
                        clanAbbrev='ENEMY')
selfVO = PlayerInfoVO(accountDBID=1, avatarSessionID='s1', name='MyName',
                      clanAbbrev='CLAN')
friendVO = PlayerInfoVO(accountDBID=2, avatarSessionID='s2', name='Buddy',
                        clanAbbrev='OTHER')
clanmateVO = PlayerInfoVO(accountDBID=5, avatarSessionID='s5', name='ClanGuy',
                          clanAbbrev='CLAN')
squadVO = PlayerInfoVO(accountDBID=3, avatarSessionID='s3', name='SquadGuy',
                       clanAbbrev='ZZZ')
botVO = PlayerInfoVO(accountDBID=0, avatarSessionID=None, name='BotName',
                     clanAbbrev='')

check('stranger anonymised', stranger.getPlayerLabel() == 'Player_001',
      stranger.getPlayerLabel())
check('self keeps name', selfVO.getPlayerLabel() == 'MyName', selfVO.getPlayerLabel())
check('friend keeps name', friendVO.getPlayerLabel() == 'Buddy', friendVO.getPlayerLabel())
check('clanmate keeps name', clanmateVO.getPlayerLabel() == 'ClanGuy',
      clanmateVO.getPlayerLabel())
check('squadmate keeps name', squadVO.getPlayerLabel() == 'SquadGuy',
      squadVO.getPlayerLabel())
check('bot gets its own prefix', botVO.getPlayerLabel() == 'Bot_001',
      botVO.getPlayerLabel())

# stable numbering
s2 = PlayerInfoVO(accountDBID=77, avatarSessionID='s77', name='Other')
check('numbers are stable', stranger.getPlayerLabel() == 'Player_001'
      and s2.getPlayerLabel() == 'Player_002', (stranger.getPlayerLabel(), s2.getPlayerLabel()))

# displayedName: no-arg must return the TANK name
vStranger = VehicleArenaInfoVO(vehicleID=10, player=stranger)
check('getDisplayedName() no-arg = tank name, untouched',
      vStranger.getDisplayedName() == 'T-34-85', vStranger.getDisplayedName())
check('getDisplayedName(vehicle short name) untouched',
      vStranger.getDisplayedName('T-34-85') == 'T-34-85',
      vStranger.getDisplayedName('T-34-85'))
check('getDisplayedName(nick) anonymised',
      vStranger.getDisplayedName('NoobKiller') == 'Player_001',
      vStranger.getDisplayedName('NoobKiller'))


def _getVehicleName(vInfo, nameParts):
    """Mirror of VehicleMarkerPlugin._getVehicleName."""
    return vInfo.getDisplayedName(nameParts.vehicleName)


class _NameParts(object):
    vehicleName = 'T-34-85'


check('marker vehicle name stays intact',
      _getVehicleName(vStranger, _NameParts()) == 'T-34-85',
      _getVehicleName(vStranger, _NameParts()))

# A nickname equal to a tank name must still be masked when it comes through
# the player-name path, otherwise the vehicle-name exception would leak it.
tankNamedVO = PlayerInfoVO(accountDBID=78, avatarSessionID='s78',
                           name='T-34-85', clanAbbrev='')
vTankNamed = VehicleArenaInfoVO(vehicleID=13, player=tankNamedVO)
check('player named like a tank still masked on the name path',
      vTankNamed.getDisplayedName(tankNamedVO.getPlayerLabel()).startswith(
          'Player_'),
      vTankNamed.getDisplayedName(tankNamedVO.getPlayerLabel()))

vBot = VehicleArenaInfoVO(vehicleID=11, player=botVO)
# bots are labelled with the bot prefix (see test_bot_numbering.py); this bot
# already got Bot_001 above, so the same object must keep that exact label
check('bot keeps its assigned label in displayed name',
      vBot.getDisplayedName('BotName') == 'Bot_001',
      vBot.getDisplayedName('BotName'))

# formatter: composite string
fmt = _PlayerFullNameFormatter()
r = fmt.format(vStranger, None)
check('composite anonymised', r.playerName == 'Player_001', r.playerName)
check('clan tag stripped from composite', 'ENEMY' not in r.playerFullName,
      r.playerFullName)
check('vehicle retained in composite', 'T-34-85' in r.playerFullName,
      r.playerFullName)
r2 = fmt.format(VehicleArenaInfoVO(vehicleID=12, player=selfVO), None)
check('self composite keeps real name', r2.playerName == 'MyName', r2.playerName)

# blank mode
mod.CONFIG._values['mode'] = 'blank'
blankVO = PlayerInfoVO(accountDBID=123, avatarSessionID='s123', name='Hidden')
check('blank mode hides name', blankVO.getPlayerLabel() == '',
      repr(blankVO.getPlayerLabel()))
mod.CONFIG._values['mode'] = 'label'

# disabled entirely
mod.CONFIG._values['enable'] = False
offVO = PlayerInfoVO(accountDBID=124, avatarSessionID='s124', name='Visible')
check('disabled => real name shown', offVO.getPlayerLabel() == 'Visible',
      offVO.getPlayerLabel())
mod.CONFIG._values['enable'] = True

# reset numbering across battles
mod.onAvatarBecomePlayer()
check('numbering resets per battle',
      PlayerInfoVO(accountDBID=200, avatarSessionID='s200',
                   name='X').getPlayerLabel() == 'Player_001')

# --------------------------------------------------------------------------
# team-aware labels: ally and enemy prefixes are independent
# --------------------------------------------------------------------------
mod.CONFIG._values['namePrefix'] = ''
mod.CONFIG._values['allyPrefix'] = ''
mod.CONFIG._values['enemyPrefix'] = ''
mod.ANONYMISER.reset()

teamAlly = PlayerInfoVO(accountDBID=300, avatarSessionID='s300',
                        name='TeamAlly')
teamAlly.team = 1
teamEnemy = PlayerInfoVO(accountDBID=301, avatarSessionID='s301',
                         name='TeamEnemy')
teamEnemy.team = 2

check('ally player label uses Ally_',
      teamAlly.getPlayerLabel() == 'Ally_001',
      teamAlly.getPlayerLabel())
check('enemy player label uses Enemy_',
      teamEnemy.getPlayerLabel() == 'Enemy_001',
      teamEnemy.getPlayerLabel())

teamAllyVeh = VehicleArenaInfoVO(vehicleID=30, team=1, player=teamAlly)
teamEnemyVeh = VehicleArenaInfoVO(vehicleID=31, team=2, player=teamEnemy)
check('displayed name keeps the ally label',
      teamAllyVeh.getDisplayedName('TeamAlly') == 'Ally_001',
      teamAllyVeh.getDisplayedName('TeamAlly'))
check('displayed name keeps the enemy label',
      teamEnemyVeh.getDisplayedName('TeamEnemy') == 'Enemy_001',
      teamEnemyVeh.getDisplayedName('TeamEnemy'))
check('formatter keeps the ally label',
      fmt.format(teamAllyVeh, None).playerName == 'Ally_001',
      fmt.format(teamAllyVeh, None).playerName)
check('formatter keeps the enemy label',
      fmt.format(teamEnemyVeh, None).playerName == 'Enemy_001',
      fmt.format(teamEnemyVeh, None).playerName)

# PlayerInfoVO has NO team field, so the panel path (getPlayerLabel) must still
# resolve the side from what the vehicle-aware paths already learned.
mod.ANONYMISER.noteTeam(310, 1)
mod.ANONYMISER.noteTeam(311, 2)
bareAlly = PlayerInfoVO(accountDBID=310, avatarSessionID='s310',
                        name='BareAlly')
bareEnemy = PlayerInfoVO(accountDBID=311, avatarSessionID='s311',
                         name='BareEnemy')
check('name-only path resolves an ally from the arena team map',
      bareAlly.getPlayerLabel() == 'Ally_002',
      bareAlly.getPlayerLabel())
check('name-only path resolves an enemy from the arena team map',
      bareEnemy.getPlayerLabel() == 'Enemy_002',
      bareEnemy.getPlayerLabel())
check('unknown id still falls back to the generic prefix',
      PlayerInfoVO(accountDBID=312, avatarSessionID='s312',
                   name='NoTeam').getPlayerLabel() == 'Player_001',
      PlayerInfoVO(accountDBID=312, avatarSessionID='s312',
                   name='NoTeam').getPlayerLabel())

# uninstall restores originals
mod.fini()
restored = PlayerInfoVO(accountDBID=201, avatarSessionID='s201', name='AfterFini')
check('uninstall restores original behaviour',
      restored.getPlayerLabel() == 'AfterFini', restored.getPlayerLabel())

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('failures:')
    for f in FAIL:
        print('   -', f)
sys.exit(1 if FAIL else 0)
