# -*- coding: utf-8 -*-
"""Verify the player-name prefix follows the client UI language.

Requirement: on a Chinese client strangers are labelled 玩家_001; every other
language keeps the English Player_001.

The rule lives in Config.prefix(): an EXPLICIT value (from config.json or the
in-game menu) always wins, and only the default is localised.  That ordering is
the important part -- it must be impossible for a client-language change to
silently rewrite a prefix the user chose.

Language detection uses helpers.getClientLanguage(), the same source the
settings page uses for its label table (it reads i18n #settings:LANGUAGE_CODE).

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
        self._p = 1
        self._s = 2

    @property
    def selectedBadge(self):
        return self._p

    @property
    def selectedSuffixBadge(self):
        return self._s

    def getDisplayedName(self, name=None):
        return 'T-54' if name is None else name


class PlayerFullNameFormatter(object):
    def format(self, vInfoVO, playerName=None):
        import collections
        R = collections.namedtuple('R', 'playerFullName playerName '
                                        'playerFakeName clanAbbrev regionCode '
                                        'vehicleName')
        return R(playerName, playerName, '', '', '', '')


def _install(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


arena_vos = _install('gui.battle_control.arena_info.arena_vos',
                     PlayerInfoVO=PlayerInfoVO,
                     VehicleArenaInfoVO=VehicleArenaInfoVO)
pformat = _install('gui.battle_control.arena_info.player_format',
                   PlayerFullNameFormatter=PlayerFullNameFormatter,
                   _FORMAT_MASK=type('M', (), {'NONE': 0, 'VEHICLE': 1,
                                               'REGION': 2, 'CLAN': 16,
                                               'VEHICLE_REGION': 3}),
                   _PLAYER_FULL_NAME_FORMATS={})
_install('gui.battle_control.arena_info', arena_vos=arena_vos,
         player_format=pformat)
_install('gui.battle_control')
_install('gui')


class BRPlayerInfo(object):
    __slots__ = ('_PlayerInfo__dbID',)

    def __init__(self, dbID=None):
        self._PlayerInfo__dbID = dbID


_install('gui.battle_results.reusable.players', PlayerInfo=BRPlayerInfo)
_install('gui.battle_results.reusable')
_install('gui.battle_results')
_install('gui.impl.battle.battle_page.tab_view',
         TabView=type('TabView', (object,), {}))
_install('gui.impl.battle.battle_page')
_install('gui.impl.battle')
_install('gui.impl')
_install('gui.Scaleform.daapi.view.battle.shared.stats_exchange.vehicle',
         VehicleInfoComponent=type('C', (object,), {'_data': {}}))
_install('gui.Scaleform.daapi.view.battle.shared.stats_exchange')
_install('gui.Scaleform.daapi.view.battle.shared')
_install('gui.Scaleform.daapi.view.battle')
_install('gui.Scaleform.daapi.view')
_install('gui.Scaleform.daapi')
_install('gui.Scaleform')
_install('gui.shared.badges', buildBadge=lambda *a, **k: None)
_install('gui.shared')
_install('gui.doc_loaders.badges_loader',
         getSelectedByLayout=lambda ids: (0, 0))
_install('gui.doc_loaders')

bw = types.ModuleType('BigWorld')
bw.logInfo = lambda *a: None
bw.logError = lambda *a: None
sys.modules['BigWorld'] = bw

# helpers: the language source.  A mutable box so each case can set it.
_lang_box = {'value': 'en'}


def _getClientLanguage():
    value = _lang_box['value']
    if value is None:
        raise RuntimeError('no language')
    return value


helpers = _install('helpers', getClientLanguage=_getClientLanguage)

# ------------------------------------------------------------------- load --
mod = imp.load_compiled('mod_streamer_mode',
                        os.path.join(HERE, 'build', 'mod_streamer_mode.pyc'))

print()
print('=== English client (baseline) ===')
_lang_box['value'] = 'en'
check('en -> Player_', mod.CONFIG.prefix() == 'Player_', mod.CONFIG.prefix())
_lang_box['value'] = 'ru'
check('ru -> Player_ (unchanged)', mod.CONFIG.prefix() == 'Player_',
      mod.CONFIG.prefix())
_lang_box['value'] = 'de'
check('de -> Player_', mod.CONFIG.prefix() == 'Player_', mod.CONFIG.prefix())

print()
print('=== Chinese client ===')
_lang_box['value'] = 'zh'
got = mod.CONFIG.prefix()
check('zh -> 玩家_', got == '玩家_', got)
_lang_box['value'] = 'zh_CN'
check('zh_CN -> 玩家_', mod.CONFIG.prefix() == '玩家_',
      mod.CONFIG.prefix())
_lang_box['value'] = 'ZH'
check('uppercase ZH -> 玩家_ (case-insensitive)',
      mod.CONFIG.prefix() == '玩家_', mod.CONFIG.prefix())

print()
print('=== the prefix is actually used in labels ===')
_lang_box['value'] = 'zh'
mod.CONFIG._values['enable'] = True
mod.CONFIG._values['mode'] = 'label'
mod.CONFIG._values['scope.inBattle'] = True
mod.IDENTITY.ownDBID = 1000
mod.IDENTITY.friendDBIDs = set()
mod.IDENTITY.ownClanAbbrev = None
mod.IDENTITY.squadmateDBIDs = set()
mod.ANONYMISER.reset()
label = mod.ANONYMISER.displayForID(7777, 'SomeStranger', '')
check('zh label is 玩家_001', label == '玩家_001', label)
check('zh label is not Player_001', not label.startswith('Player_'), label)

_lang_box['value'] = 'en'
mod.ANONYMISER.reset()
label_en = mod.ANONYMISER.displayForID(7777, 'SomeStranger', '')
check('en label is Player_001', label_en == 'Player_001', label_en)

print()
print('=== an explicit prefix always wins ===')
_lang_box['value'] = 'zh'
mod.CONFIG._values['namePrefix'] = 'Hidden_'
check('explicit value beats the zh default',
      mod.CONFIG.prefix() == 'Hidden_', mod.CONFIG.prefix())
mod.ANONYMISER.reset()
explicit = mod.ANONYMISER.displayForID(8888, 'SomeStranger', '')
check('explicit prefix used in the label', explicit == 'Hidden_001', explicit)

# An explicit value the user typed themselves also survives a language switch.
_lang_box['value'] = 'en'
check('explicit value independent of language',
      mod.CONFIG.prefix() == 'Hidden_', mod.CONFIG.prefix())
mod.CONFIG._values['namePrefix'] = 'Player_'

# A blank/absent value falls back to the localised default again.
for blank in ('', '   ', None):
    mod.CONFIG._values['namePrefix'] = blank
    _lang_box['value'] = 'zh'
    check('blank %r falls back to 玩家_' % (blank,),
          mod.CONFIG.prefix() == '玩家_', mod.CONFIG.prefix())
mod.CONFIG._values['namePrefix'] = 'Player_'

print()
print('=== unknown language degrades to English ===')
_lang_box['value'] = None
check('language lookup failure -> Player_',
      mod.CONFIG.prefix() == 'Player_', mod.CONFIG.prefix())
_lang_box['value'] = ''
check('empty language -> Player_', mod.CONFIG.prefix() == 'Player_',
      mod.CONFIG.prefix())

print()
print('=== bot prefix is NOT localised ===')
_lang_box['value'] = 'zh'
check('bot prefix stays Bot_ on a zh client',
      mod.CONFIG.botPrefix() == 'Bot_', mod.CONFIG.botPrefix())

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)
