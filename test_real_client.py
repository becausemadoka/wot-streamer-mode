# -*- coding: utf-8 -*-
"""Load REAL client classes and run the mod's hooks on them.

This closes the loop between the mod and the shipped client: instead of
hand-written stubs, the real arena_vos / player_format class definitions are
loaded and rebuilt, then patched exactly as the mod does.

Requires the extracted client fixtures, which are NOT part of the repository
(they are Wargaming's files).  Generate them first with:

    py -2.7 refresh_fixtures.py

with WOT_GAME pointing at your install.  Without them this test skips rather
than fails, so a clean checkout is not reported as broken.

Python 2.7.
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WOT = os.path.join(os.path.dirname(HERE), '_wot')
EXTRACTED = os.path.join(WOT, 'extracted')

if not os.path.isfile(os.path.join(WOT, 'py27.py')) or \
        not os.path.isdir(EXTRACTED):
    print('SKIP: client fixtures not present.')
    print('      Run "py -2.7 refresh_fixtures.py" with WOT_GAME set to your')
    print('      install to generate them, then re-run this test.')
    sys.exit(0)

sys.path.insert(0, WOT)

import py27  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + repr(detail)) if detail and not cond else ''))


# --------------------------------------------------------------------------
# Rebuild real classes from the shipped bytecode
# --------------------------------------------------------------------------
EXTRACTED = os.path.join(WOT, 'extracted')


class _RealCode(object):
    """Deserialise real client module data with this interpreter's native marshal.

    We run under Python 2.7 -- the same version the client uses -- so native
    marshal gives us genuine code objects (py27.py's custom Code class is for
    inspecting the files from Python 3).
    """

    @staticmethod
    def load(pyc_path):
        import marshal
        raw = open(pyc_path, 'rb').read()
        return marshal.loads(raw[8:])

    @staticmethod
    def run(pyc_path, globs):
        code = _RealCode.load(pyc_path)
        exec code in globs
        return globs


def build_real_classes():
    """Rebuild ONLY the class bodies of interest from real bytecode.

    Executing the full client modules drags in the whole game (enum, typing,
    dependency injection...).  The class body code objects are self-contained
    apart from a few globals, so we execute those directly with a small
    namespace.  This is still the *real* compiled logic -- __init__, isBot,
    getPlayerLabel, __slots__ all come from the shipped .pyc.
    """
    code = _RealCode.load(os.path.join(EXTRACTED, 'arena_vos.pyc'))

    def find(c, name, acc=None):
        if acc is None:
            acc = []
        if c.co_name == name:
            acc.append(c)
        for k in c.co_consts:
            if hasattr(k, 'co_code'):
                find(k, name, acc)
        return acc

    # Sanity: the class body must be found before we try to exec it.
    for cls_name in ('PlayerInfoVO', 'VehicleArenaInfoVO'):
        if not find(code, cls_name):
            print('  (%s NOT FOUND in module tree)' % cls_name)

    # Globals the class bodies reference at definition time.
    g = {
        '__name__': 'gui.battle_control.arena_info.arena_vos',
        '__builtins__': __builtins__,
        'object': object,
        'property': property,
        'staticmethod': staticmethod,
        'classmethod': classmethod,
        'False': False, 'True': True, 'None': None,
        'i18n': types.ModuleType('i18n'),
        'settings': types.ModuleType('settings'),
    }
    g['i18n'].makeString = lambda *a: 'Unknown'
    g['settings'].UNKNOWN_PLAYER_NAME = 'unknown'

    # minimal real-ish dependencies referenced inside methods
    class _IEventsCache(object):
        def getPersonalMissions(self):
            return None
    class _IGR_TYPE(object):
        NONE = 0
    g['IEventsCache'] = _IEventsCache
    g['IGR_TYPE'] = _IGR_TYPE
    dep = types.ModuleType('helpers.dependency')
    dep.descriptor = lambda cls: _IEventsCache()
    g['dependency'] = dep
    g['eventsCache'] = _IEventsCache()
    g['avatar_getter'] = types.ModuleType('avatar_getter')
    g['avatar_getter'].getArena = lambda: None
    g['collectDisplayedClassTagGetter'] = lambda *a: None
    g['getSelectedByLayout'] = lambda *a: (None, None)
    g['LocalizableBotName'] = None
    g['BotNamingType'] = type('BotNamingType', (), {'CUSTOM': 1})
    g['_INVALIDATE_OP'] = type('_INVALIDATE_OP', (), {'SORTING': 1, 'NONE': 0})()
    g['GameModeDataVO'] = object
    g['PlayerRankedInfoVO'] = object
    g['VehicleTypeInfoVO'] = object
    g['_PLAYER_STATUS'] = type('_PLAYER_STATUS', (), {'IS_SQUAD_MAN': 1,
                                                      'IS_TEAM_KILLER': 2})
    g['PLAYER_GUI_PROPS'] = None
    g['BOT_DISPLAY_STATUS'] = type('BOT_DISPLAY_STATUS', (), {'REGULAR': 0})
    g['TEAMS_IN_ARENA'] = None

    def _enum(**kw):
        """Enum members expose .value, as the client's enums do."""
        return type('E', (), {k: type('M', (), {'value': v})()
                              for k, v in kw.items()})
    g['TEAM_PANEL_MODE'] = _enum(SHOW=1, HIDE=0)
    g['_DELIVERY_STATUS'] = _enum(NONE=0, UNDEFINED=0, DELIVERED=1)

    out = {}
    for cls_name in ('PlayerInfoVO', 'VehicleArenaInfoVO'):
        codes = find(code, cls_name)
        if not codes:
            print('  (%s code object not found)' % cls_name)
            continue
        body = codes[0]
        # A class-body code object ends with LOAD_LOCALS / RETURN_VALUE: it
        # *returns* its namespace, which the module level then feeds to
        # BUILD_CLASS.  So we eval it and build the class ourselves.
        local = {}
        try:
            ns = eval(body, g, local)
        except Exception as e:
            import traceback
            print('  (%s body eval failed: %s)' % (cls_name, e))
            traceback.print_exc()
            continue
        try:
            cls = type(cls_name, (object,), ns)
        except Exception as e:
            print('  (%s type() failed: %s)' % (cls_name, e))
            continue
        out[cls_name] = cls
        # Methods resolve globals through their defining module namespace, so
        # publish each class back into g (VehicleArenaInfoVO.__init__ builds a
        # PlayerInfoVO by name, and PlayerInfoVO.__init__ calls super()).
        g[cls_name] = cls
        print('  (built real %s, slots=%r)' % (cls_name, getattr(cls, '__slots__', None)))
    # VehicleArenaInfoVO depends on more client machinery; PlayerInfoVO alone
    # is enough to exercise the mod's core anonymisation path.
    return out.get('PlayerInfoVO'), out.get('VehicleArenaInfoVO')


print('=== rebuilding REAL client classes ===')
real = build_real_classes()
if real is None:
    print('could not rebuild real classes; falling back to schema checks')
    PlayerInfoVO = VehicleArenaInfoVO = None
else:
    PlayerInfoVO, VehicleArenaInfoVO = real
    print('  got PlayerInfoVO=%s  VehicleArenaInfoVO=%s' % (PlayerInfoVO, VehicleArenaInfoVO))

# --------------------------------------------------------------------------
# schema assertions against the real bytecode
# --------------------------------------------------------------------------
print()
print('=== real class schema ===')
code = _RealCode.load(os.path.join(EXTRACTED, 'arena_vos.pyc'))


def _all_codes(c, acc=None):
    if acc is None:
        acc = []
    acc.append(c)
    for k in c.co_consts:
        if hasattr(k, 'co_code'):
            _all_codes(k, acc)
    return acc


by_name = {c.co_name: c for c in _all_codes(code)}
piv = by_name.get('PlayerInfoVO')
# The class body returns its namespace; __slots__ is a top-level constant of
# that body, not of the enclosing module.
slots = None
for k in piv.co_consts:
    if isinstance(k, tuple) and 'accountDBID' in k:
        slots = k
if slots is None and PlayerInfoVO is not None:
    slots = getattr(PlayerInfoVO, '__slots__', None)
check('real PlayerInfoVO has expected slots',
      slots is not None and 'fakeName' in slots and 'clanAbbrev' in slots, slots)

if PlayerInfoVO is not None:
    print()
    print('=== drive the real classes with the mod hooks ===')
    # The mod patches these exact objects; emulate identity
    sys.modules['BigWorld'] = types.ModuleType('BigWorld')
    sys.modules['BigWorld'].logInfo = lambda *a: None
    sys.modules['BigWorld'].logError = lambda *a: None

    import imp
    mod = imp.load_compiled('mod_streamer_mode',
                            os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))
    mod.CONFIG._values.update({'enable': True, 'mode': 'label',
                               'namePrefix': 'Player_', 'hideClanTag': True,
                               'scope.inBattle': True})
    mod.IDENTITY.ownDBID = 1
    mod.IDENTITY.friendDBIDs = set([2])
    mod.IDENTITY.ownClanAbbrev = 'CLAN'
    mod.IDENTITY.squadmateDBIDs = set()

    # patch the REAL PlayerInfoVO
    undo = mod.patch(PlayerInfoVO, 'getPlayerLabel', mod._hookPlayerLabel)
    check('patched real PlayerInfoVO.getPlayerLabel', undo is not None)

    # construct real VOs (kwargs matching the real __init__)
    try:
        stranger = PlayerInfoVO(accountDBID=99, avatarSessionID='s99',
                                name='NoobKiller', clanAbbrev='ENEMY',
                                igrType=0, personalMissionIDs=None,
                                personalMissionInfo=None,
                                isPrebattleCreator=False,
                                forbidInBattleInvitations=False, fakeName='')
        me = PlayerInfoVO(accountDBID=1, avatarSessionID='s1', name='MyName',
                          clanAbbrev='CLAN', igrType=0, personalMissionIDs=None,
                          personalMissionInfo=None, isPrebattleCreator=False,
                          forbidInBattleInvitations=False, fakeName='')
        check('stranger anonymised on REAL class',
              stranger.getPlayerLabel() == 'Player_001', stranger.getPlayerLabel())
        check('self keeps real name on REAL class',
              me.getPlayerLabel() == 'MyName', me.getPlayerLabel())
        # NOTE: in arena_vos, isBot is a @property, not a method.  The mod only
        # calls isBot() if it is callable, so both shapes are handled; here we
        # assert the real property shape and that the mod coped with it.
        check('real isBot is a bool property', me.isBot is False, me.isBot)
        bot = PlayerInfoVO(accountDBID=0, avatarSessionID=None, name='BotName',
                           clanAbbrev='', igrType=0, personalMissionIDs=None,
                           personalMissionInfo=None, isPrebattleCreator=False,
                           forbidInBattleInvitations=False, fakeName='')
        # bots are detected via the real isBot property, and since the bot-prefix
        # feature they get their own label rather than keeping the client name
        check('real bot detected and given a bot label',
              bot.isBot is True and bot.getPlayerLabel() == 'Bot_001',
              (bot.isBot, bot.getPlayerLabel()))
    except Exception as e:
        import traceback
        traceback.print_exc()
        check('construct real VOs', False, e)

    if undo:
        undo()

    # ---------------------------------------------------------------
    # battle-results PlayerInfo.realName is a property, not a method
    # ---------------------------------------------------------------
    print()
    print('=== real battle-results PlayerInfo (property hook) ===')
    br_code = _RealCode.load(os.path.join(EXTRACTED, 'players.pyc'))

    def find_br(c, name):
        if c.co_name == name:
            return c
        for k in c.co_consts:
            if hasattr(k, 'co_code'):
                r = find_br(k, name)
                if r:
                    return r
        return None

    bb = find_br(br_code, 'PlayerInfo')
    if bb is None:
        check('found real battle-results PlayerInfo', False)
    else:
        g2 = {'__name__': 'gui.battle_results.reusable.players',
              '__builtins__': __builtins__, 'object': object,
              'property': property, 'staticmethod': staticmethod,
              'True': True, 'False': False, 'None': None}
        # minimal pieces the property getters touch
        g2['getUnknownPlayerName'] = lambda *a: 'Unknown'
        g2['ILobbyContext'] = object
        g2['getRegionCode'] = lambda *a: ''
        g2['addTag'] = lambda *a: None
        g2['style'] = type('style', (), {'getUnknownPlayerName': staticmethod(lambda: 'Unknown')})
        dep2 = types.ModuleType('helpers.dependency')
        dep2.descriptor = lambda *a, **k: None
        g2['dependency'] = dep2
        try:
            ns = eval(bb, g2, {})
            RealPlayerInfo = type('PlayerInfo', (object,), ns)
            check('built real battle-results PlayerInfo',
                  'realName' in ns and isinstance(ns['realName'], property),
                  type(ns.get('realName')))
        except Exception as e:
            import traceback
            traceback.print_exc()
            RealPlayerInfo = None
            check('built real battle-results PlayerInfo', False, e)

        if RealPlayerInfo is not None:
            # patch the property exactly as the installer does
            undo2 = mod.patch(RealPlayerInfo, 'realName',
                              mod._hookResultsRealName, is_property=True)
            check('patched real realName property', undo2 is not None)

            def make_pi(dbID, real, fake):
                pi = RealPlayerInfo.__new__(RealPlayerInfo)
                pi._PlayerInfo__dbID = dbID
                pi._PlayerInfo__realName = real
                pi._PlayerInfo__fakeName = fake
                pi._PlayerInfo__team = 1
                pi._PlayerInfo__prebattleID = None
                pi._PlayerInfo__igrType = 0
                pi._PlayerInfo__clanInfo = None
                pi._PlayerInfo__isTeamKiller = False
                pi._PlayerInfo__tags = set()
                pi.squadIndex = 0
                return pi

            try:
                mod.CONFIG._values['scope.battleResults'] = True
                stranger2 = make_pi(555, 'SomeStranger', '')
                check('results: stranger anonymised',
                      stranger2.realName == 'Player_001'
                      or (stranger2.realName or '').startswith('Player_'),
                      stranger2.realName)
                mine = make_pi(1, 'MyOwnName', '')
                check('results: self keeps real name',
                      mine.realName == 'MyOwnName', mine.realName)
                friend2 = make_pi(2, 'BuddyName', '')
                check('results: friend keeps real name',
                      friend2.realName == 'BuddyName', friend2.realName)
                # game's own anonymiser already applied -> still masked, because
                # a native fake name is a per-player identifier too (reviewer
                # finding: this used to be passed through untouched).
                already = make_pi(777, 'RealGuy', 'FakeGuy')
                label = already.realName or ''
                check('results: game-anonymised stranger is masked',
                      label.startswith('Player_') and label not in
                      ('RealGuy', 'FakeGuy'), label)
                mod.CONFIG._values['scope.battleResults'] = False
                off = make_pi(888, 'VisibleName', '')
                check('results: scope off => real name', off.realName == 'VisibleName',
                      off.realName)
            except Exception as e:
                import traceback
                traceback.print_exc()
                check('results behaviour', False, e)
            if undo2:
                undo2()

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)
