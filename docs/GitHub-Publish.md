# 发布到 GitHub（v0.1.1 测试版，不建 Release）

本文是**本仓库**的发布操作指南：把源码推到公开仓库，让别人可以 `git clone` 后按 README 安装。
当前版本是 `v0.1.1` 测试版，**不创建 GitHub Release，也不打 tag**；等真实迁移和宿主兼容性验证
差不多后再走发布流程。

目标仓库：`https://github.com/xukirito/programmer-workflow`（公开）。

## 0. 发布前检查

在仓库根目录执行：

```powershell
python tests\run_tests.py
node --check dsh-plugin\index.js
node --check dsh-plugin\client.js
python skills\programmer-workflow\scripts\companion.py docs --host dsh --spec docs\spec.json --check
```

确认：

- `VERSION`、`kimi.plugin.json`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、
  `dsh-plugin/package.json`、`skills/programmer-workflow/scripts/companion.py` 的版本都是 `0.1.1`。
- 没有 `.tmp-tests/`、`.agents/`、`.programmer-workflow/`、`debug-logs/`、`node_modules/` 进入暂存区。
- 没有 token、密码、私钥、真实记忆、客户数据或完整个人路径。示例路径统一用
  `C:\Users\example`、`D:\AgentData` 这类占位。
- README 中的本地图片路径存在，且图片本身不含个人路径。

检查暂存内容：

```powershell
git status --short
git diff --cached --stat
```

## 1. 在 GitHub 创建空仓库

1. 打开 <https://github.com/new>。
2. Owner 选 `xukirito`，Repository name 填 `programmer-workflow`。
3. 可见性选 **Public**。
4. **不要**勾选 “Add a README file”“Add .gitignore”“Choose a license”；本地已经有这些文件，
   空仓库可以避免第一次推送冲突。
5. 创建后记下远程地址：

```text
https://github.com/xukirito/programmer-workflow.git
```

如果 GitHub 用户名不是 `xukirito`，以实际账号为准，并同步修改 README 中的 clone 地址。

## 2. 本地初始化并提交

仓库目前可能还没有 `.git`。只需执行一次：

```powershell
cd "F:\C++\programme\AI_Skill-Plugin"

git init -b main
git add .
git commit -m "chore: publish v0.1.1 preview"
```

如果本机 Git 还没配置身份：

```powershell
git config --global user.name "xukirito"
git config --global user.email "<你的 GitHub 账号邮箱>"
```

公开仓库的提交记录会显示这个邮箱；不想公开真实邮箱时，用 GitHub 的
`<id>+<username>@users.noreply.github.com` 代替。

`git add .` 之后先跑一次 `git status --short`，确认忽略规则生效。首次提交前不要 `git add -f`
把 `.tmp-tests/` 或真实记忆目录强行加进去。

## 3. 关联远程并推送

```powershell
git remote add origin https://github.com/xukirito/programmer-workflow.git
git push -u origin main
```

认证方式二选一：

- **Git Credential Manager**：推送时弹出浏览器登录 GitHub，最省事；凭据由系统凭据管理器保存。
- **Personal Access Token**：GitHub → Settings → Developer settings → Personal access tokens，
  至少给目标仓库 `Contents: Read and write`。在提示密码时粘贴 token。
  **不要把 token 写进 remote URL、README、脚本或提交历史。**

如果远程仓库创建时不小心带了 README，第一次推送会被拒绝。先合并再推：

```powershell
git pull --rebase origin main
git push -u origin main
```

不要用 `git push --force` 覆盖远程，除非确认远程只有自己刚创建的空提交。

## 4. 仓库设置

推送成功后，在 GitHub 仓库页面设置：

- **Description**：`Approval-gated memory, plan-first workflow, stall recovery, instrumented debugging, offline docs/prototypes for coding agents.`
- **Topics**：`agent-skills`、`deepseek-harness`、`kimi-code`、`codebuddy`、`claude-code`、`workflow`、
  `memory`、`debugging`、`architecture`、`prototype`。
- **Default branch**：`main`。
- 不需要开启 Wiki；Issues 保持开启，方便测试反馈。

## 5. 推送后验证

找一台干净环境（或临时目录）重新 clone，验证下载者能看到什么：

```powershell
$tmp = Join-Path $env:TEMP "pw-clone-check"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
git clone https://github.com/xukirito/programmer-workflow.git $tmp
Set-Location $tmp

Get-Content README.md -TotalCount 40
Test-Path docs\Install.html
Test-Path dsh-plugin\package.json
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -DryRun -Targets dsh -HostId dsh
```

在 GitHub 网页上确认：

- README 的图片、`docs/Install.html`、`docs/Migration.html`、`README.en.md` 链接都能打开。
- 仓库首页没有 Release 区块（因为还没发布）。
- 文件列表里没有 `.tmp-tests`、`.agents`、`.programmer-workflow`、`debug-logs`。

## 6. 现在不要做的事

- **不要创建 GitHub Release**，也不要打 `v0.1.0` tag。当前只是源码测试版；Release 会给人“可稳定下载”的
  信号，而真实宿主迁移还没有验证。
- 不要上传 `~/.dsh` 下的记忆、会话、凭据、日志或截图。
- 不要把 `dsh-plugin` 的本地 `link:` 路径提交成绝对路径；DSH profile 里的路径属于用户本机数据，
  不是仓库内容。

如果误推了 tag，可以删除远程 tag（不会删代码）：

```powershell
git push origin :refs/tags/v0.1.0
```

## 7. 以后要发 Release 时的检查清单

只有在以下条件都满足后再考虑：

1. `python tests/run_tests.py` 全绿，且 CI（如果启用）通过。
2. DSH 真实数据的阶段 1 / 阶段 2 迁移至少各验证一次，并更新 README 适配矩阵。
3. Kimi / CodeBuddy / Claude / Cursor / Codex 的目标宿主至少做过一次安装冒烟测试。
4. README、CHANGELOG、`VERSION`、各清单版本一致。
5. 仓库中没有个人路径、真实记忆、凭据或未脱敏日志。

发布命令（届时再执行）：

```powershell
git tag -a v0.1.0 -m "Programmer Workflow v0.1.0"
git push origin v0.1.0
```

然后在 GitHub → Releases → Draft a new release，选择 `v0.1.0`，写清安装方式、支持矩阵和已知限制。
