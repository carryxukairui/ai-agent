package com.karry.ruiaiagent.demo.invoke;// 建议dashscope SDK的版本 >= 2.12.0

import java.util.Arrays;
import java.lang.System;

import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.utils.JsonUtils;
import com.karry.ruiaiagent.service.TestApiKey;

// 阿里云 DashScope SDK 调用 AI 模型
public class SdkAiInvoke {

    public static GenerationResult callWithMessage() throws ApiException, NoApiKeyException, InputRequiredException {
        // 创建 Generation 实例，用于调用 AI 模型
        Generation gen = new Generation();

        // 构建系统消息，指导 AI 行为
        Message systemMsg = Message.builder()
                .role(Role.SYSTEM.getValue())
                .content("You are a helpful assistant.")
                .build();

        // 构建用户消息，表示用户的提问
        Message userMsg = Message.builder()
                .role(Role.USER.getValue())
                .content("你是谁？")
                .build();

        // 构造请求参数
        GenerationParam param = GenerationParam.builder()
                // 设置 API Key，用于身份验证
                .apiKey(TestApiKey.API_KEY)
                // 指定使用的模型名称
                .model("qwen-plus")
                // 设置消息列表，包含系统消息和用户消息
                .messages(Arrays.asList(systemMsg, userMsg))
                // 设置结果格式为 MESSAGE
                .resultFormat(GenerationParam.ResultFormat.MESSAGE)
                .build();

        // 调用 AI 模型并返回结果
        return gen.call(param);
    }

    // 程序入口，用于测试调用 AI 模型的功能
    public static void main(String[] args) {
        try {
            // 调用 callWithMessage 方法获取 AI 生成结果
            GenerationResult result = callWithMessage();
            // 将结果转换为 JSON 字符串并打印
            System.out.println(JsonUtils.toJson(result));
        } catch (ApiException | NoApiKeyException | InputRequiredException e) {
            // 捕获异常并输出错误信息
            System.err.println("An error occurred while calling the generation service: " + e.getMessage());
        }
        // 程序正常退出
        System.exit(0);
    }
}
