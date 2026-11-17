# -*- coding: utf-8 -*-
"""Verify the battle-results screen keeps bots and players the right way round.

Reported from a real session: in "战斗结果 → 个人战绩" the types were swapped --
bots were shown as players and players as bots.

Root cause, read out of the shipped client:

  battle_results/reusable/__init__.pyc, the bot branch (L403 / L461):

      botInfo  = common.getBotInfo(vehicleID)
      botName  = botInfo.realName if botInfo else ''
      playerInfo = players.makePlayerInfo(realName=botName, fakeName=botName,
                                          isEnemy=..., wasInBattle=...)

  -- note there is NO dbID argument, so makePlayerInfo falls back to its default
  and a bot's PlayerInfo ends up with a FALSY dbID.  Real players always come
  from the branch above it, which passes the real accountDBID.

Our old hook treated "falsy dbID" as "stranger" and labelled it Player_NNN, so
bots looked like players and the numbering was effectively inverted.

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
        return self.name if self.name else 'Unknown'

    def getPlayerFakeLabel(self):
        return ''


class VehicleArenaInfoVO(object):
    def __init__(self, player=None, vehicleType=None):
        self.player = player or PlayerInfoVO()
        self.vehicleType = vehicleType

    def getDisplayedName(self, name=None):
        return name


class PlayerFullNameFormatter(object):
    def format(self, vInfoVO, playerName=None):
        return playerName


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


# --- battle-results ProjectInfo mirroring the real __slots__
class ClanInfo(object):
    """Mirror of the client's _ClanInfo: clanAbbrev lives on a nested object.

    The real PlayerInfo.clanAbbrev property is `self.__clanInfo.clanAbbrev`
    (confirmed against the client's players module).
    """

    __slots__ = ('clanAbbrev', 'clanDBID')

    def __init__(self, clanAbbrev='', clanDBID=0):
        self.clanAbbrev = clanAbbrev
        self.clanDBID = clanDBID


class BRPlayerInfo(object):
    __slots__ = ('_PlayerInfo__dbID', '_PlayerInfo__team',
                 '_PlayerInfo__fakeName', '_PlayerInfo__realName',
                 '_PlayerInfo__prebattleID', '_PlayerInfo__igrType',
                 '_PlayerInfo__clanInfo', '_PlayerInfo__isTeamKiller',
                 'squadIndex', '_PlayerInfo__tags', '_PlayerInfo__vehicleID')

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

    @property
    def isAnonymized(self):
        return self._PlayerInfo__realName != self._PlayerInfo__fakeName


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
                           'hideResultsClanTag': True,
                           'scope.inBattle': True, 'scope.battleResults': True,
                           'exclude.ownName': True, 'exclude.friendName': True,
                           'exclude.clanmateName': True, 'exclude.divmateName': True})
mod.IDENTITY.ownDBID = 1000
mod.IDENTITY.friendDBIDs = set([2000])
mod.IDENTITY.ownClanAbbrev = 'MYCLAN'
mod.IDENTITY.squadmateDBIDs = set([4000])
mod.init()

print()
print('=== battle results: bot vs player ===')
# a bot: the client builds it via makePlayerInfo() with NO dbID
botInfo = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:', vehicleID=501)
# a real player: has an account DBID
playerInfo = BRPlayerInfo(dbID=3000, realName='RealDude', vehicleID=502)
# ourselves and a friend
meInfo = BRPlayerInfo(dbID=1000, realName='MyOwnName', vehicleID=503)
friendInfo = BRPlayerInfo(dbID=2000, realName='BuddyName', vehicleID=504)

botLabel = botInfo.realName
playerLabel = playerInfo.realName
check('results: bot labelled with Bot_ prefix, not Player_',
      botLabel.startswith('Bot_'), botLabel)
check('results: real player labelled with Player_ prefix',
      playerLabel.startswith('Player_'), playerLabel)
check('results: bot is NOT shown as a player',
      not botLabel.startswith('Player_'), botLabel)
check('results: player is NOT shown as a bot',
      not playerLabel.startswith('Bot_'), playerLabel)
check('results: own name preserved', meInfo.realName == 'MyOwnName',
      meInfo.realName)
check('results: friend name preserved', friendInfo.realName == 'BuddyName',
      friendInfo.realName)

print()
print('=== results: clanmate / squadmate keep their real names too ===')
# Regression: _resultsLabel only exempted self and friends, while the in-battle
# path (isStrangerIdentity) and the results clan-tag hook both exempt four
# groups.  A clanmate or platoon mate was therefore masked in "battle results ->
# personal scoreboard" but kept in battle -- the same player under two names.
clanmateInfo = BRPlayerInfo(dbID=3000, realName='ClanBuddy', vehicleID=505,
                            clanAbbrev='MYCLAN')
squadmateInfo = BRPlayerInfo(dbID=4000, realName='PlatoonBuddy', vehicleID=506,
                             clanAbbrev='OTHER')
check('results: clanmate name preserved',
      clanmateInfo.realName == 'ClanBuddy', clanmateInfo.realName)
check('results: squadmate name preserved',
      squadmateInfo.realName == 'PlatoonBuddy', squadmateInfo.realName)

# ...and the same decision has to hold for the clan tag, which is a separate
# hook.  Both must agree or the scoreboard shows a real [TAG] next to a label.
check('results: clanmate clan tag preserved',
      clanmateInfo.clanAbbrev == 'MYCLAN', clanmateInfo.clanAbbrev)
check('results: squadmate clan tag preserved',
      squadmateInfo.clanAbbrev == 'OTHER', squadmateInfo.clanAbbrev)

# A stranger must still be masked on both fields, so the fix cannot be "exempt
# everyone".
strangerInfo = BRPlayerInfo(dbID=5000, realName='WhoIsThis', vehicleID=507,
                            clanAbbrev='STRANGER')
check('results: stranger name still masked',
      strangerInfo.realName.startswith('Player_'), strangerInfo.realName)
check('results: stranger clan tag still hidden',
      strangerInfo.clanAbbrev == '', repr(strangerInfo.clanAbbrev))

# The exemption flags must actually gate the behaviour.
mod.CONFIG._values['exclude.clanmateName'] = False
mod.CONFIG._values['exclude.divmateName'] = False
clanOff = BRPlayerInfo(dbID=3000, realName='ClanBuddy', vehicleID=508,
                       clanAbbrev='MYCLAN')
squadOff = BRPlayerInfo(dbID=4000, realName='PlatoonBuddy', vehicleID=509,
                        clanAbbrev='OTHER')
check('results: exclude.clanmateName=false masks a clanmate',
      clanOff.realName.startswith('Player_'), clanOff.realName)
check('results: exclude.divmateName=false masks a squadmate',
      squadOff.realName.startswith('Player_'), squadOff.realName)
mod.CONFIG._values['exclude.clanmateName'] = True
mod.CONFIG._values['exclude.divmateName'] = True

print()
print('=== bots keep stable labels ===')
mod.ANONYMISER.reset()
b1 = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:')
b1a = b1.realName
b2 = BRPlayerInfo(dbID=None, realName=':Jan Kowalski:')
b2a = b2.realName
check('first bot gets Bot_001', b1a == 'Bot_001', b1a)
check('second bot gets Bot_002', b2a == 'Bot_002', b2a)
# the same bot name must map to the same label across refreshes
again = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:').realName
check('same bot name -> same label', again == b1a, (again, b1a))

print()
print('=== players are numbered independently of bots ===')
mod.ANONYMISER.reset()
pA = BRPlayerInfo(dbID=7001, realName='HumanA').realName
pB = BRPlayerInfo(dbID=7002, realName='HumanB').realName
bX = BRPlayerInfo(dbID=None, realName=':Some Bot:').realName
check('player numbering starts at Player_001', pA == 'Player_001', pA)
check('player numbering continues', pB == 'Player_002', pB)
check('bot numbering starts at Bot_001', bX == 'Bot_001', bX)

print()
print('=== botMode honoured in results ===')
mod.CONFIG._values['botMode'] = 'keep'
mod.ANONYMISER.reset()
kept = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:').realName
check('botMode=keep leaves the bot name', kept == ':Ivan Petrov:', kept)

mod.CONFIG._values['botMode'] = 'blank'
mod.ANONYMISER.reset()
blanked = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:').realName
check('botMode=blank hides the bot name', blanked == '', repr(blanked))

mod.CONFIG._values['botMode'] = 'label'
mod.ANONYMISER.reset()
same = BRPlayerInfo(dbID=None, realName=':Ivan Petrov:').realName
check('botMode=label uses the player scheme', same.startswith('Player_'), same)

print()
print('=== game-anonymised players still left alone ===')
mod.CONFIG._values['botMode'] = 'botLabel'
mod.ANONYMISER.reset()
anonymised = BRPlayerInfo(dbID=8001, realName='RealNick', fakeName='FakeNick')
check('client-anonymised name untouched', anonymised.realName == 'RealNick',
      anonymised.realName)

print()
print('=== scope.battleResults=false disables the hook ===')
mod.CONFIG._values['scope.battleResults'] = False
raw = BRPlayerInfo(dbID=9001, realName='Untouched')
check('results scope off => real name', raw.realName == 'Untouched', raw.realName)
mod.CONFIG._values['scope.battleResults'] = True

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)