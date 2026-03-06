<template>
  <section class="chat card">
    <header class="chat-header">
      <div class="left">
        <div class="title-row">
          <button class="btn" @click="$router.push('/')">返回</button>
          <div class="title">{{ title }}</div>
        </div>
        <div class="meta">
          <div class="subtitle">{{ subtitle }}</div>
          <div class="chatid">
            chatId：<span class="mono">{{ chatId }}</span>
            <button class="mini" @click="regenChatId" title="重新生成 chatId">重置</button>
          </div>
        </div>
      </div>

      <div class="right">
        <button class="btn danger" :disabled="messages.length === 0" @click="clearAll">清空聊天</button>
      </div>
    </header>

    <div ref="scrollEl" class="chat-body" @scroll="onUserScroll">
      <div v-if="messages.length === 0" class="empty">
        <div class="empty-title">开始对话</div>
        <div class="empty-desc">在下方输入框输入内容并发送，AI 会以 SSE 形式实时返回。</div>
      </div>

      <div v-for="m in messages" :key="m.id" class="row" :class="m.role">
        <div class="avatar-wrap" v-if="m.role === 'ai'">
          <div class="avatar" :class="{ 'avatar-img': isAvatarUrl }">
            <img v-if="isAvatarUrl" :src="props.aiAvatar" alt="AI" />
            <span v-else>{{ props.aiAvatar }}</span>
          </div>
        </div>
        <div class="bubble">
          <div class="bubble-meta">
            <span class="role">{{ m.role === 'user' ? '你' : 'AI' }}</span>
            <span v-if="m.streaming" class="streaming">输出中…</span>
          </div>
          <!-- 思考过程：上边、可折叠，默认折叠 -->
          <div v-if="m.text" class="thinking-block">
            <button type="button" class="thinking-toggle" @click="toggleThinking(m.id)" :aria-expanded="expandedThinkingIds.has(m.id)">
              <span class="toggle-icon">{{ expandedThinkingIds.has(m.id) ? '▼' : '▶' }}</span>
              <span>思考过程</span>
            </button>
            <div v-show="expandedThinkingIds.has(m.id)" class="thinking-content">
              <pre class="text thinking">{{ m.text }}</pre>
            </div>
          </div>
          <!-- 正式回答：下边固定展示 -->
          <div v-if="m.finalResult" class="result-block">
            <div class="result-label">回答</div>
            <pre class="text result">{{ m.finalResult }}</pre>
          </div>
        </div>
      </div>
    </div>

    <footer class="chat-footer">
      <form class="composer" @submit.prevent="send">
        <textarea
          v-model="draft"
          class="input"
          :disabled="sending"
          placeholder="输入消息：Enter 发送，Shift+Enter 换行"
          rows="2"
          @keydown.enter="onEnter"
        />
        <button class="btn primary" type="submit" :disabled="sending || draft.trim().length === 0">
          {{ sending ? "发送中…" : "发送" }}
        </button>
      </form>
      <div class="hint">
        <span class="dot" :class="{ ok: backendOk }" />
        <span>{{ backendOk ? "后端连接正常（SSE）" : "未确认后端状态：请确保后端已启动并允许跨域" }}</span>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { openSse } from "@/lib/sse";

type Role = "user" | "ai";
type ChatMsg = {
  id: string;
  role: Role;
  /** 兼容旧接口：无 event 时流式内容累积在此；有 event 时 thinking 流也先累积在此便于“输出中”展示 */
  text: string;
  /** 后端 event=result 时的最终结果（有则单独展示） */
  finalResult?: string;
  streaming?: boolean;
};

const props = withDefaults(
  defineProps<{
    title: string;
    subtitle: string;
    ssePath: string;
    sendChatId: boolean;
    /** AI 默认头像：图片 URL 或 emoji/文字（显示在圆形区域） */
    aiAvatar?: string;
    /** 超级智能体模式：每次 SSE chunk 后额外加一个换行（后端每步一次响应） */
    addNewlinePerChunk?: boolean;
  }>(),
  { aiAvatar: "🤖", addNewlinePerChunk: false }
);

const chatId = ref<string>(newChatId());
const draft = ref("");
const messages = ref<ChatMsg[]>([]);
const sending = ref(false);
const backendOk = ref(false);

const scrollEl = ref<HTMLDivElement | null>(null);
const userPinnedToBottom = ref(true);
/** 已展开思考过程的消息 id 集合，默认折叠故为空 */
const expandedThinkingIds = ref<Set<string>>(new Set());

const lastMsg = computed(() => messages.value[messages.value.length - 1]);
const isAvatarUrl = computed(
  () =>
    typeof props.aiAvatar === "string" &&
    (props.aiAvatar.startsWith("http") || props.aiAvatar.startsWith("/"))
);

function toggleThinking(id: string) {
  const next = new Set(expandedThinkingIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expandedThinkingIds.value = next;
}

let sseCloser: null | (() => void) = null;

function newChatId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function regenChatId() {
  chatId.value = newChatId();
}

function clearAll() {
  stopStream();
  messages.value = [];
  draft.value = "";
}

function stopStream() {
  if (sseCloser) sseCloser();
  sseCloser = null;
  sending.value = false;
  const lm = lastMsg.value;
  if (lm && lm.role === "ai") lm.streaming = false;
}

function scrollToBottom(force = false) {
  const el = scrollEl.value;
  if (!el) return;
  if (!force && !userPinnedToBottom.value) return;
  el.scrollTop = el.scrollHeight;
}

function onUserScroll() {
  const el = scrollEl.value;
  if (!el) return;
  const threshold = 40;
  userPinnedToBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - threshold;
}

function onEnter(e: KeyboardEvent) {
  if (e.shiftKey) return;
  e.preventDefault();
  void send();
}

async function send() {
  const text = draft.value.trim();
  if (!text || sending.value) return;

  stopStream();
  sending.value = true;

  const userMsg: ChatMsg = { id: newChatId(), role: "user", text };
  const aiMsg: ChatMsg = { id: newChatId(), role: "ai", text: "", streaming: true };
  messages.value.push(userMsg, aiMsg);
  draft.value = "";
  scrollToBottom(true);

  const params: Record<string, string | undefined> = {
    message: text,
    chatId: props.sendChatId ? chatId.value : undefined,
  };

  const { close } = openSse(props.ssePath, params, {
    onOpen: () => {
      backendOk.value = true;
    },
    onChunk: (chunk, event) => {
      console.log("前端收到一段 SSE chunk:", event ?? "(无event)", chunk);
      backendOk.value = true;
      if (event === "result") {
        aiMsg.finalResult = chunk;
        aiMsg.streaming = false;
        sending.value = false;
        const nextCollapsed = new Set(expandedThinkingIds.value);
        nextCollapsed.delete(aiMsg.id);
        expandedThinkingIds.value = nextCollapsed;
      } else {
        aiMsg.text += chunk;
        if (chunk && !chunk.endsWith("\n")) aiMsg.text += "\n";
        if (props.addNewlinePerChunk && chunk) aiMsg.text += "\n";
        const nextExpanded = new Set(expandedThinkingIds.value);
        nextExpanded.add(aiMsg.id);
        expandedThinkingIds.value = nextExpanded;
      }
      messages.value = [...messages.value];
      scrollToBottom();
    },
    onError: () => {
      aiMsg.streaming = false;
      sending.value = false;
      const next = new Set(expandedThinkingIds.value);
      next.delete(aiMsg.id);
      expandedThinkingIds.value = next;
    },
  });

  sseCloser = () => {
    close();
  };

  // 如果后端关闭连接，通常会触发 onerror，从而结束本次发送状态
}

onMounted(() => {
  scrollToBottom(true);
});

onBeforeUnmount(() => {
  stopStream();
});
</script>

<style scoped>
.chat {
  padding: 0;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(2, 6, 23, 0.25);
}

@media (min-width: 768px) {
  .chat-header {
    padding: 14px 14px 12px;
  }
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.title {
  font-weight: 800;
  letter-spacing: 0.2px;
}
.meta {
  display: grid;
  gap: 6px;
  margin-top: 8px;
}
.subtitle {
  color: rgba(226, 232, 240, 0.72);
  font-size: 13px;
}
.chatid {
  color: rgba(226, 232, 240, 0.72);
  font-size: 13px;
  display: inline-flex;
  gap: 8px;
  align-items: center;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  color: rgba(248, 250, 252, 0.92);
}
.mini {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(2, 6, 23, 0.25);
  color: rgba(226, 232, 240, 0.88);
  border-radius: 999px;
  padding: 4px 8px;
  cursor: pointer;
}
.mini:hover {
  border-color: rgba(99, 102, 241, 0.4);
}

.chat-body {
  height: min(60vh, 500px);
  overflow: auto;
  padding: 12px;
  background: rgba(2, 6, 23, 0.12);
}

@media (min-width: 768px) {
  .chat-body {
    height: min(66vh, 640px);
    padding: 14px;
  }
}

.empty {
  padding: 24px;
  border: 1px dashed rgba(148, 163, 184, 0.22);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.35);
  color: rgba(226, 232, 240, 0.85);
}
.empty-title {
  font-weight: 800;
  margin-bottom: 6px;
}
.empty-desc {
  color: rgba(226, 232, 240, 0.68);
  line-height: 1.6;
}

.row {
  display: flex;
  margin-bottom: 12px;
}
.row.user {
  justify-content: flex-end;
}
.row.ai {
  justify-content: flex-start;
  align-items: flex-start;
  gap: 10px;
}
.avatar-wrap {
  flex-shrink: 0;
}
.avatar {
  width: 32px;
  height: 32px;
  font-size: 16px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(20, 184, 166, 0.4));
  border: 1px solid rgba(148, 163, 184, 0.2);
  font-size: 18px;
  overflow: hidden;
}
.avatar.avatar-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bubble {
  max-width: min(780px, 100%);
  border-radius: var(--radius-lg);
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.55);
}
.row.user .bubble {
  background: rgba(99, 102, 241, 0.16);
  border-color: rgba(99, 102, 241, 0.28);
}
.row.ai .bubble {
  background: rgba(20, 184, 166, 0.12);
  border-color: rgba(20, 184, 166, 0.22);
}

.bubble-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.72);
}
.role {
  font-weight: 700;
}
.streaming {
  color: rgba(248, 250, 252, 0.8);
}

.text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.6;
  color: rgba(248, 250, 252, 0.92);
  text-align: left;
}

.thinking-block {
  margin-bottom: 10px;
}
.thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 0;
  border: none;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.4);
  color: rgba(226, 232, 240, 0.85);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
}
.thinking-toggle:hover {
  background: rgba(30, 41, 59, 0.5);
}
.toggle-icon {
  font-size: 10px;
  color: rgba(148, 163, 184, 0.9);
}
.thinking-content {
  margin-top: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(2, 6, 23, 0.35);
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.text.thinking {
  font-size: 0.88em;
  color: rgba(226, 232, 240, 0.78);
  margin: 0;
}

.result-block {
  margin-top: 4px;
}
.result-label {
  font-size: 12px;
  font-weight: 600;
  color: rgba(34, 197, 94, 0.9);
  margin-bottom: 6px;
}
.text.result {
  font-weight: 500;
  margin: 0;
}

.chat-footer {
  border-top: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(2, 6, 23, 0.25);
  padding: 12px;
  display: grid;
  gap: 10px;
}

@media (min-width: 768px) {
  .chat-footer {
    padding: 12px 14px 14px;
  }
}

.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: flex-end;
}

@media (max-width: 480px) {
  .composer {
    grid-template-columns: 1fr;
  }
}

.composer textarea {
  resize: vertical;
  min-height: 44px;
  max-height: 180px;
}

.hint {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  color: rgba(226, 232, 240, 0.65);
  font-size: 12px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.35);
}
.dot.ok {
  background: rgba(34, 197, 94, 0.95);
}

@media (min-width: 768px) {
  .avatar {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }
  .row.ai {
    gap: 12px;
  }
}
</style>

