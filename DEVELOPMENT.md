> 语言: **简体中文** | [English](DEVELOPMENT.en.md)

# 开发说明

如何修改、构建、测试和发布《坦克世界》主播模式。

- 语言：**CPython 2.7**（客户端内嵌 2.7，字节码 magic `03f30d0a`）
- 交付形态：`.wotmod` —— 一个**所有条目均为 STORED（不压缩）的 ZIP**
  （客户端加载器遇到 deflate 会报 `compression not supported`）
- 技术路线：**运行时猴子补丁（monkey patch）显示函数**。只改返回给 UI 的字符串，不改存储数据，所以出错也不会污染客户端，`fini()` 能精确还原。

## 项目结构

```
StreamerModeWoT/
├── src/
│   ├── mod_streamer_mode.py        核心：配置、身份判定、编号、全部钩子、入口
│   └── streamer_mode_settings.py   游戏内设置页（Aslain / ModsSettingsAPI）
├── build.py                        正常发布版构建（用 2.7 编译 + 打包）
├── build_internal.py               内部测试版构建，锁定到单一客户端版本
├── py27_env.py                     定位 CPython 2.7 解释器
├── refresh_fixtures.py             客户端更新后重新提取测试 fixture
├── test_*.py                       测试套件（自包含，自带 PASS/FAIL 计数）
└── config.default.json             带注释的默认配置样例
```

## 环境要求

1. **CPython 2.7** —— 构建脚本通过 `py -2.7` 自动定位；也可用环境变量
   `WOT_PY27` 指定 `python.exe` 路径。3.x 编出来的字节码游戏加载不了，这是硬约束。
2. **Python 3.x** 用来跑构建脚本（用了 `subprocess.run`）。
3. **`WOT_GAME`** —— 你的客户端目录，仅 `refresh_fixtures.py`、
   `test_real_client.py` 和 `test_package.py` 需要：

   ```powershell
   set WOT_GAME=D:\Games\World_of_Tanks_XX
   ```

## 构建

```powershell
python build.py          # -> build/akemi.streamermode_<版本>.wotmod + .zip
python build_internal.py # -> dist_internal/（锁定版本的内部测试版）
```

`build.py` 自带校验：所有条目 STORED、`meta.xml` 是合法 XML、`.pyc` magic 正确、
入口函数齐全。任何一项不通过都会中止构建，所以坏包不会在无提示的情况下产生。

完整发布 zip 还需要把两个第三方包原样放进 `vendor/`：
`aslain.modmenu_2.1.16.wotmod` 和 `net.openwg.gameface_1.2.2.wotmod`。它们不随
源码仓库提交，需从上游发布页获取；缺少时 `build.py` 会明确报错。

`build_internal.py` 会复制源码、填入 `TARGET_VERSION`、编译后打包。锁定版在
其他客户端版本上会拒绝运行：`init()` 在安装任何钩子之前就返回，只写一行
`DISABLED` 日志。

## 发布

GitHub 的 MCP 连接器只有仓库 / PR / issue 类工具，建 Release 和传附件需要
带 `contents: write` 的 token 直连 REST API，所以仓库里带了一个小脚本：

```powershell
python publish_release.py --save-token   # 交互输入，DPAPI 加密保存
python publish_release.py --notes-file notes.md [--clobber]
```

脚本从 `build.py` 读 `MOD_VERSION`，默认操作 tag `v<版本>` 和
`build/akemi.streamermode_<版本>.zip`：Release 不存在就新建，存在就更新
标题 / 正文；附件已存在时需加 `--clobber` 才会覆盖。tag 必须先在本地存在
（否则 GitHub 会把 Release 建在默认分支上），脚本会提前拦下。token 默认
保存在 `%APPDATA%\streamer-mode\gh_token.dpapi`，由 Windows DPAPI 按当前用户
加密；只有同一个 Windows 用户能解密。也可继续用 `GH_TOKEN` /
`GITHUB_TOKEN` 环境变量，或通过 `--token-file` 指定其它 DPAPI 文件。

## 测试套件

```powershell
foreach ($f in Get-ChildItem test_*.py) { py -2.7 $f.Name }
```

| 文件 | 项数 | 验证什么 |
|---|---|---|
| `test_mod.py` | 35 | 对真实类形状的钩子假设（主回归） |
| `test_real_client.py` | 13 | 加载**真实客户端类**（fixture）并跑钩子 |
| `test_identity.py` | 17 | 自己 / 好友 / 军团 / 组队 / 本地队伍 |
| `test_bots.py` | 18 | 机器人前缀处理 |
| `test_bot_numbering.py` | 12 | 每台机器人编号互不相同且稳定 |
| `test_tab_panel.py` | 24 | TAB 全屏战绩面板 + 军团标签 |
| `test_tab_bot_numbers.py` | 13 | TAB 与战斗内面板编号一致 |
| `test_results.py` | 40 | 结算界面：机器人与玩家、豁免规则、队伍视角 |
| `test_results_numbers.py` | 17 | 结算编号与战斗内一致 |
| `test_team_badges.py` | 21 | 团队战绩奖章隐藏 |
| `test_profile_clan.py` | 18 | 结算军团隐藏 + 资料页开关 |
| `test_badges.py` | 43 | 奖章隐藏（战斗内 / 机器人 / 豁免 / 总开关） |
| `test_prefix_language.py` | 42 | 友军/敌军前缀、语言回退、本地队伍视角 |
| `test_settings.py` | 56 | 设置页注册、版本递增、回调签名兼容 |
| `test_surface_switches.py` | 113 | 各界面开关、异常隔离与恢复 |
| `test_review_findings.py` | 22 | 复查发现的问题回归 |
| `test_loader.py` | 9 | 模拟客户端 mod 加载器 |
| `test_package.py` | 8 | 复刻加载器的包校验 |
| `test_internal_artifact.py` | 19 | 内部版版本锁与产物校验 |
| `test_version_lock.py` | 38 | 版本锁机制 |

客户端打完补丁后要**先刷新 fixture**，否则测试验证的是旧客户端 —— 可能全绿但插件其实已经坏了：

```powershell
py -2.7 refresh_fixtures.py
py -2.7 test_real_client.py
```

## 架构：改名流水线

游戏里"显示一个玩家名字"会经过**多条互不相干的代码路径**。这是本项目最大的复杂度来源：只修一条，别的界面照样泄露。

| 界面 | 路径 | 挂钩点 |
|---|---|---|
| 玩家面板、小地图、伤害记录、击杀提示、3D 标记、阵亡回放 | `BattleContext.getPlayerFullNameParts` → `PlayerFullNameFormatter.format` → `VehicleArenaInfoVO.getDisplayedName` → `PlayerInfoVO.getPlayerLabel` | 这四个函数 |
| TAB 全屏战绩（Gameface） | `TabView` 直接从引擎 arena 字典填模型，**不调用**上面任何助手 | `TabView._invalidatePersonalInfo` / `_invalidateVehiclesInfo` |
| 战后结算「个人战绩」 | `PlayerNameBlock` 通过**四个**入口取同一个玩家 | `realName`、`fakeName`、`getFullName`、`clanAbbrev` |
| 战后结算「团队战绩」 | 另一套 Block，直读可重用战果记录 | `RegularVehicleStatsBlock.setRecord`、`BadgeBlock.setRecord` |
| 奖章 | arena VO 属性、TAB 的 `BadgeModel`、`_setBadges`、`buildBadge` | 这四处 |
| 军团标签 | 面板直接读 `playerVO.clanAbbrev`，不走格式化结果 | `VehicleInfoComponent.addVehicleInfo` |

### 编号一致性

同一个机器人会出现在面板、TAB、结算、阵亡回放、小地图等处，必须显示**同一个**编号。踩过的三种失败方案：

- 用 `accountDBID` / `avatarSessionID` 做键 —— 机器人两者都空，全部撞成一个号
- 用**名字**做键 —— 机器人名字来自名字池、会重复，两台机器人被合并
- 用 VO 本身当字典键 —— `PlayerInfoVO` 定义了 `__eq__` 却没有 `__hash__`，Python 2 里不可哈希

现方案以 **`vehicleID`** 为键：整场战斗唯一且稳定。名字只做弱回退。
`onAvatarBecomeNonPlayer` **不**重置编号（结算界面在其之后渲染），重置交给下一场的 `onAvatarBecomePlayer`。

### 队伍分类

arena 里的 `team` 是**原始边号 1/2**，不是友军/敌军标志：玩家在 2 队时，1 队才是敌军。所以分类统一走 `_isAllyTeam(team)`，内部以 `IDENTITY.localTeam()` 为基准：

1. `BigWorld.player().team`
2. `player.arena.vehicles[playerVehicleID]['team']`
3. arenaDP 的玩家载具记录 / 按 `ownDBID` 匹配

本地队伍在 `Identity.resolve()` 时快照一次并缓存。但回到车库后这个缓存可能被清空，而结算界面还会显示上一场甚至更早的战果，所以姓名块（`PlayerNameBlock.setRecord`）会先读 `reusable.getPersonalTeam()`，把**这一份战果自己的队伍**记到 `_RESULTS_CONTEXT`，结算标签优先用它。TAB 的 `getAllies()/getEnemies()` 本身已相对本地玩家，因此不能把 1/2 原样传下去，要走 `_sideTeam()` 换算。

## 配置

配置文件：`<游戏>/mods/configs/akemi.streamermode/config.json`。缺失或不可读时保留 `DEFAULTS`，其值全是"匿名/隐藏"的安全值。

| 键 | 默认 | 含义 |
|---|---|---|
| `enable` | true | 总开关 |
| `mode` | `label` | `label` = `友军_001` / `敌军_001`；`blank` = 完全隐藏 |
| `allyPrefix` | `""` | 友军前缀；空 = 跟随客户端语言（中文 `友军_`，其他 `Ally_`） |
| `enemyPrefix` | `""` | 敌军前缀；空 = 跟随客户端语言（中文 `敌军_`，其他 `Enemy_`） |
| `namePrefix` | `""` | 旧版通用前缀，仅作两队共享回退 |
| `botMode` | `botLabel` | `botLabel` / `label` / `keep` / `blank` |
| `botPrefix` | `Bot_` | 机器人前缀，与玩家前缀独立 |
| `exclude.ownName` / `friendName` / `clanmateName` / `divmateName` | true | 谁保留真名 |
| `hideClanTag` / `hideBotClanTag` / `hideResultsClanTag` | true | 军团标签（战斗内 / 机器人 / 结算） |
| `hideBadges` / `hideBotBadges` / `badges.exemptKnown` | true | 奖章 |
| `showRealNamesInProfile` | true | 单人资料页显示真名 |
| `scope.*` | true | 各界面开关 |

### 设置页

依赖 **Aslain Mod Menu** 或 **ModsSettingsAPI**；两者都没有时插件照常工作，改用 JSON 配置。`MOD_LINKAGE` 就是 mod id。

`SETTINGS_VERSION` **必须在模板改动时递增**。框架只在 `new > old` 时替换缓存模板，版本号不变会被静默丢弃，菜单继续渲染旧布局。

设置变更回调必须接受 `*extra`：Aslain 传 2 个参数，ModsSettingsAPI 传 3 个。

## 容易踩的规则

1. **只改显示，不改数据。** 每个钩子只改变函数返回值。
2. **名字 fail-closed，奖章 fail-open。** 名字出错就隐藏名字；奖章出错则保持原样，因为奖章是装饰性的，把所有人的勋章都抹掉是更烦人的失败。
3. **所有包条目必须 ZIP_STORED。** 有任何条目被压缩，`build.py` 直接让构建失败。
4. **`BigWorld.logInfo` 要三个参数** —— `(tag, msg, None)`。两个参数会抛 `TypeError`，被 `except: pass` 吞掉后插件就完全静默了。
5. **`isBot` 是 `property` 不是方法。** 用 `_isBot()` 助手兼容两种形态。
6. **`patch()` 必须保留描述符。** `UserNames._setBadges` 是 `classmethod`，包成普通函数会丢失隐式 `cls`、参数错位。
7. **`VehicleArenaInfoVO.__init__` 在 `player` 挂上之前就调用 `getSelectedByLayout`。** 该函数不能按玩家判断，否则会把豁免对象的奖章一起抹掉。
8. **不能只信一次核对的结果。** 早前有份中间产物把 `addVehicleInfo` 标成了生成器，实际不是；关键结论都要用两种独立方式确认过。

## 上机验证

测试全绿不等于游戏可用 —— 测试是离线跑的。

1. 启动后在 `game.log` 找 `[StreamerMode] init (...)`。若出现
   `... missing; not installed.`，说明该钩子点在这个客户端版本已不存在。
2. 战斗内：友军显示 `友军_001` / `Ally_001`，敌军显示 `敌军_001` / `Enemy_001`；自己、好友、组队队友保留真名。
   分在 2 队时也要验证一遍：2 队成员必须显示友军前缀，1 队显示敌军前缀。
3. TAB：编号与面板一致；军团标签、奖章都隐藏。
4. 击杀提示、小地图、战车标记、阵亡回放：同样隐藏。
5. 结算：个人战绩与团队战绩都一致，名字与标签隐藏；同样核对 2 队视角，标签不能沿用上一场的阵营。
6. 右键查看某人资料：按 `showRealNamesInProfile` 显示真名。
7. 设置菜单：分组齐全。若缺，查 `SETTINGS_VERSION`。

## 排查

日志在 `<游戏>/game.log`，过滤 `[StreamerMode]`。

| 日志行 | 含义 |
|---|---|
| `init (WoT ...)` | 正常启动 |
| `DISABLED: this build is locked to client ...` | 版本锁生效（内部版） |
| `X.Y missing; not installed.` | 该钩子点在此版本不存在 —— 客户端改动了，需重新核对 |
| `settings template changed, re-registering` | 版本号递增后的正常重注册 |

## 已知限制

- **只影响你自己的客户端**；别人看到的仍是真名。
- 只覆盖战斗流程，车库、军团、聊天窗口未处理。
- 回放走同一套逻辑，所以名字同样被匿名。
- 结算界面会对所有陌生人打码，**包括游戏官方匿名功能已经改过名字的玩家**；
  官方生成的假名同样是逐玩家的标识。豁免对象仍显示真实数据。
