> 语言: **简体中文** | [English](README.en.md)

# 坦克世界 2.4.1 主播模式（Streamer Mode）

在战斗中**匿名化其他玩家的昵称**，避免直播时把路人 ID 播出去。好友、军团战友、组队队友和你自己保留真实昵称。

本插件是《战舰世界》[AndrewTaro/StreamerMode](https://github.com/AndrewTaro/StreamerMode) 同款思路在《坦克世界》上的移植。坦克世界此前没有同类插件——Wargaming 官方的「匿名功能」方向正好相反（隐藏**你自己**的名字、在服务端生效、给别人看），而 WoT mod 圈围绕它做的多是反方向的「还原真名」工具。本插件在你的画面上隐藏**其他玩家**的昵称。

> 它覆盖战斗流程中的主要界面，但不保证所有界面、所有情况下都隐藏身份。具体例外见下方「隐私边界」。

## 效果

战斗中每个路人的昵称会被替换成一个稳定的编号：

```
    友军_001            (T-34-85)
    敌军_001            (IS-3)
    Bot_001             (T-54)            <- 官方机器人，独立前缀
    我的真名      [军团] (Object 277)     <- 你自己
    好友真名      [队友] (Bat.-Châtillon) <- 好友
```

友军和敌军使用**独立前缀 + 独立编号**：友军从 `友军_001` 开始，敌军从 `敌军_001` 开始。同一个人在**已覆盖的界面**里都是同一个编号——玩家面板、小地图、伤害记录、击杀提示、3D 战车标记、阵亡回放面板、TAB 全屏战绩——所以画面读起来依然自然。

也可以设置 `"mode": "blank"`，直接显示空白而不是编号。

### 官方机器人（BOT）

客户端里那些**冒号包起来**的名字（例如 `:张三:`）就是官方机器人。这不是猜的——`helpers/bots.pyc` 里的格式串写得很明确：

```python
_NAME_FORMAT_CREW = ':{0} {1}:'        # bots.pyc L12
```

而且这个名字是在 C++ 层（`ClientArena` → `preprocessBotName`）生成后才交给 Python 的。

机器人本身不涉及隐私，但很容易和真人混淆，所以默认给它们**独立前缀 + 独立计数**：

| `botMode` | 效果 |
|---|---|
| `botLabel`（默认） | `Bot_001`、`Bot_002`……与玩家分开计数 |
| `label` | 与玩家同一套编号（通用玩家前缀，`玩家_001`） |
| `keep` | 保留游戏原本的机器人名字 |
| `blank` | 完全隐藏 |

前缀与玩家前缀**相互独立**，想用中文就填 `机器人_`，效果是 `机器人_001`。

### 前缀跟随客户端语言

默认前缀跟随客户端界面语言和队伍：中文客户端显示 `友军_001` / `敌军_001`，其他语言显示 `Ally_001` / `Enemy_001`。一旦你在配置文件或设置菜单里手动填了前缀，就始终以你填的为准。

旧版的 `namePrefix` 仍然兼容：如果它留空，就使用上面的队伍默认值；如果里面填了自定义值，则作为友军/敌军的共享回退，直到你在 `allyPrefix` / `enemyPrefix` 里分别设置。

友军/敌军按**本地玩家所在队伍**分类，而不是写死某一方。即使你出生在 2 队，队友仍然显示友军前缀，对面显示敌军前缀；战斗中和战后结算都一致。

## 安装

从 [Releases](https://github.com/becausemadoka/wot-streamer-mode/releases) 下载 **`akemi.streamermode_1.0.4.zip`**（本地构建时位于 `build/`）。里面有三个 `.wotmod` 和一个 `THIRD-PARTY-NOTICE.txt`：

| 文件 | 作用 |
|---|---|
| `akemi.streamermode_1.0.4.wotmod` | 插件本体 |
| `aslain.modmenu_2.1.16.wotmod` | 游戏内设置菜单（依赖） |
| `net.openwg.gameface_1.2.2.wotmod` | Mod Menu 需要的运行环境 |

把**这三个 `.wotmod` 一起**解压到：

```
<游戏目录>/mods/<客户端版本>/
```

> `mods/` 下的目录名必须与客户端当前版本一致（可从 `<游戏目录>/version.xml` 查看）。放进版本不匹配的目录，游戏不会加载它。

只复制插件本体、不带上另外两个，插件仍然会运行并匿名化昵称，但你只能编辑配置文件，没有图形设置页面。三个文件都是**原样分发**。其中 Mod Menu 和 Gameface 是第三方作品，不适用本项目自己的 MIT 声明；Mod Menu 的源码仓库采用 MIT，但其包内 NOTICE 明确说明该 MIT 许可不覆盖构建出的包，只允许原样转发。两个上游项目的许可全文都收录在包内 `THIRD-PARTY-NOTICE.txt`。

**不改动 `res_mods` 里的任何东西**，所以游戏更新替换脚本时不会留下失效的覆盖文件。

## 游戏内设置菜单

插件会把自己注册进 **Aslain Mod Menu**（基于 ModsSettingsAPI 的界面），在游戏内的模组设置里就能改，不用手动编辑文件。菜单本身随上面的发布包一起提供，不需要另外下载。

菜单里提供的开关（中英文界面都会自动匹配）：

| 分组 | 项目 |
|---|---|
| 常规 | 启用主播模式、昵称隐藏方式（编号/隐藏）、友军名称前缀、敌军名称前缀 |
| 官方机器人 | 机器人昵称显示方式、机器人前缀、隐藏机器人军团标签 |
| 保留真实昵称 | 自己、好友、军团战友、组队队友、同时隐藏军团标签、结算界面同时隐藏军团标签 |
| 奖章（勋章） | 隐藏昵称旁的奖章、同时隐藏机器人奖章、认识的玩家保留奖章 |
| 玩家资料窗口 | 查看单个玩家资料时显示真实昵称 |
| 生效界面 | 战斗内界面、战后结算、玩家面板（两侧）、TAB 战绩面板、小地图、击杀/事件提示、战车标记、阵亡回放面板 |

> 界面开关的改动会在**下一场战斗**生效（战斗中的名字列表已经生成）。

## JSON 配置（可选）

也可以把 `config.default.json` 复制到 `<游戏目录>/mods/configs/akemi.streamermode/config.json` 手动改：

| 键 | 默认值 | 含义 |
|---|---|---|
| `enable` | `true` | 总开关 |
| `mode` | `"label"` | `"label"` → `友军_001` / `敌军_001`；`"blank"` → 完全隐藏 |
| `allyPrefix` | `""` | 友军前缀。**留空** = 跟随客户端语言（中文 `友军_`，其他 `Ally_`） |
| `enemyPrefix` | `""` | 敌军前缀。**留空** = 跟随客户端语言（中文 `敌军_`，其他 `Enemy_`） |
| `namePrefix` | `""` | 旧版通用前缀，仅作兼容回退：`allyPrefix` / `enemyPrefix` 为空时，若这里填了自定义值则两队共用；留空则使用上面的队伍默认值 |
| `botMode` | `"botLabel"` | 机器人：`"botLabel"` / `"label"` / `"keep"` / `"blank"` |
| `botPrefix` | `"Bot_"` | 机器人昵称前缀（可填 `机器人_`） |
| `hideBotClanTag` | `true` | 隐藏机器人的军团标签 |
| `exclude.ownName` | `true` | 保留自己的昵称 |
| `exclude.friendName` | `true` | 保留好友昵称 |
| `exclude.clanmateName` | `true` | 保留军团战友昵称 |
| `exclude.divmateName` | `true` | 保留组队队友昵称 |
| `hideClanTag` | `true` | 同时隐藏陌生人的军团标签 |
| `hideResultsClanTag` | `true` | 结算界面也隐藏军团标签（该界面直读属性，需独立开关） |
| `hideBadges` | `true` | 仅在已开启匿名化的界面隐藏昵称旁的奖章。关闭 TAB 战绩或战后结算的界面开关时，该界面的奖章照常显示 |
| `hideBotBadges` | `true` | 机器人奖章一并隐藏 |
| `badges.exemptKnown` | `true` | 自己/好友/军团/组队保留奖章 |
| `showRealNamesInProfile` | `true` | 查看单个玩家资料时显示真实昵称（设为 `false` 则该窗口也匿名） |
| `scope.inBattle` | `true` | 战斗内界面 |
| `scope.battleResults` | `true` | 战后结算界面 |
| `scope.playersPanel` | `true` | 玩家面板（两侧信息栏，以及载入界面的队伍列表） |
| `scope.tabPanel` | `true` | 局内按 TAB 打开的全屏战绩面板 |
| `scope.minimap` | `true` | 小地图 |
| `scope.messages` | `true` | 击杀/事件提示 |
| `scope.markers` | `true` | 战车标记 |
| `scope.postmortem` | `true` | 阵亡回放面板 |

配置读取失败或格式错误时会被忽略，并**保留「匿名」这套默认值**。这是刻意的：隐私工具绝不能「失效即放行」。

游戏内菜单和 JSON 文件是同一份配置，菜单里改完会立即写回。

## 工作原理

战斗中的所有昵称都汇聚到客户端 `arena_info` 包里少数几个显示函数上，插件把这几个函数包了一层：

| 被挂钩的函数 | 作用 |
|---|---|
| `PlayerInfoVO.getPlayerLabel` | 所有面板读取的基础昵称 |
| `PlayerInfoVO.getPlayerFakeLabel` | 本地生成的昵称（机器人保留自己的） |
| `VehicleArenaInfoVO.getDisplayedName` | 悬浮文字里的昵称 |
| `PlayerFullNameFormatter.format` | `名字 [军团] (坦克)` 组合串 |
| `battle_results.PlayerInfo.realName` | 战后结算界面（这是个 `property`） |

插件**从不修改存储的数据**，只改这些函数的**返回值**。所以不会有任何下游数据被污染，`fini()` 也能精确还原。

## 构建与测试

客户端跑的是 CPython 2.7 字节码，所以**必须用 2.7 编译**（3.x 编出来的 .pyc 游戏加载不了）。构建脚本会自动找 2.7：优先 `py -2.7`，找不到时可用环境变量 `WOT_PY27` 指定解释器路径。

```powershell
python build.py          # 用 Python 2.7 编译并打包 .wotmod + .zip
py -2.7 test_mod.py          # 行为测试（35 项）
py -2.7 test_real_client.py  # 对客户端真实类测试（13 项）
py -2.7 test_loader.py       # 模拟客户端 mod 加载器（9 项）
py -2.7 test_package.py      # 包结构可被游戏加载（8 项）
py -2.7 test_settings.py     # 设置菜单集成（56 项）
py -2.7 test_tab_panel.py    # TAB 面板 + 军团标签（24 项）
py -2.7 test_identity.py     # 身份识别/自己不被匿名（17 项）
py -2.7 test_bots.py         # 官方机器人前缀（18 项）
py -2.7 test_bot_numbering.py   # 机器人编号唯一且一致（12 项）
py -2.7 test_tab_bot_numbers.py # TAB 与面板编号一致（13 项）
py -2.7 test_results_numbers.py # 结算界面与面板编号一致（17 项）
py -2.7 test_profile_clan.py # 结算军团隐藏 + 资料页开关（18 项）
py -2.7 test_badges.py       # 奖章隐藏（43 项）
py -2.7 test_team_badges.py  # 团队战绩奖章隐藏（21 项）
py -2.7 test_results.py      # 结算界面机器人/玩家区分（35 项）
py -2.7 test_prefix_language.py # 昵称/队伍前缀（42 项）
py -2.7 test_surface_switches.py # 各界面开关与异常隔离（113 项）
py -2.7 test_review_findings.py  # 复查问题回归（22 项）
py -2.7 test_internal_artifact.py # 内部版版本锁（19 项）
```

`test_real_client.py` / `test_package.py` / `refresh_fixtures.py` 需要读客户端文件，运行前把 `WOT_GAME` 指向你的游戏目录：

```powershell
set WOT_GAME=D:\Games\World_of_Tanks_XX
```

完整的开发说明（架构、易踩的坑、上机验证清单）见 [DEVELOPMENT.md](DEVELOPMENT.md)。

## 兼容性

针对 **v.2.4.1.0 #975（国服客户端）** 开发并验证。

挂钩目标都是战斗 UI 的核心函数，已稳定多个版本；但客户端更新仍可能改名。那时插件会在日志里明确报错并停用对应的挂钩，而不会搞坏 HUD。在 `game.log` 里搜 `[StreamerMode]` 即可。

插件被设计为可以干净卸载，并且**拒绝覆盖其他 mod 已经替换过的函数**。

## 已知限制

* **只影响你自己的客户端**。别人看你仍是真名，除非对方也开了官方匿名功能。
* 重点是战斗流程；车库、军团、聊天窗口未做处理。
* 回放走的是同一套战斗逻辑，所以回放里的名字同样会被匿名化。
* 结算界面会对所有陌生人打码，**包括游戏官方匿名功能已经改过名字的玩家**——官方生成的假名同样是逐玩家的标识。被豁免的对象仍显示真实数据。
* 设置菜单由发布包内附带的 Aslain Mod Menu 提供；只复制插件本体时不显示界面，需要改配置文件。

### 隐私边界（请务必读完）

这个插件**不保证**在所有情况下都隐藏身份。以下是明确不予隐藏、或可能显示原文的情况：

| 场景 | 行为 | 原因 |
|---|---|---|
| **右键查看单个玩家资料** | **默认显示真实昵称与军团** | 查证/举报是主动行为，由 `showRealNamesInProfile` 控制，默认开 |
| 客户端找不到某个显示函数 | 该处保留原文 | 客户端版本更新改名时，插件只停用那一个钩子，不会强行改写 |
| 钩子内部抛异常 | 该处按“安全方向”处理（名字清空/奖章保留） | 宁可少显示，但无法保证覆盖所有界面 |
| 你自己的名字 | 始终显示真名 | 这是设计目标 |
| 好友 / 军团战友 / 组队队友 | 始终显示真名 | 可通过 `exclude.*` 关闭 |
| 游戏官方匿名功能已处理的玩家 | 仍会被本插件替换为编号 | 但官方本身的匿名效果不受影响 |
| 聊天窗口、车库、军团界面 | 不做任何处理 | 本插件只覆盖战斗流程 |
| 玩家面板的载入界面与局内两侧栏 | **共用一个开关，同时生效或同时失效** | 客户端把载入时写入的行沿用到战斗中，拆成两个开关会出现一半打码、一半真名 |

如果你需要“任何界面都不出现真名”，请把 `showRealNamesInProfile` 设为 `false`，并注意上表中“钩子缺失”一类情况仍可能保留原文——这是客户端兼容性问题，本插件会记录日志而不是静默失败。

## 排查

启动游戏后看 `game.log`，正常应出现：

```
[StreamerMode] init (WoT 2.4.1, enabled=True, mode=label)
[StreamerMode] installed with N hook(s)
[StreamerMode] settings page registered in the mod menu
[StreamerMode] identity: self=<DBID> clan=... friends=<N> squadmates=<N>
```

几个要点：

* 若出现 `Mod package '...' load error: compression not supported` → 包被压缩了，用仓库里 `build.py` 重新打包。
* `settings page registered` 缺失 → 没有装 ModsSettingsAPI（功能仍正常）。
* `identity ... friends=0` → 好友名单没取到，好友会被一起匿名化。这属于**安全方向的失败**（宁可多藏），若你在意请把该行日志发我。
* `installed with N hook(s)` 若 N 明显小于预期 → 有挂钩没装上，通常意味着客户端函数改名了。

## 致谢

思路来自 [AndrewTaro/StreamerMode](https://github.com/AndrewTaro/StreamerMode)——一个《战舰世界》的模组，在战斗中隐藏其他玩家的昵称。本项目把这个想法移植到《坦克世界》：WoT 客户端没有那种单一的网络钩子，所以这里的实现是针对 WoT 客户端**从零写的**，没有共用它的代码。

也感谢那些记录 `.wotmod` 格式和客户端 Python 环境的相关资料。

## 许可证

[MIT](LICENSE) © 2026 akemi
