> Language: **English** | [简体中文](README.md)

# Streamer Mode for World of Tanks 2.4.1

Anonymises **other players' nicknames in battle** so a stream does not broadcast
them. Friends, clanmates, platoon mates and yourself keep their real names.

This is a port of the idea behind
[AndrewTaro/StreamerMode](https://github.com/AndrewTaro/StreamerMode) for World of
Warships. WoT had no equivalent mod: Wargaming's own *Anonymizer* works the other
way round (it hides **your own** name, server-side, for everyone else), and the
WoT mod scene mostly built the inverse — tools that *reveal* names. This is the
first mod that hides everyone else's names on your own screen.

## What it does

In battle, every stranger's nickname becomes a stable per-battle label:

```
    Player_001   [ENEMY] (T-34-85)
    Player_002   [FOE]   (IS-3)
    Bot_001              (T-54)             <- official bot, own prefix
    MyRealName   [CLAN]  (Object 277)       <- you
    BuddyName    [ALLY]  (Bat.-Châtillon)   <- friend
```

The same stranger keeps the same number everywhere — players panel, minimap,
damage log, kill messages, 3D markers, postmortem panel, TAB full-stats — so the
layout still reads naturally.

You can also set `"mode": "blank"` to show nothing at all instead of a label.

### Official bots

The colon-wrapped names in the client (e.g. `:Ivan Petrov:`) are bots. That is
not a guess — the format is defined in `helpers/bots.pyc`:

```python
_NAME_FORMAT_CREW = ':{0} {1}:'        # bots.pyc L12
```

and the name is built in C++ (`ClientArena` → `preprocessBotName`) before any
Python display code runs.

Bots are not a privacy concern, but they are easy to mistake for players, so
they get their own prefix and their own counter by default:

| `botMode` | result |
|---|---|
| `botLabel` (default) | `Bot_001`, `Bot_002`, … counted separately from players |
| `label` | share the player numbering (`Player_001`) |
| `keep` | leave the game's own bot name |
| `blank` | hide it |

The prefix is independent of the player prefix: set `botPrefix` to `机器人_` for
`机器人_001`.

### The prefix follows the client language

The default prefix tracks the client UI language: `玩家_001` on a Chinese client,
`Player_001` elsewhere. Once you set a prefix yourself in the config file or the
in-game menu, your value always wins.

## Install

Copy **`build/akemi.streamermode_1.0.wotmod`** to:

```
<game>/mods/<client version>/
```

That is all. Nothing in `res_mods` is touched, so a game update that changes
scripts cannot leave a stale override behind.

> The folder under `mods/` must match the client's current version (see
> `res/version.xml`). The game will not load a package from a mismatched folder.

## In-game settings menu

The mod registers a settings page with **Aslain Mod Menu / ModsSettingsAPI**, so
you can change everything in game instead of editing files.

Optional dependency: [ModsSettingsAPI](https://wgmods.net/2340/)
(`izeberg.modssettingsapi`). Without that framework the mod still works — you
just get the JSON config below instead of the GUI.

The menu provides (labels follow the client language):

| Group | Items |
|---|---|
| General | master switch, how to hide a nickname (label/blank), player prefix |
| Bots | how to show bots, bot prefix, hide bot clan tags |
| Keep real names for | yourself, friends, clanmates, platoon mates, also hide clan tags, also hide clan tags on the results screen |
| Badges (medals) | hide badges next to nicknames, also hide bot badges, keep badges for people you know |
| Player details window | show real names in the profile window |
| Screens to anonymise | battle HUD, post-battle results, players panel (Tab), minimap, kill/event messages, vehicle markers, death-cam panel |

> Scope changes apply to the **next battle** — the name list for the current
> battle is already built.

## Configuration

Optionally copy `config.default.json` to
`<game>/mods/configs/akemi.streamermode/config.json` and edit it:

| key | default | meaning |
|---|---|---|
| `enable` | `true` | master switch |
| `mode` | `"label"` | `"label"` → `Player_001`; `"blank"` → hide entirely |
| `namePrefix` | `""` | player prefix. **Empty** = follow the client language (`玩家_` on zh, `Player_` elsewhere); a value overrides it |
| `botMode` | `"botLabel"` | bots: `"botLabel"` / `"label"` / `"keep"` / `"blank"` |
| `botPrefix` | `"Bot_"` | bot prefix (e.g. `机器人_`) |
| `hideBotClanTag` | `true` | hide bot clan tags |
| `exclude.ownName` | `true` | keep your own name |
| `exclude.friendName` | `true` | keep friends' names |
| `exclude.clanmateName` | `true` | keep clanmates' names |
| `exclude.divmateName` | `true` | keep platoon mates' names |
| `hideClanTag` | `true` | also hide strangers' clan tags |
| `hideResultsClanTag` | `true` | also hide clan tags on the results screen (it reads the tag directly, so it needs its own switch) |
| `hideBadges` | `true` | hide badges next to nicknames |
| `hideBotBadges` | `true` | also hide bot badges |
| `badges.exemptKnown` | `true` | keep badges for self/friends/clan/platoon |
| `showRealNamesInProfile` | `true` | show real names in the single-player profile window (set `false` to keep it masked too) |
| `scope.inBattle` | `true` | battle HUD |
| `scope.battleResults` | `true` | post-battle results |
| `scope.playersPanel` | `true` | players panel (Tab) |
| `scope.minimap` | `true` | minimap |
| `scope.messages` | `true` | kill / event messages |
| `scope.markers` | `true` | vehicle markers |
| `scope.postmortem` | `true` | death-cam panel |

An unreadable or malformed config is ignored and the **anonymising** defaults
are kept. That is deliberate: a privacy tool must not fail open.

The in-game menu and the JSON file are the same config — menu changes are written
back immediately.

## How it works

All battle nicknames funnel through a small number of display functions in the
client's `arena_info` package. The mod wraps them:

| wrapped | why |
|---|---|
| `PlayerInfoVO.getPlayerLabel` | the base nickname every panel reads |
| `PlayerInfoVO.getPlayerFakeLabel` | locally generated labels (bots keep theirs) |
| `VehicleArenaInfoVO.getDisplayedName` | nickname for floating text |
| `PlayerFullNameFormatter.format` | the composite `name [tag] (tank)` string |
| `battle_results.PlayerInfo.realName` | post-battle scoreboard (a `property`) |

Stored data is never modified — only what these functions *return*. So nothing
downstream can be corrupted, and `fini()` restores the originals exactly.

## Building and testing

The client runs CPython 2.7 bytecode, so **the mod must be compiled with 2.7** —
a 3.x compile produces `.pyc` files the game cannot load. The build scripts look
for 2.7 automatically (via `py -2.7`); set `WOT_PY27` to a `python.exe` path if
you need to point at a specific interpreter.

```powershell
python build.py          # compile with Python 2.7 + package the .wotmod
py -2.7 test_mod.py          # behaviour (19 checks)
py -2.7 test_real_client.py  # against the REAL client classes (13)
py -2.7 test_loader.py       # client mod-loader simulation (9)
py -2.7 test_package.py      # package is loadable by the game (8)
py -2.7 test_settings.py     # settings menu integration (51)
py -2.7 test_tab_panel.py    # TAB panel + clan tags (18)
py -2.7 test_identity.py     # identity detection, self never masked (13)
py -2.7 test_bots.py         # official bot prefix (18)
py -2.7 test_bot_numbering.py   # each bot gets a distinct stable number (12)
py -2.7 test_tab_bot_numbers.py # TAB and panel numbers agree (13)
py -2.7 test_results_numbers.py # results numbers match the battle (17)
py -2.7 test_profile_clan.py # results clan hiding + profile switch (18)
py -2.7 test_badges.py       # badge hiding (27)
py -2.7 test_team_badges.py  # team-stats badge hiding (17)
py -2.7 test_results.py      # results: bots vs players (25)
py -2.7 test_prefix_language.py # prefix follows the client language (18)
```

`test_real_client.py`, `test_package.py` and `refresh_fixtures.py` read client
files. Point `WOT_GAME` at your install before running them:

```powershell
set WOT_GAME=D:\Games\World_of_Tanks_XX
```

See [DEVELOPMENT.en.md](DEVELOPMENT.en.md) for the full development guide
(architecture, pitfalls, in-game verification).

## Compatibility

Built and verified against **v.2.4.1.0 #975 (CN client)**.

The hook targets are core battle-UI functions that have been stable for many
versions, but a client update can rename them. When that happens the mod logs a
clear error and disables the affected hook rather than breaking the HUD. Search
`game.log` for `[StreamerMode]`.

The mod is written to be un-hooked cleanly and to refuse to overwrite a function
another mod already replaced.

## Limitations

* Only affects **your own client**. Other players still see real names unless
  they too use Wargaming's anonymizer.
* Battles are the focus; hangar, clan and chat windows are untouched.
* Replay playback uses the same battle path, so names are anonymised there too.
* The post-battle scoreboard only anonymises names it can attribute to a DBID;
  it deliberately leaves alone any player the game's own anonymizer already
  renamed.
* The settings menu needs ModsSettingsAPI; without it everything still works but
  there is no GUI.

## Troubleshooting

After launching, look for these lines in `game.log`:

```
[StreamerMode] init (WoT 2.4.1, enabled=True, mode=label)
[StreamerMode] installed with N hook(s)
[StreamerMode] settings page registered in the mod menu
[StreamerMode] identity: self=<DBID> clan=... friends=<N> squadmates=<N>
```

Notes:

* `Mod package '...' load error: compression not supported` → the package is
  compressed; rebuild it with `build.py`.
* `settings page registered` missing → ModsSettingsAPI is not installed (the mod
  still works).
* `identity ... friends=0` → the friend list could not be read, so friends get
  anonymised too. This fails in the **safe** direction (hide more); if it matters
  to you, send that log line.
* `installed with N hook(s)` where N is well below the expected count → some hook
  did not install, which usually means the client renamed it.

## Credits

The idea comes from [AndrewTaro/StreamerMode](https://github.com/AndrewTaro/StreamerMode),
a World of Warships mod that hides other players' names in battle. This project
applies the same idea to World of Tanks, where the client exposes no single
network hook — the implementation here is written from scratch against the WoT
client and shares no code with it.

Thanks also to the modding resources that document the `.wotmod` format and the
client's Python environment.

## License

[MIT](LICENSE) © 2026 akemi
