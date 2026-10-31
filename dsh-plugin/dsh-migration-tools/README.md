# DeepSeek Harness 运行数据迁移（第二阶段）

本目录只处理 **DSH 编辑器自身的运行数据**（会话、storages、桌面端 profile、登录凭据等），
不是 Programmer Workflow 插件数据。插件数据的第一阶段由设置页/`companion.py migrate-plugin`
单独完成；两个阶段不能合并。

脚本做法：**复制 → 校验 → 源目录改名 `.old` → 原位置建 Junction → 写测试**。
迁移后 DSH 仍按原路径读写，新数据自动落到目标盘。

## 源与目标

- 源：解析后的 `DSH_HOME`（默认 `%USERPROFILE%\.dsh`）；启动脚本通过 `DSH_MIG_SRC`
  传入真实源，不能固定假设 `%USERPROFILE%\.dsh`。
- 目标根：`DSH_MIG_DEST`；本阶段目标为 `<目标根>\.dsh`。设置页生成的 launcher 会传入目标根；
  直接双击 bat 时的默认值是 `D:\DSHData\migrated`，使用前请按自己的磁盘改掉。
- 桌面端 `%APPDATA%\@deepseek-ai` 仍按原逻辑处理，目标是 `<目标根>\@deepseek-ai`。
- 不支持 UNC 目标；目标已有未知数据时预检失败，不会静默合并。
- 已存在的 Junction 必须指向预期目标；指向别处会失败，不会当作成功跳过。

## 运行步骤

1. 完全退出 DeepSeek Harness（含托盘）；确认进程不存在。
2. 先完成并校验**第一阶段插件数据迁移**；设置页第二阶段才会开放。
3. 双击设置页生成的 `run-stage2-runtime.cmd`（或 `migrate-dsh-data.bat`）。
4. 看到各项完成后再启动 DSH，检查历史会话、登录、工作区。
5. 至少稳定使用一天后再删除 `.old`；它是回滚依据。

## 回滚

1. 完全退出 DSH。
2. 运行设置页生成的 `run-stage2-rollback.cmd`（内部调用 `rollback-dsh-data.bat`）。
3. 脚本会逐个处理，并检查每个 `RollbackOne` 的返回码；任一项失败以非零状态结束，
   不会显示整体成功。任一阶段失败时先处理失败项，不要继续下一步。
4. 目标盘副本保留，可手动清理。

**回滚顺序**：先回滚第二阶段运行数据，再回滚第一阶段插件数据。第二阶段处于
`prepared`/`completed` 时，第一阶段回滚会被 CLI 拒绝并提示先回滚第二阶段；成功回滚
第二阶段后，启动脚本会写 `runtime-rolled-back.txt`，CLI 以此解除门禁。第一阶段回滚会先
备份目标中当前最新的插件数据；若与迁移时不同，会保留 `latestBackup` 并提示新增/修改，
不会用旧 `.old` 静默覆盖后让用户以为新记忆仍在。

## 注意

- 检查完成前不要删除/移动 `.old`。
- 日志：`migrate-dsh-log.txt` / `rollback-dsh-log.txt`。
- 无法读取进程列表时脚本中止；可从普通 `cmd` 运行重试。
- 运行期间不要启动 DSH。
- `retentionDays` 不会清理这里的脚本、日志、备份或记忆。
