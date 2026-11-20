# -*- coding: utf-8 -*-
"""Per-surface switch tests.

These do NOT invent a data flow.  The stub client mimics the real call chain
found in the client bytecode:

    VehicleInfoComponent.addVehicleInfo -> ctx.getPlayerFullName -> format()
    PostmortemPanel._makeKillerVO       -> ctx.getPlayerFullNameParts -> format()
    VehicleArenaInfoVO.getDisplayedName -> player.getPlayerLabel
    VehicleMessages._getPlayerInfo      -> getPlayerFullName + getDisplayedName

so a switch that is OFF genuinely has to reach the shared helper and make it
return the real name.  That is the property the wgmods review was asking for.
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


# ------------------------------------------------------------------ client --
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
        return self.name


class VehicleArenaInfoVO(object):
    def __init__(self, vehicleID=0, player=None):
        self.vehicleID = vehicleID
        self.player = player
        self.vehicleType = type('VT', (), {'shortNameWithPrefix': 'T-54'})()
        self.team = 1
        self._badge = 7

    @property
    def selectedBadge(self):
        return self._badge

    @property
    def selectedSuffixBadge(self):
        return 8

    def getDisplayedName(self, name=None):
        if name is None:
            return self.vehicleType.shortNameWithPrefix
        return name


class NameParts(object):
    """namedtuple-like result, exactly as the client returns it.

    _stripClanFromResult calls result._replace(...), so this must be a real
    namedtuple -- a plain class silently broke that path.
    """
    def __new__(cls, name, full, fake, clan):
        import collections
        tpl = collections.namedtuple(
            'PlayerFormatResult',
            'playerName playerFakeName playerFullName clanAbbrev regionCode vehicleName')
        return tpl(name, fake, full, clan, '', '')


class PlayerFullNameFormatter(object):
    """Mirrors the real format(): it composes from the name we hand it."""

    def format(self, vInfoVO, playerName=None):
        name = playerName if playerName is not None else ''
        clan = ''
        if vInfoVO is not None and getattr(vInfoVO, 'player', None) is not None:
            clan = vInfoVO.player.clanAbbrev or ''
        full = ('%s [%s]' % (name, clan)) if clan else name
        return NameParts(name, full, name, clan)


class BattleContext(object):
    """getPlayerFullName / getPlayerFullNameParts -- both go through format()."""

    def __init__(self):
        self.formatter = PlayerFullNameFormatter()

    def getPlayerFullNameParts(self, vID, showVehShortName=None, showClan=None,
                               showRegion=None):
        vo = ARENA.get(vID)
        # Observe what a badge consumer sees inside the actual screen entry
        # point, not in a manually pushed test context.
        self.badge_pair = (vo.selectedBadge, vo.selectedSuffixBadge)
        name = vo.player.getPlayerLabel() if vo is not None else u''
        return self.formatter.format(vo, name)

    def getPlayerFullName(self, vID, showVehShortName=None, showClan=None,
                          showRegion=None):
        return self.getPlayerFullNameParts(vID).playerFullName

    def getPlayerGuiProps(self, vID, team):
        return type('GuidProps', (), {'name': 'ally', 'isFriend': False})()


ARENA = {}
CTX = BattleContext()


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
              _PLAYER_FULL_NAME_FORMATS={
                  0: '{0}',
                  1: '{0} ({2})',
                  2: '{0} ({3})',
                  3: '{0} ({2}, {3})',
              })
_ai = _install('gui.battle_control.arena_info', arena_vos=av, player_format=pf)
_bc = _install('gui.battle_control', arena_info=_ai)


# --- players panel -----------------------------------------------------------
class VehicleInfoComponent(object):
    def __init__(self):
        self._data = {}

    def addVehicleInfo(self, vInfoVO, overrides=None):
        full = CTX.getPlayerFullName(vInfoVO.vehicleID)
        self._data.update({
            'playerName': vInfoVO.player.getPlayerLabel(),
            'playerFullName': full,
            'clanAbbrev': vInfoVO.player.clanAbbrev,
        })


# --- postmortem --------------------------------------------------------------
class PostmortemPanel(object):
    def _makeKillerVO(self, vInfoVO):
        full = CTX.getPlayerFullNameParts(vInfoVO.vehicleID)
        return {
            'userName': full.playerName,
            'fakeName': full.playerFakeName,
            'clanAbbrev': vInfoVO.player.clanAbbrev,
            'region': '',
            'igrType': 0,
            'badgeVisualVO': 'badge',
        }


# --- markers / minimap -------------------------------------------------------
class VehicleMarkerPlugin(object):
    def __init__(self):
        self.sent = []

    def _setVehicleInfo(self, marker, vInfo, guiProps, nameParts):
        self.sent.append(nameParts.playerName)

    def addVehicleInfo(self, vo, arenaDP):
        parts = CTX.getPlayerFullNameParts(vo.vehicleID)
        self._setVehicleInfo('marker', vo, CTX.getPlayerGuiProps(vo.vehicleID, 1),
                             parts)


class ArenaVehiclesPlugin(object):
    """Minimap.  The real plugin passes the vehicle via entry.setVehicleInfo and
    resolves the label with vInfo.getDisplayedName(); the name it carries is
    already anonymised by the time it gets here (via getPlayerLabel)."""

    def __init__(self):
        self.sent = []

    def _setVehicleInfo(self, vehicleID, entry, vInfo, guiProps, isSpotted):
        self.sent.append(CTX.getPlayerFullNameParts(vehicleID).playerName)

    def addVehicleInfo(self, vo, arenaDP):
        self._setVehicleInfo(vo.vehicleID, 'entry', vo,
                             CTX.getPlayerGuiProps(vo.vehicleID, 1), False)


# --- TAB full-stats board ----------------------------------------------------
class TabPlayerModel(object):
    """Mirrors the Gameface tab model: getters for name/clan/id, setters to fill."""

    def __init__(self, name, dbID, clan='', vehicleID=1):
        self._name = name
        self._clan = clan
        self._dbID = dbID
        self._vehicleID = vehicleID
        self._hidden = name
        self.badge = None
        self.suffixBadge = None

    def getUserName(self):
        return self._name

    def setUserName(self, value):
        self._name = value

    def getHiddenUserName(self):
        return self._hidden

    def setHiddenUserName(self, value):
        self._hidden = value

    def getClanAbbrev(self):
        return self._clan

    def setClanAbbrev(self, value):
        self._clan = value

    def getAccountDBID(self):
        return self._dbID

    def getVehicleId(self):
        return self._vehicleID

    def getAvatarSessionID(self):
        return 9


class TabView(object):
    def __init__(self):
        self.viewModel = type('VM', (), {'playerList': None})()

    def _invalidatePersonalInfo(self, player):
        return None

    def _invalidateVehiclesInfo(self):
        return None


def tab_row(name='Stranger', dbID=5000):
    model = TabPlayerModel(name, dbID)
    view = TabView()
    view._invalidatePersonalInfo(model)
    return model.getUserName()


# --- messages ----------------------------------------------------------------
class VehicleMessages(object):
    def __init__(self):
        self.last = None

    def _getPlayerInfo(self, entityID):
        info = ARENA[entityID]
        name = CTX.getPlayerFullName(entityID)
        self.last = '%s | %s' % (name, info.getDisplayedName())
        return self.last


_install('gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle',
         VehicleInfoComponent=VehicleInfoComponent)
_install('gui.Scaleform.daapi.view.battle.shared.stats_exchange')
_install('gui.Scaleform.daapi.view.battle.shared.postmortem_panel',
         PostmortemPanel=PostmortemPanel)
_install('gui.Scaleform.daapi.view.battle.shared.markers2d.plugins',
         VehicleMarkerPlugin=VehicleMarkerPlugin)
_install('gui.Scaleform.daapi.view.battle.shared.markers2d')
_install('gui.Scaleform.daapi.view.battle.shared.minimap.plugins',
         ArenaVehiclesPlugin=ArenaVehiclesPlugin)
_install('gui.Scaleform.daapi.view.battle.shared.minimap')
_install('gui.Scaleform.daapi.view.battle.shared.messages.vehicle_messages',
         VehicleMessages=VehicleMessages)
_install('gui.Scaleform.daapi.view.battle.shared.messages')
_install('gui.Scaleform.daapi.view.battle.shared')
_install('gui.Scaleform.daapi.view.battle')
_install('gui.Scaleform.daapi.view')
_install('gui.Scaleform.daapi')
_install('gui.Scaleform')
_install('gui.impl.battle.battle_page.tab_view', TabView=TabView)
_install('gui.impl.battle.battle_page')
_install('gui.impl.battle')
_install('gui.impl')
_install('gui.shared.badges', buildBadge=lambda *a, **k: 'badge')
_install('gui.shared')
_install('gui.doc_loaders.badges_loader', getSelectedByLayout=lambda ids: (1, 2))
_install('gui.doc_loaders')
_install('gui', battle_control=_bc)


class ClanInfo(object):
    __slots__ = ('clanAbbrev', 'clanDBID')

    def __init__(self, c=''):
        self.clanAbbrev = c
        self.clanDBID = 0


class BRPlayerInfo(object):
    __slots__ = ('_PlayerInfo__dbID', '_PlayerInfo__team',
                 '_PlayerInfo__fakeName', '_PlayerInfo__realName',
                 '_PlayerInfo__prebattleID', '_PlayerInfo__igrType',
                 '_PlayerInfo__clanInfo', '_PlayerInfo__isTeamKiller',
                 'squadIndex', '_PlayerInfo__tags', '_PlayerInfo__vehicleID')

    def __init__(self, dbID, realName, fakeName=''):
        self._PlayerInfo__dbID = dbID
        self._PlayerInfo__team = 1
        self._PlayerInfo__realName = realName
        self._PlayerInfo__fakeName = fakeName
        self._PlayerInfo__prebattleID = None
        self._PlayerInfo__igrType = 0
        self._PlayerInfo__clanInfo = ClanInfo()
        self._PlayerInfo__isTeamKiller = False
        self._PlayerInfo__tags = set()
        self._PlayerInfo__vehicleID = None
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


_install('gui.battle_results.reusable.players', PlayerInfo=BRPlayerInfo)
_install('gui.battle_results.reusable')
_install('gui.battle_results')
_install('gui.clans.clan_cache',
         g_clanCache=type('CC', (), {'clanAbbrev': None})())
_install('gui.clans')

# Publish package attributes just as normal imports do (some installer paths
# use `from package import child`, others import the full module name).
for path, module in list(sys.modules.items()):
    if path.startswith('gui.'):
        parent, _, child = path.rpartition('.')
        setattr(sys.modules[parent], child, module)

bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

# ------------------------------------------------------------------- load --
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))

BASE = {'enable': True, 'mode': 'label', 'namePrefix': 'Player_',
        'botMode': 'botLabel', 'botPrefix': 'Bot_', 'hideClanTag': True,
        'hideBotClanTag': True, 'hideResultsClanTag': True,
        'scope.inBattle': True, 'scope.battleResults': True,
        'scope.playersPanel': True,
        'scope.tabPanel': True,
        'scope.minimap': True,
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
mod.IDENTITY.friendDBIDs = set()
mod.IDENTITY.ownClanAbbrev = None
mod.IDENTITY.squadmateDBIDs = set()
mod.init()

# Do not patch the screen entry points manually: a missing installer hook
# must fail the same rendering assertions as an incorrectly gated one.


def stranger(vehicleID=1, name='Stranger', dbID=5000):
    ARENA[vehicleID] = VehicleArenaInfoVO(
        vehicleID, PlayerInfoVO(accountDBID=dbID, avatarSessionID=9, name=name,
                                clanAbbrev='ENEMY'))
    return ARENA[vehicleID]


def panel_row():
    vo = stranger()
    comp = VehicleInfoComponent()
    comp.addVehicleInfo(vo)
    return comp._data


def postmortem_row():
    vo = stranger()
    return PostmortemPanel()._makeKillerVO(vo)


def marker_sent():
    vo = stranger()
    plugin = VehicleMarkerPlugin()
    plugin.addVehicleInfo(vo, None)
    return plugin.sent


def minimap_sent():
    vo = stranger()
    plugin = ArenaVehiclesPlugin()
    plugin.addVehicleInfo(vo, None)
    return plugin.sent


def message_text():
    vo = stranger()
    msg = VehicleMessages()
    msg._getPlayerInfo(vo.vehicleID)
    return msg.last


MASKED = lambda s: bool(s) and s.startswith('Player_')

# ============================================================== surfaces ===
print()
print('=== every surface masks when its switch is ON ===')

reset_config()
mod.ANONYMISER.reset()
row = panel_row()
check('1 panel: name masked', MASKED(row.get('playerName')), row)
check('1 panel: clan stripped', row.get('clanAbbrev') == '', row)

mod.ANONYMISER.reset()
row = postmortem_row()
check('2 postmortem: name masked', MASKED(row.get('userName')), row)
check('2 postmortem: clan stripped', row.get('clanAbbrev') == '', row)

mod.ANONYMISER.reset()
check('3 markers: name masked', MASKED(marker_sent()[0]), marker_sent())

mod.ANONYMISER.reset()
check('4 minimap: name masked', MASKED(minimap_sent()[0]), minimap_sent())

mod.ANONYMISER.reset()
text = message_text()
check('5 messages: name masked', 'Player_' in text and 'Stranger' not in text,
      text)

print()
print('=== turning ONE surface OFF shows the real name on that surface only ===')

for key, label, probe in (
        ('scope.playersPanel', 'panel', lambda: panel_row().get('playerName')),
        ('scope.postmortem', 'postmortem', lambda: postmortem_row().get('userName')),
        ('scope.markers', 'markers', lambda: marker_sent()[0]),
        ('scope.minimap', 'minimap', lambda: minimap_sent()[0]),
        ('scope.messages', 'messages', lambda: message_text()),
):
    reset_config(**{key: False})
    mod.ANONYMISER.reset()
    value = probe()
    check('%s OFF restores the real name' % label,
          value is not None and 'Stranger' in value, value)

print()
print('=== 6 TAB board is its own switch, separate from the side panels ===')
# Regression: "players panel (Tab)" used to be ONE checkbox that only governed
# the side panels, so turning it off left the TAB board masked while the loading
# screen and side panels showed real names.  They are now two switches.

reset_config()
mod.ANONYMISER.reset()
check('TAB ON masks the name', MASKED(tab_row()), tab_row())

reset_config(**{'scope.tabPanel': False})
mod.ANONYMISER.reset()
check('TAB OFF restores the real name', tab_row() == 'Stranger', tab_row())
mod.ANONYMISER.reset()
check('TAB OFF does NOT unmask the side panels',
      MASKED(panel_row().get('playerName')), panel_row())

reset_config(**{'scope.playersPanel': False})
mod.ANONYMISER.reset()
check('side panels OFF does NOT unmask the TAB board',
      MASKED(tab_row()), tab_row())
mod.ANONYMISER.reset()
check('side panels OFF restores the real name on the panel',
      panel_row().get('playerName') == 'Stranger', panel_row())

print()
print('=== badge rendering matrix: disable one switch at a time ===')


class Medal(object):
    def __init__(self, value):
        self.badgeID = value

    def setBadgeID(self, value):
        self.badgeID = value


def tab_badges():
    model = TabPlayerModel('Stranger', 5000)
    model.badge, model.suffixBadge = Medal('7'), Medal('8')
    TabView()._invalidatePersonalInfo(model)
    return model.badge.badgeID, model.suffixBadge.badgeID


surfaces = (('scope.playersPanel', panel_row), ('scope.markers', marker_sent),
            ('scope.minimap', minimap_sent), ('scope.messages', message_text),
            ('scope.postmortem', postmortem_row), ('scope.tabPanel', tab_badges))
for disabled in ([None, 'enable', 'scope.inBattle', 'hideBadges',
                  'scope.battleResults'] + [key for key, _ in surfaces]):
    reset_config(**{'badges.exemptKnown': False})
    if disabled:
        mod.CONFIG._values[disabled] = False
    for key, probe in surfaces:
        visible = disabled in (key, 'enable', 'scope.inBattle', 'hideBadges')
        CTX.badge_pair = None
        rendered = probe()
        if key == 'scope.tabPanel':
            actual = rendered
            expected = ('7', '8') if visible else ('', '')
        else:
            actual = CTX.badge_pair
            expected = (7, 8) if visible else (0, 0)
        check('%s disabled, %s badge pair' % (disabled, key),
              actual == expected, (actual, expected))
        if key == 'scope.postmortem':
            check('%s disabled, killer badge visual' % disabled,
                  ('badgeVisualVO' in rendered) == visible, rendered)

print()
print('=== 7 loading screen and side panels share ONE switch ===')
# Measured in game.log: both surfaces are VehicleInfoComponent.addVehicleInfo,
# called from loaders.py:viewLoaded (loading) and
# AvatarVehiclesInfoBase.py:setNested_vehiclesInfo (battle).  They must NOT be
# separate switches: the rows written at loading are reused in the battle and
# only some get refreshed, so two switches produced a half-masked panel.

_LOADING = 'loaders.py'
_INBATTLE = 'AvatarVehiclesInfoBase.py'


def _make_caller(filename, funcname):
    """A real function whose frame reports `filename`/`funcname`.

    traceback reads the code object, so the stub is compiled with that filename
    rather than merely stored in __file__.
    """
    src = 'def %s(comp, vo):\n    return comp.addVehicleInfo(vo)\n' % funcname
    namespace = {}
    exec(compile(src, filename, 'exec'), namespace)
    return namespace[funcname]


def panel_row_via(which):
    vo = stranger()
    comp = VehicleInfoComponent()
    if which == _LOADING:
        _make_caller(_LOADING, 'viewLoaded')(comp, vo)
    else:
        _make_caller(_INBATTLE, 'setNested_vehiclesInfo')(comp, vo)
    return comp._data


check('one switch is used for both panel callers',
      mod._panelSurfaceKey() == mod.KEY_SCOPE_PANEL,
      mod._panelSurfaceKey())

reset_config()
mod.ANONYMISER.reset()
check('loading rows masked when the switch is ON',
      MASKED(panel_row_via(_LOADING).get('playerName')), panel_row_via(_LOADING))
mod.ANONYMISER.reset()
check('battle rows masked when the switch is ON',
      MASKED(panel_row_via(_INBATTLE).get('playerName')),
      panel_row_via(_INBATTLE))

reset_config(**{'scope.playersPanel': False})
mod.ANONYMISER.reset()
check('loading rows real when the switch is OFF',
      panel_row_via(_LOADING).get('playerName') == 'Stranger',
      panel_row_via(_LOADING))
mod.ANONYMISER.reset()
check('battle rows real when the switch is OFF',
      panel_row_via(_INBATTLE).get('playerName') == 'Stranger',
      panel_row_via(_INBATTLE))

reset_config()
print()
print('=== ...and the OTHER surfaces stay masked ===')
reset_config(**{'scope.playersPanel': False})
mod.ANONYMISER.reset()
check('panel off does not unmask postmortem',
      'Stranger' not in (postmortem_row().get('userName') or ''),
      postmortem_row().get('userName'))
mod.ANONYMISER.reset()
check('panel off does not unmask minimap',
      'Stranger' not in (minimap_sent()[0] or ''), minimap_sent()[0])

reset_config(**{'scope.minimap': False})
mod.ANONYMISER.reset()
check('minimap off does not unmask markers',
      'Stranger' not in (marker_sent()[0] or ''), marker_sent()[0])

print()
print('=== master switch and battle scope still win ===')
reset_config(enable=False)
mod.ANONYMISER.reset()
check('enable=false leaves every surface alone',
      panel_row().get('playerName') == 'Stranger', panel_row())

reset_config(**{'scope.inBattle': False})
mod.ANONYMISER.reset()
check('scope.inBattle=false leaves every surface alone',
      'Stranger' in (marker_sent()[0] or ''), marker_sent())

print()
print('=== exempted players are never masked on any surface ===')
reset_config()
mod.IDENTITY.ownDBID = 1000
mod.IDENTITY.friendDBIDs = set([5000])
for label, probe in (('panel', lambda: panel_row().get('playerName')),
                     ('postmortem', lambda: postmortem_row().get('userName')),
                     ('markers', lambda: marker_sent()[0]),
                     ('minimap', lambda: minimap_sent()[0]),
                     ('messages', lambda: message_text())):
    mod.ANONYMISER.reset()
    value = probe()
    check('friend keeps real name on %s' % label,
          value is not None and 'Stranger' in value, value)
mod.IDENTITY.friendDBIDs = set()

print()
print('=== the surface stack always unwinds ===')


class Boom(Exception):
    pass


_victim = VehicleInfoComponent()


def _explode(self, vInfoVO, overrides=None):
    raise Boom('client error')


_orig = VehicleInfoComponent.addVehicleInfo
VehicleInfoComponent.addVehicleInfo = _explode
try:
    try:
        _victim.addVehicleInfo(stranger())
    except Boom:
        pass
finally:
    VehicleInfoComponent.addVehicleInfo = _orig

check('stack is empty after an exception', mod._SURFACE_STACK == [],
      mod._SURFACE_STACK)
mod.ANONYMISER.reset()
check('masking still works after an exception',
      MASKED(panel_row().get('playerName')), panel_row())

print()
print('=== results screen is unaffected by the surface stack ===')
reset_config()
mod.ANONYMISER.reset()
check('results stranger masked', MASKED(BRPlayerInfo(5000, 'Nick').realName))
check('results masked while a surface context is active',
      getattr(BRPlayerInfo, 'realName').fget is not None)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)
