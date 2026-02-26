package com.karry.ruiaiagent.app;


import com.karry.ruiaiagent.advisors.DatingMatchAdvisor;
import com.karry.ruiaiagent.advisors.ForbiddenWordAdvisor;
import com.karry.ruiaiagent.advisors.MyLoggerAdvisors;
import com.karry.ruiaiagent.chatMemory.FileBaseChatsMemory;
import com.karry.ruiaiagent.rag.LoveAppRagCustomAdvisorFactory;
import com.karry.ruiaiagent.rag.QueryRewriter;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.client.advisor.QuestionAnswerAdvisor;
import org.springframework.ai.chat.client.advisor.api.Advisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.tool.ToolCallingManager;
import org.springframework.ai.model.tool.ToolExecutionResult;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Set;

import static org.springframework.ai.chat.client.advisor.AbstractChatMemoryAdvisor.CHAT_MEMORY_CONVERSATION_ID_KEY;
import static org.springframework.ai.chat.client.advisor.AbstractChatMemoryAdvisor.CHAT_MEMORY_RETRIEVE_SIZE_KEY;

/**
 * 恋爱 AI 核心应用
 *
 * <p>封装了与大模型的所有交互逻辑，对外提供多种对话模式：
 * <ul>
 *   <li>{@link #doChat} —— 带记忆的基础多轮对话</li>
 *   <li>{@link #doChatWithReport} —— 对话并生成结构化恋爱报告</li>
 *   <li>{@link #doChatWithRag} —— 结合本地向量知识库的 RAG 对话</li>
 *   <li>{@link #doChatWithCloudRag} —— 结合阿里云百炼知识库的云端 RAG 对话</li>
 *   <li>{@link #doChatWithRagMatchUser} —— 基于知识库的恋爱对象匹配推荐</li>
 * </ul>
 *
 * <p>Advisor 执行顺序（order 值越小越先执行）：
 * <pre>
 *   ForbiddenWordAdvisor(1) → MessageChatMemoryAdvisor → MyLoggerAdvisors(0，按需挂载)
 *   → QuestionAnswerAdvisor / DatingMatchAdvisor（按需挂载）→ ChatModel
 * </pre>
 */
@Component
@Slf4j
public class LoveApp {

    /** 本地简单向量存储，由 {@link com.karry.ruiaiagent.rag.LoveAppVectorStoreConfig} 构建 */
    @Resource
    private VectorStore loveAppVectorStore;

    /** 云端 RAG Advisor，由 {@link com.karry.ruiaiagent.rag.LoveAppRagCloudAdvisorConfig} 构建 */
    @Resource
    private Advisor loveAppRagCloudAdvisor;

    /** 全局敏感词集合，传入 {@link ForbiddenWordAdvisor} 用于构建 Aho-Corasick Trie */
    Set<String> forbiddenWords = Set.of("暴力", "违法", "色情");
    @Resource
    private QueryRewriter queryRewriter;

    @Resource
    private ToolCallback[] allTools;
    @Resource
    private ToolCallingManager toolCallingManager;
    @Resource
    private ChatModel chatModel;

    @Resource
    private ToolCallbackProvider toolCallbackProvider;
    /**
     * 结构化输出：恋爱报告
     *
     * <p>Spring AI 支持将大模型的 JSON 响应直接反序列化为 Java Record，
     * 无需手动解析，只需在 {@code .call().entity(LoveReport.class)} 处声明目标类型即可。
     *
     * @param title       报告标题，通常为"{用户名}的恋爱报告"
     * @param suggestions 具体建议列表
     */
    public record LoveReport(String title, List<String> suggestions) {
    }

    /** Spring AI ChatClient —— 链式 Fluent API 构建器，封装了模型调用、Advisor 拦截链、对话记忆等能力 */
    private final ChatClient client;

    /**
     * 系统提示词模板
     *
     * <p>使用 {@code {type}} 和 {@code {answer}} 两个占位符，在构造时通过
     * {@code .param()} 注入，避免硬编码，便于后期灵活替换角色定位或回答风格。
     */
    private static final String SYSTEM_PROMPT = """
            扮演深耕 {type} 心理领域的专家。开场向用户表明身份，告知用户可倾诉恋爱难题。
            围绕单身、恋爱、已婚三种状态提问：单身状态询问社交圈拓展及追求心仪对象的困扰；
            恋爱状态询问沟通、习惯差异引发的矛盾；已婚状态询问家庭责任与亲属关系处理的问题。
            引导用户详述事情经过、对方反应及自身想法，以便给出专属解决{answer}。如果需要发送邮箱，就发送邮箱""";

    // 以下为早期使用 InMemoryChatMemory（内存记忆）的版本，已切换为文件持久化记忆，保留供参考
//    public LoveApp(@Qualifier("dashscopeChatModel")ChatModel dashcopeChatModel) {
//        ChatMemory chatMemory = new InMemoryChatMemory();
//        client = ChatClient.builder(dashcopeChatModel)
//                .defaultSystem(SYSTEM_PROMPT)
//                .defaultAdvisors(
//                        new MessageChatMemoryAdvisor(chatMemory),
//                        new MyAdvisors()
//                )
//                .build();
//    }

    /**
     * 构造 LoveApp，初始化 ChatClient
     *
     * <p>关键设计点：
     * <ol>
     *   <li>使用 {@link FileBaseChatsMemory} 将对话历史持久化到磁盘，服务重启后仍可恢复上下文</li>
     *   <li>{@link ForbiddenWordAdvisor} 作为 defaultAdvisor 注册，对所有对话方法生效，
     *       order=1 确保敏感词检测在记忆读写之前执行</li>
     *   <li>系统提示词通过 {@code .param()} 动态注入，与模板解耦</li>
     * </ol>
     *
     * @param dashscopeChatModel 通义千问大模型（由 Spring AI Alibaba 自动配置并注入）
     */
    public LoveApp(@Qualifier("dashscopeChatModel") ChatModel dashscopeChatModel) {
        // 对话记忆文件存储目录，位于项目运行目录下的 chat-memory 文件夹
        String fileDir = System.getProperty("user.dir") + "/chat-memory";
        ChatMemory chatMemory = new FileBaseChatsMemory(fileDir);
        client = ChatClient.builder(dashscopeChatModel)
                // 配置默认系统提示词，并注入模板变量
                .defaultSystem(system -> system
                        .text(SYSTEM_PROMPT)
                        .param("type", "恋爱")
                        .param("answer", "方案"))
                // 注册全局 Advisor：敏感词过滤 + 对话记忆
                .defaultAdvisors(
                        new ForbiddenWordAdvisor(forbiddenWords),
                        new MessageChatMemoryAdvisor(chatMemory)
                )
                .build();
    }

    /**
     * 基础多轮对话（支持持久化对话记忆）
     *
     * <p>{@code CHAT_MEMORY_CONVERSATION_ID_KEY} 指定会话 ID，不同 chatId 之间记忆完全隔离；
     * {@code CHAT_MEMORY_RETRIEVE_SIZE_KEY} 控制每次从历史记忆中取回的消息条数。
     *
     * @param message 用户当前输入的消息
     * @param chatId  会话唯一标识，用于区分不同用户/不同对话
     * @return 模型回复的文本内容
     */
    public String doChat(String message, String chatId) {
        ChatResponse chatResponse = client
                .prompt()
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 1))
                        .call()
                .chatResponse();
        String content = chatResponse.getResult().getOutput().getText();
        log.info("content: {}", content);

        return content;
    }

    /**
     * 对话并生成结构化恋爱报告
     *
     * <p>Spring AI 的 {@code .entity(Class)} 能力：将大模型输出的 JSON 自动反序列化为指定 Java 类型，
     * 相比手动解析 JSON 更简洁，且类型安全。
     *
     * @param message 用户消息
     * @param chatId  会话 ID
     * @return {@link LoveReport} 包含报告标题和建议列表
     */
    public LoveReport doChatWithReport(String message, String chatId) {
        LoveReport loveReport = client
                .prompt()
                .system(SYSTEM_PROMPT + "每次对话后都需要生成恋爱结果，标题为{用户名}的恋爱报告，内容为建议列表")
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 10))
                .call()
                // 直接将模型响应映射为 Java Record，Spring AI 内部自动处理 JSON Schema 生成和反序列化
                .entity(LoveReport.class);
        log.info("LoveReport: {}", loveReport);
        return loveReport;
    }

    /**
     * 结合本地 RAG 知识库的对话
     *
     * <p>{@link QuestionAnswerAdvisor} 是 Spring AI 提供的标准 RAG Advisor：
     * 它在请求发往大模型前，先用用户问题检索向量库，将召回的文档拼接进 Prompt，
     * 从而让模型基于知识库内容回答，减少"幻觉"。
     *
     * @param message 用户消息
     * @param chatId  会话 ID
     * @return 基于本地知识库增强后的模型回复
     */
    public String doChatWithRag(String message, String chatId) {
        ChatResponse response = client
                .prompt()
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 10))
                // 记录完整请求/响应日志，便于调试 RAG 效果
                .advisors(new MyLoggerAdvisors())
                // 核心：将本地向量库注入 RAG 检索，topK 默认为 4
                .advisors(new QuestionAnswerAdvisor(loveAppVectorStore))
                .call()
                .chatResponse();
        String content = response.getResult().getOutput().getText();
        log.info("content: {}", content);
        return content;
    }

    /**
     * 结合阿里云百炼云端 RAG 知识库的对话
     *
     * <p>相比本地 RAG，云端 RAG 直接使用百炼平台托管的知识索引"恋爱大师"，
     * 无需在本地存储和维护向量数据，适合知识库较大或需要动态更新的场景。
     *
     * @param message 用户消息
     * @param chatId  会话 ID
     * @return 基于云端知识库增强后的模型回复
     */
    public String doChatWithCloudRag(String message, String chatId) {
        ChatResponse response = client
                .prompt()
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 10))
                .advisors(new MyLoggerAdvisors())
                // 使用 Spring Bean 注入的云端 RAG Advisor（对应百炼知识库索引）
                .advisors(loveAppRagCloudAdvisor)
                .call()
                .chatResponse();
        String content = response.getResult().getOutput().getText();
        log.info("content: {}", content);
        return content;
    }

    /**
     * 基于向量知识库的恋爱对象智能匹配推荐
     *
     * <p>使用自定义 {@link DatingMatchAdvisor}，与标准 {@link QuestionAnswerAdvisor} 的区别：
     * <ul>
     *   <li>添加了元数据过滤（{@code fileName == '约会对象.md'}），只在特定文档中检索</li>
     *   <li>重新构造了专属 Prompt，明确告知模型扮演"恋爱匹配顾问"角色</li>
     *   <li>支持自定义 topK 控制候选人数量</li>
     * </ul>
     *
     * @param message 用户描述的择偶偏好或问题
     * @param chatId  会话 ID
     * @return 模型推荐的恋爱对象及理由
     */
    public String doChatWithRagMatchUser(String message, String chatId) {
        ChatResponse response = client
                .prompt()
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 10))
                .advisors(new MyLoggerAdvisors())
                // topK=2：从知识库中召回最相似的 2 位候选人
                .advisors(new DatingMatchAdvisor(loveAppVectorStore, 2))
                .call()
                .chatResponse();
        String content = response.getResult().getOutput().getText();
        log.info("content: {}", content);
        return content;
    }




    public String doChatWithRagRewriter(String message, String chatId,String status) {
        // 查询重写
        String rewrittenMessage = queryRewriter.doQueryRewrite(message);
        ChatResponse chatResponse = client
                .prompt()
                .user(rewrittenMessage)
                .advisors(LoveAppRagCustomAdvisorFactory.createLoveAppRagCustomAdvisor(
                        loveAppVectorStore, status))
                .call()
                .chatResponse();
        String content = chatResponse.getResult().getOutput().getText();
        return content;
    }


    public String doChatWithTools(String message, String chatId) {
        ChatResponse response = client
                .prompt()
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 10))
                // 开启日志，便于观察效果
                .advisors(new MyLoggerAdvisors())
                .tools(allTools)
                .call()
                .chatResponse();
        String content = response.getResult().getOutput().getText();
        log.info("content: {}", content);
        return content;
    }


    //TODO: 手动工具调用，控制工具调用
    public String chat(String message){

        log.info("Agent开始执行, message={}", message);
        Prompt prompt = new Prompt(
                new UserMessage(message)
        );
        // Step 2 调用 LLM（不会自动执行Tool）
        ChatResponse response =
                client
                        .prompt(message)
                        .call()
                        .chatResponse();

        AssistantMessage assistantMessage =
                response.getResult().getOutput();

        List<AssistantMessage.ToolCall> toolCalls =
                assistantMessage.getToolCalls();

        if(toolCalls == null || toolCalls.isEmpty()){
            log.info("无Tool调用");
            return assistantMessage.getText();
        }

        log.info("==========Tool调用开始==========");
        log.info("检测到Tool调用: {}", toolCalls.size());

        toolCalls.forEach(toolCall -> {
            log.info("Tool名称: {}", toolCall.name());
            log.info("Tool参数: {}", toolCall.arguments());
        });

        long start = System.currentTimeMillis();

        // Step 3 正确执行 Tool（新版写法）
        ToolExecutionResult result =
                toolCallingManager.executeToolCalls(
                        prompt,
                        response
                );

        log.info("Tool执行完成");
        long end = System.currentTimeMillis();
        log.info("Tool执行耗时: {} ms", end - start);

        // Step 4 把 Tool 执行结果返回 LLM
        ChatResponse finalResponse =
                chatModel.call(
                        new Prompt(
                                result.conversationHistory()
                        )
                );

        return finalResponse
                .getResult()
                .getOutput()
                .getText();
    }



    public String doChatWithMcp(String message, String chatId) {
        ChatResponse response = client
                .prompt()
                .user(message)
                .advisors(spec -> spec.param(CHAT_MEMORY_CONVERSATION_ID_KEY, chatId)
                        .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 10))
                // 开启日志，便于观察效果
                .advisors(new MyLoggerAdvisors())
                .tools(toolCallbackProvider)
                .call()
                .chatResponse();
        String content = response.getResult().getOutput().getText();
        log.info("content: {}", content);
        return content;
    }

}
