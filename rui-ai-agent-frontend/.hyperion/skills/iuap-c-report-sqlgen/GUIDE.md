# 旗舰版报表 SQL 生成技能 - 深度指南

本文档是 [SKILL.md](SKILL.md) 的补充，提供详细的配置、脚本和高级用法说明。

---

## 目录

1. [配置详解](#配置详解)
2. [脚本详解](#脚本详解)
3. [高级用法](#高级用法)
4. [故障排查](#故障排查)

---

## 配置详解

### config.yaml 完整结构

```yaml
# 路径配置
paths:
  workspace_root: ""           # 项目根目录（空则自动推断）
  scheme_info_json: "reference/scheme-info.json"
  sql_guide_md: "reference/旗舰版通用_后端_报表_SQL生成.md"
  output_dir: "output"         # 元数据输出目录
  report_deliverable_dir: "report_sql_output"  # 报表交付目录

# API 配置
api:
  base_url: "${API_BASE_URL:-https://c1pocpro.yonyoucloud.com/}"
  app_key: "${API_APP_KEY}"
  app_secret: "${API_APP_SECRET}"
  path_token: "/iuap-api-auth/open-auth/selfAppAuth/getAccessToken"
  metadata_byname: "/iuap-api-gateway/${YONBIP_TENANT_ID:-q6shbpxc}/current_yonbip_default_sys/GDBG/businessobject/searchByName"
  metadata_byboid: "/iuap-api-gateway/${YONBIP_TENANT_ID:-q6shbpxc}/current_yonbip_default_sys/GDBG/businessobject/getEntityListByBOId"
  metadata_entityid: "/iuap-api-gateway/${YONBIP_TENANT_ID:-q6shbpxc}/current_yonbip_default_sys/GDBG/getEntityInfoByBOIdAndEntityId"
  metadata_uri: "/iuap-api-gateway/${YONBIP_TENANT_ID:-q6shbpxc}/current_yonbip_default_sys/GDBG/queryByUri"
  http_timeout_seconds: 120
  insecure_tls: false
  token_refresh_skew_seconds: 120
  token_fallback_ttl_seconds: 3500
  auth_retry_business_codes: []

# 请求参数
request:
  allbillname: "销售订单"
  isIncludeSub: "Y"
  docFields: ""
  isSQL: "Y"
  isDescField: "Y"
  tableTemplate: ""

# 性能配置
performance:
  max_concurrent_query_by_uri: 16
  max_concurrent_bills: 6
  max_concurrent_entities: 8
  max_reference_fields_expand: 30

# 输出配置
output:
  strip_attribute_names: true
  write_entities_json: true
  entities_json_filename: "entities.json"
  write_bundle_md: true
  bundle_md_filename: "report_sql_context.md"

# 限流配置（防止网关被限流）
rate_limit:
  enabled: true
  requests_per_second: 10.0
  burst_capacity: 20.0

# 缓存配置（用于 URI 查询结果缓存）
cache:
  enabled: true
  ttl_seconds: 300.0
  max_entries: 1000

# 日志配置
logging:
  level: "${LOG_LEVEL:-INFO}"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: ""

# 环境区分
environment:
  name: "${ENV_NAME:-development}"
  debug: "${ENV_DEBUG:-false}"

# 数据库配置
database:
  enabled: "${DB_ENABLED:-true}"
  driver: "${DB_DRIVER:-mysql}"
  host: "${DB_HOST:-192.168.19.151}"
  port: "${DB_PORT:-3306}"
  user: "${DB_USER:-kk1mysql_linshi}"
  password: "${DB_PASSWORD}"
  database: "${DB_NAME:-crm}"
  sslmode: "${DB_SSLMODE:-prefer}"
  charset: "${DB_CHARSET:-utf8mb4}"
  service_name: "${DB_SERVICE_NAME:-ORCL}"
  report_sql_max_rows: 50
  report_sql_use_explain: true
  report_sql_execute_sample: true
  report_sql_mysql_explain_json: true
  queries:
    elastic_field_check:
      enabled: true
      schema: "uorders"
      virtual_table_name: "orders_character_define"
      ytenant_id: "${YONBIP_TENANT_ID:-q6shbpxc}"
      sql: ""
```

### 环境变量支持

配置值支持 `${VAR_NAME}` 和 `${VAR_NAME:-default}` 语法：

```yaml
database:
  password: "${DB_PASSWORD}"                    # 必须存在
  password: "${DB_PASSWORD:-default_pass}"      # 提供默认值
```

### .env 文件配置（推荐）

推荐使用 `.env` 文件管理敏感配置。复制示例文件后填入实际值：

```bash
# 复制示例文件
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# 开放平台鉴权
API_BASE_URL=https://c1pocpro.yonyoucloud.com/
API_APP_KEY=your_app_key
API_APP_SECRET=your_app_secret

# 数据库连接
DB_ENABLED=true
DB_DRIVER=mysql
DB_HOST=192.168.19.151
DB_PORT=3306
DB_USER=kk1mysql_linshi
DB_PASSWORD=your_db_password
DB_NAME=crm
DB_CHARSET=utf8mb4

# 租户配置
YONBIP_TENANT_ID=q6shbpxc
```

脚本会**自动加载**技能根目录下的 `.env` 文件，无需手动 `source`。也可通过命令行参数指定：

```bash
python fetch_metadata.py --env-file /path/to/your/.env
```

### 配置验证

运行 `--validate` 参数检查配置完整性：

```bash
python fetch_metadata.py --config ../config.yaml --validate
```

---

## 脚本详解

### fetch_metadata.py

拉取业务对象元数据。

```bash
# 基础用法
python fetch_metadata.py --config ../config.yaml

# 指定单据
python fetch_metadata.py --config ../config.yaml --allbillname "销售订单"

# 仅验证配置
python fetch_metadata.py --config ../config.yaml --validate

# 详细日志
python fetch_metadata.py --config ../config.yaml -v

# 拉取后运行数据库校验
python fetch_metadata.py --config ../config.yaml --run-db-check
```

### db_query.py

执行 SQL 校验和数据库查询。

```bash
# 校验交付的 SQL 文件
python db_query.py --config ../config.yaml --sql-file ../report_sql_output/销售明细.sql

# 仅执行命名查询
python db_query.py --config ../config.yaml --query elastic_field_check

# 同时执行文件校验和查询
python db_query.py --config ../config.yaml --sql-file ../report.sql --query elastic_field_check

# 仅显示执行计划（不执行）
python db_query.py --config ../config.yaml --sql-file ../report.sql --explain

# 跳过示例执行
python db_query.py --config ../config.yaml --sql-file ../report.sql --no-execute-sample

# 自定义最大行数
python db_query.py --config ../config.yaml --sql-file ../report.sql --report-sql-max-rows 100
```

### scaffold_report_deliverable.py

生成报表交付物骨架。

```bash
# 生成销售订单报表骨架
python scaffold_report_deliverable.py "销售订单报表"

# 指定输出目录
python scaffold_report_deliverable.py "销售订单报表" --output-dir /path/to/output

# 覆盖已存在文件
python scaffold_report_deliverable.py "销售订单报表" --force
```

---

## 高级用法

### 1. 并行配置调优

当元数据量大时，调整 `performance` 配置：

```yaml
performance:
  max_concurrent_query_by_uri: 32   # 增加 URI 查询并发
  max_concurrent_bills: 8           # 增加单据并行数
  max_concurrent_entities: 16       # 增加实体并行数
  max_reference_fields_expand: 50   # 增加参照展开数
```

### 2. 多数据库支持

Oracle 配置示例（配合 `.env` 使用）：

```yaml
database:
  enabled: "${DB_ENABLED:-true}"
  driver: "${DB_DRIVER:-oracle}"
  host: "${DB_HOST:-192.168.1.100}"
  port: "${DB_PORT:-1521}"
  user: "${DB_USER:-system}"
  password: "${DB_PASSWORD}"
  service_name: "${DB_SERVICE_NAME:-ORCLPDB1}"
```

### 3. 自定义诊断查询

添加自定义数据库查询：

```yaml
database:
  queries:
    custom_check:
      enabled: true
      sql: |
        SELECT
          table_name,
          num_rows,
          blocks
        FROM user_tables
        WHERE num_rows > 10000
```

### 4. Token 缓存优化

Token 默认存储在进程内存中。可通过设置 `token_refresh_skew_seconds` 调整刷新时机：

```yaml
api:
  token_refresh_skew_seconds: 300   # 提前 5 分钟刷新
  token_fallback_ttl_seconds: 7200   # 无 expire 时 2 小时有效期
```

---

## 故障排查

### 1. 签名不正确

**症状**：API 返回"签名不正确"

**原因**：HTTP 客户端对参数值进行了二次编码

**解决**：确保 `bip_auth.py` 中的 `_request_get_java_style` 不使用 `requests(params=...)`

### 2. Token 获取失败

**症状**：`access_token` 响应中无 token

**检查**：
- `config.yaml` 中 `app_key` / `app_secret` 是否正确
- 成功码是否为 `"00000"`（五个零）
- 网络是否可达 `base_url`

### 3. 元数据拉取超时

**症状**：请求超时或响应缓慢

**解决**：
```yaml
performance:
  max_concurrent_query_by_uri: 8   # 降低并发
api:
  http_timeout_seconds: 180       # 增加超时时间
```

### 4. SQL 校验失败

**症状**：`db_query.py` 执行报错

**检查**：
- 数据库连接信息是否正确
- 用户是否有执行权限
- SQL 语法是否正确

### 5. 中文乱码

**症状**：输出中文显示为乱码

**解决**：
```bash
# Windows
chcp 65001

# 或设置环境变量
set PYTHONIOENCODING=utf-8
```

### 6. PEP 668 错误

**症状**：`pip install` 报错 "externally-managed-environment"（这是系统 Python 防止破坏全局环境的保护机制）

**解决**：

如果你**还没有虚拟环境**：`pip_install.sh`（Windows 为 `pip_install.cmd`）脚本会自动在 `scripts/.venv` 创建虚拟环境，无需手动操作：
```bash
./pip_install.sh run fetch_metadata.py ...
```
在 **Windows** 上请将上述命令中的 `./pip_install.sh` 换为 `pip_install.cmd`（参数不变）。

如果你**已经激活了虚拟环境**（如 conda、venv 等）：可以直接跳过自动创建，直接运行：
```bash
# 确认已在虚拟环境中
which python
# 直接安装依赖
pip install -r requirements-minimal.txt
# 直接运行脚本
python fetch_metadata.py ...
```

如果你想**手动创建**：
```bash
cd scripts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-minimal.txt
```

> **注意**：`requirements.txt` 包含所有可选数据库驱动（如 Oracle、达梦等），某些驱动在特定平台上难以安装。
> 默认安装 `requirements-minimal.txt`（MySQL + 基础依赖），如需其他驱动请手动安装。

---

## 最佳实践

1. **始终校验**：交付 SQL 前必须运行 `db_query.py --sql-file`
2. **分离配置**：敏感信息使用环境变量
3. **增量拉取**：大单据分批拉取
4. **版本控制**：提交配置前验证有效性
5. **文档同步**：更新报表说明文档

---

## API 参考

### 内部模块

| 模块 | 用途 |
|------|------|
| `utils` | 共享工具函数 |
| `logging_config` | 日志配置 |
| `metadata_parse` | 元数据解析 |
| `paths_util` | 路径解析 |
| `bip_auth` | 认证与 HTTP |

### Exit Codes

| Code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 配置错误 |
| 2 | 网络错误 |
| 3 | 校验失败 |
| 4 | 文件错误 |
| 99 | 未知错误 |
