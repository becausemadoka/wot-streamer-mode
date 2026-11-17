# -*- coding: utf-8 -*-
"""Verify the in-game settings page integrates correctly.

Stubs gui.aslainMenu (g_modsSettingsApi + templates) with the REAL signatures,
which mirror the shipped ModsSettingsAPI 1.7.1 API:

    setModTemplate(linkage, template, callback, buttonHandler)
    getModSettings(linkage, template)
    registerCallback(linkage, callback, buttonHandler)
    createDropdown(text, varName, options, value, tooltip, ...)
    createCheckbox(text, varName, value, tooltip, ...)
    createInput(text, varName, value, tooltip, ...)
    createLabel(text, tooltip, ...)
    createEmpty(height)

Python 2.7.
"""
import os
import sys
import types
import imp

HERE = os.path.dirname(os.path.abspath(__file__))

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  <- ' + repr(detail)) if detail and not cond else ''))


# ---------------------------------------------------------------- stubs ----
calls = {'setModTemplate': [], 'registerCallback': [], 'getModSettings': []}


class _Templates(object):
    """Mirror of ModsSettingsAPI.templates with the real argument order."""

    @staticmethod
    def createLabel(text, tooltip=None, tooltipIcon=None):
        return {'type': 'Label', 'text': text, 'tooltip': tooltip}

    @staticmethod
    def createCheckbox(text, varName, value, tooltip=None, tooltipIcon=None,
                       button=None):
        return {'type': 'CheckBox', 'text': text, 'varName': varName,
                'value': value, 'tooltip': tooltip}

    @staticmethod
    def createDropdown(text, varName, options, value, tooltip=None,
                       tooltipIcon=None, button=None, width=None):
        return {'type': 'Dropdown', 'text': text, 'varName': varName,
                'options': options, 'value': value, 'tooltip': tooltip}

    @staticmethod
    def createInput(text, varName, value, tooltip=None, tooltipIcon=None,
                    button=None, width=None):
        return {'type': 'Input', 'text': text, 'varName': varName,
                'value': value, 'tooltip': tooltip}

    @staticmethod
    def createEmpty(height=20):
        return {'type': 'Empty', 'height': height}


class _Api(object):
    """Faithful stand-in for ModsSettingsAPI.

    Mirrors the real control flow (api.pyc setModTemplate / compareTemplates):

        current = self.state['templates'].get(linkage)
        if not current or self.compareTemplates(template, current):
            self.state['templates'][linkage] = template
            self.state['settings'][linkage] = getSettingsFromTemplate(template)
            self.saveState()

    and compareTemplates() short-circuits to a version comparison:

        if 'settingsVersion' in new and 'settingsVersion' in old:
            return new['settingsVersion'] > old['settingsVersion']
        return jsonDump(new) != jsonDump(old)

    This matters: a template whose version is NOT greater than the cached one is
    DISCARDED, so adding controls without bumping settingsVersion makes them
    invisible in the menu.
    """

    # lets a test pretend the framework already has saved settings
    _savedNext = None
    # persists across _Api instances, like the framework's on-disk state
    _state = {'templates': {}, 'settings': {}}

    @staticmethod
    def _tplVersion(t):
        return t.get('settingsVersion') if isinstance(t, dict) else None

    @staticmethod
    def _jsonDump(t):
        import json
        return json.dumps(t, sort_keys=True)

    def compareTemplates(self, newTemplate, oldTemplate):
        newV = self._tplVersion(newTemplate)
        oldV = self._tplVersion(oldTemplate)
        if newV is not None and oldV is not None:
            return newV > oldV
        return self._jsonDump(newTemplate) != self._jsonDump(oldTemplate)

    @staticmethod
    def getSettingsFromTemplate(template):
        settings = {}
        if isinstance(template, dict):
            if 'enabled' in template:
                settings['enabled'] = template['enabled']
            for col in ('column1', 'column2'):
                for c in template.get(col, []):
                    if 'varName' in c:
                        settings[c['varName']] = c.get('value')
        return settings

    def getModSettings(self, linkage, template):
        calls['getModSettings'].append(linkage)
        saved = _Api._savedNext
        if isinstance(saved, dict):
            return dict(saved)
        return self._state['settings'].get(linkage)

    def setModTemplate(self, linkage, template, callback, buttonHandler=None):
        calls['setModTemplate'].append((linkage, template, callback))
        current = self._state['templates'].get(linkage)
        if current is None or self.compareTemplates(template, current):
            self._state['templates'][linkage] = template
            self._state['settings'][linkage] = \
                self.getSettingsFromTemplate(template)
        self.onSettingsChanged = [callback]
        self._callback = callback
        return self._state['settings'].get(linkage, {})

    def registerCallback(self, linkage, callback, buttonHandler=None):
        calls['registerCallback'].append((linkage, callback))
        self._callback = callback


# register the fake gui.aslainMenu package
gui = types.ModuleType('gui')
gui.__path__ = []
sys.modules['gui'] = gui
aslain = types.ModuleType('gui.aslainMenu')
aslain.g_modsSettingsApi = _Api()
aslain.templates = _Templates
sys.modules['gui.aslainMenu'] = aslain
gui.aslainMenu = aslain

bw = types.ModuleType('BigWorld')
LOG_RECORDS = []


def _fake_logInfo(*a):
    """The real engine signature is (tag, message, None)."""
    if len(a) < 2:
        raise TypeError('logInfo() takes at least 2 arguments (%d given)' % len(a))
    LOG_RECORDS.append(('INFO',) + a)


def _fake_logError(*a):
    if len(a) < 2:
        raise TypeError('logError() takes at least 2 arguments (%d given)' % len(a))
    LOG_RECORDS.append(('ERROR',) + a)


bw.logInfo = _fake_logInfo
bw.logError = _fake_logError
sys.modules['BigWorld'] = bw

# gui.mods package so `from gui.mods.streamer_mode_settings import ...` works
mods_pkg = types.ModuleType('gui.mods')
mods_pkg.__path__ = [os.path.join(HERE, 'build')]
sys.modules['gui.mods'] = mods_pkg

# ---------------------------------------------------------------- load -----
mod = imp.load_compiled(
    'streamer_mode_settings',
    os.path.join(HERE, 'build', 'streamer_mode_settings.pyc'))
print('settings module loaded')
check('has SettingsPage', hasattr(mod, 'SettingsPage'))
check('MOD_LINKAGE set', mod.MOD_LINKAGE == 'akemi.streamermode', mod.MOD_LINKAGE)

# a stand-in for the mod's Config
class FakeConfig(object):
    def __init__(self):
        self._values = {
            'enable': True, 'mode': 'label', 'namePrefix': 'Player_',
            'botMode': 'botLabel', 'botPrefix': 'Bot_', 'hideBotClanTag': True,
            'exclude.ownName': True, 'exclude.friendName': True,
            'exclude.clanmateName': True, 'exclude.divmateName': True,
            'hideClanTag': True, 'scope.inBattle': True,
            'scope.battleResults': True, 'scope.playersPanel': True,
            'scope.minimap': True, 'scope.messages': True,
            'scope.markers': True, 'scope.postmortem': True,
        }

    def flag(self, k):
        return bool(self._values.get(k, True))

    def enabled(self):
        return self.flag('enable')

    def mode(self):
        return self._values.get('mode', 'label')

    def prefix(self):
        return self._values.get('namePrefix', 'Player_')

    def botMode(self):
        return self._values.get('botMode', 'botLabel')

    def botPrefix(self):
        return self._values.get('botPrefix', 'Bot_')


cfg = FakeConfig()
page = mod.SettingsPage(cfg)
check('available() true when framework present', page.available())

ok = page.register()
check('register() returned True', ok is True)
check('setModTemplate was called once', len(calls['setModTemplate']) == 1,
      calls['setModTemplate'])

if calls['setModTemplate']:
    linkage, template, callback = calls['setModTemplate'][0]
    check('linkage is our mod id', linkage == 'akemi.streamermode', linkage)
    check('template has modDisplayName', 'modDisplayName' in template, list(template))
    check('template has settingsVersion',
          template.get('settingsVersion') == mod.SETTINGS_VERSION,
          template.get('settingsVersion'))
    check('template has both columns',
          'column1' in template and 'column2' in template)

    names = set()
    for col in ('column1', 'column2'):
        for c in template[col]:
            if 'varName' in c:
                names.add(c['varName'])
    expected = set(mod.VAR_TO_KEY.keys())
    check('every config key has a control', expected <= names,
          sorted(expected - names))
    check('no unexpected controls', names <= expected, sorted(names - expected))

    # dropdown must carry options before value (real signature)
    dd = [c for c in template['column1'] if c.get('varName') == 'mode']
    check('mode is a dropdown with options',
          dd and dd[0]['type'] == 'Dropdown' and len(dd[0]['options']) == 2,
          dd)
    check('mode defaults to index 0 (label)', dd and dd[0]['value'] == 0,
          dd and dd[0]['value'])

    inputs = [c for c in template['column1'] if c.get('varName') == 'namePrefix']
    check('namePrefix is an Input seeded from config',
          inputs and inputs[0]['type'] == 'Input'
          and inputs[0]['value'] == 'Player_', inputs)

    # --- bot controls
    bots = [c for c in template['column1'] if c.get('varName') == 'botMode']
    check('botMode is a dropdown with 4 options',
          bots and bots[0]['type'] == 'Dropdown' and len(bots[0]['options']) == 4,
          bots)
    check('botMode defaults to index 0 (own prefix)',
          bots and bots[0]['value'] == 0, bots and bots[0]['value'])
    botPrefix = [c for c in template['column1'] if c.get('varName') == 'botPrefix']
    check('botPrefix is an Input seeded from config',
          botPrefix and botPrefix[0]['value'] == 'Bot_', botPrefix)
    botClan = [c for c in template['column1'] if c.get('varName') == 'hideBotClanTag']
    check('hideBotClanTag checkbox present',
          botClan and botClan[0]['type'] == 'CheckBox', botClan)

    # seeded from config: turning a checkbox off must be reflected.
    # NOTE: with the faithful fake, re-registering the SAME template version is
    # (correctly) discarded by the framework, so inspect what our page builds
    # rather than what the API chose to keep.
    cfg2 = FakeConfig()
    cfg2._values['exclude.friendName'] = False
    tmpl2 = mod.SettingsPage(cfg2)
    mod._LANG = 'en'
    seeded = mod.buildTemplate()
    defaults2 = mod._defaultsFromConfig(cfg2)
    for col in ('column1', 'column2'):
        for control in seeded.get(col, []):
            var = control.get('varName')
            if var in defaults2:
                control['value'] = defaults2[var]
    friend = [c for c in seeded['column1'] if c.get('varName') == 'excludeFriend']
    check('checkbox seeded from JSON config (False honoured)',
          friend and friend[0]['value'] is False, friend)

# ------------------------------------------------- callback applies values --
print()
print('=== applying changes from the menu ===')
cb = calls['setModTemplate'][0][2] if calls['setModTemplate'] else None
check('callback captured', cb is not None)

# REGRESSION: Aslain Mod Menu calls the callback with only TWO arguments
# (linkage, new_settings) -- unlike izeberg ModsSettingsAPI which passes
# (linkage, settings, isFirst).  A fixed 3-arg signature raised
#   TypeError: _onChanged() takes exactly 4 arguments (3 given)
# inside the framework's _fireSettingsChanged, which is exactly the bug that
# showed up in game.log.
if cb:
    try:
        cb('akemi.streamermode', {
            'enabled': False,
            'mode': 1,                     # -> 'blank'
            'namePrefix': 'Hidden_',
            'excludeFriend': False,
            'scopeMinimap': False,
        })
        check('2-arg (Aslain) callback accepted', True)
    except TypeError as e:
        check('2-arg (Aslain) callback accepted', False, e)

check('enabled applied', cfg._values['enable'] is False, cfg._values['enable'])
check('mode index 1 -> "blank"', cfg._values['mode'] == 'blank',
      cfg._values['mode'])
check('prefix applied', cfg._values['namePrefix'] == 'Hidden_',
      cfg._values['namePrefix'])
check('checkbox off applied', cfg._values['exclude.friendName'] is False,
      cfg._values['exclude.friendName'])
check('scope off applied', cfg._values['scope.minimap'] is False,
      cfg._values['scope.minimap'])

# and it must still work with the 3-arg ModsSettingsAPI convention
if cb:
    try:
        cb('akemi.streamermode', {'mode': 0}, False)
        check('3-arg (ModsSettingsAPI) callback accepted', True)
    except TypeError as e:
        check('3-arg (ModsSettingsAPI) callback accepted', False, e)
check('mode index 0 -> "label"', cfg._values['mode'] == 'label',
      cfg._values['mode'])

# bot dropdown index -> config value
if cb:
    cb('akemi.streamermode', {'botMode': 2, 'botPrefix': 'Robot_'}, False)
check('botMode index 2 -> "keep"', cfg._values['botMode'] == 'keep',
      cfg._values['botMode'])
check('botPrefix applied', cfg._values['botPrefix'] == 'Robot_',
      cfg._values['botPrefix'])
if cb:
    cb('akemi.streamermode', {'botMode': 99}, False)
check('out-of-range botMode falls back to botLabel',
      cfg._values['botMode'] == 'botLabel', cfg._values['botMode'])

# An empty box means "not chosen", so the prefix falls back to Config.prefix()
# -- i.e. to whatever the mod considers the default for this client language
# (玩家_ on a Chinese client, Player_ elsewhere).  FakeConfig currently reports
# 'Hidden_', so that is what an emptied field must restore; hard-coding
# 'Player_' here would pin every client to one language.
cb('akemi.streamermode', {'namePrefix': '   '}, False)
check('blank prefix falls back to the config default',
      cfg._values['namePrefix'] == 'Hidden_', cfg._values['namePrefix'])

# a callback for another mod must be ignored
before = dict(cfg._values)
cb('someone.else', {'enabled': False, 'mode': 1}, False)
check('foreign linkage ignored', cfg._values == before)

# ------------------------------------------------- graceful degradation -----
print()
print('=== graceful degradation ===')
saved = aslain.g_modsSettingsApi
aslain.g_modsSettingsApi = None
import gui.aslainMenu as _am
_am.g_modsSettingsApi = None
mod2 = imp.load_compiled(
    'streamer_mode_settings_nofw',
    os.path.join(HERE, 'build', 'streamer_mode_settings.pyc'))
mod2.g_modsSettingsApi = None
page2 = mod2.SettingsPage(FakeConfig())
check('available() false without framework', page2.available() is False)
check('register() returns False, does not raise', page2.register() is False)
_am.g_modsSettingsApi = saved

print()
print('=== the framework only accepts a template whose version is HIGHER ===')
# ROOT CAUSE of "new controls never appeared": ModsSettingsAPI.compareTemplates
# short-circuits to  new['settingsVersion'] > old['settingsVersion']  (api.pyc
# L167), so a template with the SAME version is discarded and the menu keeps
# rendering the cached one -- no matter what we send.
check('settingsVersion is > 1 (was bumped for the bot controls)',
      mod.SETTINGS_VERSION > 1, mod.SETTINGS_VERSION)

# prove the framework really does reject an equal version
api = _Api()
tplV1 = {'settingsVersion': 1, 'column1': [{'varName': 'a'}]}
tplV1b = {'settingsVersion': 1, 'column1': [{'varName': 'a'},
                                            {'varName': 'botMode'}]}
check('same version => compareTemplates False (would be discarded)',
      api.compareTemplates(tplV1b, tplV1) is False)
check('higher version => compareTemplates True (accepted)',
      api.compareTemplates({'settingsVersion': 2}, tplV1) is True)

# and that our real template beats the previously cached one
mod._LANG = 'en'
realTemplate = mod.buildTemplate()
cachedOld = {'settingsVersion': 1,
             'column1': [{'varName': 'enabled'}, {'varName': 'mode'}],
             'column2': [{'varName': 'scopeBattle'}]}
check('our template outranks the previously cached one',
      api.compareTemplates(realTemplate, cachedOld) is True,
      (mod.SETTINGS_VERSION, cachedOld.get('settingsVersion')))

# simulate the real-world sequence: framework already cached v1 without bots
_Api._savedNext = None
_Api._state = {'templates': {'akemi.streamermode': cachedOld},
               'settings': {'akemi.streamermode': {'enabled': True}}}
calls['setModTemplate'] = []
upgradePage = mod.SettingsPage(FakeConfig())
upgradePage.register()
check('upgrade path re-sends the template',
      len(calls['setModTemplate']) == 1, len(calls['setModTemplate']))
if calls['setModTemplate']:
    sentTpl = calls['setModTemplate'][0][1]
    sentVars = set()
    for col in ('column1', 'column2'):
        for c in sentTpl.get(col, []):
            if c.get('varName'):
                sentVars.add(c['varName'])
    check('bot controls survive the upgrade',
          'botMode' in sentVars and 'botPrefix' in sentVars, sorted(sentVars))
    check('cached template was replaced',
          _Api._state['templates']['akemi.streamermode'] is sentTpl)
    # the settings the framework hands back must include the bot controls
    handedBack = _Api._state['settings']['akemi.streamermode']
    check('framework settings now include botMode',
          'botMode' in handedBack, sorted(handedBack))
_Api._state = {'templates': {}, 'settings': {}}

print()
print('=== stale saved settings trigger a re-registration ===')
# REGRESSION: after the bot controls were added, a client with previously saved
# settings kept showing the OLD page. getModSettings() returns the saved dict
# (no botMode/botPrefix), the code took the "already registered" path and never
# re-sent the template -- so the new fields never appeared in the menu.
calls['setModTemplate'] = []
_Api._savedNext = {'enabled': True, 'mode': 0, 'namePrefix': 'Player_',
                   'excludeSelf': True, 'excludeFriend': True,
                   'excludeClanmate': True, 'excludeSquad': True,
                   'hideClanTag': True, 'scopeBattle': True,
                   'scopeResults': True, 'scopePanel': True,
                   'scopeMinimap': True, 'scopeMessages': True,
                   'scopeMarkers': True, 'scopePostmortem': True}
stalePage = mod.SettingsPage(FakeConfig())
stalePage.register()
check('stale template re-sent to the API',
      len(calls['setModTemplate']) == 1, len(calls['setModTemplate']))
if calls['setModTemplate']:
    sent = calls['setModTemplate'][0][1]
    sentVars = set()
    for col in ('column1', 'column2'):
        for c in sent.get(col, []):
            if c.get('varName'):
                sentVars.add(c['varName'])
    check('re-sent template carries the bot controls',
          'botMode' in sentVars and 'botPrefix' in sentVars, sorted(sentVars))
_Api._savedNext = None

print()
print('=== up-to-date saved settings do NOT re-register ===')
calls['setModTemplate'] = []
calls['registerCallback'] = []
fresh_saved = {'enabled': True, 'mode': 0, 'namePrefix': 'Player_',
               'botMode': 0, 'botPrefix': 'Bot_', 'hideBotClanTag': True,
               'excludeSelf': True, 'excludeFriend': True,
               'excludeClanmate': True, 'excludeSquad': True,
               'hideClanTag': True, 'hideResultsClanTag': True,
               'hideBadges': True, 'hideBotBadges': True,
               'badgesExemptKnown': True,
               'showRealNamesInProfile': True,
               'scopeBattle': True, 'scopeResults': True,
               'scopePanel': True, 'scopeMinimap': True, 'scopeMessages': True,
               'scopeMarkers': True, 'scopePostmortem': True}
_Api._savedNext = fresh_saved
currentPage = mod.SettingsPage(FakeConfig())
currentPage.register()
check('no re-registration when template matches',
      len(calls['setModTemplate']) == 0, len(calls['setModTemplate']))
check('callback attached instead',
      len(calls['registerCallback']) == 1, calls['registerCallback'])
_Api._savedNext = None

print()
print('=== logging actually reaches the engine ===')
# REGRESSION: the mod originally called BigWorld.logInfo(tag, msg) with two
# arguments.  The engine wants (tag, msg, None); the resulting TypeError was
# swallowed by the mod's own except, so nothing ever appeared in game.log and
# the mod looked silently broken.
check('registration produced log output', len(LOG_RECORDS) > 0, LOG_RECORDS)
check('no log call raised (all reached the engine)',
      all(len(r) >= 3 for r in LOG_RECORDS), LOG_RECORDS)
joined = ' '.join(str(r[-2]) for r in LOG_RECORDS)
check('log mentions settings page registered',
      'settings page registered' in joined, joined[:200])

print()
print('=' * 62)
print('PASS %d   FAIL %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   -', f)
sys.exit(1 if FAIL else 0)