# -*- coding: utf-8 -*-
"""Verify every bot gets a DISTINCT number.

Reported from a real battle: "the in-battle panel shows all bots sharing the
same name Bot_013".

Root cause, in our own code.  Two facts about bots in WoT:

  * PlayerInfoVO.isBot() is `not avatarSessionID` -- so every bot has an EMPTY
    avatarSessionID, and bots have no accountDBID either.
  * Bot display names come from a first/last-name pool in helpers/bots.pyc, so
    two bots in one battle can legitimately share a name.

labelForID() had `if not key: key = 0`, and callers passed exactly those empty
fields as the key -- so all bots hashed to the same slot and were handed one
shared label.  The fix keys bots by vehicle id (unique per bot), falling back to
the value-object identity, and never to a shared constant.

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
    """Mirrors the real VO: bots have no dbID and an empty session id."""

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
pf = types.ModuleType('gui.battle_control.arena_info.player_format')
pf.PlayerFullNameFormatter = PlayerFullNameFormatter
pf._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16})
pf._PLAYER_FULL_NAME_FORMATS = {0: '{0:>s}', 1: '{0:>s} ({2:>s})',
                                16: '{0:>s}[{1:>s}]', 17: '{0:>s}[{1:>s}] ({2:>s})'}

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

print()
print('=== the reported bug: 13 bots must get 13 distinct numbers ===')
mod.ANONYMISER.reset()
labels = []
for vid in range(101, 114):          # 13 bots
    botVO = PlayerInfoVO(accountDBID=None, avatarSessionID=None,
                         name=':Ivan Petrov:')          # all SAME name
    vInfo = VehicleArenaInfoVO(vehicleID=vid, player=botVO)
    labels.append(fmt.format(vInfo, None).playerName)

check('13 bots produced 13 labels', len(labels) == 13, len(labels))
check('all labels are distinct', len(set(labels)) == 13, labels)
check('no shared label (the old "all Bot_013" symptom)',
      not (len(set(labels)) == 1), labels)
check('labels are Bot_001..Bot_013',
      labels == ['Bot_%03d' % i for i in range(1, 14)], labels)

print()
print('=== identical bot names must still be distinguished ===')
mod.ANONYMISER.reset()
same = []
for vid in (201, 202, 203):
    botVO = PlayerInfoVO(accountDBID=None, avatarSessionID=None,
                         name=':Jan Kowalski:')
    same.append(fmt.format(VehicleArenaInfoVO(vehicleID=vid, player=botVO),
                           None).playerName)
check('same-named bots get different numbers', len(set(same)) == 3, same)

print()
print('=== a bot keeps ONE number across repeated renders ===')
mod.ANONYMISER.reset()
botVO = PlayerInfoVO(accountDBID=None, avatarSessionID=None, name=':Bot Guy:')
vInfo = VehicleArenaInfoVO(vehicleID=301, player=botVO)
first = fmt.format(vInfo, None).playerName
again = fmt.format(vInfo, None).playerName
viaLabel = botVO.getPlayerLabel()
check('repeated format() is stable', first == again, (first, again))
check('getPlayerLabel agrees with format()', viaLabel == first,
      (viaLabel, first))

print()
print('=== bots and players stay in separate counters ===')
mod.ANONYMISER.reset()
b1 = fmt.format(VehicleArenaInfoVO(
    vehicleID=401, player=PlayerInfoVO(accountDBID=None, avatarSessionID=None,
                                       name=':B1:')), None).playerName
p1 = PlayerInfoVO(accountDBID=5001, avatarSessionID='s1', name='Human1')
p1Label = p1.getPlayerLabel()
b2 = fmt.format(VehicleArenaInfoVO(
    vehicleID=402, player=PlayerInfoVO(accountDBID=None, avatarSessionID=None,
                                       name=':B2:')), None).playerName
check('bot counter independent', b1 == 'Bot_001' and b2 == 'Bot_002',
      (b1, b2))
check('player counter unaffected by bots', p1Label == 'Player_001', p1Label)

print()
print('=== unattributable bots never share a number ===')
mod.ANONYMISER.reset()
# no key at all: labelForID must mint a fresh number, not reuse slot 0
orphans = [mod.ANONYMISER.labelForID(None, isBot=True) for _ in range(4)]
check('keyless bots each get their own number', len(set(orphans)) == 4, orphans)

print()
print('=== botMode variants still behave ===')
mod.CONFIG._values['botMode'] = 'keep'
mod.ANONYMISER.reset()
kept = fmt.format(VehicleArenaInfoVO(
    vehicleID=501, player=PlayerInfoVO(accountDBID=None, avatarSessionID=None,
                                       name=':Keep Me:')), None).playerName
check('botMode=keep', kept == ':Keep Me:', kept)

mod.CONFIG._values['botMode'] = 'blank'
mod.ANONYMISER.reset()
blanked = fmt.format(VehicleArenaInfoVO(
    vehicleID=502, player=PlayerInfoVO(accountDBID=None, avatarSessionID=None,
                                       name=':Hide Me:')), None).playerName
check('botMode=blank', blanked == '', repr(blanked))
mod.CONFIG._values['botMode'] = 'botLabel'

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)