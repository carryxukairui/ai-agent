
# 开发规范指南

为保证代码质量、可维护性、安全性与可扩展性，请在开发过程中严格遵循以下规范。

## 一、项目环境与工具

- **操作系统**：Windows 11
- **工作目录**：`D:\javaProject\code\ai-agent`
- **工作区路径**：`D:\javaProject\code\ai-agent`
- **开发语言**：Java 21
- **构建工具**：Maven
- **作者**：28611
- **注释语言**：中文

## 二、技术栈要求

- **主框架**：Spring Boot 3.3.4
- **核心依赖**：
  - `spring-boot-starter-web`
  - `spring-boot-starter-jdbc`
  - `spring-boot-starter-mail`
  - `spring-ai-alibaba-starter` (1.0.0-M6.1)
  - `spring-ai-mcp-server-webflux-spring-boot-starter` (1.0.0-M6)
  - `spring-ai-vector-store-pgvector` (1.0.0-M7)
  - `dashscope-sdk-java` (2.19.1)
  - `knife4j-openapi3-jakarta-spring-boot-starter` (4.4.0)
  - `hutool-all` (5.8.37)

## 三、目录结构规范

本项目采用多模块结构，目录树如下：

```text
ai-agent
├── ai-image-search-mcp                  # 子模块：AI图片搜索MCP服务
│   └── src
│       ├── main
│       │   ├── java
│       │   │   └── com
│       │   │       └── karry
│       │   │           └── aiimagesearchmcp
│       │   │               └── tools
│       │   └── resources
│       └── test
│           └── java
│               └── com
│                   └── karry
│                       └── aiimagesearchmcp
│                           └── tools
│
├── rui-ai-agent-frontend                # 前端模块
│   └── src
│       ├── lib
│       ├── router
│       └── views
│           └── components
│
└── src                                  # 主模块：Rui AI Agent
    ├── main
    │   ├── java
    │   │   └── com
    │   │       └── karry
    │   │           └── ruiaiagent
    │   │               ├── advisors          # 拦截器/顾问
    │   │               ├── agent              # Agent定义
    │   │               ├── app                 # 应用层
    │   │               ├── chatMemory          # 聊天记忆
    │   │               ├── config              # 配置类
    │   │               ├── constant            # 常量
    │   │               ├── controller          # 控制器
    │   │               ├── demo                # 演示/调用示例
    │   │               │   └── invoke
    │   │               ├── rag                 # RAG相关
    │   │               ├── service             # 业务服务层
    │   │               └── tools               # 工具定义
    │   └── resources
    │       ├── document                      # 文档资源
    │       └── application.yaml
    └── test
        └── java
            └── com
                ├── agent
                └── ruiaiagent
```

## 四、分层架构规范

| 层级        | 职责说明                         | 开发约束与注意事项                                               |
|-------------|----------------------------------|----------------------------------------------------------------|
| **Controller** | 处理 HTTP 请求与响应，定义 API 接口 | 不得直接访问数据库或调用 AI SDK，必须通过 Service 层调用；使用 `@Valid` 校验 |
| **Service**    | 实现业务逻辑、事务管理与策略调用   | 必须通过 Agent 或 Repository 层调用；返回 DTO 而非 Entity（除非必要）；处理异步调用 |
| **Agent**      | 定义智能体行为、工具选择与策略     | 定义 Tool Calling 逻辑；配置 Prompt Template；处理 `@Transactional` 事务边界 |
| **RAG**        | 检索增强生成相关逻辑              | 使用 `VectorStore` 进行数据索引与检索；配置 PGVector 参数             |
| **Tools**      | 定义外部工具（如 MCP、API 调用）   | 封装第三方 API 调用逻辑；实现 Tool 接口；处理异常与日志               |

### 接口与实现分离

- 所有业务逻辑通过接口定义（如 `ChatService`），具体实现放在 `impl` 包中（如 `ChatServiceImpl`）。

## 五、安全与性能规范

### 输入校验

- 使用 `@Valid` 与 JSR-303 校验注解（如 `@NotBlank`, `@Size` 等）。
- 注意：Spring Boot 3.x 中校验注解位于 `jakarta.validation.constraints.*`。

### 敏感信息处理

- **严禁**在代码或配置文件中硬编码 `api-key`、`password` 等敏感信息。
- **当前配置**：项目中部分配置文件包含敏感信息（如 `application.yaml` 中的 API Key），**开发环境**请勿提交此类文件到版本控制，**生产环境**请务必使用环境变量或密钥管理服务。

### 事务管理

- `@Transactional` 注解仅用于 **Service 层**或 **Agent 层**方法。
- 避免在循环中频繁提交事务，影响性能。

## 六、代码风格规范

### 命名规范

| 类型       | 命名方式             | 示例                  |
|------------|----------------------|-----------------------|
| 类名       | UpperCamelCase       | `RuiAiAgent`          |
| 方法/变量  | lowerCamelCase       | `callDashScope()`     |
| 常量       | UPPER_SNAKE_CASE     | `MAX_RETRY_COUNT`     |

### 注释规范

- 所有类、方法、字段需添加 **中文 Javadoc** 注释。

### 类型命名规范（阿里巴巴风格）

| 后缀 | 用途说明                     | 示例         |
|------|------------------------------|--------------|
| DTO  | 数据传输对象                 | `ChatRequest`|
| DO   | 数据库实体对象               | `UserDO`     |
| BO   | 业务逻辑封装对象             | `SearchParam`|
| VO   | 视图展示对象                 | `ChatResponse`|
| Query| 查询参数封装对象             | `PageQuery`  |

### 实体类简化工具

- 使用 Lombok 注解替代手动编写 getter/setter/构造方法：
  - `@Data`
  - `@NoArgsConstructor`
  - `@AllArgsConstructor`

## 七、扩展性与日志规范

### 接口优先原则

- 所有业务逻辑通过接口定义（如 `ChatService`），具体实现放在 `impl` 包中（如 `ChatServiceImpl`）。

### 日志记录

- 使用 `@Slf4j` 注解代替 `System.out.println`。
- 日志级别：`debug` 用于调试，`info` 用于关键流程，`error` 用于异常捕获。

## 八、特定依赖使用规则

### Spring AI (MCP Server/WebFlux)

- 本项目使用 `spring-ai-mcp-server-webflux-spring-boot-starter`，主模块使用 `spring-ai-mcp-client-spring-boot-starter`。
- **注意**：MCP Server 需通过 `application.yaml` 配置 `spring.ai.mcp.client.sse.connections` 或 `stdio` 模式。

### PostgreSQL 向量存储

- 使用 `spring-ai-pgvector-store` 和 `spring-ai-starter-vector-store-pgvector`。
- **配置项**：
  - `index-type`: HNSW
  - `dimensions`: 1536
  - `distance-type`: COSINE_DISTANCE

## 九、编码原则总结

| 原则       | 说明                                       |
|------------|--------------------------------------------|
| **SOLID**  | 高内聚、低耦合，增强可维护性与可扩展性     |
| **DRY**    | 避免重复代码，提高复用性                   |
| **KISS**   | 保持代码简洁易懂                           |
| **YAGNI**  | 不实现当前不需要的功能                     |
| **OWASP**  | 防范常见安全漏洞，如 SQL 注入、XSS 等      |
