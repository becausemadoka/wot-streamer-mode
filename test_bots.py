# -*- coding: utf-8 -*-
"""Verify bot nicknames get their own prefix (default `Bot_001`).

Requested after a real battle: the player saw colon-wrapped names like
":Ivan Petrov:" left untouched. Those are bots -- the client builds them in
C++ via ClientArena -> helpers/bots.pyc, whose crew-name format is literally

    _NAME_FORMAT_CREW = ':{0} {1}:'          bots.pyc L12

so a colon-wrapped name is a bot, and the client pre-processes it before any
Python display code runs.  Bots are not a privacy risk, but they should not be
mistaken for players, hence a separate prefix and a separate counter.

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


class _VehType(object):
    def __init__(self, short='T-34-85'):
        self.shortNameWithPrefix = short
        self.name = short


class VehicleArenaInfoVO(object):
    def __init__(self, player=None, vehicleType=None):
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
        player = vInfoVO.player
        if playerName is None:
            playerName = vInfoVO.getDisplayedName(player.getPlayerLabel())
        key = 0
        veh = ''
        if self._PlayerFullNameFormatter__isVehicleShortNameShown \
                and vInfoVO.vehicleType is not None:
            veh = vInfoVO.vehicleType.shortNameWithPrefix
            key |= 1
        clan = ''
        if self._PlayerFullNameFormatter__isClanShown:
            clan = player.clanAbbrev
            if clan:
                key |= 16
        masks = {0: '{0:>s}', 1: '{0:>s} ({2:>s})', 16: '{0:>s}[{1:>s}]',
                 17: '{0:>s}[{1:>s}] ({2:>s})'}
        full = masks.get(key, '{0:>s}').format(playerName, clan, veh, '')
        return R(full, playerName, '', clan, '', veh)


arena_vos = types.ModuleType('gui.battle_control.arena_info.arena_vos')
arena_vos.PlayerInfoVO = PlayerInfoVO
arena_vos.VehicleArenaInfoVO = VehicleArenaInfoVO
player_format = types.ModuleType('gui.battle_control.arena_info.player_format')
player_format.PlayerFullNameFormatter = PlayerFullNameFormatter
player_format._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16,
                                            'REGION': 256})
player_format._PLAYER_FULL_NAME_FORMATS = {0: '{0:>s}', 1: '{0:>s} ({2:>s})',
                                           16: '{0:>s}[{1:>s}]',
                                           17: '{0:>s}[{1:>s}] ({2:>s})'}

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
sys.modules['gui.battle_control.arena_info.player_format'] = player_format
sys.modules['gui.battle_control.arena_info'].arena_vos = arena_vos
sys.modules['gui.battle_control.arena_info'].player_format = player_format

brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = type('P', (object,), {'realName': property(lambda s: 'Real')})
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp

# --- TAB panel stub
class TabPlayerModel(object):
    def __init__(self, dbID=0, userName='', hiddenUserName='', clanAbbrev='',
                 sessionID='s'):
        self._dbID = dbID
        self._userName = userName
        self._hiddenUserName = hiddenUserName
        self._clanAbbrev = clanAbbrev
        self._sessionID = sessionID

    def getDatabaseID(self):
        return self._dbID

    def setDatabaseID(self, v):
        self._dbID = v

    def getAvatarSessionID(self):
        return self._sessionID

    def setAvatarSessionID(self, v):
        self._sessionID = v

    def getUserName(self):
        return self._userName

    def setUserName(self, v):
        self._userName = v

    def getHiddenUserName(self):
        return self._hiddenUserName

    def setHiddenUserName(self, v):
        self._hiddenUserName = v

    def getClanAbbrev(self):
        return self._clanAbbrev

    def setClanAbbrev(self, v):
        self._clanAbbrev = v


class TabView(object):
    """Only _invalidatePersonalInfo is needed for these checks."""

    def __init__(self, vehicles):
        self._vehicles = vehicles

    def _invalidatePersonalInfo(self, player):
        info = self._vehicles[player.getDatabaseID()]
        player.setClanAbbrev(info['clanAbbrev'])
        player.setAvatarSessionID(info['avatarSessionID'])
        player.setUserName(info['name'])


tab_view = types.ModuleType('gui.impl.battle.battle_page.tab_view')
tab_view.TabView = TabView
sys.modules['gui.impl.battle.battle_page.tab_view'] = tab_view
sys.modules['gui.impl.battle.battle_page'].tab_view = tab_view

se = types.ModuleType('gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle')
se.VehicleInfoComponent = type('C', (object,), {
    'addVehicleInfo': lambda self, v, o=None: {}, '_data': {}})
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
                           'namePrefix': 'Player_', 'hideClanTag': True,
                           'scope.inBattle': True, 'scope.battleResults': True,
                           'exclude.ownName': True, 'exclude.friendName': True})
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set()
mod.IDENTITY.ownClanAbbrev = 'CLAN'
mod.IDENTITY.squadmateDBIDs = set()
mod.init()


def fresh(mode, prefix='Bot_'):
    mod.ANONYMISER.reset()
    mod.CONFIG._values['botMode'] = mode
    mod.CONFIG._values['botPrefix'] = prefix


def bot(session=None, name=':Ivan Petrov:', dbid=0):
    return PlayerInfoVO(accountDBID=dbid, avatarSessionID=session, name=name)


print()
print('=== default: bots get their own prefix ===')
fresh('botLabel')
b1 = bot(session=None, name=':Ivan Petrov:')
b2 = bot(session=None, name=':Jan Kowalski:')
check('bot labelled Bot_001', b1.getPlayerLabel() == 'Bot_001',
      b1.getPlayerLabel())
check('second bot labelled Bot_002', b2.getPlayerLabel() == 'Bot_002',
      b2.getPlayerLabel())
check('original colon name no longer shown', b1.getPlayerLabel() != ':Ivan Petrov:',
      b1.getPlayerLabel())

print()
print('=== players and bots use independent counters ===')
fresh('botLabel')
p1 = PlayerInfoVO(accountDBID=900, avatarSessionID='s900', name='Stranger1')
p2 = PlayerInfoVO(accountDBID=901, avatarSessionID='s901', name='Stranger2')
bb = bot()
check('player counter independent of bots',
      p1.getPlayerLabel() == 'Player_001' and p2.getPlayerLabel() == 'Player_002',
      (p1.getPlayerLabel(), p2.getPlayerLabel()))
check('bot counter independent of players', bb.getPlayerLabel() == 'Bot_001',
      bb.getPlayerLabel())

print()
print('=== custom bot prefix (e.g. a non-Latin script) ===')
fresh('botLabel', prefix=u'\u673a\u5668\u4eba_')   # 机器人_
b3 = bot()
check('custom bot prefix honoured',
      b3.getPlayerLabel().endswith('_001')
      and b3.getPlayerLabel() != 'Bot_001', b3.getPlayerLabel())
print('     bot label = %r' % b3.getPlayerLabel())

print()
print('=== botMode = "label": same scheme as players ===')
fresh('label')
b4 = bot()
check('bot uses player prefix in "label" mode',
      b4.getPlayerLabel().startswith('Player_'), b4.getPlayerLabel())

print()
print('=== botMode = "keep": untouched (opt-out) ===')
fresh('keep')
b5 = bot(name=':Ivan Petrov:')
check('bot name kept when mode=keep', b5.getPlayerLabel() == ':Ivan Petrov:',
      b5.getPlayerLabel())

print()
print('=== botMode = "blank": hidden ===')
fresh('blank')
b6 = bot()
check('bot name hidden when mode=blank', b6.getPlayerLabel() == '',
      repr(b6.getPlayerLabel()))

print()
print('=== stable numbering: same bot keeps its label ===')
fresh('botLabel')
mod.ANONYMISER.labelForID(1234, isBot=True)
again = mod.ANONYMISER.labelForID(1234, isBot=True)
check('same bot id -> same label', again == 'Bot_001', again)
playerSameId = mod.ANONYMISER.labelForID(1234, isBot=False)
check('same numeric id as a player does not collide',
      playerSameId == 'Player_001', playerSameId)

print()
print('=== VPN-safe: real bot name never leaks through format() ===')
fresh('botLabel')
fmt = PlayerFullNameFormatter()
botVO = bot(session=None, name=':Ivan Petrov:')
vInfo = VehicleArenaInfoVO(player=botVO)
result = fmt.format(vInfo, None)
check('composed bot name uses Bot_ prefix',
      result.playerName == 'Bot_001', result.playerName)
check('colon bot name absent from full string',
      ':Ivan Petrov:' not in result.playerFullName, result.playerFullName)
check('bot clan tag stripped', result.clanAbbrev == '', repr(result.clanAbbrev))

print()
print('=== TAB panel path handles bots too ===')
fresh('botLabel')
view = TabView({1: {'accountDBID': 0, 'avatarSessionID': None,
                    'name': ':Bot Guy:', 'clanAbbrev': 'BOTCLAN'}})
playerModel = TabPlayerModel(dbID=1, sessionID='')
view._invalidatePersonalInfo(playerModel)
check('TAB: bot labelled with Bot_ prefix',
      playerModel.getUserName() == 'Bot_001', playerModel.getUserName())
check('TAB: bot clan stripped', playerModel.getClanAbbrev() == '',
      repr(playerModel.getClanAbbrev()))

view2 = TabView({2: {'accountDBID': 909, 'avatarSessionID': 's909',
                     'name': 'HumanPlayer', 'clanAbbrev': 'HUMANCLAN'}})
humanModel = TabPlayerModel(dbID=2, sessionID='s909')
view2._invalidatePersonalInfo(humanModel)
check('TAB: human still gets Player_ prefix',
      humanModel.getUserName().startswith('Player_'), humanModel.getUserName())

print()
print('=== real player names unaffected by bot handling ===')
fresh('botLabel')
human = PlayerInfoVO(accountDBID=1, avatarSessionID='s1', name='MyOwnName')
check('self keeps real name', human.getPlayerLabel() == 'MyOwnName',
      human.getPlayerLabel())

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)