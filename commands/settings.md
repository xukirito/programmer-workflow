---
description: 打开程序员工作流的本地独立配置页（Kimi Code 适配）
---

为当前宿主打开 Programmer Workflow 的本地设置页。

> Kimi Code 的插件详情“主页”已指向 `http://127.0.0.1:8765/quick?host=kimi`；SessionStart hook 会幂等
> 启动该服务。若用户只是要打开配置页，先让用户试这个主页链接，不要为此调用模型或重复启动服务。
> 只有链接打不开、端口被占用或用户明确要求时，才执行下面的后台命令。

## 做法

1. 从**当前已加载的 Skill** 定位 `companion.py`，不要假定固定的宿主 home 路径：
   - 用 Skill 加载时显示的目录，拼接 `scripts/companion.py`；
   - 通过 `/plugins install` 安装时，实际运行的是 `plugins/managed` 下的插件副本，
     应使用该副本的 `scripts/companion.py`；
   - 如果无法确定，先运行 `python "<skill>/scripts/companion.py" doctor --host kimi --workspace .`
     确认路径，再继续。
2. 用宿主的**后台命令能力**启动并保持运行（不要用带固定超时的 `companion.py run` 包裹它）：

   ```bash
   python "<skill>/scripts/companion.py" settings --host kimi --workspace . --open
   ```

   - `--host` 使用当前宿主；Kimi Code 用 `kimi`，DSH 用 `dsh`，CodeBuddy 用 `codebuddy`。
   - `--workspace .` 固定本次服务的工作区；服务启动后 API 不再接受任意 workspace 路径。
   - `--open` 让默认浏览器打开设置页；宿主禁止打开浏览器时去掉它，把命令打印的 URL 发给用户。
   - `--port` 默认 0，自动选择 127.0.0.1 的随机空闲端口。
3. 命令会持续运行并打印一行 URL（形如 `http://127.0.0.1:<port>/?host=kimi#token=...`）。
   把该 URL 交给用户；不要只给端口，也不要在回复里粘贴 token。
4. 这个页面只读写当前宿主自己的 `config.json`，并**只准备**迁移/回滚脚本；
   它不会执行迁移、回滚或外部 batch 文件。真正的迁移需要用户在退出编辑器后手动运行生成脚本。
5. 页面由后台任务承载。用户确认完成后，结束该后台任务（或让用户按 Ctrl+C）即可停止本地服务；
   停止服务不会删除配置、记忆或迁移状态。

## 边界

- 不在 `kimi.plugin.json` 里添加 `settings`、`configFile`、`apps`、`inject` 等字段。
- 不加载 `dsh-plugin/client.js`——它依赖 DSH 专有的 ModuleLoader、React 和 `settings.section` Slot。
- 不引入 React、Node、MCP、CDN 或第三方 Python 包；服务只用 Python 3.8+ 标准库。
- 如果当前宿主不是 Kimi Code，使用对应的 `--host`，不要伪造 Kimi 的配置页。
- 保存失败时让用户根据页面上的字段错误修改，不要替用户静默改回默认值。
