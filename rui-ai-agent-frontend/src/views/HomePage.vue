<template>
  <div class="home">
    <section class="hero card">
      <div class="hero-left">
        <div class="badge">本地后端：{{ apiBase }}</div>
        <h1 class="title">选择一个 AI 应用</h1>
        <p class="desc">进入后会自动创建会话 chatId，并通过 SSE 实时渲染 AI 输出。</p>
        <div class="actions">
          <button class="btn primary" @click="$router.push('/love')">AI 恋爱大师</button>
          <button class="btn" @click="$router.push('/manus')">AI 超级智能体</button>
        </div>
      </div>
      <div class="hero-right">
        <div class="mock card">
          <div class="mock-line" />
          <div class="mock-line short" />
          <div class="mock-bubble left" />
          <div class="mock-bubble right" />
          <div class="mock-bubble left wide" />
        </div>
      </div>
    </section>

    <section class="grid">
      <div class="card tile" @click="$router.push('/love')">
        <div class="tile-title">页面 1：AI 恋爱大师</div>
        <div class="tile-desc">调用 `doChatWithLoveAppSSE`，聊天室样式，流式输出。</div>
      </div>
      <div class="card tile" @click="$router.push('/manus')">
        <div class="tile-title">页面 2：AI 超级智能体</div>
        <div class="tile-desc">调用 `getDoChatWithManus`，聊天室样式，流式输出。</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { API_BASE_URL } from "@/lib/http";

const apiBase = API_BASE_URL;
</script>

<style scoped>
.home {
  display: grid;
  gap: 16px;
}

.hero {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 14px;
  align-items: center;
}

.badge {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(99, 102, 241, 0.35);
  background: rgba(99, 102, 241, 0.12);
  color: rgba(226, 232, 240, 0.85);
  font-size: 12px;
  width: fit-content;
}

.title {
  margin: 12px 0 6px;
  font-size: 28px;
  letter-spacing: 0.2px;
}
.desc {
  margin: 0 0 12px;
  color: var(--muted);
  line-height: 1.6;
}
.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.mock {
  height: 170px;
  background: rgba(2, 6, 23, 0.25);
  display: grid;
  align-content: start;
  gap: 10px;
  border-radius: 18px;
}
.mock-line {
  height: 12px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
}
.mock-line.short {
  width: 70%;
}
.mock-bubble {
  height: 18px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.14);
  width: 60%;
}
.mock-bubble.left {
  justify-self: start;
}
.mock-bubble.right {
  justify-self: end;
  background: rgba(99, 102, 241, 0.18);
  width: 55%;
}
.mock-bubble.wide {
  width: 80%;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.tile {
  cursor: pointer;
  transition: transform 140ms ease, border-color 140ms ease;
}
.tile:hover {
  transform: translateY(-1px);
  border-color: rgba(99, 102, 241, 0.4);
}
.tile-title {
  font-weight: 700;
  margin-bottom: 8px;
}
.tile-desc {
  color: var(--muted);
  line-height: 1.6;
}

@media (max-width: 860px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>

