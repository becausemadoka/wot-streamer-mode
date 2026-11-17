# -*- coding: utf-8 -*-
"""Verify the TAB panel and the in-battle panel assign the SAME bot numbers.

Reported from a real battle: "the in-battle panel numbers look right, but the
TAB panel's bot numbers do not match them -- TAB numbers are larger".

Cause (our code): the Gameface TAB view is a separate code path and was calling

    botKey(realName, None)          # no vehicle id

while the in-battle panel keys bots by vehicleID.  That created a SECOND,
independent bot counter, so TAB simply continued counting where the panel had
stopped -- hence systematically larger numbers.

The fix feeds the TAB model's own getVehicleId() into botKey(), so both paths
share one counter and one identity per bot.

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
        player = vInfoVO.player
        if playerName is None:
            playerName = vInfoVO.getDisplayedName(player.getPlayerLabel())
        return R(playerName, playerName, '', player.clanAbbrev, '', 'T-54')


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

brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = type('P', (object,), {'realName': property(lambda s: 'Real')})
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp

# --- Gameface TAB view stub
class TabPlayerModel(object):
    """Mirrors the real model: vehicleId, DBID, avatarSessionID, userName."""

    def __init__(self, vehicleId=0, dbID=0, sessionID='', userName='',
                 clanAbbrev=''):
        self._vehicleId = vehicleId
        self._dbID = dbID
        self._sessionID = sessionID
        self._userName = userName
        self._clanAbbrev = clanAbbrev
        self._hidden = ''

    def getVehicleId(self):
        return self._vehicleId

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
        return self._hidden

    def setHiddenUserName(self, v):
        self._hidden = v

    def getClanAbbrev(self):
        return self._clanAbbrev

    def setClanAbbrev(self, v):
        self._clanAbbrev = v


class TabView(object):
    def __init__(self, arena):
        self._arena = arena          # {vehicleId: dict}

    def _invalidatePersonalInfo(self, player):
        info = self._arena[player.getVehicleId()]
        player.setClanAbbrev(info['clanAbbrev'])
        player.setAvatarSessionID(info.get('avatarSessionID', ''))
        player.setHiddenUserName(info.get('fakeName', ''))
        player.setUserName(info['name'])


tab_view = types.ModuleType('gui.impl.battle.battle_page.tab_view')
tab_view.TabView = TabView
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

# The arena: 3 bots (identical display names, distinct vehicle ids)
BOT_NAMES = [':Ivan Petrov:', ':Jan Kowalski:', ':Boris Ivanov:']
BOT_VIDS = [101, 102, 103]


def panelLabel(vid, name):
    """Battle-panel label for a BOT (no dbID, empty session id)."""
    vo = PlayerInfoVO(accountDBID=None, avatarSessionID=None, name=name)
    return fmt.format(VehicleArenaInfoVO(vehicleID=vid, player=vo), None).playerName


def panelLabelHuman(dbID, name):
    """Battle-panel label for a real player (has dbID + session id)."""
    vo = PlayerInfoVO(accountDBID=dbID, avatarSessionID='s%d' % dbID, name=name)
    return fmt.format(VehicleArenaInfoVO(vehicleID=dbID, player=vo), None).playerName


def tabLabel(view, vid):
    model = TabPlayerModel(vehicleId=vid, dbID=0, sessionID='',
                           userName=':placeholder:')
    view._invalidatePersonalInfo(model)
    return model.getUserName()


print()
print('=== TAB first, then the panel: numbers must match ===')
mod.ANONYMISER.reset()
arena = dict((vid, {'accountDBID': 0, 'avatarSessionID': '',
                    'name': name, 'clanAbbrev': '', 'fakeName': ''})
             for vid, name in zip(BOT_VIDS, BOT_NAMES))
view = TabView(arena)

tabLabels = [tabLabel(view, vid) for vid in BOT_VIDS]
panelLabels = [panelLabel(vid, name) for vid, name in zip(BOT_VIDS, BOT_NAMES)]

check('TAB labels are distinct', len(set(tabLabels)) == 3, tabLabels)
check('panel labels are distinct', len(set(panelLabels)) == 3, panelLabels)
check('TAB and panel agree per bot', tabLabels == panelLabels,
      (tabLabels, panelLabels))
check('numbering starts at Bot_001 in both',
      tabLabels[0] == 'Bot_001' and panelLabels[0] == 'Bot_001',
      (tabLabels[0], panelLabels[0]))

print()
print('=== panel first, then TAB: numbers must match ===')
mod.ANONYMISER.reset()
panelFirst = [panelLabel(vid, name) for vid, name in zip(BOT_VIDS, BOT_NAMES)]
tabSecond = [tabLabel(view, vid) for vid in BOT_VIDS]
check('panel labels distinct', len(set(panelFirst)) == 3, panelFirst)
check('TAB follows the panel numbering', panelFirst == tabSecond,
      (panelFirst, tabSecond))

print()
print('=== TAB does not run its own counter (the reported symptom) ===')
mod.ANONYMISER.reset()
# simulate: panel labels a few bots, then TAB renders the same bots
partial = [panelLabel(BOT_VIDS[0], BOT_NAMES[0])]
tabAfter = [tabLabel(view, BOT_VIDS[0])]
check('TAB reuses the panel label, no extra number burned',
      tabAfter[0] == partial[0], (partial, tabAfter))
check('bot counter not advanced by TAB',
      mod.ANONYMISER._botNext == 1, mod.ANONYMISER._botNext)

print()
print('=== many bots: TAB numbering stays identical to the panel ===')
mod.ANONYMISER.reset()
vids = list(range(201, 214))
names = [':Bot %d:' % i for i in range(13)]
arena2 = dict((vid, {'accountDBID': 0, 'avatarSessionID': '',
                     'name': name, 'clanAbbrev': '', 'fakeName': ''})
              for vid, name in zip(vids, names))
view2 = TabView(arena2)
tabAll = [tabLabel(view2, vid) for vid in vids]
panelAll = [panelLabel(vid, name) for vid, name in zip(vids, names)]
check('13 TAB labels distinct', len(set(tabAll)) == 13, tabAll)
check('13 panel labels distinct', len(set(panelAll)) == 13, panelAll)
check('TAB == panel for all 13', tabAll == panelAll, (tabAll, panelAll))
check('TAB numbers are not larger than panel numbers',
      tabAll == panelAll, (tabAll, panelAll))

print()
print('=== human players unaffected by the bot path ===')
mod.ANONYMISER.reset()
humans = [panelLabelHuman(900 + i, 'Human%d' % i) for i in range(2)]
check('human numbering independent', humans == ['Player_001', 'Player_002'],
      humans)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)