package com.karry.ruiaiagent.config;

import com.karry.ruiaiagent.rag.LoveAppDocumentLoader;
import com.karry.ruiaiagent.rag.MyKeywordEnricher;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.document.Document;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.ai.vectorstore.pgvector.PgVectorStore;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;


import java.util.List;

import static org.springframework.ai.vectorstore.pgvector.PgVectorStore.PgDistanceType.COSINE_DISTANCE;
import static org.springframework.ai.vectorstore.pgvector.PgVectorStore.PgIndexType.HNSW;

/**
 * 配置PostgreSQL向量存储
 */

@Configuration
@Slf4j
public class PgVectorVectorStoreConfig {

    @Resource
    private LoveAppDocumentLoader loveAppDocumentLoader;
    @Resource
    private MyKeywordEnricher myKeywordEnricher;

    @Bean
    public VectorStore pgVectorVectorStore(JdbcTemplate jdbcTemplate, EmbeddingModel dashscopeEmbeddingModel) {
        VectorStore vectorStore = PgVectorStore.builder(jdbcTemplate, dashscopeEmbeddingModel)
                .dimensions(1536)                    // Optional: defaults to model dimensions or 1536
                .distanceType(COSINE_DISTANCE)       // Optional: defaults to COSINE_DISTANCE
                .indexType(HNSW)                     // Optional: defaults to HNSW
                .initializeSchema(true)              // Optional: defaults to false
                .schemaName("public")                // Optional: defaults to "public"
                .vectorTableName("vector_store")     // Optional: defaults to "vector_store"
                .maxDocumentBatchSize(10000)         // Optional: defaults to 10000
                .build();
        // 加载文档，分批添加（DashScope Embedding API 限制单次 batch size 不超过 10）
        List<Document> documents = loveAppDocumentLoader.loadMarkdown();
        List<Document> enrichedDocuments = myKeywordEnricher.enrichDocuments(documents);
        int batchSize = 10;
        for (int i = 0; i < enrichedDocuments.size(); i += batchSize) {
            int end = Math.min(i + batchSize, enrichedDocuments.size());
            vectorStore.add(enrichedDocuments.subList(i, end));
        }
        return vectorStore;
    }
}
