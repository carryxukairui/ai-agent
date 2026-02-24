package com.karry.ruiaiagent.advisors;


import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.advisor.api.*;
import org.springframework.ai.chat.messages.*;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 恋爱对象智能匹配 Advisor（自定义 RAG Advisor）
 */
@Slf4j
public class DatingMatchAdvisor implements CallAroundAdvisor {

    private final VectorStore vectorStore;

    /**
     * 召回候选对象数量
     */
    private final int topK;

    public DatingMatchAdvisor(VectorStore vectorStore, int topK) {
        this.vectorStore = vectorStore;
        this.topK = topK;
    }


    @Override
    public String getName() {
        return this.getClass().getSimpleName();
    }

    @Override
    public int getOrder() {
        return 3;
    }

    @Override
    public AdvisedResponse aroundCall(AdvisedRequest advisedRequest, CallAroundAdvisorChain chain) {
        // 1️⃣ 提取用户问题
        String userQuestion = advisedRequest.userText();

        // 2️⃣ 从“恋爱对象向量库”中召回候选人
        List<Document> documents =
                vectorStore.similaritySearch(
                        SearchRequest.builder()
                                .query(userQuestion)
                                .topK(topK)
                                .filterExpression("fileName == '约会对象.md'")
                                .build()
                );

        if (documents.isEmpty()) {
            log.warn("未召回任何恋爱对象文档");
            return chain.nextAroundCall(advisedRequest);
        }
        // 3. 拼接恋爱对象上下文
        String context = documents.stream()
                .map(Document::getText)
                .collect(Collectors.joining("\n\n"));
        // 4. 构造增强 Prompt
        String ragPrompt = """
                你是一位专业的恋爱匹配顾问。
                以下是可能的恋爱对象信息：
                ---------------------
                %s
                ---------------------
                用户的问题是：
                %s
                请根据用户的需求，从上述恋爱对象中推荐合适的人选，
                并说明推荐理由。
                """.formatted(context, userQuestion);

        log.info("RAG Prompt: {}", ragPrompt);
        // 5. 替换用户消息
        List<Message> newMessages = new ArrayList<>();
        advisedRequest.messages().stream()
                .filter(m -> m.getMessageType() == MessageType.SYSTEM)
                .forEach(newMessages::add);
        newMessages.add(new UserMessage(ragPrompt));

        AdvisedRequest newRequest = AdvisedRequest.builder()
                .chatModel(advisedRequest.chatModel())
                .systemText(advisedRequest.systemText())
                .messages(newMessages)
                .userText(ragPrompt)
                .build();

        // 6. 继续调用 LLM
        return chain.nextAroundCall(newRequest);
    }
}
