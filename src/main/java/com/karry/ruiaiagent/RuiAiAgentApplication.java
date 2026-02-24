package com.karry.ruiaiagent;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 恋爱 AI 助手 —— Spring Boot 启动入口
 *
 * <p>技术栈：
 * <ul>
 *   <li>Spring Boot 3.3.4 + Java 21</li>
 *   <li>Spring AI / Spring AI Alibaba —— 接入阿里云 DashScope（通义千问）大模型</li>
 *   <li>PostgreSQL + pgvector —— 向量数据库，用于 RAG 语义检索</li>
 *   <li>Kryo —— 高性能二进制序列化，用于文件持久化对话记忆</li>
 *   <li>Aho-Corasick —— 多模式字符串匹配算法，用于敏感词过滤</li>
 * </ul>
 *
 * <p>核心功能：
 * <ol>
 *   <li>多轮对话：基于文件持久化 {@link com.karry.ruiaiagent.chatMemory.FileBaseChatsMemory} 保留上下文</li>
 *   <li>敏感词拦截：{@link com.karry.ruiaiagent.advisors.ForbiddenWordAdvisor} 在请求到达模型前过滤违规内容</li>
 *   <li>本地 RAG：加载 Markdown 知识库并写入内存向量库，结合 QuestionAnswerAdvisor 做语义增强</li>
 *   <li>云端 RAG：通过阿里云百炼平台的知识索引"恋爱大师"进行检索增强</li>
 *   <li>恋爱对象匹配：{@link com.karry.ruiaiagent.advisors.DatingMatchAdvisor} 从向量库召回候选人，交由大模型推荐</li>
 *   <li>结构化输出：将大模型返回内容直接映射为 Java Record（LoveReport）</li>
 * </ol>
 */
@SpringBootApplication
public class RuiAiAgentApplication {

    public static void main(String[] args) {
        SpringApplication.run(RuiAiAgentApplication.class, args);
    }

}
