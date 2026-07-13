<template>
  <el-drawer
    :model-value="modelValue"
    class="insight-drawer-shell"
    direction="rtl"
    :size="size"
    @update:model-value="emit('update:modelValue', $event)"
    @open="emit('open')"
    @opened="emit('opened')"
    @close="emit('close')"
    @closed="emit('closed')"
  >
    <template #header="{ close, titleId, titleClass }">
      <slot
        name="header"
        :close="close"
        :title-id="titleId"
        :title-class="titleClass"
      />
    </template>

    <div class="insight-drawer-shell__content">
      <slot />
    </div>
  </el-drawer>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  size: { type: [String, Number], default: 'min(600px, 100vw)' }
})

const emit = defineEmits(['update:modelValue', 'open', 'opened', 'close', 'closed'])
</script>

<style>
.insight-drawer-shell {
  overflow: hidden;
  border-left: 1px solid var(--color-border-strong);
  background:
    radial-gradient(circle at 18% 0, var(--color-aurora-violet-soft), transparent 24rem),
    var(--color-surface-elevated);
  box-shadow: var(--shadow-dialog);
}

.insight-drawer-shell .el-drawer__header {
  position: relative;
  flex: 0 0 auto;
  min-height: 5.5rem;
  padding: var(--space-5) var(--space-6);
  margin: 0;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-primary);
  background: color-mix(in srgb, var(--color-surface-glass) 88%, transparent);
}

.insight-drawer-shell .el-drawer__header::after {
  position: absolute;
  right: var(--space-6);
  bottom: -1px;
  left: var(--space-6);
  height: 1px;
  background: var(--aurora-gradient);
  content: '';
  opacity: .72;
}

.insight-drawer-shell .el-drawer__close-btn {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  place-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
}

.insight-drawer-shell .el-drawer__close-btn:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.insight-drawer-shell .el-drawer__close-btn:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.insight-drawer-shell .el-drawer__body {
  min-height: 0;
  padding: 0;
  overflow: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.insight-drawer-shell__content {
  min-height: 100%;
  padding: var(--space-6);
}

@media (max-width: 600px) {
  .insight-drawer-shell {
    border-left: 0;
  }

  .insight-drawer-shell .el-drawer__header {
    min-height: 4.75rem;
    padding: var(--space-4);
  }

  .insight-drawer-shell .el-drawer__header::after {
    right: var(--space-4);
    left: var(--space-4);
  }

  .insight-drawer-shell__content {
    padding: var(--space-5) var(--space-4) max(var(--space-6), env(safe-area-inset-bottom));
  }
}

@media (prefers-reduced-transparency: reduce) {
  .insight-drawer-shell,
  .insight-drawer-shell .el-drawer__header {
    background: var(--color-surface-elevated);
  }
}
</style>
