<template>
  <div class="home">
    <section class="hero">
      <h1 class="hero-title">Rui AI Agent</h1>
      <p class="hero-slogan">/ 探索 AI 的无限可能 /</p>
      <div class="hero-badge">后端：{{ apiBase }}</div>
    </section>

    <section class="cards">
      <article class="app-card" @click="$router.push('/love')">
        <div class="card-avatar love">
          <span>💕</span>
        </div>
        <h2 class="card-title">AI 恋爱大师</h2>
        <p class="card-desc">智能情感顾问，帮你解答恋爱烦恼</p>
        <button type="button" class="btn primary card-btn">
          立即体验 <span class="arrow">→</span>
        </button>
      </article>

      <article class="app-card" @click="$router.push('/manus')">
        <div class="card-avatar manus">
          <span>🤖</span>
        </div>
        <h2 class="card-title">AI 超级智能体</h2>
        <p class="card-desc">全能型 AI 助手，解决各类专业问题</p>
        <button type="button" class="btn primary card-btn">
          立即体验 <span class="arrow">→</span>
        </button>
      </article>
    </section>

    <footer class="footer">
      <div class="footer-inner">
        <div class="footer-col">
          <div class="footer-title">Rui AI Agent</div>
          <a href="#" class="footer-link">用户协议</a>
          <a href="#" class="footer-link">隐私政策</a>
        </div>
        <div class="footer-col">
          <div class="footer-title">关于</div>
          <span class="footer-text">Vue3 · SSE · 流式输出</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { API_BASE_URL } from "@/lib/http";

const apiBase = API_BASE_URL;
</script>

<style scoped>
.home {
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 16px 24px;
}

.hero {
  text-align: center;
  margin-bottom: 48px;
}

.hero-title {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: 0.02em;
  margin: 0 0 12px;
  background: linear-gradient(135deg, #22d3ee 0%, #14b8a6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0 0 24px rgba(34, 211, 238, 0.4));
}

.hero-slogan {
  font-size: 15px;
  color: var(--muted);
  margin: 0 0 16px;
  letter-spacing: 0.1em;
}

.hero-badge {
  display: inline-block;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(2, 6, 23, 0.4);
}

.cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
  max-width: 720px;
  width: 100%;
  flex: 1;
}

.app-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 24px;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.15);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: all 0.25s ease;
}

.app-card:hover {
  transform: translateY(-4px);
  border-color: rgba(34, 211, 238, 0.35);
  box-shadow: 0 8px 40px rgba(34, 211, 238, 0.12), 0 0 0 1px rgba(34, 211, 238, 0.1);
}

.card-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 36px;
  margin-bottom: 20px;
  box-shadow: 0 0 24px rgba(0, 0, 0, 0.2);
}

.card-avatar.love {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.3), rgba(244, 114, 182, 0.35));
  border: 1px solid rgba(244, 114, 182, 0.4);
  box-shadow: 0 0 30px rgba(244, 114, 182, 0.2);
}

.card-avatar.manus {
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.3), rgba(20, 184, 166, 0.35));
  border: 1px solid rgba(34, 211, 238, 0.4);
  box-shadow: 0 0 30px rgba(34, 211, 238, 0.2);
}

.card-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 10px;
}

.card-desc {
  font-size: 14px;
  color: var(--muted);
  line-height: 1.5;
  margin: 0 0 24px;
  text-align: center;
  flex: 1;
}

.card-btn {
  width: 100%;
  max-width: 180px;
  padding: 12px 20px;
  font-size: 15px;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
}

.card-btn .arrow {
  margin-left: 4px;
}

.footer {
  margin-top: auto;
  padding-top: 48px;
  width: 100%;
  max-width: 720px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.footer-inner {
  display: flex;
  gap: 48px;
  flex-wrap: wrap;
}

.footer-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.footer-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.footer-link,
.footer-text {
  font-size: 13px;
  color: var(--muted);
  text-decoration: none;
  transition: color 0.2s;
}

.footer-link:hover {
  color: var(--glow);
}

/* 平板 */
@media (max-width: 768px) {
  .home {
    padding: 24px 12px;
  }
  .hero-title {
    font-size: 28px;
  }
  .cards {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .app-card {
    padding: 28px 20px;
  }
  .card-avatar {
    width: 64px;
    height: 64px;
    font-size: 32px;
  }
}

/* 手机 */
@media (max-width: 480px) {
  .hero-title {
    font-size: 24px;
  }
  .hero-slogan {
    font-size: 13px;
  }
  .cards {
    margin-bottom: 0;
  }
  .footer-inner {
    flex-direction: column;
    gap: 24px;
  }
}
</style>
