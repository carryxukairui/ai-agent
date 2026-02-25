package com.karry.ruiaiagent;

import com.karry.ruiaiagent.tools.FileOperationTool;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest
public class FileOperationToolTest {

    @Test
    public void testReadFile() {
        FileOperationTool tool = new FileOperationTool();
        String fileName = "文件测试.txt";
        String result = tool.readFile(fileName);
        assertNotNull(result);
    }

    @Test
    public void testWriteFile() {
        FileOperationTool tool = new FileOperationTool();
        String fileName = "文件测试.txt";
        String content = "https://open.bigmodel.cn 语言模型 Prompt 工程";
        String result = tool.writeFile(fileName, content);
        assertNotNull(result);
    }
}
