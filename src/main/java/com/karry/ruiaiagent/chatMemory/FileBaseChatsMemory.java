package com.karry.ruiaiagent.chatMemory;

import com.esotericsoftware.kryo.Kryo;
import com.esotericsoftware.kryo.io.Input;
import com.esotericsoftware.kryo.io.Output;
import org.objenesis.strategy.StdInstantiatorStrategy;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.messages.Message;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * 基于文件持久化的对话记忆
 */
public class FileBaseChatsMemory implements ChatMemory {

    private final String BASE_DIR;
    private static final Kryo kryo = new Kryo();
    static {
        kryo.setRegistrationRequired( false);
        kryo.setInstantiatorStrategy(new StdInstantiatorStrategy());
    }
    public FileBaseChatsMemory(String baseDir) {
        BASE_DIR = baseDir;
        File file = new File(BASE_DIR);
        if (!file.exists()) {
            file.mkdirs();
        }
    }

    @Override
    public void add(String conversationId, List<Message> messages) {
        List<Message> messagesList = getOrCreateMessage(conversationId);
        messagesList.addAll(messages);
        saveConversation(conversationId, messagesList);
    }



    @Override
    public List<Message> get(String conversationId, int lastN) {
        List<Message> allMessages = getOrCreateMessage(conversationId);
        return allMessages.stream()
                .skip(Math.max(0, allMessages.size() - lastN))
                .toList();
    }

    @Override
    public void clear(String conversationId) {
        File file = getConversationFile(conversationId);
        if (file.exists()) {
            file.delete();
        }
    }

    private void saveConversation(String conversationId, List<Message> messagesList) {
        File file = getConversationFile(conversationId);
        try(var output = new Output(new FileOutputStream( file))){
            kryo.writeObject(output, messagesList);
        }catch (Exception e){
            e.printStackTrace();
        }
    }

    private List<Message> getOrCreateMessage(String conversationId) {
        File file = getConversationFile(conversationId);
        List<Message> messagesList = new ArrayList<>();
        // 文件不存在：第一次会话，直接返回空列表
        if (!file.exists()) {
            return new ArrayList<>();
        }

        try (Input input = new Input(new FileInputStream(file))) {
            return kryo.readObject(input, ArrayList.class);
        } catch (Exception e) {
            throw new RuntimeException("Failed to read chat memory: " + file.getAbsolutePath(), e);
        }

    }

    private File getConversationFile(String conversationId) {
        return new File(BASE_DIR, conversationId+".kryo");
    }
}
