package com.karry.ruiaiagent;

import com.karry.ruiaiagent.tools.EmailTool;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest
public class EmailToolTest {
    @Autowired
    private EmailTool tool;
    @Test
    public void testScrapeWebPage() {

        String result = tool.sendEmail( "1617921455@qq.com","主题是七夕","内容是七夕，我们走吧");
        assertNotNull(result);
    }
}
