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
  background: radial-gradient(1200px 800px at 10% 0%, rgba(99, 102, 241, 0.18), transparent 60%),
    radial-gradient(1000px 800px at 90% 10%, rgba(20, 184, 166, 0.16), transparent 60%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 1));
  color: var(--text);
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  backdrop-filter: blur(10px);
  background: rgba(2, 6, 23, 0.5);
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.logo {
  width: 34px;
  height: 34px;
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
  padding: 8px 10px;
  border-radius: 10px;
  color: rgba(226, 232, 240, 0.84);
  text-decoration: none;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.3);
}
.nav-link.router-link-active {
  color: rgba(255, 255, 255, 0.95);
  border-color: rgba(99, 102, 241, 0.45);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
}

.main {
  padding: 18px;
  max-width: 1100px;
  margin: 0 auto;
}
</style>

