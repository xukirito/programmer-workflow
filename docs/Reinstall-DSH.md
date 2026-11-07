# 重装 DeepSeek Harness 并保留运行数据

目标：替换 DSH 程序文件，但保留会话、登录、Skill、插件配置和 `programmer-workflow` 记忆。
**安装器只应替换程序目录；用户数据在 `~/.dsh` 和 `%APPDATA%`，不在安装目录。**
仍然建议先备份，尤其是 `~/.dsh` 已经被迁移成 Junction 的机器。

本文以 Windows 桌面版为例；路径按你的实际安装位置替换。当前仓库的 `v0.1.1` 测试版没有自动
“备份/恢复 DSH”按钮，下面的命令都是手动、可回滚的。

## 0. 先认清哪些是数据

| 内容 | 默认位置 | 重装时 |
|---|---|---|
| DSH 主目录（会话、凭据、attachments、skills、profiles、插件数据） | `%USERPROFILE%\.dsh`，或 `%DSH_HOME%` | **必须保留** |
| DSH 主目录的真实落盘位置 | 如果 `.dsh` 是 Junction，通常是另一个盘，例如 `D:\...\ .dsh` | **必须保留** |
| Electron 桌面 profile（窗口状态、Cookie、缓存、Local Storage） | `%APPDATA%\@deepseek-ai\dsh-desktop` | 建议保留；丢失通常只需重新登录 |
| 更新缓存 | `%LOCALAPPDATA%\@deepseek-aidsh-desktop-updater` | 可丢失 |
| 程序文件 | 例如 `D:\Program Files\DeepSeek Harness` | 会被替换 |
| 工作区/项目 | 你自己的项目目录 | 不受影响 |
| Programmer Workflow 的 Skill | `%USERPROFILE%\.dsh\skills\programmer-workflow` | 在 `.dsh` 内，随主目录保留 |
| Programmer Workflow 的 DSH 插件 | `.dsh\profiles\desktop` 里的 `link:` 依赖 | 通常保留；重装后要检查 |

**关键原则**：如果 `%USERPROFILE%\.dsh` 是 Junction，不要把它当成普通文件夹删掉再重建。
数据在它指向的真实目录里；删链接不会删数据，但重建错链接会让 DSH 以为数据丢了。

## 1. 退出 DSH

完全退出，包括托盘图标和后台进程：

```powershell
Get-Process | Where-Object { $_.ProcessName -match 'DeepSeek Harness|dsh' } |
  Select-Object Id, ProcessName, Path
```

如果还有进程，先从托盘退出；必要时在任务管理器结束 `DeepSeek Harness`。不要在 DSH 运行时复制
`.dsh` 或运行迁移脚本。

## 2. 记录当前状态

```powershell
$homeLink = Get-Item (Join-Path $HOME ".dsh") -Force
$homeLink | Format-List FullName, LinkType, Target

# 解析真实落盘位置（Junction 时取 Target；普通目录时取自身）
$real = if ($homeLink.LinkType) { @($homeLink.Target)[0] } else { $homeLink.FullName }
Write-Host "DSH 真实数据目录: $real"

# 关键文件是否存在
Test-Path (Join-Path $real ".credentials.yaml")
Test-Path (Join-Path $real "sessions")
Test-Path (Join-Path $real "programmer-workflow\memory\memory.json")
```

再记录 DSH 插件链接（如果已安装）：

```powershell
$profilePkg = Join-Path $real "profiles\desktop\package.json"
if (Test-Path $profilePkg) { Get-Content $profilePkg }
$pluginLink = Join-Path $real "profiles\desktop\node_modules\@local\programmer-workflow"
if (Test-Path $pluginLink) { Get-Item $pluginLink | Format-List LinkType, Target }
```

把输出保存到备份目录的 `SOURCE.txt`，后续恢复时对照。

## 3. 备份 `.dsh` 和桌面 profile

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "D:\DSHBackup\$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null

# 1) DSH 主目录（按真实路径复制，避免把 Junction 本身复制成普通目录）
robocopy $real "$backup\dsh-home" /MIR /XJ /R:1 /W:1

# 2) Electron 桌面 profile
robocopy "$env:APPDATA\@deepseek-ai" "$backup\appdata-deepseek-ai" /MIR /XJ /R:1 /W:1

# 3) 记录来源与日期
@(
  "backup=$stamp"
  "home=$HOME"
  "dshHomeLink=$($homeLink.FullName)"
  "dshHomeReal=$real"
  "linkType=$($homeLink.LinkType)"
) | Set-Content (Join-Path $backup "SOURCE.txt") -Encoding UTF8
```

`robocopy` 的退出码 `0`–`7` 都表示成功（`1` 表示复制了文件），`8` 及以上才是失败。备份完成后确认：

```powershell
Get-ChildItem $backup -Force
(Get-ChildItem "$backup\dsh-home" -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
```

备份里可能包含登录凭据、Cookie 和会话内容，**按敏感数据处理**，不要上传 GitHub 或发到聊天里。
稳定使用一段时间后再删除旧备份。

## 4. 重装 DSH

### 方案 A：覆盖安装（推荐）

1. 从 DSH 官方渠道下载当前 Windows 安装包。
2. 保持 DSH 完全退出。
3. 运行安装包，安装到与原来相同的目录（或新目录）。
4. 安装完成后先不要启动，按第 5 节检查数据；确认无误再启动。

覆盖安装不会清理 `%USERPROFILE%\.dsh` 或 `%APPDATA%`，因为它们在程序目录之外。
但**不要**在安装器里勾选任何“清理/重置用户数据”的选项（如果有）。

### 方案 B：卸载后重装

只有覆盖安装失败、或你确实需要干净程序目录时才用：

```powershell
# 从注册表读取卸载命令（路径按实际安装位置）
& "D:\Program Files\DeepSeek Harness\Uninstall DeepSeek Harness.exe" /currentuser
```

卸载完成后立即检查：

```powershell
Test-Path (Join-Path $HOME ".dsh")
Get-Item (Join-Path $HOME ".dsh") -Force | Format-List LinkType, Target
Test-Path "$env:APPDATA\@deepseek-ai\dsh-desktop"
Test-Path (Join-Path $real ".credentials.yaml")
```

如果 `.dsh` 或其真实目录不见了，**先按第 6 节恢复，再安装/启动**。
不要在看不清状态时启动新版本，以免新版本把空目录当成首次运行并生成新配置。

## 5. 安装后、启动前检查

```powershell
# Junction 还在、目标还在
Get-Item (Join-Path $HOME ".dsh") -Force | Format-List LinkType, Target
Test-Path (Join-Path $real "sessions")
Test-Path (Join-Path $real "programmer-workflow\memory\memory.json")

# 会话数量（示例：统计目录数）
(Get-ChildItem (Join-Path $real "sessions") -Directory -ErrorAction SilentlyContinue).Count

# 插件依赖仍然指向仓库
$profilePkg = Join-Path $real "profiles\desktop\package.json"
if (Test-Path $profilePkg) { Get-Content $profilePkg }
```

然后启动 DSH，逐项确认：

- 能进入主界面，不需要重新走首次引导。
- 历史会话可打开，工作区列表正常。
- 登录状态还在；如果掉登录，重新登录即可（`.credentials.yaml` 和桌面 profile 都在备份里）。
- **设置 → 程序员工作流** 存在，记忆条数和迁移状态正常。
- 侧边栏 **插件** 里能看到 `@local/programmer-workflow`，且没有 Client 同步错误。

## 6. 数据丢失或不一致时恢复

先完全退出 DSH。先重新解析一次链接类型，再按“Junction / 普通目录”分开处理：

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "D:\DSHBackup\<备份时间戳>"
$linkPath = Join-Path $HOME ".dsh"
$link = Get-Item $linkPath -Force
$isLink = [bool]$link.LinkType
$real = if ($isLink) { @($link.Target)[0] } else { $linkPath }
Write-Host "linkPath=$linkPath isLink=$isLink real=$real"

# 情况 A：原 .dsh 是 Junction（真实数据在 $real）
if ($isLink) {
    if (Test-Path $real) { Rename-Item $real "$real.broken-$stamp" }
    robocopy "$backup\dsh-home" $real /MIR /XJ /R:1 /W:1

    # 如果链接还在，先改名保留；如果链接已损坏，Test-Path 可能为 false，用 cmd 的 dir 确认后再删
    if (Test-Path $linkPath) { Rename-Item $linkPath "$linkPath.broken-$stamp" }
    cmd /c mklink /J "$linkPath" "$real"
}
# 情况 B：原 .dsh 就是普通目录（没有跨盘迁移）
else {
    if (Test-Path $linkPath) { Rename-Item $linkPath "$linkPath.broken-$stamp" }
    robocopy "$backup\dsh-home" $linkPath /MIR /XJ /R:1 /W:1
}

# 恢复桌面 profile（确认 DSH 已退出）
robocopy "$backup\appdata-deepseek-ai" "$env:APPDATA\@deepseek-ai" /MIR /XJ /R:1 /W:1
```

注意：

- `mklink /J` 的目标必须已经存在（上面已先恢复 `$real`）。
- Junction 情况：**不要**把备份复制到 `C:\Users\...\.dsh` 当作普通目录；C 盘路径只是入口，
  真实数据在 `$real`。
- 普通目录情况：恢复后不要执行 `mklink`，否则会把原目录变成指向自己/错误位置的链接。
- 如果 `.dsh` 是一个损坏的 Junction，`Test-Path` 可能返回 false；先用
  `cmd /c dir /AL "%USERPROFILE%"` 确认，再删除/改名链接，不要直接删真实数据目录。
- 恢复后再启动 DSH，重复第 5 节检查。

## 7. 重装后重新挂载 Programmer Workflow 插件

覆盖安装通常保留 `profiles\desktop\package.json` 里的 `link:` 依赖，但以下情况会让插件消失：

- 重装/升级时 profile 被重建；
- 仓库目录被移动、重命名或删除；
- `pnpm install` 没有重新创建 `node_modules\@local\programmer-workflow` 链接。

检查：

```powershell
Get-Content (Join-Path $real "profiles\desktop\package.json")
Get-Item (Join-Path $real "profiles\desktop\node_modules\@local\programmer-workflow") -Force |
  Format-List LinkType, Target
```

如果缺失，在 DSH 侧边栏 **插件** → 安装/添加本地组合包，选择仓库的 `dsh-plugin` 目录并启用；
然后重启 DSH。不要把 `dsh-plugin` 复制到 `.dsh\profiles` 里手工改 `package.json`，优先用插件管理器。

最后验证 CLI：

```powershell
$repo = "F:\C++\programme\AI_Skill-Plugin"   # 换成你的仓库路径
python "$repo\skills\programmer-workflow\scripts\companion.py" doctor --host dsh --workspace $repo
python "$repo\skills\programmer-workflow\scripts\companion.py" boot --host dsh --workspace $repo
```

`doctor` 应该显示 `user_memory`、`config`、`global_data` 和工作区记忆，并列出已安装的 Skill。

## 8. 重装检查清单

- [ ] DSH 已完全退出（含托盘/后台进程）。
- [ ] 已记录 `%USERPROFILE%\.dsh` 的 `LinkType` / `Target`。
- [ ] 已备份真实 `.dsh` 目录和 `%APPDATA%\@deepseek-ai`。
- [ ] 卸载/安装过程中没有勾选“删除用户数据/重置”。
- [ ] 卸载后 `.dsh` Junction 和目标目录仍在。
- [ ] 启动后历史会话、登录、工作区正常。
- [ ] 设置 → 程序员工作流 存在，记忆条数正常。
- [ ] `@local/programmer-workflow` 插件链接存在且无同步错误。
- [ ] `doctor --host dsh` 全部 `[ok]`。
- [ ] 旧备份保留至少一周，确认稳定后再清理。

## 9. 不要做什么

- 不要删除 `%USERPROFILE%\.dsh` 来“清空重装”；它是数据入口，可能是 Junction。
- 不要在 DSH 运行时运行 `.dsh` 迁移脚本或复制 `.dsh`。
- 不要把备份里的 `dsh-home` 直接覆盖到 `C:\Users\...\.dsh` 而不检查它原本是不是链接。
- 不要删除备份中的 `.old`/`*.broken-*`，直到确认新环境稳定。
- 不要把包含凭据、Cookie、会话的备份上传到 GitHub 或公开网盘。
