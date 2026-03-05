package com.karry.ruiaiagent.tools;

import org.springframework.ai.model.function.FunctionCallback;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.ToolCallbacks;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

@Configuration
public class ToolRegistration {

    @Value("${search-api.api-key}")
    private String searchApiKey;

    @Autowired
    private EmailTool emailTool;

    @Autowired
    private ToolCallbackProvider toolCallbackProvider; //  注入 MCP Provider

    @Bean
    public ToolCallback[] allTools() {

        FileOperationTool fileOperationTool = new FileOperationTool();
        WebSearchTool webSearchTool = new WebSearchTool(searchApiKey);
        WebScrapingTool webScrapingTool = new WebScrapingTool();
        ResourceDownloadTool resourceDownloadTool = new ResourceDownloadTool();
        TerminalOperationTool terminalOperationTool = new TerminalOperationTool();
        PDFGenerationTool pdfGenerationTool = new PDFGenerationTool();
        TerminateTool terminateTool = new TerminateTool();

        // 本地工具
        ToolCallback[] localTools = ToolCallbacks.from(
                fileOperationTool,
                webSearchTool,
                webScrapingTool,
                resourceDownloadTool,
                terminalOperationTool,
                pdfGenerationTool,
                terminateTool,
                emailTool
        );

//        //关键：拿到 MCP 工具
//        FunctionCallback[] functionCallbacks = toolCallbackProvider.getToolCallbacks();
//
//        ToolCallback[] mcpTools = Arrays.stream(functionCallbacks)
//                .map(fc -> (ToolCallback) fc)
//                .toArray(ToolCallback[]::new);
//
//        //  合并
//        List<ToolCallback> merged = new ArrayList<>();
//        merged.addAll(Arrays.asList(localTools));
//        merged.addAll(Arrays.asList(mcpTools));
//
//        return merged.toArray(new ToolCallback[0]);
        return localTools;
    }
}
