package com.karry.ruiaiagent.tools;

import cn.hutool.http.HttpUtil;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class WebSearchTool {

    // SearchAPI 的搜索接口地址
    private static final String SEARCH_API_URL = "https://www.searchapi.io/api/v1/search";

    private final String apiKey;

    public WebSearchTool(String apiKey) {
        this.apiKey = apiKey;
    }


    /**
     * {
     *   "organic_results": [
     *     ...
     *     {
     *       "position": 1,
     *       "title": "编程导航 - 程序员一站式编程学习交流社区,做您编程学习路...",
     *       "link": "https://codefather.cn/",
     *       "displayed_link": "codefather.cn/",
     *       "snippet": "学编程,就来编程导航,程序员免费编程学习交流社区。Java,Python,前端,web网站开发,C语言,C++,Go,后端,SQL,数据库,PHP入门学习、技能提升、求职面试法宝。提升编程效率、优质IT技术文章、海...",
     *       "snippet_highlighted_words": [
     *         "编程",
     *         "编程导航",
     *         "程序员"
     *       ],
     *       "thumbnail": "https://t8.baidu.com/it/u=661528516,2886240705&fm=217&app=126&size=f242,150&n=0&f=JPEG&fmt=auto?s=73B489634AD237E3660C19280200A063&sec=1744477200&t=b5d8762a6f5728d5f2fbc6bcf1774b20"
     *     },
     *     ...
     *   ]
     * }
     * @param query
     * @return
     */

    @Tool(description = "Search for information from Baidu Search Engine")
    public String searchWeb(
            @ToolParam(description = "Search query keyword") String query) {
        Map<String, Object> paramMap = new HashMap<>();
        paramMap.put("q", query);
        paramMap.put("api_key", apiKey);
        paramMap.put("engine", "baidu");
        try {
            String response = HttpUtil.get(SEARCH_API_URL, paramMap);
            // 取出返回结果的前 5 条
            JSONObject jsonObject = JSONUtil.parseObj(response);
            // 提取 organic_results 部分
            JSONArray organicResults = jsonObject.getJSONArray("organic_results");
            List<Object> objects = organicResults.subList(0, 5);
            // 拼接搜索结果为字符串
            String result = objects.stream().map(obj -> {
                JSONObject tmpJSONObject = (JSONObject) obj;
                return tmpJSONObject.toString();
            }).collect(Collectors.joining(","));
            return result;
        } catch (Exception e) {
            return "Error searching Baidu: " + e.getMessage();
        }
    }
}
