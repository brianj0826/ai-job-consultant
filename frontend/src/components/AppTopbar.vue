<template>
  <header class="app-topbar">
    <div class="app-topbar__leading">
      <button
        ref="navigationToggleRef"
        class="app-topbar__nav-toggle"
        type="button"
        :aria-label="navigationOpen ? '关闭导航' : '打开导航'"
        :aria-expanded="navigationOpen"
        aria-controls="app-navigation"
        @click="$emit('toggle-navigation', $event)"
      >
        <el-icon :size="20" aria-hidden="true">
          <Close v-if="navigationOpen" />
          <Menu v-else />
        </el-icon>
      </button>

      <div class="app-topbar__titles" aria-live="polite">
        <Transition name="topbar-title" mode="out-in">
          <div :key="viewKey" class="app-topbar__title-copy">
            <h1 class="app-topbar__title">{{ title }}</h1>
            <p v-if="context" class="app-topbar__context">{{ context }}</p>
          </div>
        </Transition>
      </div>
    </div>

    <div v-if="username" class="app-topbar__account" :aria-label="`当前用户：${username}`">
      <span class="app-topbar__account-icon" aria-hidden="true">
        <el-icon :size="16"><User /></el-icon>
      </span>
      <span class="app-topbar__account-copy">
        <span class="app-topbar__account-label">SIGNED IN</span>
        <span class="app-topbar__account-name">{{ username }}</span>
      </span>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { Close, Menu, User } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, required: true },
  context: { type: String, default: '' },
  username: { type: String, default: '' },
  navigationOpen: { type: Boolean, default: false },
  viewKey: { type: String, default: '' }
})

defineEmits(['toggle-navigation'])

const navigationToggleRef = ref(null)

defineExpose({
  focusNavigationToggle: () => navigationToggleRef.value?.focus()
})
</script>

<style scoped>
.app-topbar {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: var(--topbar-height);
  padding: 0 var(--page-padding);
  border-bottom: 1px solid var(--color-border-strong);
  background: var(--color-surface-elevated);
}

@supports ((-webkit-backdrop-filter: blur(1px)) or (backdrop-filter: blur(1px))) {
  .app-topbar {
    background:
      linear-gradient(90deg, var(--color-aurora-violet-soft), transparent 42%),
      var(--color-surface-glass);
    -webkit-backdrop-filter: blur(18px);
    backdrop-filter: blur(18px);
  }
}

.app-topbar__leading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.app-topbar__nav-toggle {
  display: none;
  flex: 0 0 44px;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    color var(--duration-control) var(--ease-standard),
    border-color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard);
}

.app-topbar__nav-toggle:hover {
  border-color: color-mix(in srgb, var(--color-primary) 36%, var(--color-border));
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.app-topbar__nav-toggle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong, var(--focus-ring));
}

.app-topbar__titles {
  display: grid;
  min-width: 0;
}

.app-topbar__title-copy {
  grid-area: 1 / 1;
  min-width: 0;
}

.topbar-title-enter-active {
  transition:
    opacity var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard)),
    transform var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard));
}

.topbar-title-leave-active {
  transition:
    opacity var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard)),
    transform var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard));
}

.topbar-title-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.topbar-title-leave-to {
  opacity: 0;
  transform: translateY(-2px);
}

.app-topbar__title {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: var(--line-height-component-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-topbar__context {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  letter-spacing: 0.035em;
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-topbar__account {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-1) var(--space-3) var(--space-1) var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: color-mix(in srgb, var(--color-surface-subtle) 82%, transparent);
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 500;
}

.app-topbar__account-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 28%, var(--color-border));
  border-radius: var(--radius-pill);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.app-topbar__account-copy {
  display: grid;
  min-width: 0;
}

.app-topbar__account-label {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 600;
  letter-spacing: 0.11em;
  line-height: var(--line-height-caption);
}

.app-topbar__account-name {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: var(--line-height-label);
}

@media (max-width: 767px) {
  .app-topbar {
    padding-right: max(var(--space-4), env(safe-area-inset-right));
    padding-left: max(var(--space-4), env(safe-area-inset-left));
  }

  .app-topbar__nav-toggle {
    display: inline-flex;
  }

  .app-topbar__account-copy {
    display: none;
  }

  .app-topbar__account {
    gap: 0;
    padding: var(--space-1);
    border-color: transparent;
    background: transparent;
  }

}

@media (prefers-reduced-transparency: reduce) {
  .app-topbar,
  .app-topbar__account {
    background: var(--color-surface-elevated);
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .topbar-title-enter-active,
  .topbar-title-leave-active {
    transition-duration: 0.01ms;
  }

  .topbar-title-enter-from,
  .topbar-title-leave-to {
    transform: none;
  }
}
</style>
