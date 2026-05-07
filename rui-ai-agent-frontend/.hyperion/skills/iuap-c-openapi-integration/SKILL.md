---
name: iuap-c-openapi-integration
description: >-
  BIP旗舰版 OpenAPI 集成技能：通过自然语言描述查询业务接口定义（OpenAPI文档），提供完整的
  API调用流程支持（鉴权、HTTP调用、响应解析）。返回接口 URL、请求方式、入参出参结构
  （AI 友好的 JSON 格式）。支持从用户话术中提取接口搜索关键词和入参关注点。
  增强特性：重试机制、熔断保护、限流控制、并行查询、响应缓存、环境变量支持。
  **执行本技能时必须先读取 skills/iuap-c-openapi-integration/reference 下全部参考文档（bip_api_calling_framework、openapi_integration_spec 等）再作答或执行脚本。**
references:
  - name: bip_api_calling_framework
    description: BIP标准API调用框架（鉴权、HTTP调用、响应解析）
    path: ./reference/bip_api_calling_framework.md
  - name: openapi_integration_spec
    description: OpenAPI集成公共规范（分层架构、异常处理）
    path: ./reference/openapi_integration_spec.md
---

# BIP OpenAPI 集成（iuap-c-openapi-integration）

## 执行前必读（强制）

在依据本技能回答用户、运行脚本或给出调用方案前，**必须先获取并通读** `reference` 目录下的全部文件（随技能演进可能增加新文件，以目录内实际文件为准）：

- **绝对路径（本仓库）**：`/Users/zhangchaocai/Documents/project/nexacodeagent/.hyperion/skills/iuap-c-openapi-integration/reference`
- **相对路径**（自技能根目录，任意克隆位置通用）：`./reference/`
- **当前已包含**：[bip_api_calling_framework.md](reference/bip_api_calling_framework.md)、[openapi_integration_spec.md](reference/openapi_integration_spec.md)

未读取上述 reference 前，不得仅依赖本 SKILL 正文做鉴权/分层/异常处理等结论；`bip_api_calling_framework` 与 `openapi_integration_spec` 为规范来源，正文为操作说明。

## Reference 引用

本技能整合了两个专业的API对接框架作为 Reference：

| Reference | 来源 | 用途 |
|-----------|------|------|
| [bip_api_calling_framework.md](reference/bip_api_calling_framework.md) | bip_base_api_skill | BIP标准API调用框架（鉴权、HTTP调用、响应解析） |
| [openapi_integration_spec.md](reference/openapi_integration_spec.md) | openapi_integ_skill | OpenAPI集成公共规范（分层架构、异常处理） |

## 新特性

| 特性 | 说明 |
|------|------|
| **请求重试** | 自动重试失败请求，指数退避策略 |
| **熔断器** | 防止持续请求不稳定服务 |
| **限流器** | 控制请求频率，避免触发限流 |
| **并行查询** | 多个描述并行执行，加速查询 |
| **响应缓存** | 减少 API 重复查询 |
| **安全配置** | 支持环境变量，避免硬编码密钥 |
| **单元测试** | 完整的测试覆盖 |

## 何时使用

- 用户需要**按描述查找业务接口**，拿到接口 URL、请求方式、入参与出参结构。
- 典型话术：「销售发票列表查询接口是什么」「查客户档案 API」「接口入参出参」等。

## 配置

编辑本技能目录下的 [config.yaml](config.yaml) 或使用 [.env](.env) 环境变量文件。

### 安全配置（重要）

**推荐使用 `.env` 文件存储敏感信息**：

```bash
# 在技能目录下创建 .env 文件
API_BASE_URL=https://c1pocpro.yonyoucloud.com/
API_APP_KEY=your_app_key
API_APP_SECRET=your_app_secret
```

支持的语法：
- `${VAR}` — 环境变量，不存在则为空字符串
- `${VAR:-default}` — 环境变量，不存在则使用 default

### 关键配置段

| 配置段 | 说明 |
|--------|------|
| `api` | 开放平台鉴权（base_url、app_key、app_secret、token 缓存） |
| `business_interface` | 列表/详情接口路径、成功码、分页大小 |
| `rate_limit` | 限流配置（requests_per_second、burst_capacity） |
| `cache` | 缓存配置（enabled、ttl_seconds） |
| `logging` | 日志级别和格式 |

## 从用户话术解析并注入 `request`（Agent 必做）

开放平台列表接口只接收**一条字符串** `param` 用于匹配接口。Agent 需从用户自然语言中拆出两类信息：

1. **接口匹配用语** → `allInterfaceDesc`（多条用英文逗号分隔）
2. **入参相关表述** → `interface_input_hints`（关键词或短语，逗号/顿号分隔）

### 映射表（话术 → `request`）

| 配置项 | 从话术识别 | 典型取值 |
|--------|-----------|----------|
| `allInterfaceDesc` | 「XX 列表查询接口」「查客户档案的 API」中的接口描述 | `销售发票列表查询` 或 `查询客户档案,采购订单提交` |
| `interface_input_hints` | 「要传组织」「带客户编码」「分页」→ 拆成短词 | `组织,客户编码,pageIndex` |

## 命令行用法

### 基本用法

```bash
cd scripts

# 安装依赖（仅首次）
./pip_install.sh

# 单个查询（使用 pip_install.sh run 自动管理环境）
./pip_install.sh run business_interface_query.py --config ../config.yaml \
  --all-interface-desc "销售发票列表查询"

# 或手动激活虚拟环境后执行
source .venv/bin/activate
python business_interface_query.py --config ../config.yaml \
  --all-interface-desc "销售发票列表查询"

# Windows（PowerShell / CMD）：用 pip_install.cmd 代替 ./pip_install.sh，逻辑与 bash 版一致
# pip_install.cmd
# pip_install.cmd run business_interface_query.py --config ..\config.yaml --all-interface-desc "销售发票列表查询"

# 带入参关注点
python business_interface_query.py --config ../config.yaml \
  --all-interface-desc "销售发票列表查询" \
  --interface-input-hints "组织,客户,分页"
```

### 并行查询（新）

```bash
# 多个描述并行执行
python business_interface_query.py --config ../config.yaml \
  --all-interface-desc "销售发票列表查询,采购订单提交,客户档案查询" \
  --parallel --max-workers 5
```

### 缓存控制（新）

```bash
# 禁用缓存
python business_interface_query.py --config ../config.yaml \
  --all-interface-desc "销售发票列表查询" \
  --no-cache

# 清除缓存
python business_interface_query.py --config ../config.yaml \
  --clear-cache
```

### 运行测试

```bash
cd scripts
python -m pytest tests/ -v

# 带覆盖率
python -m pytest tests/ -v --cov=. --cov-report=html
```

## 脚本说明

| 脚本 | 作用 |
|------|------|
| [business_interface_query.py](scripts/business_interface_query.py) | 主查询逻辑，支持并行、缓存、重试 |
| [bip_auth.py](scripts/bip_auth.py) | Token 管理，含熔断器、限流器 |
| [retry_utils.py](scripts/retry_utils.py) | 重试、熔断器、限流器工具 |
| [secure_config.py](scripts/secure_config.py) | 安全配置加载，环境变量支持 |

## 输出格式

### AI 友好 JSON 结构

```json
{
  "接口地址": "https://api.example.com/orders",
  "请求协议": "HTTP",
  "请求方式": "POST",
  "入参列表": [
    {
      "参数名": "orgId",
      "参数描述": "组织ID",
      "参数类型": "String",
      "子参数": []
    }
  ],
  "出参结构": {
    "id": {"描述": "单据ID", "类型": "Long"}
  },
  "用户话术中的入参关注点": ["组织", "客户"],
  "与关注点匹配的入参": [...],
  "代码生成提示": "..."
}
```

## 常见问题

### Token 获取失败

检查：
1. `app_key` / `app_secret` 是否正确
2. 成功码应为 `"00000"`（开放平台）
3. 网络连接是否正常

### 限流触发

调整 `config.yaml`：
```yaml
rate_limit:
  requests_per_second: 5.0  # 降低频率
  burst_capacity: 10.0      # 降低突发容量
```

### PEP 668 错误（externally-managed-environment）

**症状**：`pip install` 报错 "externally-managed-environment"，这是系统 Python 防止破坏全局环境的保护机制。

**解决**：

- **如果你还没有虚拟环境**：`pip_install.sh`（Windows 为 `pip_install.cmd`）会**自动**在 `scripts/.venv` 创建虚拟环境，无需手动操作：
  ```bash
  ./pip_install.sh run business_interface_query.py ...
  ```
  在 **Windows** 上请将 `./pip_install.sh` 换为 `pip_install.cmd`。

- **如果你已经激活了虚拟环境**（如 conda、venv 等）：可以直接跳过自动创建，直接运行：
  ```bash
  # 确认已在虚拟环境中
  which python
  # 直接安装依赖
  pip install -r requirements.txt
  # 直接运行脚本
  python business_interface_query.py ...
  ```

- **如果你想手动创建**：
  ```bash
  cd scripts
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## 变更日志

### v2.0 (当前)
- 新增请求重试机制
- 新增熔断器保护
- 新增限流器
- 新增并行查询支持
- 新增响应缓存
- 新增安全配置（环境变量支持）
- 新增单元测试覆盖
- 消除重复 HTTP 代码
- 改进错误处理

### v1.0
- 基本查询功能
- Token 缓存
- 入参关注点匹配