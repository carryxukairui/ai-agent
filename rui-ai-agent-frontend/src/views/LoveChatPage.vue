<template>
  <ChatRoom
    title="AI 恋爱大师"
    :subtitle="`接口：/ai/love_app/chat/sse（SSE）`"
    sse-path="/ai/love_app/chat/sse"
    :send-chat-id="true"
  />
</template>

<script setup lang="ts">
import ChatRoom from "@/views/components/ChatRoom.vue";
</script>

