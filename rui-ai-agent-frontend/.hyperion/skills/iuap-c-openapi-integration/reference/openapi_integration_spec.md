# OpenAPI集成公共规范

> **来源**: openapi_integ_skill
> **用途**: 提供第三方系统API集成的通用规范，包括MCP技能调用决策、公共执行流程。

---

## 1. MCP技能调用决策

> **核心原则**: 根据不同条件自动判断场景，精准调用对应的MCP技能

### 调用决策表

| 场景 | 触发条件 | 调用的MCP技能 |
|------|---------|--------------|
| BIP数据查询 | 需要查询BIP数据 | `getOpenApiCall` |
| API调用代码生成 | 需要生成调用代码 | `getOpenApiCall` |
| 第三方API调用 | 需要调用第三方接口 | 动态生成调用代码 |

### 强制调用规则

| 任务 | 规则 | 错误示例 | 正确示例 |
|------|------|---------|---------|
| BIP查询 | 禁止手动编写API调用代码 | 手动编写HttpClient/RestTemplate | 调用getOpenApiCall获取代码 |
| 第三方调用 | 禁止只加TODO | `// TODO 调用第三方接口` | 生成完整调用代码 |

---

## 2. 执行流程架构

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    执行流程                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  1.Controller │ -> │  2.参数校验  │ -> │  3.获取鉴权  │ -> │  4.API调用   │    │
│  │   接收请求    │    │  Validate    │    │  GetToken   │    │  InvokeAPI   │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    │
│                                                                                     │
│  ┌──────────────┐    ┌──────────────┐                                               │
│  │  5.响应解析  │ -> │  6.结果返回  │                                               │
│  │  ParseResp  │    │  Response    │                                               │
│  └──────────────┘    └──────────────┘                                               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 架构分层与职责

| 层级 | 文件 | 职责 | 引用要求 |
|------|------|------|----------|
| Controller | *Controller.java | 接收请求、参数校验、调用Service | 必须 |
| Service | *Service.java | 业务逻辑、API调用 | 必须 |
| Util | *Util.java | 工具类、HTTP调用 | 按需 |
| Config | *Config.java | 配置类 | 按需 |

### 关键约束

> **Controller禁止包含业务逻辑**：只负责接收请求、参数校验、调用Service、返回结果

---

## 4. OpenAPI调用服务

### 4.1 服务接口定义

```java
public interface IOpenApiCallService {
    /**
     * 调用BIP OpenAPI
     * @param apiPath API路径
     * @param params 请求参数
     * @return 响应结果
     */
    String callBipApi(String apiPath, Map<String, Object> params);

    /**
     * 调用第三方API
     * @param url 请求地址
     * @param method 请求方法
     * @param params 请求参数
     * @return 响应结果
     */
    String callThirdPartyApi(String url, String method, Map<String, Object> params);

    /**
     * 获取BIP AccessToken
     * @return access_token
     */
    String getAccessToken();
}
```

### 4.2 实现规范

```java
@Service
public class OpenApiCallServiceImpl implements IOpenApiCallService {

    @Value("${bip.base.url}")
    private String bipBaseUrl;

    @Override
    public String callBipApi(String apiPath, Map<String, Object> params) {
        String accessToken = getAccessToken();
        String url = bipBaseUrl + apiPath;

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + accessToken);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(params, headers);
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.exchange(
            url, HttpMethod.POST, request, String.class
        );

        return response.getBody();
    }

    @Override
    public String getAccessToken() {
        String token = redisTemplate.opsForValue().get("bip_access_token");
        if (StringUtils.isBlank(token)) {
            token = refreshAccessToken();
            redisTemplate.opsForValue().set("bip_access_token", token, 2, TimeUnit.HOURS);
        }
        return token;
    }
}
```

---

## 5. 鉴权处理规范

### 5.1 BIP鉴权

```java
@Service
public class AuthService {

    public String getAccessToken() {
        String tokenKey = "bip_access_token";
        String token = redisTemplate.opsForValue().get(tokenKey);

        if (StringUtils.isBlank(token)) {
            token = refreshAccessToken();
            redisTemplate.opsForValue().set(tokenKey, token, 2, TimeUnit.HOURS);
        }
        return token;
    }

    private String refreshAccessToken() {
        String url = bipBaseUrl + "/oauth2/token";

        Map<String, String> params = new HashMap<>();
        params.put("grant_type", "client_credentials");
        params.put("client_id", appKey);
        params.put("client_secret", appSecret);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        HttpEntity<Map<String, String>> request = new HttpEntity<>(params, headers);
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.exchange(
            url, HttpMethod.POST, request, String.class
        );

        JSONObject result = JSONObject.parseObject(response.getBody());
        return result.getString("access_token");
    }
}
```

### 5.2 第三方鉴权

```java
@Service
public class ThirdPartyAuthService {

    public String getThirdPartyToken(String systemCode) {
        // 根据systemCode获取对应第三方系统的鉴权信息
        // 典型场景：诺诺发票、航天金税等第三方系统
    }
}
```

---

## 6. HTTP调用工具

### RestTemplate配置

```java
@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(30000);  // 30秒连接超时
        factory.setReadTimeout(30000);       // 30秒读取超时
        return new RestTemplate(factory);
    }
}
```

---

## 7. 错误处理规范

### API调用异常处理

```java
@Override
public String callBipApi(String apiPath, Map<String, Object> params) {
    try {
        String accessToken = getAccessToken();
        String url = bipBaseUrl + apiPath;

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + accessToken);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(params, headers);
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.exchange(
            url, HttpMethod.POST, request, String.class
        );

        return response.getBody();
    } catch (HttpClientErrorException e) {
        // 处理4xx错误
        throw new BusinessException("API调用失败: " + e.getStatusCode());
    } catch (HttpServerErrorException e) {
        // 处理5xx错误
        throw new BusinessException("API服务端错误: " + e.getStatusCode());
    } catch (Exception e) {
        throw new BusinessException("API调用异常: " + e.getMessage());
    }
}
```

### 响应结果解析

```java
public class ApiResponse<T> {
    private boolean success;
    private String code;
    private String message;
    private T data;

    public static <T> ApiResponse<T> parse(String responseBody, Class<T> dataClass) {
        JSONObject json = JSONObject.parseObject(responseBody);
        ApiResponse<T> response = new ApiResponse<>();
        response.setSuccess(json.getBooleanValue("success"));
        response.setCode(json.getString("code"));
        response.setMessage(json.getString("message"));
        if (json.containsKey("data")) {
            response.setData(json.getObject("data", dataClass));
        }
        return response;
    }
}
```

---

## 8. 场景路由规则

| 场景 | 路由目标 | 触发条件 |
|------|---------|----------|
| BIP数据查询 | bip_query_spec.md | 关键词包含"BIP查询"/"BIP数据" |
| 第三方接口 | third_party_spec.md | 关键词包含"第三方"/"税局"/"开票" |
| 鉴权处理 | auth_spec.md | 关键词包含"鉴权"/"token" |

---

## 9. 技能触发条件

| 关键词 | 触发场景 |
|--------|---------|
| API调用 / OpenAPI / 接口调用 | OpenAPI调用场景 |
| BIP查询 / BIP数据 | BIP数据查询场景 |
| 第三方接口 / 税局接口 / 开票接口 | 第三方接口调用 |
| 鉴权 / token / access_token | 鉴权处理场景 |