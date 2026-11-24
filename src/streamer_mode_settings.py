# -*- coding: utf-8 -*-
"""In-game settings page for Streamer Mode (Aslain Mod Menu / ModsSettingsAPI).

Verified integration contract, taken from the clientside mods that already
provide a settings page (izeberg.spotted, gravity.effect_control):

    from gui.aslainMenu import g_modsSettingsApi, templates

    g_modsSettingsApi.setModTemplate(linkage, template, callback)
        linkage  : a unique string id for this mod
        template : {"modDisplayName": ..., "settingsVersion": N,
                    "column1": [ controls... ], "column2": [...]}
        callback : fn(linkage, settings, isFirst)

Each control is a dict with "type", "text", "varName", "value" and optionally
"tooltip"; `templates` provides helpers for building them.

Everything here is optional: if the framework is not installed we keep the
JSON config and say so, rather than failing.
"""

import traceback

import BigWorld

# ModsSettingsAPI + Aslain menu, imported defensively: the mod must still work
# with only the JSON config present.
try:
    from gui.aslainMenu import g_modsSettingsApi, templates
except Exception:
    try:
        from gui.modsSettingsApi import g_modsSettingsApi, templates
    except Exception:
        g_modsSettingsApi = None
        templates = None

MOD_LINKAGE = 'akemi.streamermode'

# MUST be bumped whenever the template changes (controls added/removed/renamed).
#
# The framework's ModsSettingsApi.setModTemplate() only replaces its cached
# template when
#
#     compareTemplates(new, cached)  ->  new['settingsVersion'] > cached[...]
#     (api.pyc L167; falls back to a JSON diff only when the key is absent)
#
# so leaving this at 1 meant every update was silently DISCARDED and the menu
# kept rendering the first template it ever saw.  Bump it and the new page is
# picked up on the next launch.
SETTINGS_VERSION = 8
SETTINGS_KEY = 'settingsVersion'

# Maps a settings-page variable name <-> our config key.
VAR_TO_KEY = {
    'enabled': 'enable',
    'mode': 'mode',
    'allyPrefix': 'allyPrefix',
    'enemyPrefix': 'enemyPrefix',
    'botMode': 'botMode',
    'botPrefix': 'botPrefix',
    'hideBotClanTag': 'hideBotClanTag',
    'excludeSelf': 'exclude.ownName',
    'excludeFriend': 'exclude.friendName',
    'excludeClanmate': 'exclude.clanmateName',
    'excludeSquad': 'exclude.divmateName',
    'hideClanTag': 'hideClanTag',
    'hideResultsClanTag': 'hideResultsClanTag',
    'hideBadges': 'hideBadges',
    'hideBotBadges': 'hideBotBadges',
    'badgesExemptKnown': 'badges.exemptKnown',
    'scopeBattle': 'scope.inBattle',
    'scopeResults': 'scope.battleResults',
    'scopePanel': 'scope.playersPanel',
    'scopeTab': 'scope.tabPanel',
    'scopeMinimap': 'scope.minimap',
    'scopeMessages': 'scope.messages',
    'scopeMarkers': 'scope.markers',
    'scopePostmortem': 'scope.postmortem',
    # NOTE: mapped so the page can persist it, but it is a deliberate
    # "de-anonymise" option -- see showRealNameInProfile in the mod.
    'showRealNamesInProfile': 'showRealNamesInProfile',
}

# Variables from an older template that no longer have a control.  Applying
# them lets a player who set a prefix in the menu before 1.0.4 keep it as the
# legacy fallback for both teams.
LEGACY_VAR_TO_KEY = {
    'namePrefix': 'namePrefix',
}

MODE_OPTIONS = ['Ally_001 / Enemy_001 (label)', 'Hide entirely']

# Dropdown order must match BOT_MODES in the mod.
BOT_MODE_OPTIONS = ['Bot_001 (own prefix)',
                    'Same as players (Player_001)',
                    'Keep the game\'s bot name',
                    'Hide entirely']
BOT_MODE_VALUES = ('botLabel', 'label', 'keep', 'blank')
VAR_TO_KEY_BOT_MODE = 'botMode'

# Text tables. The framework reads labels from the template itself, so we do not
# need a language file; we pick the closest match to the client language.
TEXTS = {
    'en': {
        'modName': 'Streamer Mode',
        'sectionGeneral': 'General',
        'enabled': 'Enable Streamer Mode',
        'enabledTip': 'Anonymise other players\' nicknames in battle.',
        'mode': 'How to hide a nickname',
        'modeTip': 'Replace it with Ally_001 / Enemy_001, or hide it entirely.',
        'allyPrefix': 'Ally name prefix',
        'allyPrefixTip': 'Prefix for anonymised players on YOUR team, e.g. '
                         'Ally_001. Leave blank to use the default.',
        'enemyPrefix': 'Enemy name prefix',
        'enemyPrefixTip': 'Prefix for anonymised players on the ENEMY team, '
                          'e.g. Enemy_001. Leave blank to use the default.',
        'sectionBots': 'Bots',
        'botMode': 'How to show bots',
        'botModeTip': 'Bots use their own counter, separate from players.',
        'botPrefix': 'Bot name prefix',
        'botPrefixTip': 'Prefix for bots ONLY, e.g. Bot_001. Separate from the '
                        'player prefix above; try 机器人_ for Chinese.',
        'hideBotClanTag': 'Hide bot clan tags',
        'sectionExclude': 'Keep real names for',
        'excludeSelf': 'Yourself',
        'excludeFriend': 'Friends',
        'excludeClanmate': 'Clanmates',
        'excludeSquad': 'Platoon mates',
        'hideClanTag': 'Also hide clan tags',
        'hideClanTagTip': 'Hide the [TAG] shown next to a stranger\'s name.',
        'hideResultsClanTag': 'Hide clan tags on the results screen',
        'hideResultsClanTagTip': 'The results screen shows clan tags taken '
                                 'straight from the player record, so it needs '
                                 'its own switch.',
        'sectionBadges': 'Badges (medals)',
        'hideBadges': 'Hide badges next to nicknames',
        'hideBadgesTip': 'A rare medal identifies a player as well as the name '
                         'does, so this is on by default.',
        'hideBotBadges': 'Also hide bot badges',
        'badgesExemptKnown': 'Keep badges for you / friends / clan / platoon',
        'badgesExemptKnownTip': 'Same rule as nicknames, so the HUD stays '
                                'consistent about people you know.',
        'sectionProfile': 'Player details window',
        'showRealNamesInProfile': 'Show real names in the player profile',
        'showRealNamesInProfileTip': 'When you open ONE player\'s details, show '
                                     'their real name and clan. Useful for '
                                     'looking someone up; leave off to keep even '
                                     'that window masked.',
        'sectionScope': 'Screens to anonymise',
        'scopeBattle': 'Battle HUD',
        'scopeResults': 'Post-battle results',
        'scopePanel': 'Players panel (loading + side panels)',
        'scopeTab': 'TAB full-stats board',
        'scopeMinimap': 'Minimap',
        'scopeMessages': 'Kill / event messages',
        'scopeMarkers': 'Vehicle markers',
        'scopePostmortem': 'Death-cam panel',
        'note': 'Scope changes apply to the next battle.',
    },
    'zh': {
        'modName': '主播模式',
        'sectionGeneral': '常规',
        'enabled': '启用主播模式',
        'enabledTip': '在战斗中匿名化其他玩家的昵称。',
        'mode': '昵称隐藏方式',
        'modeTip': '替换为 友军_001 / 敌军_001,或完全隐藏。',
        'allyPrefix': '友军名称前缀',
        'allyPrefixTip': '匿名化【友军】真人玩家的前缀,例如 友军_001。留空则使用默认值。',
        'enemyPrefix': '敌军名称前缀',
        'enemyPrefixTip': '匿名化【敌军】真人玩家的前缀,例如 敌军_001。留空则使用默认值。',
        'sectionBots': '官方机器人(BOT)',
        'botMode': '机器人昵称显示方式',
        'botModeTip': '机器人使用独立编号,与玩家分开计数。',
        'botPrefix': '机器人名称前缀',
        'botPrefixTip': '仅用于【官方机器人】的前缀,例如 Bot_001。与上面的玩家前缀相互独立,可填 机器人_ 。',
        'hideBotClanTag': '同时隐藏机器人军团标签',
        'sectionExclude': '以下对象保留真实昵称',
        'excludeSelf': '自己',
        'excludeFriend': '好友',
        'excludeClanmate': '军团战友',
        'excludeSquad': '组队队友',
        'hideClanTag': '同时隐藏军团标签',
        'hideClanTagTip': '隐藏陌生人名字前的 [标签]。',
        'hideResultsClanTag': '结算界面同时隐藏军团标签',
        'hideResultsClanTagTip': '结算界面是直接从玩家记录里取军团的,所以需要单独的开关。',
        'sectionBadges': '奖章(勋章)',
        'hideBadges': '隐藏昵称旁边的奖章',
        'hideBadgesTip': '稀有奖章的辨识度不亚于昵称,所以默认开启隐藏。',
        'hideBotBadges': '同时隐藏机器人奖章',
        'badgesExemptKnown': '自己/好友/军团/组队 保留奖章',
        'badgesExemptKnownTip': '与昵称规则保持一致,认识的玩家不做处理。',
        'sectionProfile': '玩家资料窗口',
        'showRealNamesInProfile': '查看单个玩家资料时显示真实昵称',
        'showRealNamesInProfileTip': '当你主动打开【某一个】玩家的资料页时,显示他的真实昵称和军团。'
                                     '便于查证/举报;如果希望连这个窗口也隐藏,请关闭。',
        'sectionScope': '生效界面',
        'scopeBattle': '战斗内界面',
        'scopeResults': '战后结算',
        'scopePanel': '玩家面板(载入+两侧)',
        'scopeTab': 'TAB 战绩面板',
        'scopeMinimap': '小地图',
        'scopeMessages': '击杀/事件提示',
        'scopeMarkers': '战车标记',
        'scopePostmortem': '阵亡回放面板',
        'note': '界面开关将在下一场战斗生效。',
    },
}

_LANG = 'en'


def _logInfo(msg):
    """BigWorld logging takes (tag, message, None) -- see mod_streamer_mode."""
    text = '[StreamerMode] ' + unicode(msg)
    try:
        BigWorld.logInfo(MOD_LINKAGE, text, None)
    except TypeError:
        try:
            BigWorld.logInfo(MOD_LINKAGE, text)
        except Exception:
            pass
    except Exception:
        pass


def _logError(msg):
    text = '[StreamerMode] ' + unicode(msg)
    try:
        BigWorld.logError(MOD_LINKAGE, text, None)
    except TypeError:
        try:
            BigWorld.logError(MOD_LINKAGE, text)
        except Exception:
            pass
    except Exception:
        pass


def _detectLanguage():
    """Best-effort match of the client UI language to our text table."""
    try:
        from helpers import getClientLanguage
        lang = (getClientLanguage() or 'en').lower()
        if lang.startswith('zh'):
            return 'zh'
    except Exception:
        pass
    return 'en'


def _t(key):
    return TEXTS.get(_LANG, TEXTS['en']).get(key, key)


def _defaultNamePrefix(config):
    """The player-prefix default, following the client language.

    Ask the mod's Config when we have one (it owns the localisation rule), and
    fall back to a local copy of the same rule so this module still works when
    the Config is not reachable (e.g. building the template in a test).
    """
    if config is not None:
        try:
            return config.prefix()
        except Exception:
            pass
    try:
        from helpers import getClientLanguage
        lang = (getClientLanguage() or '').lower()
        if lang == 'zh' or lang.startswith('zh_') or lang.startswith('zh-'):
            return u'玩家_'
    except Exception:
        pass
    return 'Player_'


def _defaultTeamPrefix(isAlly):
    """The ally/enemy prefix default, following the client language."""
    try:
        from helpers import getClientLanguage
        lang = (getClientLanguage() or '').lower()
        if lang == 'zh' or lang.startswith('zh_') or lang.startswith('zh-'):
            return u'友军_' if isAlly else u'敌军_'
    except Exception:
        pass
    return 'Ally_' if isAlly else 'Enemy_'


def buildTemplate():
    """The settings page shown in the Aslain Mod Menu."""
    try:
        return {
            'modDisplayName': _t('modName'),
            SETTINGS_KEY: SETTINGS_VERSION,
            'column1': [
                templates.createLabel(_t('sectionGeneral')),
                templates.createCheckbox(
                    _t('enabled'), 'enabled', True, _t('enabledTip')),
                templates.createDropdown(
                    _t('mode'), 'mode', MODE_OPTIONS, 0, _t('modeTip')),
                templates.createInput(
                    _t('allyPrefix'), 'allyPrefix',
                    _defaultTeamPrefix(True), _t('allyPrefixTip')),
                templates.createInput(
                    _t('enemyPrefix'), 'enemyPrefix',
                    _defaultTeamPrefix(False), _t('enemyPrefixTip')),

                templates.createEmpty(10),
                templates.createLabel(_t('sectionBots')),
                templates.createDropdown(
                    _t('botMode'), 'botMode', BOT_MODE_OPTIONS, 0,
                    _t('botModeTip')),
                templates.createInput(
                    _t('botPrefix'), 'botPrefix', 'Bot_',
                    _t('botPrefixTip')),
                templates.createCheckbox(
                    _t('hideBotClanTag'), 'hideBotClanTag', True),

                templates.createEmpty(10),
                templates.createLabel(_t('sectionExclude')),
                templates.createCheckbox(_t('excludeSelf'), 'excludeSelf', True),
                templates.createCheckbox(_t('excludeFriend'), 'excludeFriend', True),
                templates.createCheckbox(_t('excludeClanmate'), 'excludeClanmate', True),
                templates.createCheckbox(_t('excludeSquad'), 'excludeSquad', True),
                templates.createCheckbox(
                    _t('hideClanTag'), 'hideClanTag', True, _t('hideClanTagTip')),
                templates.createCheckbox(
                    _t('hideResultsClanTag'), 'hideResultsClanTag', True,
                    _t('hideResultsClanTagTip')),

                templates.createEmpty(10),
                templates.createLabel(_t('sectionBadges')),
                templates.createCheckbox(
                    _t('hideBadges'), 'hideBadges', True, _t('hideBadgesTip')),
                templates.createCheckbox(
                    _t('hideBotBadges'), 'hideBotBadges', True),
                templates.createCheckbox(
                    _t('badgesExemptKnown'), 'badgesExemptKnown', True,
                    _t('badgesExemptKnownTip')),

                templates.createEmpty(10),
                templates.createLabel(_t('sectionProfile')),
                templates.createCheckbox(
                    _t('showRealNamesInProfile'), 'showRealNamesInProfile',
                    True, _t('showRealNamesInProfileTip')),
            ],
            'column2': [
                templates.createLabel(_t('sectionScope')),
                templates.createCheckbox(_t('scopeBattle'), 'scopeBattle', True),
                templates.createCheckbox(_t('scopeResults'), 'scopeResults', True),
                templates.createCheckbox(_t('scopePanel'), 'scopePanel', True),
                templates.createCheckbox(_t('scopeTab'), 'scopeTab', True),
                templates.createCheckbox(_t('scopeMinimap'), 'scopeMinimap', True),
                templates.createCheckbox(_t('scopeMessages'), 'scopeMessages', True),
                templates.createCheckbox(_t('scopeMarkers'), 'scopeMarkers', True),
                templates.createCheckbox(_t('scopePostmortem'), 'scopePostmortem', True),
                templates.createEmpty(10),
                templates.createLabel(_t('note')),
            ],
        }
    except Exception:
        _logError('could not build settings template: %s' % traceback.format_exc())
        return None


def _defaultsFromConfig(config):
    """Seed the page from the JSON config so the two agree on first open.

    Every accessor is guarded: a partially initialised Config must not stop the
    settings page from opening.
    """
    def safe(fn, fallback=None):
        try:
            return fn()
        except Exception:
            return fallback

    def flag(key, fallback=True):
        value = safe(lambda: config.flag(key), None)
        return fallback if value is None else bool(value)

    def botModeIndex():
        mode = safe(lambda: config.botMode(), 'botLabel')
        try:
            return BOT_MODE_VALUES.index(mode)
        except ValueError:
            return 0

    return {
        'enabled': bool(safe(lambda: config.enabled(), True)),
        'mode': 0 if safe(lambda: config.mode(), 'label') == 'label' else 1,
        'allyPrefix': safe(lambda: config.allyPrefix(), 'Ally_') or 'Ally_',
        'enemyPrefix': safe(lambda: config.enemyPrefix(), 'Enemy_') or 'Enemy_',
        'botMode': botModeIndex(),
        'botPrefix': safe(lambda: config.botPrefix(), 'Bot_') or 'Bot_',
        'hideBotClanTag': flag('hideBotClanTag'),
        'excludeSelf': flag('exclude.ownName'),
        'excludeFriend': flag('exclude.friendName'),
        'excludeClanmate': flag('exclude.clanmateName'),
        'excludeSquad': flag('exclude.divmateName'),
        'hideClanTag': flag('hideClanTag'),
        'hideResultsClanTag': flag('hideResultsClanTag'),
        'hideBadges': flag('hideBadges'),
        'hideBotBadges': flag('hideBotBadges'),
        'badgesExemptKnown': flag('badges.exemptKnown'),
        'showRealNamesInProfile': flag('showRealNamesInProfile'),
        'scopeBattle': flag('scope.inBattle'),
        'scopeResults': flag('scope.battleResults'),
        'scopePanel': flag('scope.playersPanel'),
        'scopeTab': flag('scope.tabPanel'),
        'scopeMinimap': flag('scope.minimap'),
        'scopeMessages': flag('scope.messages'),
        'scopeMarkers': flag('scope.markers'),
        'scopePostmortem': flag('scope.postmortem'),
    }


class SettingsPage(object):
    """Registers the page and pushes changes back into the live config."""

    def __init__(self, config):
        self._config = config
        self._registered = False
        self._applied = False

    def available(self):
        return g_modsSettingsApi is not None and templates is not None

    def register(self):
        if self._registered:
            return True
        if not self.available():
            _logInfo('ModsSettingsAPI not installed; using JSON config only')
            return False
        try:
            global _LANG
            _LANG = _detectLanguage()

            template = buildTemplate()
            if template is None:
                return False

            # Seed defaults so the toggles reflect the JSON config on first run.
            defaults = _defaultsFromConfig(self._config)
            for column in ('column1', 'column2'):
                for control in template.get(column, []):
                    var = control.get('varName')
                    if var in defaults:
                        control['value'] = defaults[var]

            setter = getattr(g_modsSettingsApi, 'setModTemplate', None)
            if setter is None:
                _logInfo('setModTemplate not exposed by this API version')
                return False

            saved = None
            getter = getattr(g_modsSettingsApi, 'getModSettings', None)
            if getter is not None:
                try:
                    saved = getter(MOD_LINKAGE, template)
                except Exception:
                    saved = None

            # A saved page may predate the current template in two ways:
            #   * new controls appeared        (variable added)
            #   * existing controls were RENAMED (same varName, new label)
            # The framework reuses the template it stored, so a rename is
            # invisible unless we force a re-registration -- which is why the
            # renamed "Players panel (Tab)" kept showing its old text.
            #
            # SETTINGS_VERSION is stamped into the template and echoed back in
            # `saved`, so bumping it is the reliable trigger.  The variable-set
            # check stays as a second net for an old saved page that has no
            # version stamp at all.
            templateVars = set()
            for column in ('column1', 'column2'):
                for control in template.get(column, []):
                    var = control.get('varName')
                    if var:
                        templateVars.add(var)

            savedVars = set(saved.keys()) if isinstance(saved, dict) else set()
            added = templateVars - savedVars
            savedVersion = None
            if isinstance(saved, dict):
                savedVersion = saved.get(SETTINGS_KEY)
            versionChanged = bool(savedVersion is not None
                                  and savedVersion != SETTINGS_VERSION)

            stale = bool(saved is not None and (added or versionChanged))

            if saved is not None and not stale:
                # already registered once: just attach our callback
                g_modsSettingsApi.registerCallback(MOD_LINKAGE, self._onChanged)
                settings = saved
            else:
                if added:
                    _logInfo('settings template gained controls: %s'
                             % ', '.join(sorted(added)))
                if versionChanged:
                    _logInfo('settings template version %s -> %s, re-registering'
                             % (savedVersion, SETTINGS_VERSION))
                settings = setter(MOD_LINKAGE, template, self._onChanged)

            # apply the starting values ourselves; mark it as the initial load
            self._applied = False
            self._onChanged(MOD_LINKAGE, settings or {}, True)
            self._registered = True
            _logInfo('settings page registered in the mod menu')
            return True
        except Exception:
            _logError('could not register settings page: %s'
                      % traceback.format_exc())
            return False

    def _onChanged(self, linkage, settings, *extra):
        """Settings-changed callback.

        The two settings frameworks do NOT agree on the arity:

          * izeberg ModsSettingsAPI  -> callback(linkage, settings, isFirst)
          * Aslain Mod Menu api      -> callback(linkage, new_settings)   (2)

        Verified by reading both: gravity.effect_control (works with Aslain's
        menu) defines `_on_settings_changed(linkage, new_settings)`, while
        izeberg.spotted defines `onSettingsUpdated(self, settings, isFirst)`.
        Using a fixed 3-arg signature raises
        "TypeError: _onChanged() takes exactly 4 arguments (3 given)" inside
        the framework's _fireSettingsChanged, so accept *extra and treat the
        first call as the initial load.
        """
        if linkage != MOD_LINKAGE:
            return
        try:
            isFirst = False
            if extra:
                isFirst = bool(extra[0])
            else:
                isFirst = not self._applied
            self._apply(settings)
            self._applied = True
            if isFirst:
                _logInfo('settings loaded from menu: enabled=%s mode=%s'
                         % (settings.get('enabled'), settings.get('mode')))
        except Exception:
            _logError('applying menu settings failed: %s' % traceback.format_exc())

    def _apply(self, settings):
        if not isinstance(settings, dict):
            return
        for var, key in list(VAR_TO_KEY.items()) + list(LEGACY_VAR_TO_KEY.items()):
            if var not in settings:
                continue
            value = settings[var]
            if var == 'mode':
                # dropdown index -> 'label' | 'blank'
                try:
                    value = 'label' if int(value) == 0 else 'blank'
                except Exception:
                    value = 'label'
            elif var == 'botMode':
                # dropdown index -> BOT_MODE_VALUES
                try:
                    value = BOT_MODE_VALUES[int(value)]
                except Exception:
                    value = 'botLabel'
            elif var == 'namePrefix':
                if not isinstance(value, basestring) or not value.strip():
                    # Empty box: fall back to the language-appropriate default,
                    # so clearing the field on a Chinese client yields 玩家_.
                    value = _defaultNamePrefix(self._config)
                value = value.strip()
            elif var in ('allyPrefix', 'enemyPrefix'):
                # Empty means "use the team default"; keep it empty instead of
                # pinning a concrete language-dependent string.
                if not isinstance(value, basestring) or not value.strip():
                    value = ''
                value = value.strip()
            elif var == 'botPrefix':
                if not isinstance(value, basestring) or not value.strip():
                    value = 'Bot_'
                value = value.strip()
            elif isinstance(value, bool):
                pass
            self._config._values[key] = value
