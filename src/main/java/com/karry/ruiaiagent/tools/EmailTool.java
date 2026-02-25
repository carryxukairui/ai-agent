package com.karry.ruiaiagent.tools;

import jakarta.annotation.Resource;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Component;

@Component
public class EmailTool {

    @Autowired
    private JavaMailSender mailSender;
    @Value("${spring.mail.username}")
    private String mail;

    @Tool(description =
            "当用户要求发送邮件时使用此工具。输入参数包括收件人邮箱、主题和邮件内容")
    public String sendEmail(@ToolParam(description = "收件人邮箱") String to,
                            @ToolParam(description = "邮件主题") String subject,
                            @ToolParam(description = "邮件内容") String content) {
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(mail);
            message.setTo(to);
            message.setSubject(subject);
            message.setText(content);
            mailSender.send(message);
            return "邮件发送成功";
        } catch (Exception e) {
            return "邮件发送失败: " + e.getMessage();
        }
    }
}