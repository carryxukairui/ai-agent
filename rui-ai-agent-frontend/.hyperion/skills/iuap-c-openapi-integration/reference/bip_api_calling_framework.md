# BIP标准API调用框架

> **来源**: bip_base_api_skill
> **用途**: 提供BIP平台OpenAPI的标准化调用流程，适用于任何需要与BIP平台交互的场景。

## 1. 架构概述

```
┌─────────────────────────────────────────────────────────────────┐
│                      业务服务层                                  │
│              (Business Service - 业务调用方)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BIP API 调用框架                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   鉴权模块   │    │  HTTP调用模块 │    │  响应解析模块 │          │
│  │AccessToken │    │OpenApiUtils │    │ JSON解析   │          │
│  │  Utils    │    │             │    │           │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BIP OpenAPI 平台                             │
│         (网关地址 + API URI + AccessToken)                       │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 核心调用流程

### Step 1: 配置初始化

```java
// application.yml 配置
bip:
  appKey: your_app_key
  appSecret: your_app_secret

domain:
  url: http://your-domain
```

### Step 2: 获取AccessToken

```java
// Token获取流程
String accessToken = accessTokenUtils.getAccessToken(
    openAuthHost,    // 认证域名: domain.url + /iuap-api-auth
    appKey,          // 应用Key
    appSecret        // 应用密钥
);
```

### Step 3: 构建请求URL

```
完整URL = openGatewayHost + apiUri + "?access_token=" + accessToken + "&业务参数"

示例: https://domain/iuap-api-gateway/yonbip/sd/vouchersaleinvoice/detail?access_token=xxx&id=yyy
```

### Step 4: 发起调用

| 场景 | 推荐方式 | 说明 |
|------|---------|------|
| 查询详情 | GET | 参数拼接在URL中 |
| 分页查询 | POST | 请求体包含分页参数和查询条件 |
| 保存/更新 | POST | 请求体包含完整业务数据 |
| 批量操作 | POST | 请求体包含批量数据数组 |

### Step 5: 解析响应

```java
// 标准响应格式
if ("200".equals(response.get("code"))) {
    Object data = response.get("data");
    return JSONObject.parseObject(JsonUtils.toJson(data));
}
```

## 3. 鉴权模块

### Token获取流程

```java
public String getAccessToken(String openApiUrl, String appKey, String appSecret) {
    Map<String, Object> params = new HashMap<>();
    params.put("appKey", appKey);
    params.put("timestamp", String.valueOf(System.currentTimeMillis()));
    params.put("signature", SignHelper.sign(params, appSecret));  // HMAC-SHA256签名
    
    String requestUrl = openApiUrl + "/open-auth/selfAppAuth/getAccessToken";
    JSONObject response = HttpClient.get(requestUrl, params);
    
    return response.getJSONObject("data").getString("access_token");
}
```

### 签名算法

```
1. 参数按 key 排序
2. 拼接为 key1value1key2value2...
3. HMAC-SHA256(appSecret, 拼接字符串)
4. Base64 编码
5. URL 编码
```

## 4. 网关与认证地址

| 地址类型 | URI模板 | 说明 |
|---------|---------|------|
| 网关地址 | `/iuap-api-gateway` | 所有业务API通过网关调用 |
| 认证地址 | `/iuap-api-auth` | Token获取专用地址 |
| Token接口 | `/open-auth/selfAppAuth/getAccessToken` | Token获取路径 |

## 5. 响应标准格式

### 成功响应

```json
{
    "code": "200",
    "data": { ... },
    "message": "success"
}
```

### 错误响应

```json
{
    "code": "500",
    "message": "错误描述",
    "detailMessage": "详细错误信息"
}
```

## 6. 异常处理规范

```java
try {
    Map<String, Object> result = OpenApiUtils.getMethod(params, url);
    
    if (!"200".equals(result.get("code"))) {
        throw new BusinessException("API调用失败: " + result.get("message"));
    }
    
    return result.get("data");
} catch (Exception e) {
    LOGGER.error("调用BIP API异常", e);
    throw new BusinessException("调用BIP接口失败: " + e.getMessage());
}
```

## 7. 最佳实践

| 实践 | 说明 |
|------|------|
| 统一入口 | 所有BIP API调用必须经过统一框架 |
| 配置分离 | API地址、密钥等配置放在配置文件中 |
| Token缓存 | 生产环境建议实现Token缓存机制，避免频繁请求 |
| 超时控制 | 为RestTemplate配置连接超时和读取超时 |
| 日志记录 | 记录请求URL、参数、响应状态 |

## 8. 扩展建议

| 扩展 | 说明 |
|------|------|
| Token自动刷新 | 实现Token过期自动刷新机制 |
| 熔断降级 | 集成Sentinel或Hystrix实现熔断 |
| 请求追踪 | 添加请求ID便于日志追踪 |