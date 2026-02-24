package com.karry.ruiaiagent.rag;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.rag.Query;
import org.springframework.ai.rag.preretrieval.query.transformation.QueryTransformer;
import org.springframework.ai.rag.preretrieval.query.transformation.RewriteQueryTransformer;
import org.springframework.stereotype.Component;

/**
 * Rag 文档过滤和检索阶段
 * 查询重写器
 */
@Component
public class QueryRewriter {

    private final QueryTransformer queryTransformer;

    // 创建一个ChatModel实例
    public QueryRewriter(ChatModel dashscopeChatModel) {
        ChatClient.Builder chatClientBuilder = ChatClient.builder(dashscopeChatModel);
        queryTransformer = RewriteQueryTransformer.builder()
                .chatClientBuilder(chatClientBuilder)
                .build();
    }

    /**
     * 重写查询
     * @param prompt
     */
    public String doQueryRewrite(String prompt) {
        Query query = new Query(prompt);
        Query rewrittenQuery = queryTransformer.transform(query);
        return rewrittenQuery.text();
    }
}
