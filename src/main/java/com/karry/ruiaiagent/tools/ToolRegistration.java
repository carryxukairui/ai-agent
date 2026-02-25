package com.karry.ruiaiagent.tools;

import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.ToolCallbacks;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 集中的工具注册类
 */
@Configuration
public class ToolRegistration {

    @Value("${search-api.api-key}")
    private String searchApiKey;
    @Autowired
    private EmailTool emailTool;

    /**
     * 所有工具 多种设计模式
     * 工厂模式
     * 依赖注入模式
     * 注册模式
     * 适配器模式 ToolCallback.from
     * @return
     */
    @Bean
    public ToolCallback[] allTools() {
        //文件操作
        FileOperationTool fileOperationTool = new FileOperationTool();
        //网页搜索
        WebSearchTool webSearchTool = new WebSearchTool(searchApiKey);
        //网页抓取
        WebScrapingTool webScrapingTool = new WebScrapingTool();
        //资源下载
        ResourceDownloadTool resourceDownloadTool = new ResourceDownloadTool();
        //终端操作
        TerminalOperationTool terminalOperationTool = new TerminalOperationTool();
        //PDF生成
        PDFGenerationTool pdfGenerationTool = new PDFGenerationTool();
        return ToolCallbacks.from(
            fileOperationTool,
            //webSearchTool,
           // webScrapingTool,
            resourceDownloadTool,
            terminalOperationTool,
            pdfGenerationTool,
                emailTool
        );
    }
}
