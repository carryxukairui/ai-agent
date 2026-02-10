package com.karry.ruiaiagent.advisors;

import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.advisor.api.*;
import reactor.core.publisher.Flux;

import org.ahocorasick.trie.Trie;
import java.util.Set;


/**
 * 拦截器，用于拦截敏感词
 */
@Slf4j
public class ForbiddenWordAdvisor implements CallAroundAdvisor, StreamAroundAdvisor {
    private final Set<String> forbiddenWords;
    private Trie trie;
    public ForbiddenWordAdvisor(Set<String> forbiddenWords) {
        this.forbiddenWords = forbiddenWords;
        this.trie = Trie.builder().addKeywords(forbiddenWords).build();
    }



    @Override
    public String getName() {
        return this.getClass().getSimpleName();
    }

    @Override
    public int getOrder() {
        return 1;
    }

    @Override
    public AdvisedResponse aroundCall(AdvisedRequest advisedRequest, CallAroundAdvisorChain chain) {
        // 执行前置检查
        before(advisedRequest);
        // 继续执行链式调用
        return chain.nextAroundCall(advisedRequest);
    }

    @Override
    public Flux<AdvisedResponse> aroundStream(AdvisedRequest advisedRequest, StreamAroundAdvisorChain chain) {
        // 执行前置检查
        before(advisedRequest);
        // 继续执行链式调用
        return chain.nextAroundStream(advisedRequest);
    }

    private AdvisedRequest before(AdvisedRequest advisedRequest){
        String userText = advisedRequest.userText();
        checkForbiddenWords(userText);
        return advisedRequest;
    }


    /**
     * Aho-Corasick 算法
     * Aho-Corasick 是一种多模式匹配算法，专门用于同时匹配多个关键词。
     * 它的运行时间复杂度为 O(m + n)，其中 m 是文本的长度，n 是关键词的数量。
     * @param message
     */
    private void checkForbiddenWords(String message) {
        trie.parseText(message).forEach(hit -> {
            log.warn("Forbidden word detected: {}", hit.getKeyword());
            throw new IllegalArgumentException("Forbidden word detected: " + hit.getKeyword());
        });
    }
}
