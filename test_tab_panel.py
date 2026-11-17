# -*- coding: utf-8 -*-
"""Verify the TAB / full-stats panel and clan-tag paths are anonymised.

These two paths were MISSING in the shipped build and reported from a real game
session: "TAB panel anonymisation has no effect, and the clan name is still the
original".

They differ from the side panel because they never call the value-object
helpers. As the client's own tab view does:

  tab_view  _invalidatePersonalInfo(player):
      player.setClanAbbrev(vehicleInfo['clanAbbrev'])
      player.setUserName(vehicleInfo['name'])
      player.setHiddenUserName(vehicleInfo['fakeName'])
  and the model shows hiddenUserName only when isFakeNameVisible is set.

  stats_exchange/vehicle.py  VehicleInfoComponent.addVehicleInfo:
      data['clanAbbrev'] = playerVO.clanAbbrev     # straight off the VO

So this test builds fakes mirroring exactly those shapes.

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
# --- arena VOs (used by the side panel / Scaleform path)
class PlayerInfoVO(object):
    def __init__(self, accountDBID=None, avatarSessionID=None, name='',
                 clanAbbrev='', fakeName=''):
        self.accountDBID = accountDBID
        self.avatarSessionID = avatarSessionID
        self.name = name
        self.clanAbbrev = clanAbbrev
        self.fakeName = fakeName

    @property
    def isBot(self):
        return not self.avatarSessionID

    def getPlayerLabel(self):
        return self.name if self.name else 'Unknown'

    def getPlayerFakeLabel(self):
        return self.fakeName or ''


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
player_format = types.ModuleType('gui.battle_control.arena_info.player_format')
player_format.PlayerFullNameFormatter = PlayerFullNameFormatter
player_format._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16})
player_format._PLAYER_FULL_NAME_FORMATS = {}

for name, obj in (
        ('gui', types.ModuleType('gui')),
        ('gui.battle_control', types.ModuleType('gui.battle_control')),
        ('gui.battle_control.arena_info', types.ModuleType('gui.battle_control.arena_info')),
        ('gui.battle_results', types.ModuleType('gui.battle_results')),
        ('gui.battle_results.reusable', types.ModuleType('gui.battle_results.reusable')),
        ('gui.impl', types.ModuleType('gui.impl')),
        ('gui.impl.battle', types.ModuleType('gui.impl.battle')),
        ('gui.impl.battle.battle_page', types.ModuleType('gui.impl.battle.battle_page')),
        ('gui.Scaleform', types.ModuleType('gui.Scaleform')),
        ('gui.Scaleform.daapi', types.ModuleType('gui.Scaleform.daapi')),
        ('gui.Scaleform.daapi.view', types.ModuleType('gui.Scaleform.daapi.view')),
        ('gui.Scaleform.daapi.view.battle', types.ModuleType('gui.Scaleform.daapi.view.battle')),
        ('gui.Scaleform.daapi.view.battle.shared',
         types.ModuleType('gui.Scaleform.daapi.view.battle.shared')),
        ('gui.Scaleform.daapi.view.battle.shared.stats_exchange',
         types.ModuleType('gui.Scaleform.daapi.view.battle.shared.stats_exchange')),
):
    obj.__path__ = []
    sys.modules[name] = obj

sys.modules['gui.battle_control.arena_info.arena_vos'] = arena_vos
sys.modules['gui.battle_control.arena_info.player_format'] = player_format
sys.modules['gui.battle_control.arena_info'].arena_vos = arena_vos
sys.modules['gui.battle_control.arena_info'].player_format = player_format

# battle results stub
brp = types.ModuleType('gui.battle_results.reusable.players')


class BRPlayerInfo(object):
    @property
    def realName(self):
        return 'Real'
brp.PlayerInfo = BRPlayerInfo
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp


# --- the Gameface TAB panel
class TabPlayerModel(object):
    """Mirrors UserNameModel: userName / hiddenUserName / clanAbbrev."""

    def __init__(self, dbID=0, userName='', hiddenUserName='', clanAbbrev='',
                 isFakeNameVisible=False):
        self._dbID = dbID
        self._userName = userName
        self._hiddenUserName = hiddenUserName
        self._clanAbbrev = clanAbbrev
        self._isFakeNameVisible = isFakeNameVisible

    # getters/setters exactly as the generated view model exposes them
    def getDatabaseID(self):
        return self._dbID

    def setDatabaseID(self, v):
        self._dbID = v

    def getAvatarSessionID(self):
        return getattr(self, '_sessionID', '')

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

    def getIsFakeNameVisible(self):
        return self._isFakeNameVisible

    def displayedName(self):
        """How the view resolves what the user sees."""
        return self._hiddenUserName if self._isFakeNameVisible else self._userName


class PlayerList(object):
    def __init__(self, allies, enemies):
        self._allies = allies
        self._enemies = enemies

    def getAllies(self):
        return self._allies

    def getEnemies(self):
        return self._enemies


class _Obj(object):
    """Python 2.7 has no types.SimpleNamespace."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


class TabView(object):
    """Mirrors TabView: fills models from the engine arena dict."""

    def __init__(self, vehicles):
        self._vehicles = vehicles          # {vehicleId: arenaDict}
        self.viewModel = _Obj(playerList=PlayerList([], []))

    def _invalidatePersonalInfo(self, player):
        info = self._vehicles[player.getVehicleId()]
        player.setClanAbbrev(info['clanAbbrev'])
        player.setDatabaseID(info['accountDBID'])
        player.setAvatarSessionID(info['avatarSessionID'])
        player.setHiddenUserName(info['fakeName'])
        player.setUserName(info['name'])

    def _invalidateVehiclesInfo(self):
        allies, enemies = [], []
        for vid, info in self._vehicles.items():
            m = TabPlayerModel()
            m.getVehicleId = lambda vid=vid: vid
            self._invalidatePersonalInfo(m)
            (allies if info.get('team') == 1 else enemies).append(m)
        self.viewModel.playerList = PlayerList(allies, enemies)


tab_view = types.ModuleType('gui.impl.battle.battle_page.tab_view')
tab_view.TabView = TabView
sys.modules['gui.impl.battle.battle_page.tab_view'] = tab_view
sys.modules['gui.impl.battle.battle_page'].tab_view = tab_view


# --- Scaleform stats_exchange VehicleInfoComponent
class VehicleInfoComponent(object):
    def __init__(self):
        self._data = {}

    def addVehicleInfo(self, vInfoVO, overrides=None):
        playerVO = vInfoVO.player
        self._data = {
            'accountDBID': playerVO.accountDBID,
            'playerName': playerVO.getPlayerLabel(),
            'clanAbbrev': playerVO.clanAbbrev,      # straight off the VO
        }
        return self._data


se_vehicle = types.ModuleType(
    'gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle')
se_vehicle.VehicleInfoComponent = VehicleInfoComponent
sys.modules[se_vehicle.__name__] = se_vehicle
sys.modules['gui.Scaleform.daapi.view.battle.shared.stats_exchange'].vehicle = se_vehicle

# --- BigWorld
bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

# ------------------------------------------------------------------- load --
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))
mod.CONFIG._values.update({'enable': True, 'mode': 'label',
                           'namePrefix': 'Player_', 'hideClanTag': True,
                           'scope.inBattle': True, 'scope.battleResults': True})
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set([2])
mod.IDENTITY.ownClanAbbrev = 'CLAN'
mod.IDENTITY.squadmateDBIDs = set()
mod.ANONYMISER.reset()
mod.init()

print()
print('=== TAB panel (Gameface full-stats) ===')
check('TabView hooks installed',
      getattr(TabView._invalidatePersonalInfo, '_streamerMode_hooked', False)
      and getattr(TabView._invalidateVehiclesInfo, '_streamerMode_hooked', False),
      (getattr(TabView._invalidatePersonalInfo, '_streamerMode_hooked', None),
       getattr(TabView._invalidateVehiclesInfo, '_streamerMode_hooked', None)))

vehicles = {
    101: {'accountDBID': 900, 'avatarSessionID': 's900', 'name': 'NoobKiller',
          'fakeName': '', 'clanAbbrev': 'ENEMY', 'team': 2},
    102: {'accountDBID': 1, 'avatarSessionID': 's1', 'name': 'MyOwnName',
          'fakeName': '', 'clanAbbrev': 'CLAN', 'team': 1},
    103: {'accountDBID': 2, 'avatarSessionID': 's2', 'name': 'BuddyName',
          'fakeName': '', 'clanAbbrev': 'OTHER', 'team': 1},
    104: {'accountDBID': 5, 'avatarSessionID': 's5', 'name': 'ClanGuy',
          'fakeName': '', 'clanAbbrev': 'CLAN', 'team': 1},
}
view = TabView(vehicles)
view._invalidateVehiclesInfo()

allies = view.viewModel.playerList.getAllies()
enemies = view.viewModel.playerList.getEnemies()
check('TAB: allies/enemies populated', len(allies) == 3 and len(enemies) == 1,
      (len(allies), len(enemies)))

strangerModel = enemies[0]
check('TAB: stranger name anonymised',
      strangerModel.displayedName().startswith('Player_'),
      strangerModel.displayedName())
check('TAB: stranger clan tag removed', strangerModel.getClanAbbrev() == '',
      repr(strangerModel.getClanAbbrev()))
check('TAB: real name no longer present in userName field',
      strangerModel.getUserName() != 'NoobKiller', strangerModel.getUserName())

byName = dict((m.getDatabaseID(), m) for m in allies)
check('TAB: self keeps real name',
      byName[1].getUserName() == 'MyOwnName', byName.get(1))
check('TAB: self keeps clan tag',
      byName[1].getClanAbbrev() == 'CLAN', byName.get(1))
check('TAB: friend keeps real name',
      byName[2].getUserName() == 'BuddyName', byName.get(2))
check('TAB: friend keeps clan tag',
      byName[2].getClanAbbrev() == 'OTHER', byName.get(2))
check('TAB: clanmate keeps real name',
      byName[5].getUserName() == 'ClanGuy', byName.get(5))

# the "fake name visible" variant must not fall back to the real name
hidden = TabPlayerModel(dbID=901, userName='AnotherGuy', clanAbbrev='FOE',
                        isFakeNameVisible=True)
view2 = TabView({201: {'accountDBID': 901, 'avatarSessionID': 's901',
                       'name': 'AnotherGuy', 'fakeName': 'FakeGuy',
                       'clanAbbrev': 'FOE', 'team': 2}})
view2._invalidateVehiclesInfo()
m2 = view2.viewModel.playerList.getEnemies()[0]
m2.setIsFakeNameVisible = None       # model has no setter in our fake
check('TAB: fake-name-visible model anonymised on userName',
      m2.getUserName().startswith('Player_'), m2.getUserName())
check('TAB: fake-name field blanked so real name cannot resurface',
      m2.getHiddenUserName() == '', repr(m2.getHiddenUserName()))

print()
print('=== Scaleform players panel clan tag ===')
comp = VehicleInfoComponent()
panelVO = VehicleInfoVO = VehicleArenaInfoVO(
    PlayerInfoVO(accountDBID=950, avatarSessionID='s950', name='PanelGuy',
                 clanAbbrev='ENEMYCLAN'))
data = comp.addVehicleInfo(panelVO)
check('panel: stranger clan stripped', data.get('clanAbbrev') == '',
      repr(data.get('clanAbbrev')))
check('panel: stranger name anonymised',
      data.get('playerName', '').startswith('Player_'), data.get('playerName'))

comp2 = VehicleInfoComponent()
selfVO = VehicleArenaInfoVO(
    PlayerInfoVO(accountDBID=1, avatarSessionID='s1', name='MyOwnName',
                 clanAbbrev='CLAN'))
data2 = comp2.addVehicleInfo(selfVO)
check('panel: self clan kept', data2.get('clanAbbrev') == 'CLAN',
      repr(data2.get('clanAbbrev')))

print()
print('=== clan hiding disabled ===')
mod.CONFIG._values['hideClanTag'] = False
comp3 = VehicleInfoComponent()
v3 = VehicleArenaInfoVO(PlayerInfoVO(accountDBID=960, avatarSessionID='s960',
                                     name='X', clanAbbrev='KEEPCLAN'))
d3 = comp3.addVehicleInfo(v3)
check('panel: clan kept when hideClanTag=false', d3.get('clanAbbrev') == 'KEEPCLAN',
      repr(d3.get('clanAbbrev')))
mod.CONFIG._values['hideClanTag'] = True

print()
print('=== uninstall restores both paths ===')
mod.fini()
fresh = TabView({301: {'accountDBID': 970, 'avatarSessionID': 's970',
                       'name': 'VisibleAgain', 'fakeName': '',
                       'clanAbbrev': 'REALCLAN', 'team': 2}})
fresh._invalidateVehiclesInfo()
fm = fresh.viewModel.playerList.getEnemies()[0]
check('TAB: original behaviour restored after fini',
      fm.getUserName() == 'VisibleAgain' and fm.getClanAbbrev() == 'REALCLAN',
      (fm.getUserName(), fm.getClanAbbrev()))
comp4 = VehicleInfoComponent()
v4 = VehicleArenaInfoVO(PlayerInfoVO(accountDBID=980, avatarSessionID='s980',
                                     name='V', clanAbbrev='BACKAGAIN'))
d4 = comp4.addVehicleInfo(v4)
check('panel: original behaviour restored after fini',
      d4.get('clanAbbrev') == 'BACKAGAIN', repr(d4.get('clanAbbrev')))

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)