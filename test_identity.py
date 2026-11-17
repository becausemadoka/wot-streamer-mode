# -*- coding: utf-8 -*-
"""Verify identity resolution: own name must survive, even when the DBID
only becomes available after the battle loads.

Reported from a real session, game.log showed:

    [StreamerMode] identity: self=None clan=None friends=0 squadmates=0

almost every time.  Because the whitelist deliberately fails toward hiding,
an unresolved own DBID meant the player's OWN nickname got anonymised.  The
DBID only exists once `BigWorld.player.arena` is populated, so resolution has
to happen late and be retried -- not just once at init().

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


arena_vos = types.ModuleType('gui.battle_control.arena_info.arena_vos')
arena_vos.PlayerInfoVO = PlayerInfoVO
arena_vos.VehicleArenaInfoVO = VehicleArenaInfoVO
player_format = types.ModuleType('gui.battle_control.arena_info.player_format')
player_format.PlayerFullNameFormatter = type('F', (object,), {'format': lambda s, v, p=None: p})
player_format._FORMAT_MASK = type('M', (), {'NONE': 0, 'VEHICLE': 1, 'CLAN': 16})
player_format._PLAYER_FULL_NAME_FORMATS = {}

for name in ('gui', 'gui.battle_control', 'gui.battle_control.arena_info',
             'gui.battle_results', 'gui.battle_results.reusable'):
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

# --- avatar_helpers: models the real one (reads player.arena.vehicles)
OWN_ID = 7047814487


class _Arena(object):
    def __init__(self, ownID=None, playerVehicleID=None, vehicles=None):
        self.vehicles = vehicles if vehicles is not None else (
            {11: {'accountDBID': ownID}} if ownID else {})


class _Player(object):
    def __init__(self, arena=None, playerVehicleID=None):
        self.arena = arena
        self.playerVehicleID = playerVehicleID


bw = types.ModuleType('BigWorld')
bw.player = None            # nothing until a battle loads
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

ah = types.ModuleType('avatar_helpers')


def _getAvatarDatabaseID():
    player = getattr(bw, 'player', None)
    if player is None:
        return 0
    arena = getattr(player, 'arena', None)
    if arena is None:
        return 0
    vehID = getattr(player, 'playerVehicleID', None)
    if vehID is None or vehID not in arena.vehicles:
        return 0
    return arena.vehicles[vehID].get('accountDBID', 0)
ah.getAvatarDatabaseID = _getAvatarDatabaseID
sys.modules['avatar_helpers'] = ah

# --- messenger storage: friendships come from the FRIEND tag
USER_TAG = type('USER_TAG', (), {'FRIEND': 'friend-tag'})


class _User(object):
    def __init__(self, dbID, tags=()):
        self.dbID = dbID
        self._tags = set(tags)

    def getTags(self):
        return self._tags


FRIEND_ID = 555


class _Storage(object):
    def getList(self, criteria=None):
        return [_User(FRIEND_ID, (USER_TAG.FRIEND,)), _User(999)]


class _Descriptor(object):
    def __init__(self, cls=None):
        pass

    def get(self):
        return _Storage()


mconst = types.ModuleType('messenger.m_constants')
mconst.USER_TAG = USER_TAG
ms = types.ModuleType('messenger.storage')
ms.UsersStorage = object
ms.__path__ = []
msd = types.ModuleType('messenger.storage.descriptor')
msd.MessengerStorageDescriptor = _Descriptor
sys.modules['messenger'] = types.ModuleType('messenger')
sys.modules['messenger.m_constants'] = mconst
sys.modules['messenger.storage'] = ms
sys.modules['messenger.storage.descriptor'] = msd

# ------------------------------------------------------------------- load --
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))
mod.CONFIG._values.update({'enable': True, 'mode': 'label',
                           'namePrefix': 'Player_', 'hideClanTag': True,
                           'scope.inBattle': True, 'scope.battleResults': True,
                           'exclude.ownName': True, 'exclude.friendName': True,
                           'exclude.clanmateName': True, 'exclude.divmateName': True})
mod.init()

print()
print('=== resolution when the arena does not exist yet (lobby) ===')
mod.IDENTITY.reset()
mod.IDENTITY.resolve()
check('own DBID unknown before battle', mod.IDENTITY.ownDBID in (None, 0),
      mod.IDENTITY.ownDBID)

print()
print('=== own name must NOT be anonymised once the arena appears ===')
# a battle loads: BigWorld.player.arena now exists
bw.player = _Player(arena=_Arena(ownID=OWN_ID), playerVehicleID=11)
me = PlayerInfoVO(accountDBID=OWN_ID, avatarSessionID='s1', name='MyOwnName')
stranger = PlayerInfoVO(accountDBID=999, avatarSessionID='s2', name='NoobKiller')

# the render path must self-heal rather than hide our own name
label = me.getPlayerLabel()
check('own name preserved after late DBID resolution', label == 'MyOwnName',
      label)
check('identity now resolved', mod.IDENTITY.ownDBID == OWN_ID,
      mod.IDENTITY.ownDBID)
check('stranger still anonymised', stranger.getPlayerLabel().startswith('Player_'),
      stranger.getPlayerLabel())

print()
print('=== friends resolved from the FRIEND tag ===')
mod.IDENTITY.reset()
mod.IDENTITY.resolve()
check('friend DBIDs discovered', FRIEND_ID in mod.IDENTITY.friendDBIDs,
      mod.IDENTITY.friendDBIDs)
friend = PlayerInfoVO(accountDBID=FRIEND_ID, avatarSessionID='s3', name='Buddy')
check('friend keeps real name', friend.getPlayerLabel() == 'Buddy',
      friend.getPlayerLabel())
nonfriend = PlayerInfoVO(accountDBID=999, avatarSessionID='s4', name='Other')
check('non-friend anonymised', nonfriend.getPlayerLabel().startswith('Player_'),
      nonfriend.getPlayerLabel())

print()
print('=== raw-id path (TAB panel) preserves self too ===')
mod.IDENTITY.ownDBID = OWN_ID
mod.IDENTITY.friendDBIDs = set([FRIEND_ID])
mod.IDENTITY.ownClanAbbrev = None
check('id path: self not a stranger',
      mod.ANONYMISER.isStrangerIdentity(OWN_ID) is False)
check('id path: friend not a stranger',
      mod.ANONYMISER.isStrangerIdentity(FRIEND_ID) is False)
check('id path: unknown id is a stranger',
      mod.ANONYMISER.isStrangerIdentity(4242) is True)
check('id path: zero/None id is a stranger',
      mod.ANONYMISER.isStrangerIdentity(None) is True
      and mod.ANONYMISER.isStrangerIdentity(0) is True)

print()
print('=== clan comparison exempts clanmates ===')
mod.IDENTITY.ownClanAbbrev = 'CLAN'
check('same clan is not a stranger',
      mod.ANONYMISER.isStrangerIdentity(7777, 'CLAN') is False)
check('other clan is a stranger',
      mod.ANONYMISER.isStrangerIdentity(7778, 'ENEMY') is True)

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)