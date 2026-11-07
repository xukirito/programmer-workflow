# 程序员工作流 / Programmer Workflow

[English](README.en.md) | 中文

把长对话里容易丢失的工作流，沉淀成**可检查、可回滚、可评审**的外部状态。

一个可安装到 DeepSeek Harness、Kimi Code、CodeBuddy、Claude Code、Cursor、Codex 等宿主的
Agent Skill / Plugin：记忆审批、Plan / Full authority、卡壳升级、带日志的调试闭环、离线工程文档
和设计原型。

[![version](https://img.shields.io/badge/version-0.1.1--preview-orange)](CHANGELOG.md)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](skills/programmer-workflow/scripts/companion.py)
[![hosts](https://img.shields.io/badge/hosts-DSH%20%7C%20Kimi%20%7C%20CodeBuddy%20%7C%20Claude%20%7C%20Cursor%20%7C%20Codex-informational)](#适配情况)

> **当前是 v0.1.1 测试版。** DSH 可直接从 GitHub 根目录安装；Kimi 使用官方 `/plugins install`。
> 配置字段、HTML 评审契约、DSH Client bundle 和迁移脚本仍可能调整；
> 不建议直接用于不可回滚的生产操作。真实宿主的迁移尚未由本插件验证，
> 详见[适配情况](#适配情况)与 [docs/Migration.html](docs/Migration.html)。

## 这是什么

长对话里，Agent 经常忘记三件事：用户已经确认过的规则、上一轮为什么卡住、以及这个工程到底长什么样。
Programmer Workflow 把这些状态放到对话之外：

- **记忆有审批门**：推断出的习惯先进入 `proposed`，用户确认后才变成 `active`；不会静默生效。
- **先计划再执行**：`workflowMode=plan` 时先生成 `plan.md` / `plan.html`，用户回复“执行”后才动项目；
  `full-authority` 只跳过例行批准，破坏性操作仍然确认。
- **卡住时给选择**：连续失败后不再瞎试，而是给出“行业做法 / 加日志定位 / 重述需求 / 缩小范围”四个方向。
- **调试可回溯**：统一加带 ticket 的日志、捕获输出、生成 `TRIAGE.md`，一次只验证一个假设。
- **环境不重复试错**：首次 `env probe` 把本机 OS、shell 和已安装命令写入工作区缓存；`run` 在真正执行前检查，
  缺失时直接给替代，跨系统只输出目标命令。
- **截图交给大模型识别**：`/screenshot` 或 `/截图` 捕获指定软件或屏幕并复制 PNG；
  Agent 用大模型自身的视觉能力读取文字，不调用 Windows OCR 或 Tesseract。
- **DSH 余额一眼可见**：左下角账号栏上方显示当前账号余额，点击刷新，关闭时不发起请求。
- **文档和原型可评审**：`Architecture.html`、`Features.html`、`Prototype.html` 都是离线单文件 HTML，
  可以在浏览器里筛选、标注、导出评审 JSON，再回到对话。

整个包只依赖 Python 标准库与浏览器；不需要 MCP、数据库、云端账号或第三方 Python 包。

## 功能一览

| 能力 | 入口 | 产出 |
|---|---|---|
| 用户 / 工作区记忆 | `memory`、`boot`、`remember` 命令或对话触发 | `memory/MEMORY.md` + `memory.json` |
| Plan / Full authority | 设置页 `workflowMode`、`plan` 命令 | `plan.md` 或 `plan.html` |
| 卡壳恢复 | 对话触发、`stall` 命令 | 方向选项 + 计数状态 |
| 调试与日志分诊 | `run`、`triage`、`env check` | `debug-logs/<label>/combined.log`、`TRIAGE.md` |
| 环境预检与缓存 | `env probe`、`env check`、`boot` | `.programmer-workflow/environment.json` + 工作区记忆 |
| 截图 / 大模型识别 / 剪贴板 | `/screenshot`（DSH 直命令）、`/截图`（Kimi/对话触发）、`screenshot` 命令 | 截图 PNG + 剪贴板图片 + 模型识别文本 |
| DSH 左下角余额 | 设置 → 余额显示 | 账号栏上方余额条 + 刷新间隔 |
| 架构 / 功能文档 | `docs` 命令或“总结架构” | `docs/Architecture.html`、`docs/Features.html` |
| UI / 美术 / 模型原型 | `prototype` 命令或“先做个原型” | `Prototype.html` |
| 插件 / 运行数据迁移 | DSH 设置页、`migrate-plugin` 命令 | 迁移脚本、回滚脚本、状态与校验 |

## 适配情况

“支持”指代码路径已实现并有契约/临时目录测试；“已验证”指在真实宿主数据上执行过。
本仓库不会把“有脚本”写成“已由本插件验证”。

| 宿主 | 安装入口 | 插件数据根（默认） | 设置页面 | 运行数据迁移 | 验证程度 |
|---|---|---|---|---|---|
| **DeepSeek Harness** | `dsh plugin --profile web add github:xukirito/programmer-workflow`（或根目录 `add .`） | `<DSH_HOME>/programmer-workflow`（默认 `~/.dsh/...`） | 有（设置 → 程序员工作流） | 内置 migrate + rollback（第二阶段） | 根包安装已应用；临时目录 + 契约测试；真实迁移未验证 |
| **Kimi Code** | `/plugins install` 或 `install.ps1 -Targets kimi` | `<KIMI_HOME>/programmer-workflow`（默认 `~/.kimi-code/...`） | 有（插件详情主页 / `/programmer-workflow:settings` 本地页） | 需要自行配置同时含 migrate + rollback 的工具目录 | 本地服务 + Chromium 端到端；真实 Kimi 会话未验证 |
| **CodeBuddy** | 项目级 `.codebuddy/skills` + `CODEBUDDY.md` | `<CODEBUDDY_HOME>/programmer-workflow`（默认 `~/.codebuddy/...`） | 本地页可切换（`--host codebuddy`） | **未适配** | 安装器与清单测试；端到端未验证 |
| **Claude Code** | `install.ps1 -Targets claude` / `.claude-plugin` | `~/.claude/programmer-workflow` | 无 | **未适配** | 清单与安装测试；插件市场方式未验证 |
| **Cursor** | `install.ps1 -Targets cursor` | `~/.cursor/programmer-workflow` | 无 | **未适配** | 安装路径与 Skill 发现测试 |
| **Codex** | `install.ps1 -Targets codex` | `~/.codex/programmer-workflow` | 无 | **未适配** | 安装路径与 Skill 发现测试 |
| **通用 / 其他 Agent** | `.agents/skills` + `AGENTS.md` 自举块 | `~/.programmer-workflow`（`--host generic`） | 无 | **不提供** | 临时目录测试 |

补充说明：

- 更细的安装页（含复制按钮和三端对照）：[docs/Install.html](docs/Install.html)。
- **DSH 版本**：在 `0.2.2-rc.1`（Windows 桌面版）上验证了根包安装、Host 路由、`/screenshot` 命令注册和余额条 slot。
  DSH 升级后若 Client 加载协议变化，设置页可能不出现；先在 DSH 的插件页看同步错误，再重新安装根包。
- **操作系统**：DSH 桌面端当前以 Windows 安装包为主；`install.sh` 覆盖 macOS / Linux 上的 Skill 安装。
  截图支持 Windows 与 Linux 图形会话；Linux 需要 `grim`/`gnome-screenshot`/`spectacle`/`scrot` 之一，复制图片还需要 `wl-copy` 或 `xclip`。识别不依赖本机 OCR。
  Windows 上 `.ps1` 受 ExecutionPolicy 限制时，用 `powershell -NoProfile -ExecutionPolicy Bypass -File ...`。
- **Python**：3.8+。没有 Python 时，Skill 的文本协议仍可阅读，但记忆、调试、文档和原型命令无法运行；
  不要假装命令执行成功。
- **数据隔离**：每个宿主有独立数据根，不共享记忆，也不会从非 DSH 宿主回退到 `~/.dsh`。
  旧的共享数据只能用设置页/CLI 做一次性导入，导入后各自独立。

## 快速开始

### 前置条件

- 一个支持的 Agent / 编辑器（推荐先试 DeepSeek Harness）。
- Python 3.8+（Windows 安装时勾选 `Add Python to PATH`）。
- Git（下载仓库、更新插件）。
- DSH 插件额外需要 DSH 桌面版；Node.js 只用于可选的 `node --check` 静态检查。

### 方式 A：DeepSeek Harness（推荐，默认安装方式）

DSH 0.2+ 可以直接从 GitHub 安装根目录包，和 `dsh-plugin-whale-pet` 一样，不需要先手动
复制 Skill 或安装本地组合包：

```powershell
dsh plugin --profile web add github:xukirito/programmer-workflow
```

安装后重启 `dsh web`（或桌面端）。包内包含 Skill、Host/Client 插件和 `cordis.patch.yml`；
Host 首次加载时会把内置 Skill 复制到 `<DSH_HOME>/skills/programmer-workflow`（已存在则保留，
便于 `install.ps1` 的受管更新）。随后出现 **设置 → 程序员工作流**。

也可以从本地源码安装（在仓库根目录执行，不是 `dsh-plugin` 子目录）：

```powershell
dsh plugin --profile web add .
```

更新 / 卸载：

```powershell
dsh plugin --profile web update dsh-plugin-programmer-workflow
dsh plugin --profile web remove dsh-plugin-programmer-workflow
```

如果之前装过旧的 `@local/programmer-workflow` 本地组合包，先卸载旧包再安装新包，避免同一个
loader entry 被两个包同时声明。

`install.ps1` 仍然可用，适合需要同时写入 `~/.dsh/AGENTS.md` 受管启动块或做离线安装的场景：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets dsh -HostId dsh -Bootstrap
```

### 方式 A2：验证

```powershell
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" doctor --host dsh --workspace .
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" boot --host dsh --workspace .
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" env probe --host dsh --workspace .
```

`boot` 会读回工作区环境缓存；`env probe` 只探测一次并写入工作区记忆。

> `install.ps1` 默认把 Skill 复制到 `~/.dsh/skills/programmer-workflow`，并只更新
> `~/.dsh/AGENTS.md` 中带标记的受管块；已有 Skill 目录默认跳过，`-Force` 会先备份。
> 先看会改什么可以加 `-DryRun`。

### 方式 B：Kimi Code

在 Kimi Code 中执行 `/plugins install`，指向本仓库根目录；插件会加载 Skill、系统提示和 `/` 命令。

**本地源码更新后必须重新安装该目录**：Kimi 会把本地目录复制到 `plugins/managed/programmer-workflow`，
之后运行的是这份副本。仅重启 Kimi Code 不会同步源码改动。请在插件管理页重新添加同一个本机目录
（必要时先在“更多操作”中卸载旧记录，再添加），确认详情页版本已从旧版变为当前版本，再新建会话。
也可以在聊天输入框执行 `/plugins install <仓库根目录>` 更新；这不是在 CMD 中执行。

### 进入配置页的两种方法

**方法 1：命令入口**

在 Kimi Code 的聊天输入框（不是 CMD）输入 `/programmer-workflow:settings` 并发送，Agent 会启动并打开
本地配置页。熟悉终端时，也可以直接使用下方“方式 B2”的 `companion.py settings ... --open` 命令。

**方法 2：双击 VBS（Windows，不消耗模型额度）**

用文件资源管理器打开下列任一位置，双击 `Open-Settings.vbs`：

- 源码安装目录：`<仓库根目录>\Open-Settings.vbs`。
- Kimi 安装副本：`<KIMI_HOME>\plugins\managed\programmer-workflow\Open-Settings.vbs`；
  默认 `<KIMI_HOME>` 为 `%USERPROFILE%\.kimi-code`，自定义安装位置以实际目录为准。

它会直接打开本地配置页；服务尚未启动时会隐藏启动服务。不需要输入命令、不经过模型，也不会显示
命令行窗口。请保留启动器与插件目录的相对位置，不要单独移动这个文件。

Kimi 当前自定义插件详情页可能不渲染主页链接，因此不要依赖该入口。

也可以只用安装器：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets kimi -HostId kimi -Bootstrap
python "$env:USERPROFILE\.kimi-code\skills\programmer-workflow\scripts\companion.py" doctor --host kimi --workspace .
```

Kimi 的插件数据根是 `~/.kimi-code/programmer-workflow`，**不是** DSH 的 `.dsh`。

`hooks.SessionStart` 只是可选的服务预启动机制，不是需要你操作的入口。Kimi 的“更多操作”菜单没有
插件自定义配置项；自定义插件详情也可能不显示主页链接，因此 Windows 直接使用上面的双击启动器。

### 方式 B2：本地设置页（Kimi Code / CodeBuddy / DSH）

Kimi 没有 DSH 的 `settings.section`，所以插件复用同一套 Python 配置能力，由
`/programmer-workflow:settings` 命令启动一个只监听 `127.0.0.1` 的本地页面：

```powershell
# Agent 用后台任务运行；<skill> 是当前实际加载的 Skill 目录
python "<skill>/scripts/companion.py" settings --host kimi --workspace . --open
```

- 通过 `/plugins install` 安装时，运行的是 `plugins/managed` 下的插件副本；命令让 Agent
  从已加载的 Skill 定位 CLI，**不要写死** `~/.kimi-code/skills`。
- 页面默认选中启动时的宿主，也可以切换 DeepSeek Harness / Kimi Code / CodeBuddy；
  每次 API 请求都显式带 host，未知 host 返回 400，不会回退到 DSH。
- 配置写入 `<host-home>/programmer-workflow/config.json`；保存失败会返回具体字段错误，
  不会静默替换成默认值。
- 页面只**准备**迁移/回滚脚本，不会执行迁移、回滚或外部 batch 文件。
- 服务用 `--port 0` 选择随机空闲端口；停止时结束该后台任务（或按 Ctrl+C）即可，
  不会删除配置、记忆或迁移状态。

### 方式 C：CodeBuddy / Claude Code / Cursor / Codex

```powershell
# CodeBuddy：项目级 Skill + CODEBUDDY.md
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets codebuddy -ProjectRoot "F:\work\my-app" -Bootstrap

# Claude Code
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets claude -HostId claude -Bootstrap

# Cursor / Codex
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets cursor -HostId cursor -Bootstrap
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Targets codex -HostId codex -Bootstrap
```

macOS / Linux 使用 `install.sh`：

```bash
./install.sh --target dsh --host dsh --bootstrap
./install.sh --target project --project ~/code/my-app --host generic --bootstrap
```

### 验证安装

```powershell
# 人看的检查：Python、模板、数据根、宿主 CLI、已安装目标
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" doctor --host dsh --workspace .

# 机器可读的迁移/插件状态
python "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py" migrate-plugin status --host dsh --json
```

设置页会分别展示应用数据、插件数据、工作区数据和两个迁移阶段；不要用“整个 `.dsh` 是 Junction”
推断插件迁移已经完成。

## 怎么用

安装后不需要记命令，直接用自然语言触发：

- **记住一件事**：“记住：这个项目用 pnpm，不要用 npm。”
  Agent 会先给出候选记忆和证据；你确认后才进入 `active`，并可随时用 `memory forget <id>` 删除。
- **打开设置**：“打开程序员工作流设置。” 在 Kimi / CodeBuddy 下会运行 `/programmer-workflow:settings`，
  启动本地设置页并打印访问 URL。
- **先给方案**：“先给方案，不要改代码。” 在 `plan` 模式下会生成 `plan.md` / `plan.html`。
- **卡住了**：“试了三轮还是不对，别猜了。” 会触发卡壳升级，给出四个方向让你选。
- **调试**：“加日志定位这个 500，然后跑一遍。” 会走 `run` + `triage` 闭环。
- **总结工程**：“总结一下这个工程的架构和功能。” 会生成 `docs/Architecture.html`、`docs/Features.html`。
- **做ui原型**：“先给设置页做两个视觉方向。” 会生成 `Prototype.html`，可切换方向并导出评审 JSON。

常用 CLI：

```powershell
$CLI = "$env:USERPROFILE\.dsh\skills\programmer-workflow\scripts\companion.py"

python $CLI boot --host dsh --workspace .
python $CLI memory review --host dsh --scope all
python $CLI docs --host dsh --spec docs/spec.json --out docs
python $CLI prototype --host dsh --spec design.json --out Prototype.html
python $CLI run --host dsh --label repro --timeout 120 --yes -- python app.py
python $CLI triage debug-logs\repro\combined.log
```

`plan`、`docs`、`prototype`、`scan`、`map` 的输出路径必须在工作区内；绝对路径和 `..` 会被拒绝。

## 工作流模式与安全边界

| `workflowMode` | 行为 | 运行命令 |
|---|---|---|
| `plan`（默认） | 普通运行先写计划、等“执行”；不直接改项目 | `run --yes` |
| `full-authority` | 普通运行不逐条批准；破坏性操作仍需确认 | `run --full-authority` |

- `--yes` 与 `--full-authority` 互斥；旧配置里的 `requireRunConsent=false` **不会**被提升为 full authority。
- 这是插件策略，不改变宿主自己的 Plan / 只读 / 沙箱权限；宿主的限制永远优先。
- 明显破坏性的命令在两种模式下都会被拦截；只有用户明确确认后才用 `--allow-destructive`。
- 记忆、日志、文档、原型里都不应出现 token、密码、私钥、客户数据或完整个人路径。

## 数据位置与隐私

| 数据 | 默认位置 | 是否随应用迁移 |
|---|---|---|
| 插件全局记忆 / 配置 | `<host-home>/programmer-workflow` | 第一阶段插件数据迁移 |
| 工作区记忆 | `<workspace>/.programmer-workflow` | 否，属于项目 |
| 调试日志 | `<workspace>/debug-logs` | 否 |
| 文档 / 原型 | `<workspace>/docs`、`<workspace>/Prototype.html` | 否 |
| DSH 运行数据 | `%USERPROFILE%\.dsh`（可被 `DSH_HOME` 覆盖） | 第二阶段运行数据迁移 |

所有数据默认留在本机；仓库不包含运行时记忆、凭据或日志。`PROGRAMMER_WORKFLOW_GLOBAL` /
`PROGRAMMER_WORKFLOW_HOME` 是显式覆盖，状态页会标记为“外部路径，未由默认迁移覆盖”，需要自行备份。

## 两阶段迁移（可选）

1. **插件数据**：只移动当前宿主的 `programmer-workflow` 目录；预检、备份、SHA-256 校验后再生成脚本。
2. **运行数据**：移动会话、配置、缓存、登录等编辑器数据；必须等第一阶段完成并校验，且适配器同时有
   migrate 与 rollback 脚本。

DSH 设置页和本地设置页都可以准备迁移脚本：第一阶段生成 `run-stage1-plugin.cmd` /
`run-stage1-rollback-plugin.cmd`，脚本使用当前真实 `companion.py` 并显式传入 `--host`；
第二阶段生成 `run-stage2-runtime.cmd` / `run-stage2-rollback.cmd`，向适配器传递
`KIMI_MIG_SRC` / `KIMI_MIG_DEST`（或 DSH 对应变量）。`prepared` 只代表脚本已生成，
只有链接或真实落盘校验通过才显示“已完成”。

Kimi 需要自行配置工具目录；CodeBuddy / Claude / Cursor / Codex 的运行数据迁移尚未适配。
迁移脚本只能在完全退出目标编辑器后运行，`.old` 目录至少保留到稳定使用一天之后。
详情见 [docs/Migration.html](docs/Migration.html)。
重装 DSH 并保留现有数据见 [docs/Reinstall-DSH.md](docs/Reinstall-DSH.md)。

## 常见问题

**设置页没有出现**
DSH：先确认 `dsh-plugin` 已通过 DSH 插件页安装并启用，而不是只复制了目录；再检查 DSH 插件页的
Client 同步错误。DSH 升级后重新安装本地组合包通常能解决协议变化。
Kimi / CodeBuddy：使用 `/programmer-workflow:settings`；若命令没有启动，检查 Agent 是否从**当前
已加载的 Skill** 定位到了 `companion.py`（managed 插件副本也可以），不要依赖固定 home 路径。

**Kimi 本地目录安装报 `EPERM ... symlink`**
安装器会复制本机目录，`.gitignore` 不会阻止测试残留被复制。先删除仓库内 `.tmp-tests` 中失败测试留下的
`pwf-host-*` 目录及其 Junction，再重新添加仓库根目录；不要删除源码、配置或真实记忆。

**本地设置页打不开 / 提示令牌无效**
重新运行 `settings` 命令并用它打印的完整 URL 打开；token 在 URL 的 `#token=` 片段里，
只接受 `X-Programmer-Workflow-Token` 请求头。服务只监听 `127.0.0.1`，不要改成 `0.0.0.0`。

**`doctor` 说找不到 Python**
安装 Python 3.8+ 并确保 `python` 在 PATH 中；DSH 桌面版自带运行时不能直接当系统 `python` 用。
没有 Python 时仍可使用 Skill 的文本协议，但不要声称命令已执行。

**PowerShell 报 `无法加载文件 ... 因为在此系统上禁止运行脚本`**
使用 `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 ...`，不要改全局策略。

**命令报 `--host is required`**
指定 `--host dsh|kimi|codebuddy|claude|cursor|codex|generic`，或设置 `PROGRAMMER_WORKFLOW_HOST`。
不存在从当前目录猜宿主、也不存在非 DSH 宿主回退到 `.dsh`。

**迁移按钮是灰的**
第一阶段没有完成/校验，或当前宿主缺少 `companion.py`（可用 `PROGRAMMER_WORKFLOW_CLI` 指定）；
Kimi 还要求 `kimiMigrationTools` 目录同时含迁移与回滚脚本。本地设置页会显示具体原因，
不要只看灰色按钮；`prepared` 不等于 `completed`。

**Kimi / CodeBuddy 会读 DSH 的记忆吗**
不会。每个宿主的数据根独立；旧共享数据只能一次性导入，不会自动同步。

## 仓库结构

```text
skills/programmer-workflow/     可安装的 Skill：SKILL.md、references/、scripts/、templates/
  scripts/lib/config.py         严格校验、合并保存、恢复默认、原子写入
  scripts/lib/settings.py       本地设置页状态与 127.0.0.1 HTTP API
  templates/settings.*          本地设置页 HTML / CSS / JS（无 CDN、无 React）
dsh-plugin/                     DSH Host/Client 组合包：设置页、迁移 UI、内置迁移工具
commands/                       Kimi / Claude 斜杠命令（含 settings.md）
kimi.plugin.json                Kimi 插件清单
.claude-plugin/                 Claude Code 插件清单
docs/                           安装、迁移、重装指南和生成的架构/功能文档
examples/                       示例计划、原型、演示输出
install.ps1 / install.sh        Windows / macOS-Linux 安装器
tests/                          临时目录测试、契约测试、静态检查
```

## 开发与测试

```powershell
python tests\run_tests.py
node --check dsh-plugin\index.js
node --check dsh-plugin\client.js   # 注意：client.js 是 classic script，详细检查见 tests
node --check skills\programmer-workflow\templates\settings.js
python skills\programmer-workflow\scripts\companion.py settings --help
python skills\programmer-workflow\scripts\companion.py docs --host dsh --spec docs\spec.json --check
```

测试使用临时目录和临时 home，不会写入真实宿主记忆。设置 `WC_NODE` 可以让测试额外检查内联 JS 语法。
修改 `docs/spec.json` 后重新生成文档，不要手改生成的 HTML：

```powershell
python skills\programmer-workflow\scripts\companion.py docs --host dsh --spec docs\spec.json --out docs
```

Windows 上如果 `pwsh` 不可用，用系统自带的 `powershell`；安装器测试需要 `-ExecutionPolicy Bypass`。

## 版本与发布

- 当前：`v0.1.1` 测试版，**未创建 GitHub Release / Tag**。
- 变更记录：[CHANGELOG.md](CHANGELOG.md)。
- 维护者发布步骤：[docs/GitHub-Publish.md](docs/GitHub-Publish.md)。
- 发布前至少需要：全部测试通过、迁移在真实数据上验证、README 适配矩阵更新、确认没有个人路径/凭据。
- 发现问题请开 GitHub Issue，附上宿主与版本、执行命令、脱敏后的错误日志；不要上传记忆文件或凭据。

## 小建议

- 希望大家多交流给建议，也可自行上传修复bug或提交你的修改
- 该插件后续会不断更新我所使用过的agent的适配，会持续更新，也可有你们（大佬们）更新新的适配agent

## License

[MIT](LICENSE) © 2026 Workflow Companion Contributors
