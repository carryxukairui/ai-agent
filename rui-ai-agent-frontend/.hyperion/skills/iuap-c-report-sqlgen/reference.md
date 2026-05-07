# iuap-c-report_sql_gen — 扩展阅读

本技能（旗舰版报表 SQL 生成）主流程写在 [SKILL.md](SKILL.md)。目录名曾用 `report-sql-gen`，请与仓库中 `skills/iuap-c-report_sql_gen/` 保持一致。生成物（`output/`、`report_sql_output/`）相对 **项目 workspace** 写入，不写回技能目录；见 `paths.workspace_root` 与 [scripts/paths_util.py](scripts/paths_util.py)。

**SQL 校验**：交付报表 `.sql` 后须在 `database.enabled: true` 时用 **`db_query.py --sql-file <该交付物路径>`**。脚本以 **sqlparse** 拆出**全部**语句：`SELECT`/`WITH` 默认执行（行数上限 `report_sql_max_rows`），DML 仅 **EXPLAIN**，DDL/会话类跳过；**`--explain`** 使 `SELECT`/`WITH` 也只跑执行计划。特征表 `elastic_field_check` 等为补充，可 `--sql-file ... --query elastic_field_check` 同次执行；不可仅凭 `--query`、不可仅凭 `--run-db-check` 替代对交付物文件的校验（见 SKILL「SQL 校验（硬性门禁）」）。

- **完整报表 SQL 规则与示例**：见同目录下 [reference/旗舰版通用_后端_报表_SQL生成.md](reference/旗舰版通用_后端_报表_SQL生成.md)）。
- **领域 schema 映射表**：`reference/scheme-info.json`。

脚本产出默认在 `output/`：`entities.json`（元数据）与 `report_sql_context.md`（元数据 JSON + 上述指南合并，便于投喂模型）。

**最终报表交付**（由 Agent 按 SKILL 写入工程根目录，默认 `report_sql_output/`）：**`{报表名}.sql`**（仅可执行 SQL）+ **`{报表名}_说明.md`**（说明与映射表，不内嵌完整 SQL）。模板见 [报表说明文档模板.md](报表说明文档模板.md)。

空骨架可一键生成：`scripts/scaffold_report_deliverable.py "报表名称"`（见 SKILL 脚本表）。
