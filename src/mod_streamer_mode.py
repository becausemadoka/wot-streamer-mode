# -*- coding: utf-8 -*-
"""Streamer Mode for World of Tanks 2.4.1.

Anonymises the nicknames of strangers during a battle so a stream does not
broadcast other players' names.  Friends, clanmates, platoon mates and the
player themselves keep their real names.

Ported from the World of Warships mod of the same name, but the WoT client has
a different shape: instead of one network hook there is a small set of display
functions that every battle UI funnels through.  Verified against the shipped
client bytecode (see DEVELOPMENT.md):

    ArenaDataProvider.addVehicleInfo/updateVehicleInfo      (network -> VO)
      VehicleArenaInfoVO.player = PlayerInfoVO(name, fakeName, clanAbbrev...)

    BattleContext.getPlayerFullNameParts(...)   battle_ctx.pyc
      -> PlayerFullNameFormatter.format(...)    player_format.pyc
           -> VehicleArenaInfoVO.getDisplayedName()
                -> PlayerInfoVO.getPlayerLabel()

    post-battle: battle_results.reusable.players.PlayerInfo.realName

Nine UI modules call getPlayerFullNameParts/getDisplayedName, so patching this
chain covers the players panel (tab scoreboard), minimap, damage log, kill and
event messages, 3D vehicle markers, crosshair and the postmortem panel.

We never rewrite the stored data: only what the display functions return.  So a
failure cannot corrupt the client, and un-hooking restores everything exactly.
"""

import os
import sys
import traceback

import BigWorld

MOD_NAME = 'akemi.streamermode'
LOG_PREFIX = '[StreamerMode] '

# markers we put on the functions we replace
_ATTR_OURS = '_streamerMode_hooked'

# --- version lock ----------------------------------------------------------
#
# TARGET_VERSION pins a build to exactly ONE client version.  It is EMPTY in the
# normal build (no lock) and is SUBSTITUTED at package time by
# build_internal.py, which produces the locked internal test build.
#
# Why a build-time constant instead of always-on: the lock belongs to a
# particular distribution, not to the mod's logic.  Keeping the shipped build
# unlocked means one source tree still serves both, and the regular suites test
# behaviour rather than the gate.
#
# Why not just rely on mods/<version>/ folders: the client only loads packages
# from a folder named after its own version, but that is a property of the
# FOLDER.  A user who unzips the .wotmod into a newer mods/2.4.1.1/ (or into
# res_mods by hand) would still get it imported.  For an internal test build the
# guarantee should travel WITH the file, so init() checks and refuses.
#
# helpers.getClientVersion() reads ../version.xml and returns the raw string,
# e.g. ' v.2.4.1.0 #975 ' -- note the surrounding spaces and the '#' build part.
# Empty string == no lock (the normal public build).
TARGET_VERSION = ''

# --- settings keys ---------------------------------------------------------

KEY_ENABLE = 'enable'
KEY_MODE = 'mode'                       # 'label' | 'blank'
KEY_PREFIX = 'namePrefix'
KEY_BOT_MODE = 'botMode'                # 'botLabel' | 'label' | 'keep' | 'blank'
KEY_BOT_PREFIX = 'botPrefix'
KEY_EXCLUDE_SELF = 'exclude.ownName'
KEY_EXCLUDE_FRIEND = 'exclude.friendName'
KEY_EXCLUDE_CLANMATE = 'exclude.clanmateName'
KEY_EXCLUDE_SQUAD = 'exclude.divmateName'
KEY_HIDE_CLAN_TAG = 'hideClanTag'
KEY_HIDE_BOT_CLAN_TAG = 'hideBotClanTag'
KEY_HIDE_RESULTS_CLAN = 'hideResultsClanTag'
KEY_HIDE_BADGES = 'hideBadges'
KEY_HIDE_BOT_BADGES = 'hideBotBadges'
KEY_EXEMPT_BADGES = 'badges.exemptKnown'
KEY_SHOW_REAL_IN_PROFILE = 'showRealNamesInProfile'
KEY_SCOPE_BATTLE = 'scope.inBattle'
KEY_SCOPE_RESULTS = 'scope.battleResults'
KEY_SCOPE_PANEL = 'scope.playersPanel'
KEY_SCOPE_TAB = 'scope.tabPanel'
KEY_SCOPE_MINIMAP = 'scope.minimap'
KEY_SCOPE_MESSAGES = 'scope.messages'
KEY_SCOPE_MARKERS = 'scope.markers'
KEY_SCOPE_POSTMORTEM = 'scope.postmortem'

# ---------------------------------------------------------------------------
# surface context
#
# The five per-screen switches only work if the SHARED helpers know which screen
# is asking for a name.  The client builds every battle label through a handful
# of shared functions (PlayerFullNameFormatter.format, PlayerInfoVO.
# getPlayerLabel, VehicleArenaInfoVO.getDisplayedName), and all five surfaces
# occupy them from inside their own entry points:
#
#   players panel  VehicleInfoComponent.addVehicleInfo
#   minimap        ArenaVehiclesPlugin.addVehicleInfo / _setVehicleInfo
#   markers        VehicleMarkerPlugin._setVehicleInfo
#   messages       VehicleMessages._getPlayerInfo
#   postmortem     PostmortemPanel._makeKillerVO / __setPlayerInfo
#
# So each entry point pushes its key here for the duration of the call, and the
# shared helpers consult the top of the stack.  Everything in those entry points
# is synchronous -- the name is resolved, composed and handed to the engine
# before the method returns -- so a plain stack is enough; no thread or task
# state has to be carried.
#
# An EMPTY stack means "not inside a surface entry point": shared helpers then
# fall back to scope.inBattle, preserving the previous behaviour for call sites
# that were not wrapped.
# ---------------------------------------------------------------------------

_SURFACE_STACK = []


class _Surface(object):
    """Context manager: mark which battle surface is currently building a name.

    try/finally in __exit__ guarantees the stack is unwound even when the client
    raises inside the wrapped method, so one bad frame cannot leave every later
    name permanently masked (or permanently visible).
    """

    __slots__ = ('key',)

    def __init__(self, key):
        self.key = key

    def __enter__(self):
        _SURFACE_STACK.append(self.key)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        try:
            if _SURFACE_STACK and _SURFACE_STACK[-1] == self.key:
                _SURFACE_STACK.pop()
            elif self.key in _SURFACE_STACK:
                # out-of-order unwind: remove the last matching entry
                for index in range(len(_SURFACE_STACK) - 1, -1, -1):
                    if _SURFACE_STACK[index] == self.key:
                        del _SURFACE_STACK[index]
                        break
        except Exception:
            pass
        return False

DEFAULT_PREFIX = 'Player_'
DEFAULT_BOT_PREFIX = 'Bot_'

# The default prefix follows the client's UI language, so a Chinese client shows
# 玩家_001 rather than Player_001.  Only ever used when the user has NOT set
# namePrefix themselves: an explicit config/menu value always wins, so this can
# never override a deliberate choice.
LOCALISED_PREFIXES = {
    'zh': u'玩家_',
}

# How bots are treated.  Bots are not a privacy concern -- their names are game
# content -- but they are easy to confuse with players, so by default they get
# their own prefix and their own numbering.
BOT_MODE_BOT_LABEL = 'botLabel'         # "Bot_001"
BOT_MODE_SAME = 'label'                 # same as players: "Player_001"
BOT_MODE_KEEP = 'keep'                  # leave the client's own bot name
BOT_MODE_BLANK = 'blank'                # hide the name entirely
BOT_MODES = (BOT_MODE_BOT_LABEL, BOT_MODE_SAME, BOT_MODE_KEEP, BOT_MODE_BLANK)

# NOTE: every default here is the ANONYMISING one.  A missing or unreadable
# config must never put real names on screen, so the safe value is the default.
DEFAULTS = {
    KEY_ENABLE: True,
    KEY_MODE: 'label',
    # Empty means "not chosen": Config.prefix() then falls back to the
    # language-appropriate default (玩家_ on a zh client, Player_ elsewhere).
    # Putting a concrete string here would shadow that fallback forever.
    KEY_PREFIX: '',
    KEY_BOT_MODE: BOT_MODE_BOT_LABEL,
    KEY_BOT_PREFIX: DEFAULT_BOT_PREFIX,
    KEY_EXCLUDE_SELF: True,
    KEY_EXCLUDE_FRIEND: True,
    KEY_EXCLUDE_CLANMATE: True,
    KEY_EXCLUDE_SQUAD: True,
    KEY_HIDE_CLAN_TAG: True,
    KEY_HIDE_BOT_CLAN_TAG: True,
    KEY_HIDE_RESULTS_CLAN: True,
    # Badges (the medal icons) sit right next to the nickname and are a strong visual
    # identifier: a rare medal often narrows a player down more than the name.
    # Off by default would mean leaving that identifier on screen, so the safe
    # default is "hide".
    KEY_HIDE_BADGES: True,
    KEY_HIDE_BOT_BADGES: True,
    # Keep the badges of people you actually know (self/friends/clan/squad),
    # consistent with how names are handled.
    KEY_EXEMPT_BADGES: True,
    # Deliberately NOT anonymising: opening one player's details is a conscious
    # action by the streamer, and that window is exactly where the real identity
    # is wanted (checking a name to report/ban, looking someone up, etc.).
    KEY_SHOW_REAL_IN_PROFILE: True,
    KEY_SCOPE_BATTLE: True,
    KEY_SCOPE_RESULTS: True,
    KEY_SCOPE_PANEL: True,
    KEY_SCOPE_TAB: True,
    KEY_SCOPE_MINIMAP: True,
    KEY_SCOPE_MESSAGES: True,
    KEY_SCOPE_MARKERS: True,
    KEY_SCOPE_POSTMORTEM: True,
}


def logInfo(message):
    """Write an informational line to the client log.

    BigWorld's logging functions take (tag, message, None) -- verified against
    the client's own debug_utils._doLogFmt, which calls
        BigWorld.logInfo(prefix, msg, None)
    Calling them with two arguments raises TypeError, so get this right or the
    mod becomes silent.
    """
    try:
        BigWorld.logInfo(MOD_NAME, LOG_PREFIX + unicode(message), None)
    except TypeError:
        # older/newer engine build with a 2-arg signature
        try:
            BigWorld.logInfo(MOD_NAME, LOG_PREFIX + unicode(message))
        except Exception:
            pass
    except Exception:
        pass


def logError(message):
    try:
        BigWorld.logError(MOD_NAME, LOG_PREFIX + unicode(message), None)
    except TypeError:
        try:
            BigWorld.logError(MOD_NAME, LOG_PREFIX + unicode(message))
        except Exception:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# version gate
# ---------------------------------------------------------------------------

def parseClientVersion(raw):
    """Reduce a client version string to a comparable tuple of ints.

    The raw value comes from version.xml and looks like
        ' v.2.4.1.0 #975 '
    i.e. optional spaces, a 'v.' prefix and a '#'-separated build number.  We
    want only the dotted numeric release: (2, 4, 1, 0).

    Anything unparseable returns None, which the caller must treat as "do not
    run" -- for a version-locked test build, refusing on doubt is the safe side.
    """
    if raw is None:
        return None
    try:
        text = u'%s' % (raw,)
    except Exception:
        return None
    # drop the build number, then everything that is not digit or dot
    text = text.split('#')[0]
    digits = []
    for ch in text:
        if ch.isdigit() or ch == '.':
            digits.append(ch)
        elif digits:
            # a non-numeric run after the number (e.g. a trailing word)
            break
    candidate = ''.join(digits).strip('.')
    if not candidate:
        return None
    parts = candidate.split('.')
    # 'v.2.4.1.0' -> the leading 'v' leaves an empty first part
    parts = [p for p in parts if p]
    if not parts:
        return None
    try:
        return tuple(int(p) for p in parts)
    except Exception:
        return None


def runningClientVersion():
    """Best-effort client version as a tuple, or None when unknown.

    helpers.getClientVersion() is the client's own accessor (helpers/__init__.py
    reads ../version.xml).  Some builds only expose the short form, so fall back
    to that, then to nothing at all.
    """
    try:
        import helpers
    except Exception:
        return None
    for name in ('getClientVersion', 'getShortClientVersion',
                 'getFullClientVersion'):
        fn = getattr(helpers, name, None)
        if not callable(fn):
            continue
        try:
            parsed = parseClientVersion(fn())
        except Exception:
            parsed = None
        if parsed:
            return parsed
    return None


def versionIsSupported():
    """True when this client is the version this build was pinned to.

    An EMPTY TARGET_VERSION means "no lock" -- that is the normal public build,
    which is expected to run on whatever the folder layout allows.

    A non-empty but unparseable TARGET_VERSION is a broken build and is refused
    rather than run un-pinned.

    Returns (ok, runningTupleOrNone) so the caller can log what it saw.
    """
    if not TARGET_VERSION:
        return True, runningClientVersion()
    wanted = parseClientVersion(TARGET_VERSION)
    running = runningClientVersion()
    if not wanted:
        # pinned build whose own pin is malformed: do not run un-pinned
        return False, running
    if not running:
        return False, None
    return running == wanted, running


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

class Config(object):

    def __init__(self):
        self._values = dict(DEFAULTS)
        self._path = self._configPath()
        self._load()

    @staticmethod
    def _configPath():
        """Locate mods/configs/<MOD_NAME>/config.json.

        The path is NOT derived from __file__ any more.  Inside a .wotmod,
        __file__ is a virtual archive path like
            <root>/mods/<ver>/akemi.streamermode.wotmod/res/scripts/client/gui/mods/...
        and the old code split it on the FIRST 'mods' component, which is the
        package folder, then appended 'mods/configs/...' again -- producing
            <root>/scripts/client/gui/mods/configs/...        (observed in game.log)
        so a config file at the documented place was never read.

        The game root comes from BigWorld / sys.path instead, which is accurate,
        and every candidate is checked against disk.
        """
        rel = os.path.join('mods', 'configs', MOD_NAME, 'config.json')
        candidates = []

        # 1. Roots the engine exposes.
        roots = []
        for attr in ('getClientRoot', 'getWatchdogRoot'):
            try:
                fn = getattr(BigWorld, attr, None)
                if callable(fn):
                    value = fn()
                    if value:
                        roots.append(str(value))
            except Exception:
                pass

        # 2. sys.path often contains the client root (<root>/res/scripts/client).
        try:
            for entry in list(sys.path):
                if not entry:
                    continue
                norm = entry.replace('\\', '/')
                for suffix in ('/res/scripts/client', '\\res\\scripts\\client',
                               '/res/scripts', '/res'):
                    if norm.lower().endswith(suffix.lower()):
                        roots.append(norm[:len(norm) - len(suffix)])
                        break
        except Exception:
            pass

        # 3. __file__, but resolved by the package layout instead of a naive
        #    split: walk up until a directory that actually exists is reached.
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            walked = here
            for _ in range(12):
                walked = os.path.dirname(walked)
                if not walked or walked == os.path.dirname(walked):
                    break
                if os.path.isdir(os.path.join(walked, 'mods')):
                    roots.append(walked)
                    break
        except Exception:
            pass

        seen = set()
        for root in roots:
            path = os.path.join(root, rel)
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(path)

        for path in candidates:
            try:
                if os.path.isfile(path):
                    return path
            except Exception:
                continue
        # Nothing found: return the best guess so both the log line and the
        # "write a default config" path point somewhere sensible.
        return candidates[0] if candidates else None

    def _load(self):
        if not self._path or not os.path.isfile(self._path):
            logInfo('no config at %r; using defaults (anonymising)' % (self._path,))
            self._writeDefaults()
            return
        try:
            import json
            with open(self._path, 'rb') as fh:
                data = json.loads(fh.read().decode('utf-8'))
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in DEFAULTS:
                        self._values[key] = value
                logInfo('config loaded from %s' % self._path)
        except Exception:
            # keep DEFAULTS: a broken config must not expose names
            logError('config unreadable, keeping anonymising defaults: %s'
                     % traceback.format_exc())

    def _writeDefaults(self):
        """Materialise a default config so the file exists to be edited.

        Without this the documented <game>/mods/configs/<mod>/config.json simply
        was not there, so a user had to guess both the path and every key before
        they could turn on a debug option.  Best effort only: a read-only or
        missing parent must never stop the mod from running, and never changes
        what is loaded -- defaults stay in memory either way.
        """
        if not self._path:
            return
        try:
            import json
            folder = os.path.dirname(self._path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            if os.path.isfile(self._path):
                return
            payload = json.dumps(dict(DEFAULTS), indent=2, sort_keys=True)
            with open(self._path, 'wb') as fh:
                fh.write(payload.encode('utf-8') + b'\n')
            logInfo('wrote default config to %s' % self._path)
        except Exception:
            logError('could not write default config to %r: %s'
                     % (self._path, traceback.format_exc()))

    def flag(self, key):
        return bool(self._values.get(key, True))

    def enabled(self):
        return self.flag(KEY_ENABLE)

    def scope(self, key):
        """True when the given UI scope should be anonymised."""
        return self.enabled() and self.flag(key)

    def surface(self, key):
        """True when one *specific* battle surface may be anonymised.

        The five per-screen switches are narrower than scope.inBattle: a surface
        is only masked when the mod is on, the battle scope is on, AND its own
        switch is on.  scope.inBattle therefore stays the master gate for the
        whole battle HUD -- turning it off disables every surface.
        """
        return (self.enabled() and self.flag(KEY_SCOPE_BATTLE)
                and self.flag(key))

    def surfaceAllowed(self):
        """True when the surface currently asking for a name may be masked.

        The shared helpers (format / getPlayerLabel / getDisplayedName) cannot
        tell which screen is asking, so the answer comes from the context that
        the surface wrapper pushed.  Outside any context we fall back to the
        battle scope, which is the historical behaviour.
        """
        surface = _SURFACE_STACK[-1] if _SURFACE_STACK else None
        if surface is not None:
            return self.surface(surface)
        return self.scope(KEY_SCOPE_BATTLE)

    def mode(self):
        mode = self._values.get(KEY_MODE, 'label')
        return mode if mode in ('label', 'blank') else 'label'

    @staticmethod
    def _cleanPrefix(value, fallback):
        if not isinstance(value, basestring):
            return fallback
        value = value.strip()
        if not value:
            return fallback
        if isinstance(value, unicode):
            try:
                return value.encode('utf-8')
            except Exception:
                return fallback
        return value

    @staticmethod
    def _clientLanguage():
        """The client's UI language code, lowercased, or None when unknown.

        helpers.getClientLanguage() returns the i18n code (#settings:LANGUAGE_CODE,
        e.g. 'zh' on the CN client, 'en'/'ru'/... elsewhere) and falls back to
        constants.DEFAULT_LANGUAGE.  This is the same source the settings page
        uses to pick its label table.
        """
        try:
            from helpers import getClientLanguage
            lang = getClientLanguage()
            if lang:
                return unicode(lang).lower()
        except Exception:
            pass
        return None

    @classmethod
    def _defaultPrefix(cls):
        """Language-appropriate default prefix: 玩家_ on zh clients, else Player_.

        Returned as UTF-8 bytes to match what _cleanPrefix() produces for a
        user-supplied value.  prefix() must not change type depending on whether
        the prefix came from the config or from this default.
        """
        lang = cls._clientLanguage()
        if lang:
            # 'zh_CN' / 'zh-Hans' etc. all reduce to the 'zh' family
            for code, prefix in LOCALISED_PREFIXES.items():
                if lang == code or lang.startswith(code + '_') \
                        or lang.startswith(code + '-'):
                    try:
                        return prefix.encode('utf-8')
                    except Exception:
                        return DEFAULT_PREFIX
        return DEFAULT_PREFIX

    def prefix(self):
        """Player label prefix: the user's choice, else the localised default.

        Localisation applies only to the DEFAULT.  A value the user set -- in
        config.json or in the in-game menu -- is used verbatim, so switching the
        client language never silently rewrites a deliberate choice.
        """
        return self._cleanPrefix(self._values.get(KEY_PREFIX),
                                 self._defaultPrefix())

    def botMode(self):
        """How bot nicknames are treated. Default: give them their own prefix.

        Bots are not a privacy risk (their names are static game content), but
        they are easy to mistake for players. The client renders them with a
        distinguishing format -- helpers/bots.pyc uses ':{0} {1}:' -- which is
        why they show up as colon-wrapped names.
        """
        mode = self._values.get(KEY_BOT_MODE, BOT_MODE_BOT_LABEL)
        return mode if mode in BOT_MODES else BOT_MODE_BOT_LABEL

    def botPrefix(self):
        return self._cleanPrefix(self._values.get(KEY_BOT_PREFIX),
                                 DEFAULT_BOT_PREFIX)

    def hideBotClanTag(self):
        return bool(self._values.get(KEY_HIDE_BOT_CLAN_TAG, True))

    def botsAnonymised(self):
        """True when bots should be relabelled at all."""
        return self.botMode() != BOT_MODE_KEEP

    def hideResultsClanTag(self):
        """Strip the clan tag on the post-battle results screen.

        Results build their own name block from the PlayerInfo fields, so this
        needs its own switch rather than reusing hideClanTag (which the in-battle
        panels already apply).
        """
        return bool(self._values.get(KEY_HIDE_RESULTS_CLAN, True))

    def showRealNameInProfile(self):
        """Leave a single player's detail/profile window un-anonymised.

        The profile is opened deliberately from a context menu, and it reads the
        server dossier by DBID -- it never passes through the hooks used for the
        battle HUD.  This switch is what makes that behaviour intentional and
        configurable instead of accidental.
        """
        return bool(self._values.get(KEY_SHOW_REAL_IN_PROFILE, True))

    def hideBadges(self):
        """Hide the medal/badge drawn next to a nickname.

        Badges are a strong identifier in their own right: a rare medal narrows a
        player down even when the name is masked, so this is on by default.
        """
        return bool(self._values.get(KEY_HIDE_BADGES, True))

    def hideBotBadges(self):
        return bool(self._values.get(KEY_HIDE_BOT_BADGES, True))

    def badgesExemptKnown(self):
        """Keep badges for self/friends/clanmates/squadmates.

        Matches how names are treated, so the HUD stays consistent about "people
        you know" instead of stripping their medals too.
        """
        return bool(self._values.get(KEY_EXEMPT_BADGES, True))


CONFIG = Config()


# ---------------------------------------------------------------------------
# identity: who keeps a real name
# ---------------------------------------------------------------------------

class Identity(object):
    """Self / friends / clanmates / platoon mates.

    Any lookup that fails leaves the corresponding set empty, which means
    "nobody is exempt" -- i.e. more names are hidden.  That is the safe side.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.ownDBID = None
        self.ownClanAbbrev = None
        self.friendDBIDs = set()
        self.squadmateDBIDs = set()
        self.resolved = False
        self._tries = 0

    # -- lookups ------------------------------------------------------------

    def resolve(self):
        """(Re)gather identity data. Safe to call repeatedly.

        This REPLACES every snapshot rather than merging, and a failed or empty
        lookup leaves the corresponding set empty.  Merging was a real bug: an
        empty friend list or an empty platoon was ignored, so the previous
        account's friends and the previous battle's platoon mates stayed exempt
        forever.  Empty now means "nobody", which is the safe direction.

        Timing matters: in the lobby `BigWorld.player.arena` does not exist yet,
        so the own DBID is only available once a battle is loading. We therefore
        refresh at every battle start and at every account boundary.
        """
        self._tries += 1

        own = None
        try:
            own = self._readOwnDBID()
        except Exception:
            logError('own DBID lookup failed: %s' % traceback.format_exc())

        clan = None
        try:
            clan = self._readOwnClanAbbrev()
        except Exception:
            pass

        friends = set()
        try:
            friends = self._readFriendDBIDs() or set()
        except Exception:
            logError('friend lookup failed: %s' % traceback.format_exc())

        mates = set()
        try:
            mates = self._readSquadmateDBIDs() or set()
        except Exception:
            pass

        # Assign unconditionally -- an empty result must clear the old snapshot.
        self.ownDBID = own or None
        self.ownClanAbbrev = clan or None
        self.friendDBIDs = set(friends)
        self.squadmateDBIDs = set(mates)

        self.resolved = True
        logInfo('identity: self=%r clan=%r friends=%d squadmates=%d'
                % (self.ownDBID, self.ownClanAbbrev,
                   len(self.friendDBIDs), len(self.squadmateDBIDs)))

    @staticmethod
    def _readOwnDBID():
        """Own account DBID.

        `avatar_helpers.getAvatarDatabaseID` is the authoritative source while a
        battle is loading -- it reads BigWorld.player.arena.vehicles[ownVID]
        ['accountDBID'], which is exactly the id the arena data uses.
        """
        # 1) during battle: the arena's own record for our vehicle
        try:
            from avatar_helpers import getAvatarDatabaseID
            dbID = getAvatarDatabaseID()
            if dbID:
                return dbID
        except Exception:
            pass
        # 2) once the player object exists
        try:
            player = getattr(BigWorld, 'player', None)
            if player is not None:
                arena = getattr(player, 'arena', None)
                if arena is not None:
                    vehID = getattr(player, 'playerVehicleID', None)
                    vehicles = getattr(arena, 'vehicles', None)
                    if vehID is not None and vehicles is not None and vehID in vehicles:
                        dbID = vehicles[vehID].get('accountDBID')
                        if dbID:
                            return dbID
        except Exception:
            pass
        # 3) lobby helpers
        try:
            from gui.shared.utils import getPlayerDatabaseID
            dbID = getPlayerDatabaseID()
            if dbID:
                return dbID
        except Exception:
            pass
        try:
            from account_helpers import getAccountDatabaseID
            dbID = getAccountDatabaseID()
            if dbID:
                return dbID
        except Exception:
            pass
        return None

    @staticmethod
    def _readOwnClanAbbrev():
        """Own clan tag, from the clan cache in the lobby.

        The accessor is `g_clanCache.clanAbbrev`.  An earlier version read
        `g_clanCache.clanAccountInfo.clanAbbrev`, which does not exist on this
        client, so the clan exemption never worked and clanmates were masked.
        Each candidate is tried in turn because the cache shape is not part of
        any stable API.
        """
        try:
            from gui.clans.clan_cache import g_clanCache
            for attr in ('clanAbbrev', 'clanInfo'):
                value = getattr(g_clanCache, attr, None)
                if isinstance(value, basestring) and value:
                    return value
                # some builds expose a small record rather than the string
                abbrev = getattr(value, 'clanAbbrev', None)
                if isinstance(abbrev, basestring) and abbrev:
                    return abbrev
        except Exception:
            pass
        try:
            import Account
            info = getattr(Account.Account, 'playerInfo', None) or {}
            for key in ('clanAbbrev', 'clanInfo'):
                value = info.get(key)
                if isinstance(value, basestring) and value:
                    return value
                abbrev = getattr(value, 'clanAbbrev', None)
                if isinstance(abbrev, basestring) and abbrev:
                    return abbrev
        except Exception:
            pass
        return None

    @staticmethod
    def _readFriendDBIDs():
        """DBIDs of everyone on the friends list.

        Reaches the messenger UsersStorage through its descriptor, which is
        exactly how the in-battle player context menu does it.
        """
        result = set()
        storage = None

        # Preferred: the descriptor the in-battle context menu uses.
        try:
            from messenger.storage import UsersStorage
            from messenger.storage.descriptor import MessengerStorageDescriptor
            storage = MessengerStorageDescriptor(UsersStorage).get()
        except Exception:
            storage = None

        # Fallback: try the module-level accessor if present.
        if storage is None:
            try:
                from messenger.storage import storage_getter
                storage = storage_getter()
            except Exception:
                storage = None

        if storage is None:
            logInfo('friend list unavailable (no messenger storage)')
            return result

        # Strategy A: ask for friends by criteria.
        try:
            from messenger.proto.shared_find_criteria import FriendsFindCriteria
            for user in storage.getList(FriendsFindCriteria()):
                dbID = getattr(user, 'dbID', None)
                if dbID:
                    result.add(dbID)
            if result:
                return result
        except Exception:
            pass

        # Strategy B: walk every known contact and use the client's own
        # UserEntity.isFriend() (it tests the FRIEND tag).
        try:
            from messenger.m_constants import USER_TAG
            for user in storage.getList(None):
                try:
                    if USER_TAG.FRIEND in user.getTags():
                        dbID = getattr(user, 'dbID', None)
                        if dbID:
                            result.add(dbID)
                except Exception:
                    continue
        except Exception:
            pass

        if not result:
            logInfo('friend list empty or unavailable')
        return result

    @staticmethod
    def _readSquadmateDBIDs():
        """DBIDs of our platoon mates, read from the arena data provider."""
        result = set()
        try:
            arenaDP = _arenaDP()
            if arenaDP is None:
                return result
            ownVID = None
            try:
                from gui.battle_control import avatar_getter
                ownVID = avatar_getter.getPlayerVehicleID()
            except Exception:
                pass
            ownPrebattle = None
            for vo in arenaDP.getVehiclesInfoIterator():
                if ownVID is not None and vo.vehicleID == ownVID:
                    ownPrebattle = vo.prebattleID
                    break
            if not ownPrebattle:
                return result
            for vo in arenaDP.getVehiclesInfoIterator():
                if vo.prebattleID == ownPrebattle:
                    dbID = getattr(vo.player, 'accountDBID', None)
                    if dbID:
                        result.add(dbID)
        except Exception:
            logError('squadmate lookup failed: %s' % traceback.format_exc())
        return result

    # -- predicates ---------------------------------------------------------

    def isSelf(self, playerVO):
        if not self.ownDBID:
            return False
        return getattr(playerVO, 'accountDBID', None) == self.ownDBID

    def isFriend(self, playerVO):
        dbID = getattr(playerVO, 'accountDBID', None)
        return bool(dbID) and dbID in self.friendDBIDs

    def isClanmate(self, playerVO):
        if not self.ownClanAbbrev:
            return False
        tag = getattr(playerVO, 'clanAbbrev', None)
        return bool(tag) and tag == self.ownClanAbbrev

    def isSquadmate(self, playerVO):
        dbID = getattr(playerVO, 'accountDBID', None)
        return bool(dbID) and dbID in self.squadmateDBIDs


IDENTITY = Identity()


def _arenaDP():
    """Arena data provider for the current battle, or None."""
    try:
        from helpers import dependency
        from skeletons.gui.battle_session import IBattleSessionProvider
        provider = dependency.instance(IBattleSessionProvider)
        if provider is not None:
            return provider.getArenaDP()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# the anonymiser
# ---------------------------------------------------------------------------

def _isBot(playerVO):
    """True when this player is a bot.

    In arena_vos, isBot is a @property returning a bool; do not assume a method.
    """
    try:
        value = getattr(playerVO, 'isBot', None)
        if value is None:
            return False
        return bool(value() if callable(value) else value)
    except Exception:
        return False


class _ObjKey(object):
    """Hashable identity for a bot's value object.

    PlayerInfoVO defines __eq__ but no __hash__, so it is UNHASHABLE in Python 2
    and cannot be used as a dict key (TypeError).  This wraps it: equality and
    hashing are by identity, and the reference keeps the object alive so its id
    can never be recycled into another bot's slot.
    """

    __slots__ = ('obj', 'token')

    def __init__(self, obj):
        self.obj = obj
        self.token = id(obj)

    def __hash__(self):
        return self.token

    def __eq__(self, other):
        if isinstance(other, _ObjKey):
            return self.token == other.token and self.obj is other.obj
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __repr__(self):
        return '<bot %d>' % self.token


class Anonymiser(object):
    """Assigns display labels.

    Players and bots get independent counters, so the HUD shows e.g.
    `Player_001..Player_014` beside `Bot_001..Bot_003` rather than one
    interleaved sequence -- which also makes match composition readable at a
    glance.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self._index = {}          # key -> label, shared lookup
        self._next = 0            # player counter
        self._botNext = 0         # bot counter
        self._warned = False
        # bot name -> canonical key, so a caller that lacks a vehicle id still
        # resolves to the same entry the vehicle-aware path created
        self._botNameKeys = {}
        # dbID -> the original name we replaced, so the profile window can undo
        # our masking when the "show real names in profile" option is on.
        self._realNames = {}
        # session-scoped, so a new battle starts clean
        self._prevSession = None

    # -- bot keys -----------------------------------------------------------

    def noteBotVehicle(self, rawName, vehicleID):
        """Bind a bot name to its vehicle id.

        Called from the one hook that knows BOTH (VehicleArenaInfoVO
        .getDisplayedName).  PlayerInfoVO carries no vehicle id, so this binding
        is what lets getPlayerLabel() agree with the rest of the HUD.
        """
        if rawName and vehicleID is not None:
            if rawName not in self._botNameKeys:
                self._botNameKeys[rawName] = vehicleID
            elif self._botNameKeys[rawName] == rawName:
                # a name-only entry exists; upgrade it to the real vehicle id so
                # later calls land on the same label
                self._botNameKeys[rawName] = vehicleID

    def botKey(self, realName, hint=None, obj=None):
        """Canonical identity for one bot.

        Bots expose no accountDBID and an empty avatarSessionID -- those are
        deliberately never used, because being empty for EVERY bot is exactly
        what made them all share one label ("all bots are Bot_013").

        Identity sources, best first:
          1. ``hint`` -- the vehicle id.  Unique for the whole battle and never
             recycled, so it can never merge two bots.
          2. the bot name -- the only handle getPlayerLabel() has (PlayerInfoVO
             carries no vehicle id).  Bot names come from a first/last-name pool,
             so they CAN repeat; we therefore accept a collision only by
             reusing the id already given to that name, which is the lesser evil
             compared with showing one bot two different numbers.
          3. the value object via _ObjKey (PlayerInfoVO is unhashable, so it
             cannot be used directly as a dict key).

        Returns something hashable.
        """
        # 1. CONSISTENCY FIRST.  getPlayerLabel() carries no vehicle id, so it
        #    keys the bot by its value object.  When a vehicle-aware path runs
        #    later for the SAME object it must reuse that label, otherwise the
        #    same bot shows one number in the panel and another in the feed.
        if obj is not None:
            objKey = _ObjKey(obj)
            if ('bot', objKey.token) in self._index:
                return objKey
        # 2. Otherwise prefer the vehicle id: genuinely unique per bot for the
        #    whole battle, and never recycled.  Bot NAMES cannot be trusted here
        #    -- helpers/bots.pyc builds them from a first/last-name pool, so two
        #    bots may share one, and binding on the name would merge them (which
        #    is what produced the "all bots are Bot_013" report).
        if hint is not None and isinstance(hint, (int, long)) and hint:
            # If this exact object was already labelled (via getPlayerLabel),
            # alias the vehicle id onto that same label so both paths agree.
            if obj is not None:
                objToken = _ObjKey(obj).token
                existing = self._index.get(('bot', objToken))
                if existing is not None:
                    self._index[('bot', hint)] = existing
            self.bindBotName(realName, hint)
            return hint
        if realName:
            # Reuse whatever identity another path already bound to this bot's
            # name, so one bot never shows two numbers across panels.  This must
            # be checked BEFORE falling through to the object key, otherwise a
            # caller that passes obj (display()) would bypass the name binding
            # entirely and mint a fresh label.
            bound = self._botNameKeys.get(realName)
            if bound is not None:
                return bound
        if obj is not None:
            key = _ObjKey(obj)
            self.bindBotName(realName, key)
            return key
        if realName:
            self._botNameKeys[realName] = realName
            return realName
        return None

    # -- labels -------------------------------------------------------------

    def labelFor(self, playerVO):
        """Stable per-battle label, so a player keeps one number everywhere."""
        if _isBot(playerVO):
            vehicleID = getattr(playerVO, 'vehicleID', None)
            name = getattr(playerVO, 'name', None) or \
                getattr(playerVO, 'fakeName', None)
            if vehicleID:
                # Unique handle: use it and record the name binding so the
                # name-only path (getPlayerLabel) resolves to this same label.
                self.bindBotName(name, vehicleID)
                return self.labelForID(vehicleID, isBot=True)
            key = self.botKey(name, None, obj=playerVO)
            if key is None:
                key = _ObjKey(playerVO)
            return self.labelForID(key, isBot=True)
        key = getattr(playerVO, 'accountDBID', None)
        if not key:
            key = getattr(playerVO, 'avatarSessionID', None)
        return self.labelForID(key if key else id(playerVO), isBot=False)

    def labelForID(self, key, isBot=False):
        """Same numbering, addressed by raw DBID/session id or a bot identity.

        The TAB panel only gives us an integer id, and it must produce the SAME
        number the rest of the HUD already assigned to that player.

        Bots have NO accountDBID and an EMPTY avatarSessionID, so a bare
        `if not key: key = 0` made every bot share one entry and therefore one
        label ("all bots showed Bot_013").  When nothing unique is available we
        deliberately mint a fresh label instead of reusing the shared 0 slot.

        Bot identity is expressed as an _ObjKey wrapper, NOT the VO itself:
        PlayerInfoVO defines __eq__ without __hash__, so it is unhashable in
        Python 2 and using it as a dict key raises TypeError.  _ObjKey also keeps
        a reference to the object, so its id cannot be recycled into another
        bot's slot.
        """
        if isinstance(key, _ObjKey):
            key = key.token
        if not key:
            if isBot:
                # no usable identity: give this bot its own number rather than
                # letting every unidentified bot share one.
                self._botNext += 1
                return '%s%03d' % (CONFIG.botPrefix(), self._botNext)
            key = 0

        # bot keys are namespaced so a bot and a player can never collide
        lookup = ('bot', key) if isBot else ('player', key)
        label = self._index.get(lookup)
        if label is None:
            if isBot:
                self._botNext += 1
                label = '%s%03d' % (CONFIG.botPrefix(), self._botNext)
            else:
                self._next += 1
                label = '%s%03d' % (CONFIG.prefix(), self._next)
            self._index[lookup] = label
        return label

    def bindBotName(self, realName, key):
        """Remember name -> identity for a bot, without overriding an existing
        binding.  Called by the vehicle-aware paths so the name-only path
        (getPlayerLabel) lands on the same label."""
        if realName and realName not in self._botNameKeys:
            self._botNameKeys[realName] = key

    # -- original names -----------------------------------------------------

    def rememberRealName(self, dbID, realName):
        """Record the name we are about to replace, keyed by DBID.

        The profile window is fed by the context menu, which passes whatever name
        the results screen handed it -- i.e. our label.  Keeping the original lets
        that window show the true name again when the user opts out.
        """
        if dbID and realName:
            self._realNames.setdefault(dbID, realName)

    def realNameFor(self, dbID):
        """The original name for a DBID, or None if we never masked it."""
        if not dbID:
            return None
        return self._realNames.get(dbID)

    # -- decisions ----------------------------------------------------------

    def botDisplay(self, realName, key=None, isBot=True):
        """Name to show for a bot, honouring the configured bot mode.

        ``key`` must identify THIS bot.  Bots expose no accountDBID and an empty
        avatarSessionID, so those are useless as keys -- using them made every
        bot share one label (the "all bots are Bot_013" bug).  Bot display names
        also come from a first/last-name pool and can repeat, so they are only a
        weak fallback.  Callers should pass the vehicle id or the value object's
        identity; see _botKey().
        """
        mode = CONFIG.botMode()
        if mode == BOT_MODE_KEEP:
            return realName
        if mode == BOT_MODE_BLANK:
            return u''
        if not key:
            key = self.botKey(realName, None)
        if not key:
            key = realName
        # Remember name -> key so the name-only path (getPlayerLabel carries no
        # vehicle id) reuses this label instead of minting a second one.  Never
        # overwrite: whatever the first path chose owns the number this battle.
        self.bindBotName(realName, key)
        if mode == BOT_MODE_SAME:
            # same numbering space as players
            return self.labelForID(key, isBot=False)
        return self.labelForID(key, isBot=True)

    # -- badges -------------------------------------------------------------

    def shouldHideBadge(self, playerVO=None, dbID=None, clanAbbrev=None,
                        isBot=False):
        """True when the medal next to a nickname should be suppressed.

        Decision mirrors the name rules so the HUD stays consistent: people you
        know keep their badges, strangers and bots lose them.

        The MASTER switch is checked first.  Every badge path funnels through
        this method, so with `enable: false` no badge is ever touched -- an
        earlier version only consulted hideBadges(), so the global buildBadge /
        getSelectedByLayout wrappers kept stripping medals with the mod off.

        Any failure returns False, i.e. "leave the badge alone".  That is the
        opposite of the name rule on purpose: a badge is not personal data, so a
        bug here is cosmetic rather than a leak, and quietly blanking every
        medal would be the more annoying failure.
        """
        try:
            if not CONFIG.enabled():
                return False
            if not CONFIG.hideBadges():
                return False
            if playerVO is not None:
                if _isBot(playerVO):
                    return CONFIG.hideBotBadges()
                dbID = getattr(playerVO, 'accountDBID', None)
                clanAbbrev = getattr(playerVO, 'clanAbbrev', None)
            if isBot:
                return CONFIG.hideBotBadges()
            if CONFIG.badgesExemptKnown() \
                    and not self.isStrangerIdentity(dbID, clanAbbrev):
                return False
            return True
        except Exception:
            return False

    def displayForID(self, dbID, realName, clanAbbrev=None, isBot=False):
        """Name to show for a raw player id (TAB panel path)."""
        if not CONFIG.scope(KEY_SCOPE_BATTLE):
            return realName
        try:
            if isBot:
                # dbID is meaningless for a bot (always falsy); resolve through
                # the canonical bot key instead.
                return self.botDisplay(realName, key=self.botKey(realName, None))
            if not self.isStrangerIdentity(dbID, clanAbbrev):
                return realName
            if CONFIG.mode() == 'blank':
                return u''
            return self.labelForID(dbID)
        except Exception:
            if not self._warned:
                self._warned = True
                logError('anonymiser error (id path), hiding: %s'
                         % traceback.format_exc())
            return u''

    def clanTagForID(self, dbID, realTag, clanAbbrev=None):
        """Clan tag to show for a raw player id."""
        if not CONFIG.scope(KEY_SCOPE_BATTLE) or not CONFIG.flag(KEY_HIDE_CLAN_TAG):
            return realTag
        try:
            if not self.isStrangerIdentity(dbID, clanAbbrev):
                return realTag
            return u''
        except Exception:
            return u''

    def isStranger(self, playerVO):
        """True when this player's nickname must be hidden.

        Bots are NOT anonymised: their names are static game content, never a
        privacy leak, and rewriting them would fight the client's own bot-naming
        and localisation.
        """
        if playerVO is None:
            return True
        if _isBot(playerVO):
            return False
        return self.isStrangerIdentity(getattr(playerVO, 'accountDBID', None),
                                       getattr(playerVO, 'clanAbbrev', None))

    def isStrangerIdentity(self, dbID, clanAbbrev=None):
        """Same decision, from raw id/clan values.

        The Gameface battle page (TAB panel) never hands us a PlayerInfoVO -- it
        fills view models from the engine's arena dict, so we have to decide from
        the id alone.  An unknown/zero id is treated as a stranger (hide), which
        is the safe direction.
        """
        if not dbID:
            return True
        # If we never learned our own DBID, "unknown" would otherwise be read as
        # "stranger", which masks the player's OWN name.  The arena exists by the
        # time names are rendered, so retry before giving up -- the game.log
        # showed `identity: self=None` for the first frames of a battle, during
        # which the streamer's own row was masked.
        #
        # The counter only guards against a retry storm; it is reset by
        # IDENTITY.reset() at each battle/account boundary, so a long lobby stay
        # cannot exhaust it before a battle starts.
        if not IDENTITY.ownDBID and IDENTITY._tries < 8:
            IDENTITY.resolve()
        if CONFIG.flag(KEY_EXCLUDE_SELF) and IDENTITY.ownDBID \
                and dbID == IDENTITY.ownDBID:
            return False
        if CONFIG.flag(KEY_EXCLUDE_SQUAD) and dbID in IDENTITY.squadmateDBIDs:
            return False
        if CONFIG.flag(KEY_EXCLUDE_CLANMATE) and clanAbbrev \
                and IDENTITY.ownClanAbbrev and clanAbbrev == IDENTITY.ownClanAbbrev:
            return False
        if CONFIG.flag(KEY_EXCLUDE_FRIEND) and dbID in IDENTITY.friendDBIDs:
            return False
        return True

    def display(self, playerVO, realName):
        """Name to show.  On any internal error we hide rather than leak."""
        if not CONFIG.surfaceAllowed():
            return realName
        try:
            if _isBot(playerVO):
                # Key on the player VO itself: arenaDP holds it for the whole
                # battle, so id() is unique per bot and stable across calls --
                # unlike dbID/sessionID (empty for every bot) or the display name
                # (repeats, since bots draw from a first/last-name pool).
                raw = getattr(playerVO, 'name', None) \
                    or getattr(playerVO, 'fakeName', None) or realName
                return self.botDisplay(raw, key=self.botKey(raw, hint=getattr(playerVO, 'vehicleID', None), obj=playerVO))
            if not self.isStranger(playerVO):
                return realName
            if CONFIG.mode() == 'blank':
                return u''
            return self.labelFor(playerVO)
        except Exception:
            if not self._warned:
                self._warned = True
                logError('anonymiser error, hiding name: %s'
                         % traceback.format_exc())
            return u''


ANONYMISER = Anonymiser()


# ---------------------------------------------------------------------------
# function patching
# ---------------------------------------------------------------------------

def patch(cls, name, factory, is_property=False):
    """Replace cls.name with factory(original); return an undo callable.

    ``is_property`` matters: some of these names (battle_results
    PlayerInfo.realName) are ``property`` objects, not plain functions.  A
    property is not callable, so calling ``original(self)`` on one would raise
    and -- because our hooks fail closed -- blank every name on that screen.
    For those we wrap the getter and re-install a property.
    """
    try:
        current = cls.__dict__.get(name)
        if current is None:
            logError('%s.%s missing; not installed.' % (cls.__name__, name))
            return None
        if getattr(current, _ATTR_OURS, False):
            return None                       # already ours (re-entrant install)

        if is_property or isinstance(current, property):
            if current.fget is None:
                logError('%s.%s has no getter; not installed.' % (cls.__name__, name))
                return None
            originalGetter = current.fget
            replacementGetter = factory(originalGetter)
            setattr(replacementGetter, _ATTR_OURS, True)
            setattr(replacementGetter, '_streamerMode_original', originalGetter)
            replacement = property(replacementGetter, current.fset, current.fdel,
                                   current.__doc__)

            def undoProp():
                try:
                    if cls.__dict__.get(name) is replacement:
                        setattr(cls, name, current)
                except Exception:
                    logError('undo %s.%s failed' % (cls.__name__, name))
            setattr(cls, name, replacement)
            return undoProp

        original = current
        # A classmethod (and staticmethod) is a descriptor, not a plain function.
        # Calling the bare replacement would lose the implicit `cls`, so the
        # argument binding would be off by one -- silently breaking the call.
        # UserNames._setBadges is a classmethod, so this matters in practice.
        #
        # We take the UNDERLYING function (__func__) and re-wrap the replacement
        # in the same descriptor.  That keeps the hook signature explicit --
        # `def _setBadges(cls, model, reusable, dbID)` -- because `cls` is then
        # supplied by the descriptor exactly as it is for the original.
        is_classmethod = isinstance(current, classmethod)
        is_staticmethod = isinstance(current, staticmethod)
        if is_classmethod or is_staticmethod:
            original = current.__func__

        replacement = factory(original)
        setattr(replacement, _ATTR_OURS, True)
        setattr(replacement, '_streamerMode_original', original)
        if is_classmethod:
            setattr(cls, name, classmethod(replacement))
        elif is_staticmethod:
            setattr(cls, name, staticmethod(replacement))
        else:
            setattr(cls, name, replacement)

        def undo():
            try:
                if cls.__dict__.get(name) is replacement or \
                        getattr(cls.__dict__.get(name), '__func__', None) is replacement:
                    setattr(cls, name, current)
            except Exception:
                logError('undo %s.%s failed' % (cls.__name__, name))
        return undo
    except Exception:
        logError('patch %s.%s failed: %s' % (name, name, traceback.format_exc()))
        return None


# ---------------------------------------------------------------------------
# hooks
# ---------------------------------------------------------------------------

def _hookPlayerLabel(original):
    """PlayerInfoVO.getPlayerLabel -- the base nickname for one player."""

    def getPlayerLabel(self):
        try:
            realName = original(self)
        except Exception:
            return u''
        if not CONFIG.surfaceAllowed():
            return realName
        return ANONYMISER.display(self, realName)
    return getPlayerLabel


def _hookPlayerFakeLabel(original):
    """PlayerInfoVO.getPlayerFakeLabel -- the locally generated label.

    This is what bots use for their names.  Bots are not anonymised (their names
    are game content), so only route real strangers through the anonymiser.
    """

    def getPlayerFakeLabel(self):
        try:
            realName = original(self)
        except Exception:
            return u''
        if _isBot(self):
            return realName
        if not CONFIG.surfaceAllowed():
            return realName
        return ANONYMISER.display(self, realName)
    return getPlayerFakeLabel


def _hookDisplayedName(original):
    """VehicleArenaInfoVO.getDisplayedName -- composes tank name + nickname.

    IMPORTANT: the client calls this two ways.
      * getDisplayedName()          -> tank short name (postmortem "vehicle")
      * getDisplayedName(nickname)  -> the nickname for display
    Only the second carries a player name, so when no argument is supplied we
    must pass the call straight through -- anonymising it would replace tank
    names with "Player_001".

    Gating uses surfaceAllowed(), not the battle scope: this is the call the
    minimap and the 3D markers use to resolve a name, so it must honour their
    individual switches.
    """

    def getDisplayedName(self, name=None):
        if name is None:
            return original(self, name)          # tank name, not a nickname
        try:
            playerVO = getattr(self, 'player', None)
            if playerVO is not None and CONFIG.surfaceAllowed():
                if _isBot(playerVO):
                    # Key on the player VO's identity, consistent with display()
                    # and format().
                    raw = getattr(playerVO, 'name', None) \
                        or getattr(playerVO, 'fakeName', None) or name
                    return ANONYMISER.botDisplay(raw, key=ANONYMISER.botKey(raw, hint=getattr(self, 'vehicleID', None), obj=playerVO))
                if ANONYMISER.isStranger(playerVO):
                    return ANONYMISER.display(playerVO, name)
            return original(self, name)
        except Exception:
            # never raise into the render path; never leak a name either
            if not CONFIG.surfaceAllowed():
                try:
                    return original(self, name)
                except Exception:
                    return u''
            return u''
    return getDisplayedName


def _blankResult(result):
    """Copy of a PlayerFormatResult with all name fields emptied."""
    try:
        return result._replace(playerName=u'', playerFakeName=u'',
                               playerFullName=u'', clanAbbrev=u'')
    except Exception:
        return result


def _stripClanFromResult(formatter, vInfoVO, result):
    """Rebuild playerFullName without the clan tag, keeping vehicle/region.

    Rather than re-implement the client's format masks, we read the formatter's
    own flags (the same ones format() consulted) to pick the right mask.
    """
    try:
        from gui.battle_control.arena_info.player_format import (
            _FORMAT_MASK, _PLAYER_FULL_NAME_FORMATS)

        isVehShown = bool(getattr(
            formatter, '_PlayerFullNameFormatter__isVehicleShortNameShown', False))
        isRegionShown = bool(getattr(
            formatter, '_PlayerFullNameFormatter__isRegionShown', False))

        key = _FORMAT_MASK.NONE
        if isVehShown and getattr(vInfoVO, 'vehicleType', None) is not None:
            key |= _FORMAT_MASK.VEHICLE
        if isRegionShown and result.regionCode:
            key |= _FORMAT_MASK.REGION
        # deliberately NOT setting the CLAN bit: the tag is being hidden

        mask = _PLAYER_FULL_NAME_FORMATS.get(key)
        if not mask:
            full = result.playerName
        else:
            full = mask.format(result.playerName, u'',
                               result.vehicleName or u'', result.regionCode or u'')
        return result._replace(playerFullName=full, clanAbbrev=u'')
    except Exception:
        return result._replace(clanAbbrev=u'')


def _hookFormat(original):
    """PlayerFullNameFormatter.format -- builds the composite name strings.

    format() accepts the nickname as an argument, so instead of trying to
    rewrite the assembled string we hand it the anonymised nickname and let the
    client lay the name, clan, vehicle and region out itself.
    """

    def format(self, vInfoVO, playerName=None):
        if not CONFIG.surfaceAllowed():
            return original(self, vInfoVO, playerName)
        try:
            playerVO = getattr(vInfoVO, 'player', None)
            if playerVO is None:
                return original(self, vInfoVO, playerName)

            if _isBot(playerVO):
                # Same key as display(): the player VO's identity.  format() and
                # getPlayerLabel() are both called with this very object (the
                # client does getDisplayedName(vInfoVO.player.getPlayerLabel())),
                # so this is what makes the two agree.
                raw = getattr(playerVO, 'name', None) \
                    or getattr(playerVO, 'fakeName', None) or playerName
                botName = ANONYMISER.botDisplay(raw, key=ANONYMISER.botKey(raw, hint=getattr(vInfoVO, 'vehicleID', None), obj=playerVO))
                result = original(self, vInfoVO, botName)
                if result is None:
                    return None
                if CONFIG.hideBotClanTag() and result.clanAbbrev:
                    result = _stripClanFromResult(self, vInfoVO, result)
                return result

            if not ANONYMISER.isStranger(playerVO):
                return original(self, vInfoVO, playerName)

            if CONFIG.mode() == 'blank':
                newName = u''
            else:
                newName = ANONYMISER.labelFor(playerVO)

            # getPlayerLabel/getPlayerFakeLabel are hooked too, so the client's
            # own composition stays anonymised.
            result = original(self, vInfoVO, newName)
            if result is None:
                return None
            if CONFIG.flag(KEY_HIDE_CLAN_TAG) and result.clanAbbrev:
                result = _stripClanFromResult(self, vInfoVO, result)
            return result
        except Exception:
            logError('format hook error: %s' % traceback.format_exc())
            try:
                return _blankResult(original(self, vInfoVO, u''))
            except Exception:
                return None
    return format


def _resultsKeepIdentity(dbID, clanAbbrev=None):
    """True when the battle-results screen must show this player's real data.

    The results screen has its own identity checks because its PlayerInfo
    carries no PlayerInfoVO -- only a dbID and (via __clanInfo) a clan tag.
    Those checks MUST mirror Identity.isStrangerIdentity(), or the same player
    is treated differently in battle and on the scoreboard: previously only
    self and friends were exempted here, so a clanmate or platoon mate was
    masked in "battle results -> personal scoreboard" while keeping their real
    name in battle.

    Both the name accessors and the clanAbbrev property call this, so the name
    and the tag can never disagree (a real name beside a "Player_007" label, or
    a stranger's real [TAG] beside a masked name).

    A falsy dbID is a bot and is never "kept".
    """
    if not dbID:
        return False
    # Same retry as isStrangerIdentity(): onAvatarBecomePlayer() resets and then
    # re-resolves, but the arena does not exist yet at that moment, so ownDBID is
    # None for the first frames.  The results screen renders later, when the
    # arena IS available -- without this retry the streamer's own row on the
    # personal scoreboard was masked as "玩家_001".
    if not IDENTITY.ownDBID and IDENTITY._tries < 8:
        IDENTITY.resolve()
    if CONFIG.flag(KEY_EXCLUDE_SELF) and IDENTITY.ownDBID \
            and dbID == IDENTITY.ownDBID:
        return True
    if CONFIG.flag(KEY_EXCLUDE_FRIEND) and dbID in IDENTITY.friendDBIDs:
        return True
    if CONFIG.flag(KEY_EXCLUDE_SQUAD) and dbID in IDENTITY.squadmateDBIDs:
        return True
    if CONFIG.flag(KEY_EXCLUDE_CLANMATE) and clanAbbrev \
            and IDENTITY.ownClanAbbrev \
            and clanAbbrev == IDENTITY.ownClanAbbrev:
        return True
    return False


def _resultsClanAbbrev(playerInfo):
    """The player's real clan tag, read from the client's nested _ClanInfo."""
    try:
        info = getattr(playerInfo, '_PlayerInfo__clanInfo', None)
        if info is None:
            return None
        return getattr(info, 'clanAbbrev', None)
    except Exception:
        return None


def _resultsLabel(playerInfo, realValue, raw):
    """Anonymised label for one battle-results PlayerInfo.

    The personal scoreboard reads the SAME player through several accessors --
    components/shared.pyc PlayerNameBlock.setPlayerInfo pulls

        playerInfo.fakeName        -> fakeNameLabel
        playerInfo.realName        -> realNameLabel
        playerInfo.getFullName()   -> fullNameLabel
        playerInfo.clanAbbrev      -> clanLabel

    so hooking only realName() left three routes showing the original text.
    This single helper is used by every one of them.

    NATIVE ANONYMISER.  When the game's own anonymiser is active for a player,
    __realName and __fakeName differ: the client built a fake name and every
    accessor returns it.  That value is NOT safe to pass through -- it is still
    a per-player identifier that links this scoreboard row to a specific person,
    and the reviewer flagged exactly this early return as a leak.  The exempted
    groups keep their real data; everybody else is masked on top of the native
    fake name, the same way as in battle.
    """
    if not CONFIG.scope(KEY_SCOPE_RESULTS):
        return realValue
    try:
        fake = getattr(playerInfo, '_PlayerInfo__fakeName', None)
        real = getattr(playerInfo, '_PlayerInfo__realName', None)
        dbID = getattr(playerInfo, '_PlayerInfo__dbID', None)

        if _resultsIsBot(playerInfo, dbID):
            if not CONFIG.botsAnonymised():
                return realValue
            # Key by the bot's CANONICAL stored name, never by the accessor's
            # return value: realName / fakeName / getFullName all describe the
            # same bot but hand back different text, so keying on that text gave
            # one bot three different numbers.  __realName is what the client
            # built from the bot table, so it is the same for all accessors.
            canonical = real or fake or raw or realValue
            return ANONYMISER.botDisplay(
                canonical, key=ANONYMISER.botKey(canonical, None))

        # Checked BEFORE the native-anonymiser case: an exempted player must keep
        # their real name even if the game anonymised them for everyone else.
        if _resultsKeepIdentity(dbID, _resultsClanAbbrev(playerInfo)):
            return realValue

        # Everything below is a stranger.  Native fake name or not, they get a
        # label -- the early return that used to sit here was the reported leak.
        source = raw or real or fake or realValue
        # Remember the true name before masking it, so the profile window can
        # restore it when "show real names in profile" is enabled.
        ANONYMISER.rememberRealName(dbID, source)
        if CONFIG.mode() == 'blank':
            return u''
        return ANONYMISER.labelFor(_DBIDKey(dbID))
    except Exception:
        # Fail closed: never hand back text we could not classify.
        logError('results label failed: %s' % traceback.format_exc())
        return u''


def _hookResultsRealName(original):
    """battle_results PlayerInfo.realName (a property)."""

    def realName(self):
        try:
            realValue = original(self)
        except Exception:
            return u''
        return _resultsLabel(self, realValue,
                             getattr(self, '_PlayerInfo__realName', None))
    return realName


def _hookResultsFakeName(original):
    """battle_results PlayerInfo.fakeName (a property).

    PlayerNameBlock reads this into `fakeNameLabel`; without anonymising it the
    results screen can show the original text even when realName is masked.
    """

    def fakeName(self):
        try:
            realValue = original(self)
        except Exception:
            return u''
        return _resultsLabel(self, realValue,
                             getattr(self, '_PlayerInfo__fakeName', None))
    return fakeName


def _hookResultsFullName(original):
    """battle_results PlayerInfo.getFullName().

    This composes "name [clan] (region)" via lobbyContext and BYPASSES the
    realName property entirely, so it needs its own hook.
    """

    def getFullName(self):
        try:
            return _resultsLabel(self, original(self),
                                 getattr(self, '_PlayerInfo__realName', None))
        except Exception:
            logError('results getFullName hook failed: %s'
                     % traceback.format_exc())
            return u''
    return getFullName


def _hookResultsClanAbbrev(original):
    """battle_results PlayerInfo.clanAbbrev (a property).

    components/shared.pyc PlayerNameBlock.setPlayerInfo reads this straight into
    `clanLabel`, i.e. it never goes through realName/fakeName/getFullName -- so
    the results screen kept showing the real [TAG] even after the names were
    masked.  Reading it off the property is what closes that last gap.
    """

    def clanAbbrev(self):
        try:
            realValue = original(self)
        except Exception:
            return u''
        try:
            if not CONFIG.scope(KEY_SCOPE_RESULTS):
                return realValue
            if not CONFIG.hideResultsClanTag():
                return realValue
            if not realValue:
                return realValue
            dbID = getattr(self, '_PlayerInfo__dbID', None)
            # Same four-group rule as the name accessors (self, friends,
            # clanmates, platoon mates).  Both paths share one helper so the
            # tag and the name cannot disagree.
            if _resultsKeepIdentity(dbID, realValue):
                return realValue
            if _resultsIsBot(self, dbID):
                return u'' if CONFIG.hideBotClanTag() else realValue
            return u''
        except Exception:
            logError('results clan hook failed: %s' % traceback.format_exc())
            return realValue
    return clanAbbrev


# ---------------------------------------------------------------------------
# Badges (medal icons drawn next to the nickname)
#
# Leave the global helpers untouched: getSelectedByLayout feeds cached arena
# VO fields, and buildBadge cannot identify the player or screen.
# ---------------------------------------------------------------------------

def _badgeHiddenFor(playerVO=None, dbID=None, clanAbbrev=None, isBot=False):
    """Shared decision for the caller-side badge wrappers.

    Deliberately does NOT consult a scope flag: the callers live in different
    screens (in-battle vs results), so each wrapper applies its own scope.
    """
    try:
        return ANONYMISER.shouldHideBadge(playerVO=playerVO, dbID=dbID,
                                          clanAbbrev=clanAbbrev, isBot=isBot)
    except Exception:
        return False


def _hookResultsSetBadges(original):
    """UserNames._setBadges -- a CLASSMETHOD, so the first argument is `cls`.

    Called as cls._setBadges(model, reusable, playerDbID), and patch() preserves
    the classmethod descriptor so this signature stays correct.
    """

    def _setBadges(cls, model, reusable, playerDbID):
        result = original(cls, model, reusable, playerDbID)
        try:
            if not CONFIG.scope(KEY_SCOPE_RESULTS) or not _badgeHiddenFor(
                    dbID=playerDbID, isBot=not playerDbID):
                return result
            for holder in ('badge', 'suffixBadge'):
                badgeModel = getattr(model, holder, None)
                setter = getattr(badgeModel, 'setBadgeID', None) if badgeModel else None
                if callable(setter):
                    try:
                        setter('')
                    except Exception:
                        pass
            # also clear the alternate spelling used by the other packer
            setter = getattr(model, 'setBadge', None)
            if callable(setter):
                try:
                    setter('')
                except Exception:
                    pass
            setter = getattr(model, 'setSuffixBadge', None)
            if callable(setter):
                try:
                    setter('')
                except Exception:
                    pass
        except Exception:
            logError('results badge strip failed: %s' % traceback.format_exc())
        return result
    return _setBadges


def _hookSelectedBadge(original):
    """Filter prefix or suffix at read time, only for a known battle surface."""
    def selectedBadge(self):
        result = original(self)
        try:
            if _SURFACE_STACK and CONFIG.surface(_SURFACE_STACK[-1]):
                playerVO = getattr(self, 'player', None)
                if playerVO is not None and _badgeHiddenFor(playerVO=playerVO):
                    return 0
        except Exception:
            logError('selected badge hook failed: %s' % traceback.format_exc())
        return result
    return selectedBadge


def _hookPostmortemBadgeFor(original):
    """PostmortemPanel._makeKillerVO -- the death-cam killer line.

    This is also where `scope.postmortem` is enforced.  The method builds its
    dict from ctx.getPlayerFullNameParts(...), i.e. through the shared format()
    helper, so running the original inside the postmortem context is what decides
    whether the name and clan come out masked.

    Verified shape of the returned dict:
        'userName', 'fakeName', 'clanAbbrev', 'region', 'igrType', 'tags'
    plus the badge as 'badgeVisualVO'.
    """

    def _makeKillerVO(self, vInfoVO):
        with _Surface(KEY_SCOPE_POSTMORTEM):
            result = original(self, vInfoVO)
            try:
                if not CONFIG.surface(KEY_SCOPE_POSTMORTEM):
                    return result
                playerVO = getattr(vInfoVO, 'player', None)
                if isinstance(result, dict):
                    if playerVO is not None and _badgeHiddenFor(playerVO=playerVO):
                        result.pop('badgeVisualVO', None)
                    # the clan tag is read straight off the VO, not from the
                    # formatter, so it needs stripping separately
                    if CONFIG.flag(KEY_HIDE_CLAN_TAG) \
                            and playerVO is not None \
                            and ANONYMISER.isStranger(playerVO):
                        if result.get('clanAbbrev'):
                            result['clanAbbrev'] = u''
            except Exception:
                logError('postmortem strip failed: %s' % traceback.format_exc())
            return result
    return _makeKillerVO


def _hookTeamStatsBadge(original):
    """components/vehicles.pyc RegularVehicleStatsBlock.setRecord.

    This is the TEAM STATS ("閸ャ垽妲﹂幋妯煎摋") path, and it is entirely separate from
    everything else we hook.  It never reads VehicleArenaInfoVO.selectedBadge or
    the results PlayerInfo name accessors -- it goes straight to the reusable
    avatar record:

        setRecord(self, result, reusable)                      vehicles.pyc
            player = result.player
            avatar = reusable.avatars.getAvatarInfo(player.dbID)
            self.hasSelectedBadge = avatar.badge != 0
            if self.hasSelectedBadge:
                self._setBadge(result, reusable)   # self.badge = PropertyValue(...)
            elif avatar.suffixBadge:
                self.suffixBadgeIcon = style.makeBadgeIcon(avatar.suffixBadge)
                self.suffixBadgeStripIcon = ...R.images...strips...

    That is why the switch worked on the personal scoreboard but the badges
    stayed visible in the team stats view.

    We run the original (it fills many other fields) and then blank just the
    badge ones -- which is exactly the state a player with no badge ends up in:
    hasSelectedBadge False, badge None, suffix icons None.
    """

    def setRecord(self, result, reusable):
        originalResult = original(self, result, reusable)
        try:
            if not CONFIG.scope(KEY_SCOPE_RESULTS):
                return originalResult
            player = getattr(result, 'player', None)
            dbID = getattr(player, 'dbID', None)
            # A results bot has no dbID at all; same rule as _resultsIsBot.
            if not _badgeHiddenFor(dbID=dbID, isBot=not dbID):
                return originalResult
            for field in ('badge', 'suffixBadgeIcon', 'suffixBadgeStripIcon'):
                try:
                    setattr(self, field, None)
                except AttributeError:
                    pass
            try:
                self.hasSelectedBadge = False
            except AttributeError:
                pass
        except Exception:
            logError('team-stats badge strip failed: %s'
                     % traceback.format_exc())
        return originalResult
    return setRecord


def _hookTeamBadgeBlock(original):
    """components/vehicles.pyc BadgeBlock.setRecord.

    The team-stats template also mounts a standalone BadgeBlock, which resolves
    the badge through the avatar record:

        avatar = reusable.avatars.getAvatarInfo(player.dbID)
        badgeInfo = avatar.getFullBadgeInfo()      # -> gui.shared.badges.buildBadge
        if badgeInfo is not None:
            self.icon = badgeInfo.getThumbnailIcon()
            self.isDynamic = badgeInfo.hasDynamicContent()
            self.content = badgeInfo.getDynamicContent()
            self.sizeContent = ICONS_SIZES.X24

    Blanking the fields leaves it in the same state as the constructor
    (icon/content/sizeContent '', isDynamic False).
    """

    def setRecord(self, result, reusable):
        originalResult = original(self, result, reusable)
        try:
            if not CONFIG.scope(KEY_SCOPE_RESULTS):
                return originalResult
            player = getattr(result, 'player', None)
            dbID = getattr(player, 'dbID', None)
            if not _badgeHiddenFor(dbID=dbID, isBot=not dbID):
                return originalResult
            for field, value in (('icon', u''), ('content', u''),
                                 ('sizeContent', u''), ('isDynamic', False)):
                try:
                    setattr(self, field, value)
                except AttributeError:
                    pass
        except Exception:
            logError('team BadgeBlock strip failed: %s'
                     % traceback.format_exc())
        return originalResult
    return setRecord


def _resultsIsBot(playerInfo, dbID):
    """True when this battle-results PlayerInfo describes a bot.

    Primary rule, taken from the client's own construction path: bots are built
    via makePlayerInfo() with no dbID, so their dbID is falsy while every real
    player has one.  We additionally consult the results bot table when a
    vehicle id is reachable, which guards against a future client change.
    """
    if dbID:
        return False
    try:
        vehicleID = playerInfo._PlayerInfo__vehicleID
    except Exception:
        vehicleID = None
    if vehicleID:
        try:
            from helpers import dependency
            from skeletons.gui.battle_results import IBattleResultsService
            service = dependency.instance(IBattleResultsService)
            reusable = service.getResults() if service else None
            common = getattr(reusable, '_ReusableInfo__common', None)
            if common is not None and common.getBotInfo(vehicleID) is not None:
                return True
        except Exception:
            pass
    return True


class _DBIDKey(object):
    """Lets the results screen share the battle's numbering."""

    def __init__(self, dbID):
        self.accountDBID = dbID
        self.avatarSessionID = None


# ---------------------------------------------------------------------------
# Single-player details / profile window
#
# The profile is opened deliberately from the context menu (USER.INFO ->
# showUserInfo -> requestProfile -> showProfileWindow) and is fed by the dossier
# looked up by DBID.  However the NAME it displays arrives as an argument:
#
#   ProfileWindow.__updateUserInfo (ProfileWindow.pyc L127):
#       lobbyContext.getPlayerFullName(info['name'], clanAbbrev=...,
#                                      regionCode=..., pDBID=self.__databaseID)
#
# and `info['name']` is the user name the context menu was built with -- i.e.
# our anonymised label.  So restoring the real name means substituting it here,
# keyed by the DBID which IS available.
#
# This is opt-in (showRealNamesInProfile, default on): looking one player up is
# a conscious action, unlike the passive battle HUD.
# ---------------------------------------------------------------------------

def _hookProfileUpdateUserInfo(original):
    """ProfileWindow._ProfileWindow__updateUserInfo(self).

    This is the narrowest place to restore the real name for a single-player
    profile.  The window builds everything from its own __userName field:

        getProfileCommonInfo(self.__userName, ...)                    L123
        lobbyContext.getPlayerFullName(info['name'], ...)              L127

    so setting __userName before the original runs fixes the whole chain.

    We deliberately do NOT hook lobbyContext.getPlayerFullName globally: that
    method has 30 callers (battle messages, invitations, the results screen
    itself...), and swapping in real names there would risk un-masking unrelated
    windows.  Touching only the profile window keeps this option's blast radius
    exactly where the user expects it.
    """

    def _ProfileWindow__updateUserInfo(self):
        try:
            if CONFIG.showRealNameInProfile():
                dbID = getattr(self, '_ProfileWindow__databaseID', None)
                real = ANONYMISER.realNameFor(dbID)
                if real:
                    self._ProfileWindow__userName = real
        except Exception:
            logError('profile name restore failed: %s' % traceback.format_exc())
        return original(self)
    return _ProfileWindow__updateUserInfo


# ---------------------------------------------------------------------------
# Gameface battle page (the TAB / full-stats panel)
#
# This view does NOT call any of the value-object helpers above.  Per
# tab_view.pyc it fills its models straight from the engine's arena dict:
#
#     _visitor.getArenaVehicles() -> arena._arena.vehicles   (C++ dict)
#     _invalidatePersonalInfo(player):            tab_view.pyc L563
#         player.setUserName(vehicleInfo['name'])            L578
#         player.setHiddenUserName(vehicleInfo['fakeName'])  L576
#         player.setClanAbbrev(vehicleInfo['clanAbbrev'])    L573
#
# and the model picks hiddenUserName only when isFakeNameVisible is set -- which
# the client drives from ITS anonymiser, not ours.  So we must rewrite the model
# after the client has filled it.
# ---------------------------------------------------------------------------

def _tabPlayerId(playerModel):
    """DBID from a TAB-panel player model, tolerating API differences."""
    for attr in ('getDatabaseID', 'getDbID'):
        fn = getattr(playerModel, attr, None)
        if callable(fn):
            try:
                value = fn()
                if value:
                    return value
            except Exception:
                pass
    return None


def _tabGetSet(playerModel, getter, setter, value):
    """Call setter(value) when the getter currently returns `value`'s target."""
    fn = getattr(playerModel, setter, None)
    if callable(fn):
        try:
            fn(value)
        except Exception:
            pass


def _anonymiseTabPlayer(playerModel):
    """Rewrite one TAB-panel player model so it shows an anonymised name.

    The TAB full-stats board is its own surface (scope.tabPanel), separate from
    the side panels (scope.playersPanel): the side panels are Scaleform
    VehicleInfoComponent, this is the Gameface TabView with its own models.

    Names and badges both respect the TAB surface switch.
    """
    if not CONFIG.surface(KEY_SCOPE_TAB):
        return
    try:
        dbID = _tabPlayerId(playerModel)
        realName = None
        for attr in ('getUserName', 'getPlayerName'):
            fn = getattr(playerModel, attr, None)
            if callable(fn):
                try:
                    realName = fn()
                except Exception:
                    realName = None
                if realName is not None:
                    break

        clanAbbrev = None
        fn = getattr(playerModel, 'getClanAbbrev', None)
        if callable(fn):
            try:
                clanAbbrev = fn()
            except Exception:
                clanAbbrev = None

        # In the arena dict a bot is identified by an empty avatarSessionID --
        # the same rule PlayerInfoVO.isBot uses. The model echoes that field.
        isBot = False
        fn = getattr(playerModel, 'getAvatarSessionID', None)
        if callable(fn):
            try:
                isBot = not fn()
            except Exception:
                isBot = False

        # Clear the medal FIRST, before any of the early returns below.  The
        # name branches return early for bots (when botMode is 'keep') and for
        # people you know, and those exits would otherwise skip the badge.
        _clearTabBadges(playerModel, dbID, isBot=isBot)

        if isBot:
            if not CONFIG.botsAnonymised():
                return
            # Key by vehicle id, EXACTLY like the in-battle panel does.  This was
            # the cause of "TAB numbers are larger than the panel numbers": the
            # TAB path used to call botKey() with no vehicle id, so it keyed bots
            # by name -- a SECOND numbering space, unrelated to the first.  The
            # tab model exposes getVehicleId(), which is the same value the arena
            # VO carries, so both paths now share one counter.
            vehicleID = None
            fn = getattr(playerModel, 'getVehicleId', None)
            if callable(fn):
                try:
                    vehicleID = fn() or None
                except Exception:
                    vehicleID = None
            if vehicleID:
                newName = ANONYMISER.botDisplay(
                    realName, key=ANONYMISER.botKey(realName, hint=vehicleID))
            else:
                newName = ANONYMISER.botDisplay(
                    realName, key=ANONYMISER.botKey(realName, None))
            hideClan = CONFIG.hideBotClanTag()
        else:
            if not ANONYMISER.isStrangerIdentity(dbID, clanAbbrev):
                return
            if CONFIG.mode() == 'blank':
                newName = u''
            else:
                newName = ANONYMISER.labelForID(dbID)
            hideClan = CONFIG.flag(KEY_HIDE_CLAN_TAG)

        # setName / setUserName are the two spellings seen across versions.
        for setter in ('setUserName', 'setPlayerName'):
            if callable(getattr(playerModel, setter, None)):
                _tabGetSet(playerModel, 'getUserName', setter, newName)
                break
        # keep the hidden/fake field consistent so the model cannot fall back
        # to the real name when isFakeNameVisible happens to be set
        if callable(getattr(playerModel, 'setHiddenUserName', None)):
            _tabGetSet(playerModel, 'getHiddenUserName', 'setHiddenUserName', u'')

        if hideClan:
            if callable(getattr(playerModel, 'setClanAbbrev', None)):
                _tabGetSet(playerModel, 'getClanAbbrev', 'setClanAbbrev', u'')
    except Exception:
        logError('tab panel anonymise failed: %s' % traceback.format_exc())


def _clearTabBadges(playerModel, dbID, isBot=False):
    """Blank the medal on a TAB-panel player model.

    Unlike the other surfaces, the TAB view is Gameface and does NOT go through
    VehicleArenaInfoVO.selectedBadge -- tab_view.pyc fills the model itself via
    getSelectedByLayout() into two BadgeModel slots.  So it has to be cleared
    here, on the model, with the badge id empty (BadgeModel.badgeID defaults to
    '').
    """
    try:
        if not _badgeHiddenFor(dbID=dbID, isBot=isBot):
            return
        for holder in ('badge', 'suffixBadge'):
            model = getattr(playerModel, holder, None)
            if model is None:
                continue
            setter = getattr(model, 'setBadgeID', None)
            if callable(setter):
                try:
                    setter('')
                except Exception:
                    pass
    except Exception:
        logError('tab badge clear failed: %s' % traceback.format_exc())


def _hookTabInvalidatePersonalInfo(original):
    """TabView._invalidatePersonalInfo(self, player) -- fills name + clan."""

    def _invalidatePersonalInfo(self, player):
        with _Surface(KEY_SCOPE_TAB):
            result = original(self, player)
        _anonymiseTabPlayer(player)
        return result
    return _invalidatePersonalInfo


def _hookTabInvalidateVehiclesInfo(original):
    """TabView._invalidateVehiclesInfo(self) -- first fill of every player."""

    def _invalidateVehiclesInfo(self):
        with _Surface(KEY_SCOPE_TAB):
            result = original(self)
        try:
            viewModel = getattr(self, 'viewModel', None)
            playerList = getattr(viewModel, 'playerList', None) if viewModel else None
            if playerList is None:
                return result
            for getter in ('getAllies', 'getEnemies'):
                fn = getattr(playerList, getter, None)
                if not callable(fn):
                    continue
                for model in (fn() or []):
                    _anonymiseTabPlayer(model)
        except Exception:
            logError('tab list anonymise failed: %s' % traceback.format_exc())
        return result
    return _invalidateVehiclesInfo


# ---------------------------------------------------------------------------
# Scaleform players panel: the clan tag is read straight off the VO
#
# stats_exchange/vehicle.py  VehicleInfoComponent.addVehicleInfo (L154) does
#
#     data['clanAbbrev'] = playerVO.clanAbbrev
#
# i.e. NOT from the formatted result -- which is why stripping the clan inside
# PlayerFullNameFormatter.format() had no effect on the panel.
# ---------------------------------------------------------------------------

def _surfaceWrapper(key):
    """Build a patch() factory that runs the original inside a surface context.

    Every entry point below does the same thing: mark which screen is building
    this name, call the client's own method unchanged, then unwind.  The masking
    itself happens in the SHARED helpers (format / getPlayerLabel /
    getDisplayedName), which is the only place that sees the name in time.

    Pushing unconditionally is deliberate.  Skipping the push when the switch is
    off would make the shared helper fall back to scope.inBattle and mask the
    name anyway -- which is exactly the bug this replaces.

    The original method's exceptions are NOT caught: the client's own error
    handling must keep working, and _Surface.__exit__ unwinds the stack in any
    case.
    """

    def factory(original):
        def wrapped(*args, **kwargs):
            with _Surface(key):
                return original(*args, **kwargs)
        return wrapped
    return factory


def _panelSurfaceKey():
    """The players-panel switch, used for BOTH panel surfaces.

    The loading-screen team lists and the in-battle side panels both go through
    VehicleInfoComponent.addVehicleInfo -- measured in game.log:

        loading screen : loaders.py:viewLoaded
        in-battle HUD  : AvatarVehiclesInfoBase.py:setNested_vehiclesInfo

    They are deliberately NOT separate switches.  `_data` is a flat per-row dict
    (fields like playerName / playerFullName, not one entry per vehicleID), and
    the rows written during loading are NOT re-created when the battle starts:
    only the handful that get refreshed during the battle are.  With two
    switches, turning the in-battle one off produced a half-masked panel --
    rows written at loading kept their labels, refreshed rows showed real names.

    One switch keeps the panel internally consistent, which is what a viewer
    actually sees.
    """
    return KEY_SCOPE_PANEL


def _hookVehicleInfoComponentAdd(original):
    """VehicleInfoComponent.addVehicleInfo(self, vInfoVO, overrides).

    Both the LOADING-SCREEN team lists and the in-battle SIDE PANELS go through
    this one method, so they cannot be told apart by the component -- see
    _panelSurfaceKey() for how the caller is used instead.

    It builds each row from ctx.getPlayerFullName(...), i.e. through
    PlayerFullNameFormatter.format, so running the original inside the matching
    surface context is what decides whether the name comes out masked.  The clan
    tag is separate: the client reads it straight off `playerVO.clanAbbrev`
    rather than from the formatted string.
    """

    def addVehicleInfo(self, vInfoVO, overrides=None):
        key = _panelSurfaceKey()
        with _Surface(key):
            result = original(self, vInfoVO, overrides)
            try:
                if not CONFIG.surface(key) \
                        or not CONFIG.flag(KEY_HIDE_CLAN_TAG):
                    return result
                playerVO = getattr(vInfoVO, 'player', None)
                if playerVO is None or not ANONYMISER.isStranger(playerVO):
                    return result
                data = getattr(self, '_data', None)
                if isinstance(data, dict) and data.get('clanAbbrev'):
                    data['clanAbbrev'] = u''
            except Exception:
                logError('panel clan strip failed: %s' % traceback.format_exc())
            return result
    return addVehicleInfo


# ---------------------------------------------------------------------------
# 3D vehicle markers and the minimap
#
# Both resolve their label through VehicleArenaInfoVO.getDisplayedName (via
# _getDisplayedName / _getVehicleName), so the switch is enforced by pushing the
# matching surface context around the client's own entry points:
#
#   VehicleMarkerPlugin.addVehicleInfo / _setVehicleInfo   -> scope.markers
#   ArenaVehiclesPlugin.addVehicleInfo / _setVehicleInfo   -> scope.minimap
#
# Verified signatures (from the client bytecode):
#   VehicleMarkerPlugin.addVehicleInfo(self, vo, arenaDP)
#   VehicleMarkerPlugin._setVehicleInfo(self, marker, vInfo, guiProps, nameParts)
#   ArenaVehiclesPlugin.addVehicleInfo(self, vo, arenaDP)
#   ArenaVehiclesPlugin._setVehicleInfo(self, vehicleID, entry, vInfo,
#                                      guiProps, isSpotted)
#
# Note the marker setter takes `marker`, NOT a vehicle id, and both minimap
# methods hand off to `entry.setVehicleInfo(...)` -- there is no dict to edit
# afterwards, which is why wrapping the call is the only workable point.
# ---------------------------------------------------------------------------

_hookMarkerSetVehicleInfo = _surfaceWrapper(KEY_SCOPE_MARKERS)
_hookMinimapSetVehicleInfo = _surfaceWrapper(KEY_SCOPE_MINIMAP)
_hookMessagesGetPlayerInfo = _surfaceWrapper(KEY_SCOPE_MESSAGES)


# ---------------------------------------------------------------------------
# installer
# ---------------------------------------------------------------------------

class Installer(object):

    def __init__(self):
        self._undos = []
        self._installed = False

    def _patchFirstAvailable(self, label, candidates, cls_name, methods,
                             factory):
        """Patch `cls_name` in the first candidate module that defines it.

        The client does not keep these plugins in one predictable module name
        across versions, and guessing wrong is silent: install() logs one line
        and that surface's switch quietly does nothing.  So try every known path
        and report which one won.
        """
        for module_path in candidates:
            try:
                module = __import__(module_path, {}, {}, ['__name__'])
            except Exception:
                continue
            cls = getattr(module, cls_name, None)
            if cls is None:
                continue
            patched = []
            for name in methods:
                undo = patch(cls, name, factory)
                if undo:
                    self._undos.append(undo)
                    patched.append(name)
            logInfo('%s hooks installed from %s: %s'
                    % (label, module_path, ', '.join(patched) or 'none'))
            return True
        logError('%s hooks unavailable: %s not found in any of %s'
                 % (label, cls_name, ', '.join(candidates)))
        return False

    def install(self):
        if self._installed:
            return
        from gui.battle_control.arena_info import arena_vos, player_format

        for cls, name, factory in (
                (arena_vos.PlayerInfoVO, 'getPlayerLabel', _hookPlayerLabel),
                (arena_vos.PlayerInfoVO, 'getPlayerFakeLabel', _hookPlayerFakeLabel),
                (arena_vos.VehicleArenaInfoVO, 'getDisplayedName', _hookDisplayedName),
                (player_format.PlayerFullNameFormatter, 'format', _hookFormat)):
            undo = patch(cls, name, factory)
            if undo:
                self._undos.append(undo)

        try:
            from gui.battle_results.reusable import players as br_players
            # The personal scoreboard (components/shared.pyc PlayerNameBlock)
            # reads the SAME player through several accessors, so all of them
            # must be masked -- hooking only realName left the others showing the
            # original text:
            #     fakeName       -> fakeNameLabel   (property)
            #     realName       -> realNameLabel   (property)
            #     getFullName()  -> fullNameLabel   (method, bypasses realName)
            #     clanAbbrev     -> clanLabel       (property, never masked by
            #                                        the three above)
            for name, factory, isProp in (
                    ('realName', _hookResultsRealName, True),
                    ('fakeName', _hookResultsFakeName, True),
                    ('getFullName', _hookResultsFullName, False),
                    ('clanAbbrev', _hookResultsClanAbbrev, True)):
                undo = patch(br_players.PlayerInfo, name, factory,
                             is_property=isProp)
                if undo:
                    self._undos.append(undo)
        except Exception:
            logError('battle-results hook unavailable: %s' % traceback.format_exc())

        # Single-player profile / details window: restore the real name when the
        # user opted in.  Scoped to that window only -- see the docstring for why
        # hooking lobbyContext.getPlayerFullName would be too broad.
        try:
            from gui.Scaleform.daapi.view.lobby.profile.ProfileWindow import (
                ProfileWindow)
            undo = patch(ProfileWindow,
                         '_ProfileWindow__updateUserInfo',
                         _hookProfileUpdateUserInfo)
            if undo:
                self._undos.append(undo)
        except Exception:
            logError('profile window hook unavailable: %s'
                     % traceback.format_exc())

        # The TAB / full-stats panel is a Gameface view that bypasses every
        # helper above and fills its models from the engine's arena dict, so it
        # needs its own hooks (see the comment block above).
        try:
            from gui.impl.battle.battle_page.tab_view import TabView
            for name, factory in (
                    ('_invalidatePersonalInfo', _hookTabInvalidatePersonalInfo),
                    ('_invalidateVehiclesInfo', _hookTabInvalidateVehiclesInfo)):
                undo = patch(TabView, name, factory)
                if undo:
                    self._undos.append(undo)
        except Exception:
            logError('TAB panel hook unavailable: %s' % traceback.format_exc())

        # The Scaleform players panel takes the clan tag straight off the VO,
        # not from the formatted string, so strip it at that point too.
        try:
            from gui.Scaleform.daapi.view.battle.shared.stats_exchange import (
                vehicle as stats_exchange_vehicle)
            undo = patch(stats_exchange_vehicle.VehicleInfoComponent,
                         'addVehicleInfo', _hookVehicleInfoComponentAdd)
            if undo:
                self._undos.append(undo)
        except Exception:
            logError('players-panel clan hook unavailable: %s'
                     % traceback.format_exc())

        # Badges (medal icons).  Every in-battle surface reads them via the arena
        # VO, so the two properties below cover the players panel, death-cam,
        # event panels and the pre-battle markers in one shot.
        try:
            from gui.battle_control.arena_info import arena_vos as _avos
            for name, factory in (
                    ('selectedBadge', _hookSelectedBadge),
                    ('selectedSuffixBadge', _hookSelectedBadge)):
                undo = patch(_avos.VehicleArenaInfoVO, name, factory,
                             is_property=True)
                if undo:
                    self._undos.append(undo)
        except Exception:
            logError('badge property hooks unavailable: %s'
                     % traceback.format_exc())

        # Death-cam killer line stores the badge on the user VO as its own key.
        try:
            from gui.Scaleform.daapi.view.battle.shared.postmortem_panel import (
                PostmortemPanel)
            undo = patch(PostmortemPanel, '_makeKillerVO',
                         _hookPostmortemBadgeFor)
            if undo:
                self._undos.append(undo)
        except Exception:
            logError('postmortem badge hook unavailable: %s'
                     % traceback.format_exc())

        # Per-surface switches.  These entry points only push a surface context;
        # the masking itself is done by the shared helpers, which consult it.
        #
        # IMPORTANT: the module paths are NOT the obvious ones.  The marker and
        # minimap plugins live in `...shared.markers2d.vehicle_plugins` and
        # `...shared.minimap.plugins`, NOT both under a `plugins` module -- the
        # first version imported `markers2d.plugins` and install() failed with
        # "module object has no attribute VehicleMarkerPlugin", so the marker
        # switch silently did nothing.  Try every known spelling.
        for label, candidates, cls_name, methods, factory in (
                ('marker',
                 ('gui.Scaleform.daapi.view.battle.shared.markers2d'
                  '.vehicle_plugins',
                  'gui.Scaleform.daapi.view.battle.shared.markers2d.plugins',
                  'gui.Scaleform.daapi.view.battle.shared.vehicle_plugins'),
                 'VehicleMarkerPlugin',
                 ('addVehicleInfo', 'updateVehiclesInfo',
                  'invalidateVehiclesInfo', '_setVehicleInfo'),
                 _hookMarkerSetVehicleInfo),
                ('minimap',
                 ('gui.Scaleform.daapi.view.battle.shared.minimap.plugins',
                  'gui.Scaleform.daapi.view.battle.shared.minimap'
                  '.vehicle_plugins'),
                 'ArenaVehiclesPlugin',
                 ('addVehicleInfo', 'updateVehiclesInfo',
                  'invalidateVehiclesInfo', '_setVehicleInfo'),
                 _hookMinimapSetVehicleInfo),
        ):
            self._patchFirstAvailable(label, candidates, cls_name, methods,
                                      factory)

        try:
            from gui.Scaleform.daapi.view.battle.shared.messages import (
                vehicle_messages)
            undo = patch(vehicle_messages.VehicleMessages, '_getPlayerInfo',
                         _hookMessagesGetPlayerInfo)
            if undo:
                self._undos.append(undo)
        except Exception:
            logError('messages hook unavailable: %s' % traceback.format_exc())

        # Results screen: badges are packed per player DBID.
        try:
            from gui.battle_results.presenters.packers.user_info import UserNames
            undo = patch(UserNames, '_setBadges', _hookResultsSetBadges)
            if undo:
                self._undos.append(undo)
        except Exception:
            logError('results badge hook unavailable: %s'
                     % traceback.format_exc())

        # Team stats (the "team performance" tab): its own blocks, own badge fields.
        # This path does NOT go through any of the hooks above -- it reads the
        # reusable avatar record directly -- which is why badges stayed visible
        # there after the personal scoreboard was fixed.
        try:
            from gui.battle_results.components.vehicles import (
                RegularVehicleStatsBlock, BadgeBlock)
            for cls, factory in ((RegularVehicleStatsBlock, _hookTeamStatsBadge),
                                 (BadgeBlock, _hookTeamBadgeBlock)):
                undo = patch(cls, 'setRecord', factory)
                if undo:
                    self._undos.append(undo)
        except Exception:
            logError('team-stats badge hooks unavailable: %s'
                     % traceback.format_exc())

        self._installed = True
        logInfo('installed with %d hook(s)' % len(self._undos))

    def uninstall(self):
        for undo in reversed(self._undos):
            try:
                undo()
            except Exception:
                pass
        self._undos = []
        self._installed = False
        logInfo('uninstalled')


INSTALLER = Installer()

# Set once by init(); every other entry point checks it, so a version-mismatched
# client never hooks anything even if the module still gets imported.
_ACTIVE = False


# ---------------------------------------------------------------------------
# mod entry points (called by gui.mods)
# ---------------------------------------------------------------------------

def init():
    """Entry point.

    This is an internal test build pinned to TARGET_VERSION.  If the running
    client is a different version we log once and do nothing at all: no hooks,
    no settings page, no config reads.  The client's folder layout already keeps
    mods/2.4.1.0 out of a 2.4.1.1 install, but the lock should travel with the
    file rather than depend on where the user unzipped it.
    """
    global _ACTIVE
    ok, running = versionIsSupported()
    if not ok:
        _ACTIVE = False
        logError('DISABLED: this build is locked to client %s, running %s'
                 % (TARGET_VERSION,
                    '.'.join(str(p) for p in running) if running else 'unknown'))
        return

    logInfo('init (WoT %s, enabled=%s, mode=%s)'
            % (TARGET_VERSION, CONFIG.enabled(), CONFIG.mode()))
    _ACTIVE = True
    try:
        INSTALLER.install()
    except Exception:
        logError('install failed: %s' % traceback.format_exc())

    # In-game settings page (Aslain Mod Menu / ModsSettingsAPI). Optional: if
    # the framework is missing we simply keep the JSON config.
    global SETTINGS_PAGE
    try:
        from gui.mods.streamer_mode_settings import SettingsPage
        SETTINGS_PAGE = SettingsPage(CONFIG)
        SETTINGS_PAGE.register()
    except Exception:
        logError('settings page unavailable: %s' % traceback.format_exc())


SETTINGS_PAGE = None


def fini():
    global _ACTIVE
    if not _ACTIVE:
        return
    INSTALLER.uninstall()
    _ACTIVE = False


def onAvatarBecomePlayer(*args, **kwargs):
    """Entering a battle: fresh numbering, fresh identity.

    IDENTITY.reset() runs first so the previous battle's platoon mates cannot
    survive into this one; resolve() then takes a complete new snapshot.
    """
    if not _ACTIVE:
        return
    try:
        ANONYMISER.reset()
        IDENTITY.reset()
        IDENTITY.resolve()
        INSTALLER.install()
    except Exception:
        logError('onAvatarBecomePlayer failed: %s' % traceback.format_exc())


def onAvatarBecomeNonPlayer(*args, **kwargs):
    """Leaving battle.

    Deliberately does NOT reset the numbering: the battle-results screen (and the
    personal scoreboard in particular) is rendered AFTER this event, and it must
    show the same bot numbers the player just saw in battle.  Wiping the table
    here made results restart from Bot_001 while the panel had used higher
    numbers.  onAvatarBecomePlayer() resets before the next battle instead.
    """
    if not _ACTIVE:
        return
    try:
        logInfo('left battle; keeping numbering for the results screen')
    except Exception:
        pass


def onAccountBecomePlayer(*args, **kwargs):
    """Account boundary: a different account may not share the same exemptions.

    Everything is dropped before re-resolving -- otherwise one account's friends
    and clan would stay exempt while playing on another.  The anonymiser is
    reset too, since DBIDs from the old account mean nothing on the new one.
    """
    if not _ACTIVE:
        return
    try:
        IDENTITY.reset()
        ANONYMISER.reset()
        IDENTITY.resolve()
    except Exception:
        logError('onAccountBecomePlayer failed: %s' % traceback.format_exc())