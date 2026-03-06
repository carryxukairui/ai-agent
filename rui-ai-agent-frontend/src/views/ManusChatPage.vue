<template>
  <ChatRoom
    title="AI 超级智能体"
    :subtitle="`接口：/ai/manus/chat（SSE）`"
    sse-path="/ai/manus/chat"
    :send-chat-id="false"
    ai-avatar="🧠"
    :add-newline-per-chunk="true"
  />
</template>

<script setup lang="ts">
import ChatRoom from "@/views/components/ChatRoom.vue";
</script>

