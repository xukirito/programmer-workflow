# 三端设置与 Plan 模式适配

> 状态：Plan mode / 待审核
> 这只是执行计划，不会自动执行。回复 `执行` 后才开始；回复 `修改：...` 或 `取消` 停止。

## 目标

让 DSH / Kimi Code / CodeBuddy 共用一份配置，并在 Plan 模式下先生成可审核的计划。

## 背景与假设

设置页已能读写全局 config.json；迁移工具分 DSH 内置与 Kimi 已验证外部工具两套；CodeBuddy 使用项目级 Skill。

## 假设

- Kimi 数据已迁移到 D:\KimiData\migrated
- DSH 数据已迁移到 D:\AgentData\migrated
- Full authority 由宿主决定，插件不自行提权

## 执行步骤

### 1. 写入 Plan 模式协议与命令

- **变更**：新增 references/plan.md、commands/plan.md 和 plan CLI
- **命令**：`python skills/programmer-workflow/scripts/companion.py plan --host dsh --spec .programmer-workflow/plan.json --format md`
- **原因**：先有统一审核文件，再执行命令
- **风险**：低
- **验证**：plan.md 包含目标、步骤、风险、回滚和“执行”门

- [ ] 已验证步骤 1

### 2. 设置页增加宿主适配

- **变更**：client.js 增加 DSH/Kimi/CodeBuddy 切换、Plan 格式和迁移目标
- **命令**：`python tests/run_tests.py`
- **原因**：避免把三端路径混在一起
- **风险**：中
- **验证**：三端切换、窄宽度和深色截图检查通过

- [ ] 已验证步骤 2

### 3. 生成 DSH 与 Kimi 迁移脚本

- **变更**：Host 增加 migration/prepare 的 host 参数
- **命令**：`curl -X POST <harness-url>/programmer-workflow/migration/prepare -d '{"host":"kimi","target":"D:\\KimiData\\migrated"}'`
- **原因**：复用已验证工具，不复制不改写
- **风险**：中
- **验证**：run-migrate-kimi.cmd 正确设置 KIMI_MIG_DEST

- [ ] 已验证步骤 3

## 整体验证

- [ ] python tests/run_tests.py 全绿
- [ ] 设置页接口返回 planFormat、kimiMigrationTarget 和 hosts
- [ ] Plan.html 在浅色/深色下可读，复制按钮可用

## 回滚

删除 plan.md/plan.html；恢复 config.json 默认值；不执行迁移脚本即可保持现状。

## 需要你确认

- Plan 文件默认放项目根，还是 .programmer-workflow/？

## 审核

- [ ] 我批准执行
- [ ] 需要修改（请在对话里说明）
- [ ] 取消

回复：`执行` / `修改：...` / `取消`
