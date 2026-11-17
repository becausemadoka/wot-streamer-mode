> Language: **English** | [简体中文](DEVELOPMENT.md)

# Development notes

How to change, build, test and ship Streamer Mode for World of Tanks.

- Language: **CPython 2.7** (the client embeds 2.7; bytecode magic `03f30d0a`)
- Deliverable: `.wotmod` — a **ZIP archive whose entries are all STORED**
  (the client loader rejects deflate with `compression not supported`)
- Approach: **runtime monkey-patching of display functions**. Only the strings
  returned to the UI are changed; stored data is never touched, so a bug cannot
  corrupt the client and `fini()` restores everything exactly.

## Project layout

```
StreamerModeWoT/
├── src/
│   ├── mod_streamer_mode.py        core: config, identity, numbering, hooks, entry points
│   └── streamer_mode_settings.py   in-game settings page (Aslain / ModsSettingsAPI)
├── build.py                        release build (compile with 2.7 + package)
├── build_internal.py               internal build, pinned to one client version
├── py27_env.py                     locates a CPython 2.7 interpreter
├── refresh_fixtures.py             re-extract client fixtures after a patch
├── test_*.py                       test suite (self-contained, PASS/FAIL counters)
└── config.default.json             documented default config
```

## Requirements

1. **CPython 2.7** — found automatically via `py -2.7`, or set `WOT_PY27` to a
   `python.exe` path. A 3.x compile produces bytecode the game cannot load, so
   this is a hard requirement.
2. **Python 3.x** to run the build scripts (they use `subprocess.run`).
3. **`WOT_GAME`** — your client install, needed only by `refresh_fixtures.py`,
   `test_real_client.py` and `test_package.py`:

   ```powershell
   set WOT_GAME=D:\Games\World_of_Tanks_XX
   ```

## Build

```powershell
python build.py          # -> build/akemi.streamermode_<game-version>.wotmod
python build_internal.py # -> dist_internal/ (version-locked test build)
```

`build.py` self-checks the result: every entry STORED, `meta.xml` valid XML,
`.pyc` magic correct, and the entry points present. Any failure aborts the
build, so a broken package cannot be produced silently.

`build_internal.py` copies the sources, fills in `TARGET_VERSION`, compiles and
packages. A locked build refuses to run on any other client version: `init()`
returns before installing a single hook and logs one `DISABLED` line.

## Test suite

```powershell
foreach ($f in Get-ChildItem test_*.py) { py -2.7 $f.Name }
```

| File | Checks | What it verifies |
|---|---|---|
| `test_mod.py` | 19 | hook assumptions against real class shapes (main regression) |
| `test_real_client.py` | 13 | loads **real client classes** from fixtures and runs the hooks |
| `test_identity.py` | 13 | self / friends / clan / platoon detection |
| `test_bots.py` | 18 | bot prefix handling |
| `test_bot_numbering.py` | 12 | each bot gets a distinct, stable number |
| `test_tab_panel.py` | 18 | TAB full-stats panel + clan tags |
| `test_tab_bot_numbers.py` | 13 | TAB and in-battle numbers agree |
| `test_results.py` | 25 | post-battle scoreboard: bots vs players, exemptions |
| `test_results_numbers.py` | 17 | results numbering matches battle |
| `test_team_badges.py` | 17 | team-stats badges hidden |
| `test_profile_clan.py` | 18 | results clan hiding + profile switch |
| `test_badges.py` | 27 | badge hiding (battle / bots / exemption / master switch) |
| `test_prefix_language.py` | 18 | prefix follows the client language |
| `test_settings.py` | 51 | settings registration, version bump, callback arity |
| `test_loader.py` | 9 | simulates the client's mod loader |
| `test_package.py` | 8 | replicates the loader's package checks |
| `test_version_lock.py` | 38 | version-lock machinery |

After a client patch, refresh the fixtures **first**, or the tests validate the
old client and pass while the mod is already broken:

```powershell
py -2.7 refresh_fixtures.py
py -2.7 test_real_client.py
```

## Architecture: the rename pipeline

One nickname reaches the screen through several unrelated code paths. That is
the main source of complexity: fixing one leaves the others leaking.

| Surface | Path | Hook |
|---|---|---|
| Players panel, minimap, damage log, kill feed, 3D markers, postmortem | `BattleContext.getPlayerFullNameParts` → `PlayerFullNameFormatter.format` → `VehicleArenaInfoVO.getDisplayedName` → `PlayerInfoVO.getPlayerLabel` | those four functions |
| TAB full-stats (Gameface) | `TabView` fills models straight from the engine's arena dict — **no** helper above is called | `TabView._invalidatePersonalInfo` / `_invalidateVehiclesInfo` |
| Post-battle personal scoreboard | `PlayerNameBlock` reads one player through **four** accessors | `realName`, `fakeName`, `getFullName`, `clanAbbrev` |
| Post-battle team stats | its own blocks, reads the reusable avatar record directly | `RegularVehicleStatsBlock.setRecord`, `BadgeBlock.setRecord` |
| Badges | arena VO properties, TAB `BadgeModel`, `_setBadges`, `buildBadge` | those four |
| Clan tags | panel reads `playerVO.clanAbbrev` directly, not the formatted string | `VehicleInfoComponent.addVehicleInfo` |

### Numbering consistency

The same bot appears in the panel, TAB, results, postmortem and minimap, and
must show **one** number. Three approaches failed before the current one:

- keying on `accountDBID` / `avatarSessionID` — both empty for bots, so every
  bot collapsed into one label
- keying on the name — bot names come from a first/last-name pool and repeat
- using the VO as a dict key — `PlayerInfoVO` defines `__eq__` without
  `__hash__`, so it is unhashable in Python 2

The current key is **`vehicleID`**: unique and stable for the whole battle.
Names are only a weak fallback. `onAvatarBecomeNonPlayer` deliberately does
**not** reset the table — the results screen renders after it — so the reset
happens at the next `onAvatarBecomePlayer` instead.

## Configuration

Config file: `<game>/mods/configs/akemi.streamermode/config.json`. A missing or
unreadable file keeps `DEFAULTS`, which are all the anonymising values.

| Key | Default | Meaning |
|---|---|---|
| `enable` | true | master switch |
| `mode` | `label` | `label` = `Player_001`; `blank` = hide entirely |
| `namePrefix` | `""` | empty = follow the client language (`玩家_` on zh, `Player_` elsewhere) |
| `botMode` | `botLabel` | `botLabel` / `label` / `keep` / `blank` |
| `botPrefix` | `Bot_` | bot prefix, independent of the player prefix |
| `exclude.ownName` / `friendName` / `clanmateName` / `divmateName` | true | who keeps their real name |
| `hideClanTag` / `hideBotClanTag` / `hideResultsClanTag` | true | clan tags (battle / bots / results) |
| `hideBadges` / `hideBotBadges` / `badges.exemptKnown` | true | badges |
| `showRealNamesInProfile` | true | show real names in the single-player profile window |
| `scope.*` | true | per-screen switches |

### Settings page

Requires **Aslain Mod Menu** or **ModsSettingsAPI**; without either the mod
still works and you get the JSON config instead. `MOD_LINKAGE` is the mod id.

`SETTINGS_VERSION` **must be bumped whenever the template changes**. The
framework only replaces a cached template when `new > old`, so an unchanged
version is dropped silently and the menu keeps rendering the old layout.

The changed-settings callback must accept `*extra`: Aslain passes 2 arguments,
ModsSettingsAPI passes 3.

## Rules that bite

1. **Display only, never data.** Every hook changes what a function returns.
2. **Names fail closed, badges fail open.** A name error hides the name; a badge
   error leaves the badge alone, because badges are cosmetic and wiping every
   medal is the more annoying failure.
3. **Every package entry must be ZIP_STORED.** `build.py` fails the build if any
   entry is compressed.
4. **`BigWorld.logInfo` takes three arguments** — `(tag, msg, None)`. Two
   arguments raise `TypeError`, which a bare `except: pass` would swallow,
   leaving the mod silent and undebuggable.
5. **`isBot` is a `property`, not a method** in `PlayerInfoVO`. Use the `_isBot()`
   helper to tolerate both forms.
6. **`patch()` must preserve descriptors.** `UserNames._setBadges` is a
   `classmethod`; re-wrapping as a plain function loses the implicit `cls` and
   shifts every argument.
7. **`VehicleArenaInfoVO.__init__` calls `getSelectedByLayout` before `player`
   is attached.** That function therefore cannot make a per-player decision, or
   it would strip the badges of exempted players too.
8. **Never trust a single check.** One intermediate result once marked
   `addVehicleInfo` as a generator when it was not; key conclusions are confirmed
   two independent ways.

## In-game verification

Passing tests does not mean the mod works — the tests run offline.

1. Launch, check `game.log` for `[StreamerMode] init (...)`. A line saying
   `... missing; not installed.` means that hook point no longer exists in this
   client version.
2. In battle: strangers show `Player_001` / `玩家_001`; yourself, friends and
   platoon mates keep real names.
3. TAB: numbers match the panel; clan tags and badges hidden.
4. Kill feed, minimap, markers, postmortem: hidden.
5. Results: personal and team stats both match, names and tags hidden.
6. Right-click a player's profile: real name per `showRealNamesInProfile`.
7. Settings menu: all groups visible. If not, check `SETTINGS_VERSION`.

## Troubleshooting

Logs live in `<game>/game.log`. Filter for `[StreamerMode]`.

| Line | Meaning |
|---|---|
| `init (WoT ...)` | normal start |
| `DISABLED: this build is locked to client ...` | version lock working (internal build) |
| `X.Y missing; not installed.` | that hook point does not exist here — the client changed, re-verify it |
| `settings template changed, re-registering` | normal after a version bump |

## Known limitations

- Only affects **your own client**; other players still see real names.
- Scoped to battle; hangar, clan and chat windows are untouched.
- Replays use the same battle path, so names are anonymised there too.
- The results screen leaves alone players the game's own anonymiser already
  renamed.
