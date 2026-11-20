# -*- coding: utf-8 -*-
"""Team-stats badges ("战斗结果 -> 团队战绩") must be hidden too.

Reported from a real client: after the badge switch was added, badges were gone
from the personal scoreboard but STILL VISIBLE in the team stats view.

Cause, all ours: the team-stats view is built by
gui/battle_results/components/vehicles.pyc, which is a completely different code
path from the personal one:

    RegularVehicleStatsBlock.setRecord(result, reusable)
        player = result.player
        avatar = reusable.avatars.getAvatarInfo(player.dbID)
        self.hasSelectedBadge = avatar.badge != 0        # vehicles.pyc
        if self.hasSelectedBadge:
            self._setBadge(result, reusable)            # -> self.badge = PropertyValue(...)
        elif avatar.suffixBadge:
            self.suffixBadgeIcon = style.makeBadgeIcon(avatar.suffixBadge)
            ...

    BadgeBlock.setRecord(result, reusable)
        avatar = reusable.avatars.getAvatarInfo(player.dbID)
        badgeInfo = avatar.getFullBadgeInfo()           # -> buildBadge(...)
        self.icon = badgeInfo.getThumbnailIcon()
        ...

Neither touches VehicleArenaInfoVO.selectedBadge nor the results
PlayerInfo name accessors, so none of the earlier hooks applied.

The fix hooks both block methods and clears the badge fields, honouring the
same self/friends/clanmates exemption.

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
        self._prefixBadge = 101
        self._suffixBadge = 202

    @property
    def selectedBadge(self):
        return self._prefixBadge

    @property
    def selectedSuffixBadge(self):
        return self._suffixBadge

    def getBadgeExtraInfo(self):
        return ('', '')

    def getDisplayedName(self, name=None):
        return 'T-54' if name is None else name


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
             'gui.battle_results.components',
             'gui.battle_results.presenters',
             'gui.battle_results.presenters.packers',
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

bl = types.ModuleType('gui.doc_loaders.badges_loader')
bl.getSelectedByLayout = lambda ids: (101, 202) if ids else (0, 0)
bl.getAvailableBadges = lambda: {}
sys.modules['gui.doc_loaders.badges_loader'] = bl
sys.modules['gui.doc_loaders'].badges_loader = bl

shared_badges = types.ModuleType('gui.shared.badges')


class _Badge(object):
    def __init__(self, badgeID):
        self.badgeID = badgeID

    def getBadgeVO(self, size=None):
        return {'badgeID': self.badgeID}

    def getThumbnailIcon(self):
        return 'THUMB_%s' % self.badgeID

    def hasDynamicContent(self):
        return False

    def getDynamicContent(self):
        return ''


shared_badges.buildBadge = lambda bid, extra=None: _Badge(bid) if bid else None
sys.modules['gui.shared.badges'] = shared_badges
sys.modules['gui.shared'].badges = shared_badges

brp = types.ModuleType('gui.battle_results.reusable.players')
brp.PlayerInfo = type('P', (object,), {'realName': property(lambda s: 'Real')})
sys.modules['gui.battle_results.reusable.players'] = brp
sys.modules['gui.battle_results.reusable'].players = brp

# --- reusable avatars: AvatarInfo with badge/suffixBadge/getFullBadgeInfo
avatars_mod = types.ModuleType('gui.battle_results.reusable.avatars')


class AvatarInfo(object):
    def __init__(self, badge=101, suffixBadge=202):
        self._badge = badge
        self._suffixBadge = suffixBadge

    @property
    def badge(self):
        return self._badge

    @property
    def suffixBadge(self):
        return self._suffixBadge

    def getFullBadgeInfo(self):
        if not self._badge:
            return None
        return shared_badges.buildBadge(self._badge)


class _Avatars(object):
    def __init__(self, badge=101, suffixBadge=202):
        self._info = {}
        self._badge = badge
        self._suffix = suffixBadge

    def getAvatarInfo(self, dbID):
        if dbID is None:
            return None
        if dbID not in self._info:
            self._info[dbID] = AvatarInfo(self._badge, self._suffix)
        return self._info[dbID]


avatars_mod.AvatarInfo = AvatarInfo
avatars_mod.AvatarsInfo = _Avatars
sys.modules[avatars_mod.__name__] = avatars_mod
sys.modules['gui.battle_results.reusable'].avatars = avatars_mod

# --- components/vehicles.pyc: the TEAM STATS blocks
veh_mod = types.ModuleType('gui.battle_results.components.vehicles')


class _Result(object):
    def __init__(self, player):
        self.player = player


class BadgeBlock(object):
    """Mirrors the real BadgeBlock (vehicles.pyc)."""

    def __init__(self, meta=None, field=None):
        self.icon = ''
        self.content = ''
        self.sizeContent = ''
        self.isDynamic = False
        self.isAtlasSource = False

    def setRecord(self, result, reusable):
        player = result.player
        avatar = reusable.avatars.getAvatarInfo(player.dbID)
        badgeInfo = avatar.getFullBadgeInfo()
        if badgeInfo is not None:
            self.icon = badgeInfo.getThumbnailIcon()
            self.isDynamic = badgeInfo.hasDynamicContent()
            self.content = badgeInfo.getDynamicContent()
            self.sizeContent = 24


class RegularVehicleStatsBlock(object):
    """Mirrors the real RegularVehicleStatsBlock badge handling."""

    def __init__(self, meta=None, field=None):
        self.hasSelectedBadge = False
        self.suffixBadgeIcon = None
        self.suffixBadgeStripIcon = None
        self.badge = None

    def _setBadge(self, result, reusable):
        # real code: self.badge = PropertyValue(result, reusable)
        player = result.player
        avatar = reusable.avatars.getAvatarInfo(player.dbID)
        self.badge = avatar.getFullBadgeInfo()

    def setRecord(self, result, reusable):
        player = result.player
        avatar = reusable.avatars.getAvatarInfo(player.dbID)
        self.suffixBadgeIcon = None
        self.suffixBadgeStripIcon = None
        if avatar is not None:
            self.hasSelectedBadge = avatar.badge != 0
            if self.hasSelectedBadge:
                self._setBadge(result, reusable)
            elif avatar.suffixBadge:
                self.suffixBadgeIcon = 'strip_%s' % avatar.suffixBadge


veh_mod.BadgeBlock = BadgeBlock
veh_mod.RegularVehicleStatsBlock = RegularVehicleStatsBlock
sys.modules[veh_mod.__name__] = veh_mod
sys.modules['gui.battle_results.components'].vehicles = veh_mod

packer_mod = types.ModuleType(
    'gui.battle_results.presenters.packers.user_info')


class UserNames(object):
    @classmethod
    def _setBadges(cls, model, reusable, playerDbID):
        return None


packer_mod.UserNames = UserNames
sys.modules[packer_mod.__name__] = packer_mod
sys.modules['gui.battle_results.presenters.packers'].user_info = packer_mod

pm_mod = types.ModuleType(
    'gui.Scaleform.daapi.view.battle.shared.postmortem_panel')
pm_mod.PostmortemPanel = type('PM', (object,), {})
sys.modules[pm_mod.__name__] = pm_mod
sys.modules['gui.Scaleform.daapi.view.battle.shared'].postmortem_panel = pm_mod

tab_mod = types.ModuleType('gui.impl.battle.battle_page.tab_view')
tab_mod.TabView = type('TV', (object,), {})
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
mod.IDENTITY.squadmateDBIDs = set()
mod.init()


def resultFor(dbID, isBot=False):
    if isBot:
        p = PlayerInfoVO(accountDBID=None, avatarSessionID=None, name=':Bot:')
    else:
        p = PlayerInfoVO(accountDBID=dbID, avatarSessionID='s%d' % dbID,
                         name='N%d' % dbID)
    p.dbID = dbID
    return _Result(p)


class _Reusable(object):
    """Stands in for the battle-results ReusableInfo (only .avatars is used)."""

    def __init__(self, avatars):
        self.avatars = avatars


def reusableFor(badge=101, suffixBadge=202):
    return _Reusable(_Avatars(badge, suffixBadge))


print()
print('=== team stats: a stranger loses the badge ===')
blk = BadgeBlock()
blk.setRecord(resultFor(7000), reusableFor())
check('BadgeBlock icon cleared', blk.icon == '', repr(blk.icon))
check('BadgeBlock not dynamic', blk.isDynamic is False, blk.isDynamic)
check('BadgeBlock content cleared', blk.content == '', repr(blk.content))

st = RegularVehicleStatsBlock()
st.setRecord(resultFor(7000), reusableFor())
check('hasSelectedBadge False', st.hasSelectedBadge is False,
      st.hasSelectedBadge)
check('stats badge cleared', st.badge is None, st.badge)
check('suffix badge icon cleared', st.suffixBadgeIcon is None,
      st.suffixBadgeIcon)

print()
print('=== team stats: you / friends keep the badge ===')
me = RegularVehicleStatsBlock()
me.setRecord(resultFor(1), reusableFor())
check('own hasSelectedBadge kept', me.hasSelectedBadge is True,
      me.hasSelectedBadge)
check('own badge kept', me.badge is not None, me.badge)

fr = RegularVehicleStatsBlock()
fr.setRecord(resultFor(2), reusableFor())
check('friend badge kept', fr.hasSelectedBadge is True, fr.hasSelectedBadge)

me_b = BadgeBlock()
me_b.setRecord(resultFor(1), reusableFor())
check('own BadgeBlock icon kept', me_b.icon == 'THUMB_101', me_b.icon)

print()
print('=== team stats: bots lose the badge ===')
bot_block = RegularVehicleStatsBlock()
bot_block.setRecord(resultFor(0, isBot=True), reusableFor())
check('bot badge hidden', bot_block.hasSelectedBadge is False,
      bot_block.hasSelectedBadge)

mod.CONFIG._values['hideBotBadges'] = False
bot_block2 = RegularVehicleStatsBlock()
bot_block2.setRecord(resultFor(0, isBot=True), reusableFor())
check('bot badge kept when switch off', bot_block2.hasSelectedBadge is True,
      bot_block2.hasSelectedBadge)
mod.CONFIG._values['hideBotBadges'] = True

print()
print('=== suffix badge path also honoured ===')
suffix_st = RegularVehicleStatsBlock()
suffix_st.setRecord(resultFor(7001), reusableFor(badge=0, suffixBadge=303))
check('suffix-only stranger badge cleared', suffix_st.suffixBadgeIcon is None,
      suffix_st.suffixBadgeIcon)

suffix_me = RegularVehicleStatsBlock()
suffix_me.setRecord(resultFor(1), reusableFor(badge=0, suffixBadge=303))
check('suffix-only own badge kept', suffix_me.suffixBadgeIcon == 'strip_303',
      suffix_me.suffixBadgeIcon)

print()
print('=== master switch off restores everything ===')
mod.CONFIG._values['hideBadges'] = False
off = RegularVehicleStatsBlock()
off.setRecord(resultFor(7002), reusableFor())
check('badge kept when master off', off.hasSelectedBadge is True,
      off.hasSelectedBadge)
off_b = BadgeBlock()
off_b.setRecord(resultFor(7002), reusableFor())
check('BadgeBlock icon kept when master off', off_b.icon == 'THUMB_101',
      off_b.icon)
mod.CONFIG._values['hideBadges'] = True

print()
print('=== results scope off leaves it alone ===')
mod.CONFIG._values['scope.battleResults'] = False
scoped = RegularVehicleStatsBlock()
scoped.setRecord(resultFor(7003), reusableFor())
check('badge kept when results scope off', scoped.hasSelectedBadge is True,
      scoped.hasSelectedBadge)
mod.CONFIG._values['scope.battleResults'] = True

# A reopened report gets new visual blocks but reuses cached avatar data.
record = resultFor(2)
regular, suffix = reusableFor(), reusableFor(badge=0, suffixBadge=303)
mod.CONFIG._values.update({'badges.exemptKnown': False, 'scope.inBattle': False})
for stage, master, scope, visible in (
        ('first open', True, True, False), ('scope off', True, False, True),
        ('scope back on', True, True, False), ('master off', False, True, True)):
    mod.CONFIG._values.update({'enable': master, 'scope.battleResults': scope})
    icon, stats, strip = BadgeBlock(), RegularVehicleStatsBlock(), RegularVehicleStatsBlock()
    icon.setRecord(record, regular)
    stats.setRecord(record, regular)
    strip.setRecord(record, suffix)
    actual = (icon.icon, stats.hasSelectedBadge, getattr(stats.badge, 'badgeID', None),
              strip.suffixBadgeIcon)
    expected = ('THUMB_101', True, 101, 'strip_303') if visible else ('', False, None, None)
    check(stage + ': reopened team stats', actual == expected, (actual, expected))

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)