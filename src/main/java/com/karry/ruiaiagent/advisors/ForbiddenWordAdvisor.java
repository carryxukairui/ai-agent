package com.karry.ruiaiagent.advisors;

import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.advisor.api.*;
import reactor.core.publisher.Flux;

import org.ahocorasick.trie.Trie;
import java.util.Set;


/**
 * 敏感词拦截 Advisor
 *
 * <p>同时实现 {@link CallAroundAdvisor}（同步）和 {@link StreamAroundAdvisor}（流式）两个接口，
 * 确保无论以哪种方式调用大模型，敏感词过滤都能生效。
 *
 * <p>工作时机：在请求发往大模型<strong>之前</strong>执行拦截（前置检查），
 * 若检测到敏感词则直接抛出异常，请求不会到达模型，避免资源浪费。
 *
 * <p>执行顺序：{@code getOrder()} 返回 1，在 Advisor 链中优先级较高，
 * 确保敏感词检测发生在对话记忆读写之前。
 */
@Slf4j
public class ForbiddenWordAdvisor implements CallAroundAdvisor, StreamAroundAdvisor {

    /** 敏感词集合，由调用方传入，支持动态配置 */
    private final Set<String> forbiddenWords;

    /**
     * Aho-Corasick Trie 树
     *
     * <p>在构造时一次性将所有敏感词编译进 Trie，后续每次检测只需 O(n) 时间（n 为文本长度），
     * 与敏感词数量无关，性能远优于逐一字符串匹配。
     */
    private Trie trie;

    /**
     * 构造敏感词 Advisor
     *
     * @param forbiddenWords 需要过滤的敏感词集合
     */
    public ForbiddenWordAdvisor(Set<String> forbiddenWords) {
        this.forbiddenWords = forbiddenWords;
        // 将所有敏感词一次性加入 Trie，构建失败自动匹配树，后续匹配 O(n)
        this.trie = Trie.builder().addKeywords(forbiddenWords).build();
    }

    @Override
    public String getName() {
        return this.getClass().getSimpleName();
    }

    /** 执行优先级，数值越小越先执行；设为 1 使其早于对话记忆 Advisor 运行 */
    @Override
    public int getOrder() {
        return 1;
    }

    /**
     * 同步调用拦截：在请求进入下一个 Advisor 前执行敏感词检测
     *
     * @param advisedRequest 封装了用户消息、系统提示等完整请求上下文
     * @param chain          Advisor 责任链，调用 {@code nextAroundCall} 将请求传递给下一环节
     */
    @Override
    public AdvisedResponse aroundCall(AdvisedRequest advisedRequest, CallAroundAdvisorChain chain) {
        // 执行前置检查，若包含敏感词则抛出异常，不会执行后续 chain.nextAroundCall
        before(advisedRequest);
        // 检查通过，继续沿责任链传递请求
        return chain.nextAroundCall(advisedRequest);
    }

    /**
     * 流式调用拦截：逻辑与同步版本一致，区别在于返回 Flux 响应流
     */
    @Override
    public Flux<AdvisedResponse> aroundStream(AdvisedRequest advisedRequest, StreamAroundAdvisorChain chain) {
        // 执行前置检查
        before(advisedRequest);
        // 继续执行链式调用
        return chain.nextAroundStream(advisedRequest);
    }

    /**
     * 前置检查：提取用户文本并执行敏感词扫描
     */
    private AdvisedRequest before(AdvisedRequest advisedRequest) {
        String userText = advisedRequest.userText();
        checkForbiddenWords(userText);
        return advisedRequest;
    }

    /**
     * 使用 Aho-Corasick 算法进行多模式敏感词匹配
     *
     * <p><b>Aho-Corasick 算法原理</b>：
     * <ul>
     *   <li>由 Alfred V. Aho 和 Margaret J. Corasick 于 1975 年提出</li>
     *   <li>基于有限自动机（DFA）在文本中同时匹配多个模式串</li>
     *   <li>时间复杂度 O(n + m + z)，其中 n 为文本长度，m 为所有关键词长度之和，z 为匹配次数</li>
     *   <li>相比朴素的逐词遍历（O(n × k)，k 为关键词数量），在关键词数量大时性能优势显著</li>
     * </ul>
     *
     * @param message 待检测的用户输入文本
     * @throws IllegalArgumentException 检测到敏感词时抛出，终止请求流程
     */
    private void checkForbiddenWords(String message) {
        trie.parseText(message).forEach(hit -> {
            log.warn("Forbidden word detected: {}", hit.getKeyword());
            throw new IllegalArgumentException("Forbidden word detected: " + hit.getKeyword());
        });
    }
}
