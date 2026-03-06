<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand" @click="$router.push('/')">
        <div class="logo">R</div>
        <div class="brand-text">
          <div class="brand-title">Rui AI Agent</div>
          <div class="brand-subtitle">Vue3 · SSE · Axios</div>
        </div>
      </div>
      <nav class="nav">
        <RouterLink class="nav-link" to="/">主页</RouterLink>
        <RouterLink class="nav-link" to="/love">AI 恋爱大师</RouterLink>
        <RouterLink class="nav-link" to="/manus">AI 超级智能体</RouterLink>
      </nav>
    </header>

    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(34, 211, 238, 0.08), transparent 50%),
    radial-gradient(ellipse 60% 40% at 20% 80%, rgba(99, 102, 241, 0.06), transparent 45%),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(20, 184, 166, 0.06), transparent 45%),
    linear-gradient(180deg, #0f172a 0%, #020617 100%);
  color: var(--text);
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  backdrop-filter: blur(10px);
  background: rgba(2, 6, 23, 0.5);
}

@media (min-width: 768px) {
  .topbar {
    padding: 14px 18px;
  }
  .logo {
    width: 34px;
    height: 34px;
    font-size: inherit;
  }
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.logo {
  width: 32px;
  height: 32px;
  font-size: 18px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 800;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.9), rgba(20, 184, 166, 0.85));
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}

.brand-title {
  font-weight: 700;
}
.brand-subtitle {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.68);
}

.nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.nav-link {
  padding: 6px 10px;
  border-radius: 10px;
  color: rgba(226, 232, 240, 0.84);
  text-decoration: none;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.3);
  font-size: 14px;
  transition: border-color 0.15s ease, color 0.15s ease;
}
@media (min-width: 768px) {
  .nav-link {
    padding: 8px 10px;
  }
}
.nav-link.router-link-active {
  color: rgba(255, 255, 255, 0.95);
  border-color: rgba(99, 102, 241, 0.45);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
}

.main {
  padding: 12px 14px;
  max-width: 1100px;
  margin: 0 auto;
  min-height: calc(100vh - 60px);
}

@media (min-width: 768px) {
  .main {
    padding: 18px;
  }
}
</style>

