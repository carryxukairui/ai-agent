# CHANGELOG

All notable changes to this skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.3.2] - 2026-04-23

### Added
- **SKILL.md**：工作流中增加 **「SQL 编写规范与禁止项」** 表格，明确禁止 `SELECT *`、隐式逗号连接、大表无筛选、非只读、不当聚合/DISTINCT/ORDER BY 等业界常见反模式，并给出高效 SQL 的简短推荐
- **禁止事项** 中补充对交付 SQL 与上述规范的一致性要求
- **reference/旗舰版通用_后端_报表_SQL生成.md**：最高优先级中改为「显式列 + 别名」示例，与禁止 `SELECT *` 一致；并指向 `SKILL.md` 的完整规范表

## [1.3.1] - 2026-04-23

### Added
- **SKILL.md**：`parameters` 中明确 `queryUri` 与多义时重试约定
- **非交互多义输出**：`fetch_metadata` 在 stdin 非 TTY 时（插件 / Agent）输出与 iuap-c-metadata-info 一致的「本地元数据索引多 URI」stdout，供侧栏 URI 选择器与 Agent 轮次暂停
- 环境变量 `HYPERION_NON_INTERACTIVE=1` 时，即使 TTY 也不阻塞 `input()`

### Fixed
- **searchByName 多结果**：完全同名或子串匹配到多个**不同**业务对象编码时不再默认取第一个，改为返回 selection
- 客户端 `Chat`：侧栏点选 URI 后，对 `iuap-c-report-sqlgen` 自动发送带 `queryUri` 的续查话术（不再写死为仅 iuap-c-metadata-info）

## [1.3.0] - 2026-04-21

### Added
- **Python 版本检测**：`python_version_check.py` 模块，跨平台检测 Python 版本
- **自动升级引导**：版本不满足时自动尝试升级或打印详细升级指南
- **`.env.example` 模板**：提供配置模板，复制后填入实际值即可使用

### Fixed
- **Windows 兼容性**：`install_and_run.py` 修复硬编码路径分隔符问题
- **配置文件路径**：改用 `os.path.join()` 确保跨平台正确解析 `config.yaml` 路径

### Changed
- **`.gitignore` 更新**：排除 `.env` 文件，发布插件时不包含敏感信息
- **db_query.py**：入口添加 `require_python_version()` 版本检查

## [1.2.0] - 2026-04-18

### Added
- **测试框架**：新增 `tests/` 目录，包含 `test_metadata_parse.py` 和 `test_utils.py`
- **共享工具模块**：`utils.py` 抽取通用函数
- **日志模块**：`logging_config.py` 提供统一日志配置
- **进度条支持**：使用 `tqdm`（可选）显示批量操作进度
- **配置验证**：新增 `--validate` 参数验证配置完整性
- **环境变量支持**：`${VAR}` 和 `${VAR:-default}` 语法
- **详细日志**：`--verbose/-v` 参数输出详细日志
- **单元测试**：为 metadata_parse 和 utils 模块编写测试

### Changed
- **SKILL.md 重构**：拆分为精简版 SKILL.md + 深度指南 GUIDE.md
- **fetch_metadata.py**：添加日志、类型注解、配置验证、进度显示
- **db_query.py**：泛化数据库驱动、改进异常处理、统一 exit codes
- **文档结构**：增加 CHANGELOG.md

### Fixed
- 修复元数据解析中的重复 `_text` 函数
- 改进异常处理，使用具体异常类型而非宽泛 `Exception`

## [2.1.0] - 2026-04-17

### Added
- **并行处理**：实体批量查询支持线程池并发
- **URI 缓存**：进程内缓存避免重复请求
- **参照字段限制**：`max_reference_fields_expand` 配置

### Changed
- 优化大批量元数据拉取性能
- 改进日志输出格式

## [1.0.0] - 2026-04-16

### Added
- 初始版本
- 基础元数据拉取功能
- SQL 校验功能
- 报表交付物生成
