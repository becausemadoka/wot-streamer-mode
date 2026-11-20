# -*- coding: utf-8 -*-
"""Verify the badge (奖章) hiding switch.

Badges sit right next to the nickname and identify a player on their own -- a
rare medal often narrows someone down more than the name does -- so they get
their own switch, defaulting to hidden.

The awkward part is that badges are resolved through several different routes,
all of which must agree:

  in battle    VehicleArenaInfoVO.selectedBadge / selectedSuffixBadge (properties)
               -> players panel, death-cam, event panels, pre-battle markers
  TAB panel    TabView._invalidatePersonalInfo -> BadgeModel.setBadgeID
  results      UserNames._setBadges -> UserNameModel.setBadgeID
  unscoped     gui.shared.badges.buildBadge / badges_loader.getSelectedByLayout

The VO caches the layout before player identity is attached. Suppression is a
rendering decision; an identity-less lookup must not poison that cache.

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


# --------------------------------------------------------------- client stubs
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


class BadgeModel(object):
    def __init__(self, badgeID=''):
        self._badgeID = badgeID

    def setBadgeID(self, value):
        self._badgeID = value

    def getBadgeID(self):
        return self._badgeID


class UserNameModel(object):
    def __init__(self):
        self.badge = BadgeModel('PREFIX_MEDAL')
        self.suffixBadge = BadgeModel('SUFFIX_MEDAL')


class VehicleArenaInfoVO(object):
    """Mirrors the real construction: __init__ resolves badges via
    getSelectedByLayout BEFORE player is attached."""

    def __init__(self, vehicleID=0, player=None, badges=(101, 202),
                 overriddenBadge=None):
        self.vehicleID = vehicleID
        self.overriddenBadge = overriddenBadge
        self._prefixBadge, self._suffixBadge = bl.getSelectedByLayout(list(badges))
        self.player = player
        self._badgeExtra = ('', '')

    @property
    def selectedBadge(self):
        return self._prefixBadge

    @property
    def selectedSuffixBadge(self):
        return self._suffixBadge

    def getBadgeExtraInfo(self):
        return self._badgeExtra

    def getDisplayedName(self, name=None):
        return 'T-54' if name is None else name


def getSelectedByLayout(badgesIDs):
    """Real implementation returns (prefixBadge, suffixBadge)."""
    if not badgesIDs:
        return (0, 0)
    return (badgesIDs[0], badgesIDs[1] if len(badgesIDs) > 1 else 0)


class _VehType(object):
    shortNameWithPrefix = 'T-54'
    name = 'T-54'


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
             'gui.battle_results.presenters', 'gui.battle_results.presenters.packers',
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
sys.modules['gui.battle_control.arena_info.player_format'] = pf
sys.modules['gui.battle_control.arena_info'].arena_vos = arena_vos
sys.modules['gui.battle_control.arena_info'].player_format = pf

# --- gui.doc_loaders.badges_loader (the real module the game imports)
bl = types.ModuleType('gui.doc_loaders.badges_loader')
bl.getSelectedByLayout = getSelectedByLayout
bl.getAvailableBadges = lambda: {}
sys.modules['gui.doc_loaders.badges_loader'] = bl
sys.modules['gui.doc_loaders'].badges_loader = bl

# --- gui.shared.badges.buildBadge
class _Badge(object):
    def __init__(self, badgeID):
        self.badgeID = badgeID

    def getBadgeVO(self, size=None):
        return {'badgeID': self.badgeID}


shared_badges = types.ModuleType('gui.shared.badges')


def buildBadge(badgeID, extraData=None):
    if not badgeID:
        return None
    return _Badge(badgeID)


def other_badge_mod(original):
    def decorated(badgeID, extraData=None):
        badge = original(badgeID, extraData)
        if badge is not None:
            badge.other_mod_data = extraData
        return badge
    return decorated


shared_badges.buildBadge = other_badge_mod(buildBadge)
sys.modules['gui.shared.badges'] = shared_badges
sys.modules['gui.shared'].badges = shared_badges

# --- battle_results reusable players
brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = type('P', (object,), {'realName': property(lambda s: 'Real')})
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp

# --- results packer UserNames with _setBadges
packer_mod = types.ModuleType(
    'gui.battle_results.presenters.packers.user_info')


class UserNames(object):
    def __init__(self):
        self.called = []

    @classmethod
    def _setBadges(cls, model, reusable, playerDbID):
        cls_calls = getattr(UserNames, '_calls', None)
        if cls_calls is None:
            cls_calls = UserNames._calls = []
        cls_calls.append(playerDbID)
        if not playerDbID:
            return None
        model.badge.setBadgeID('PREFIX_MEDAL')
        model.suffixBadge.setBadgeID('SUFFIX_MEDAL')
        return None


packer_mod.UserNames = UserNames
sys.modules[packer_mod.__name__] = packer_mod
sys.modules['gui.battle_results.presenters.packers'].user_info = packer_mod

# --- postmortem panel
pm_mod = types.ModuleType(
    'gui.Scaleform.daapi.view.battle.shared.postmortem_panel')


class PostmortemPanel(object):
    def _makeKillerVO(self, vInfoVO):
        userVO = {'playerName': 'x'}
        badge = shared_badges.buildBadge(vInfoVO.selectedBadge,
                                         vInfoVO.getBadgeExtraInfo())
        if badge is not None:
            userVO['badgeVisualVO'] = badge.getBadgeVO(24)
        return userVO


pm_mod.PostmortemPanel = PostmortemPanel
sys.modules[pm_mod.__name__] = pm_mod
sys.modules['gui.Scaleform.daapi.view.battle.shared'].postmortem_panel = pm_mod

# --- TAB panel view model + view
class TabPlayerModel(object):
    def __init__(self, vehicleId=0, dbID=0, sessionID='', userName=''):
        self._vehicleId = vehicleId
        self._dbID = dbID
        self._sessionID = sessionID
        self._userName = userName
        self.badge = BadgeModel('PREFIX_MEDAL')
        self.suffixBadge = BadgeModel('SUFFIX_MEDAL')

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
        return ''

    def setHiddenUserName(self, v):
        pass

    def getClanAbbrev(self):
        return ''

    def setClanAbbrev(self, v):
        pass

    def setIgrType(self, v):
        pass

    def setIsTeamKiller(self, v):
        pass

    def setIsFakeNameVisible(self, v):
        pass


tab_mod = types.ModuleType('gui.impl.battle.battle_page.tab_view')


class TabView(object):
    def _invalidatePersonalInfo(self, player):
        player.setUserName('UNCHANGED')
        for holder, value in (('badge', 'PREFIX_MEDAL'),
                              ('suffixBadge', 'SUFFIX_MEDAL')):
            model = getattr(player, holder)
            model.setBadgeID(value)


tab_mod.TabView = TabView
sys.modules[tab_mod.__name__] = tab_mod
sys.modules['gui.impl.battle.battle_page'].tab_view = tab_mod

se = types.ModuleType('gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle')
se.VehicleInfoComponent = type('C', (object,), {'_data': {}})
sys.modules[se.__name__] = se
sys.modules['gui.Scaleform.daapi.view.battle.shared.stats_exchange'].vehicle = se

lobby_context = types.ModuleType('gui.lobby_context')
lobby_context.LobbyContext = type('LC', (object,), {})
sys.modules['gui.lobby_context'] = lobby_context

profile_mod = types.ModuleType(
    'gui.Scaleform.daapi.view.lobby.profile.ProfileWindow')
profile_mod.ProfileWindow = type('PW', (object,), {})
sys.modules[profile_mod.__name__] = profile_mod

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
                           'hideBadges': True, 'hideBotBadges': True,
                           'badges.exemptKnown': True,
                           'showRealNamesInProfile': True,
                           'scope.inBattle': True, 'scope.battleResults': True})
mod.IDENTITY.ownDBID = 1
mod.IDENTITY.friendDBIDs = set([2])
mod.IDENTITY.ownClanAbbrev = 'MYCLAN'
mod.IDENTITY.squadmateDBIDs = set([3])
mod.init()


def strangerVO(name='Enemy', vid=100):
    return VehicleArenaInfoVO(
        vehicleID=vid, player=PlayerInfoVO(accountDBID=7000 + vid,
                                           avatarSessionID='s%d' % vid,
                                           name=name))


def meVO():
    return VehicleArenaInfoVO(vehicleID=1,
                              player=PlayerInfoVO(accountDBID=1,
                                                  avatarSessionID='own',
                                                  name='MyOwnName'))


def friendVO():
    return VehicleArenaInfoVO(vehicleID=2,
                              player=PlayerInfoVO(accountDBID=2,
                                                  avatarSessionID='fr',
                                                  name='BuddyName'))


def botVO(vid=300):
    return VehicleArenaInfoVO(vehicleID=vid,
                              player=PlayerInfoVO(accountDBID=None,
                                                  avatarSessionID=None,
                                                  name=':Bot Guy:'))


print()
print('=== VO reads depend on the rendering surface ===')
vo = strangerVO()


def panel_badges(vo):
    with mod._Surface(mod.KEY_SCOPE_PANEL):
        return vo.selectedBadge, vo.selectedSuffixBadge


check('unscoped VO reads are native',
      (vo.selectedBadge, vo.selectedSuffixBadge) == (101, 202))
check('panel hides both badges', panel_badges(vo) == (0, 0))
check('death-cam user VO has no badge',
      'badgeVisualVO' not in PostmortemPanel()._makeKillerVO(vo),
      PostmortemPanel()._makeKillerVO(vo))

print()
print('=== in battle: you / friends keep the medal (exemption) ===')
check('own badges kept', panel_badges(meVO()) == (101, 202))
check('friend badges kept', panel_badges(friendVO()) == (101, 202))
check('own death-cam badge kept',
      'badgeVisualVO' in PostmortemPanel()._makeKillerVO(meVO()),
      PostmortemPanel()._makeKillerVO(meVO()))

print()
print('=== bots lose the medal by default ===')
check('bot badges hidden', panel_badges(botVO()) == (0, 0))
mod.CONFIG._values['hideBotBadges'] = False
check('bot badges kept when switch off', panel_badges(botVO()) == (101, 202))
mod.CONFIG._values['hideBotBadges'] = True

print()
print('=== the master switch turns everything back on ===')
mod.CONFIG._values['hideBadges'] = False
check('stranger badges kept when badge switch off',
      panel_badges(strangerVO()) == (101, 202))
check('death-cam badge kept when master off',
      'badgeVisualVO' in PostmortemPanel()._makeKillerVO(strangerVO()))
mod.CONFIG._values['hideBadges'] = True

print()
print('=== exemption switch OFF hides badges for everyone ===')
mod.CONFIG._values['badges.exemptKnown'] = False
check('own badges hidden when exemption off', panel_badges(meVO()) == (0, 0))
check('friend badges hidden when exemption off', panel_badges(friendVO()) == (0, 0))


def check_unscoped(stage):
    ids = [101, 202]
    selected = bl.getSelectedByLayout(ids)
    check(stage + ': native layout and input',
          selected == (101, 202) and ids == [101, 202], (selected, ids))
    extra = object()
    badge = shared_badges.buildBadge(101, extra)
    check(stage + ': preserves other mod decoration and arguments',
          getattr(badge, 'badgeID', None) == 101 and
          getattr(badge, 'other_mod_data', None) is extra, badge)


check_unscoped('exemptKnown off')
cached = meVO()
mod.CONFIG._values['enable'] = False
check('disabling master restores both cached badges on the same VO',
      (cached.selectedBadge, cached.selectedSuffixBadge) == (101, 202))
mod.CONFIG._values['enable'] = True
mod.CONFIG._values['badges.exemptKnown'] = True

print()
print('=== the VO still builds correctly (no fixtures broken) ===')
# With the exemption ON, the VO constructor must keep real badges, because
# getSelectedByLayout cannot know the player yet -- that is precisely why it
# must not blank unconditionally.
fresh = strangerVO()
check('VO constructed with badges intact', fresh._prefixBadge == 101,
      fresh._prefixBadge)
check('hook, not the constructor, does the hiding',
      mod.ANONYMISER.shouldHideBadge(playerVO=fresh.player) is True)

print()
print('=== TAB panel: model badges cleared ===')
mod.ANONYMISER.reset()
tp = TabPlayerModel(vehicleId=500, dbID=7000, sessionID='s500',
                    userName='EnemyTab')
TabView()._invalidatePersonalInfo(tp)
check('TAB prefix badge cleared', tp.badge.getBadgeID() == '',
      tp.badge.getBadgeID())
check('TAB suffix badge cleared', tp.suffixBadge.getBadgeID() == '',
      tp.suffixBadge.getBadgeID())

me_tp = TabPlayerModel(vehicleId=1, dbID=1, sessionID='own', userName='Me')
TabView()._invalidatePersonalInfo(me_tp)
check('TAB own badge kept', me_tp.badge.getBadgeID() == 'PREFIX_MEDAL',
      me_tp.badge.getBadgeID())

bot_tp = TabPlayerModel(vehicleId=501, dbID=0, sessionID='',
                        userName=':Bot:')
TabView()._invalidatePersonalInfo(bot_tp)
check('TAB bot badge cleared', bot_tp.badge.getBadgeID() == '',
      bot_tp.badge.getBadgeID())

print()
print('=== results screen: badges cleared per DBID ===')
# _setBadges is a classmethod on the real class; patch() must PRESERVE that, so
# call it the way the client does.
check('_setBadges is still a classmethod after patching',
      isinstance(UserNames.__dict__['_setBadges'], classmethod),
      type(UserNames.__dict__['_setBadges']))

model = UserNameModel()
UserNames._setBadges(model, None, 7000)
check('results stranger badge cleared', model.badge.getBadgeID() == '',
      model.badge.getBadgeID())
check('results stranger suffix cleared', model.suffixBadge.getBadgeID() == '',
      model.suffixBadge.getBadgeID())

model2 = UserNameModel()
UserNames._setBadges(model2, None, 1)
check('results own badge kept', model2.badge.getBadgeID() == 'PREFIX_MEDAL',
      model2.badge.getBadgeID())
check('results own suffix kept',
      model2.suffixBadge.getBadgeID() == 'SUFFIX_MEDAL',
      model2.suffixBadge.getBadgeID())

print()
print('=== reopen the personal results row across scope and account changes ===')
mod.CONFIG._values.update({'badges.exemptKnown': False, 'scope.inBattle': False})
for stage, transition, master, results, expected in (
        ('return to account', mod.onAccountBecomePlayer, True, True, ('', '')),
        ('reopen scope off', None, True, False, ('PREFIX_MEDAL', 'SUFFIX_MEDAL')),
        ('reopen scope on', None, True, True, ('', '')),
        ('next battle', mod.onAvatarBecomePlayer, False, True,
         ('PREFIX_MEDAL', 'SUFFIX_MEDAL')),
        ('leave battle', mod.onAvatarBecomeNonPlayer, True, True, ('', ''))):
    if transition:
        transition()
    mod.CONFIG._values.update({'enable': master, 'scope.battleResults': results})
    UserNames._setBadges(model2, None, 1)
    pair = model2.badge.getBadgeID(), model2.suffixBadge.getBadgeID()
    check(stage + ': results badges', pair == expected, (pair, expected))
    check_unscoped(stage)

print('=== failures never blank a badge by accident ===')
mod.CONFIG._values['hideBadges'] = True
# a VO with no player at all must not explode
vo_noplayer = VehicleArenaInfoVO(vehicleID=9, player=None)
check('no-player VO still answers', vo_noplayer.selectedBadge in (0, 101),
      vo_noplayer.selectedBadge)
check('shouldHideBadge tolerates None', mod.ANONYMISER.shouldHideBadge() in
      (True, False), mod.ANONYMISER.shouldHideBadge())

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)