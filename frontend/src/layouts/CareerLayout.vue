<template>
  <section class="career-layout" :aria-labelledby="headingId">
    <header class="career-layout__header">
      <div class="career-layout__copy">
        <p class="career-layout__eyebrow">{{ eyebrow }}</p>
        <h2 :id="headingId">{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <div class="career-layout__actions">
        <slot name="actions" />
      </div>
    </header>

    <nav class="career-layout__navigation" aria-label="职业工作区板块">
      <RouterLink
        v-for="(item, index) in careerNavigation"
        :key="item.routeName"
        class="career-layout__navigation-link"
        :to="{ name: item.routeName }"
      >
        <span class="career-layout__navigation-index" aria-hidden="true">
          {{ String(index + 1).padStart(2, '0') }}
        </span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="career-layout__content">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { careerNavigation } from '../career/resources'

const props = defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, default: 'CAREER WORKSPACE' },
  description: { type: String, default: '' }
})

const headingId = computed(() => `career-${props.title.replace(/\s+/g, '-').toLowerCase()}-title`)
</script>

<style scoped>
.career-layout {
  position: relative;
  isolation: isolate;
  min-height: 100%;
  padding: clamp(var(--space-6), 3vw, var(--space-10)) var(--page-padding) var(--space-12);
  overflow-y: auto;
  overflow-x: clip;
  background:
    radial-gradient(circle at 88% 0, var(--color-aurora-cyan-soft), transparent 24rem),
    transparent;
}

.career-layout__header,
.career-layout__navigation,
.career-layout__content {
  width: min(100%, var(--content-max-width));
  margin-inline: auto;
}

.career-layout__header {
  position: relative;
  display: grid;
  min-height: 13rem;
  align-items: end;
  grid-template-columns: minmax(0, 1fr) minmax(12rem, auto);
  gap: var(--space-8);
  padding: clamp(var(--space-6), 3vw, var(--space-8));
  margin-bottom: var(--space-4);
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-panel);
  background:
    linear-gradient(110deg, var(--color-surface) 0%, var(--color-surface) 58%, transparent 100%),
    var(--aurora-gradient-soft),
    var(--color-surface);
}

.career-layout__header::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 2px;
  background: var(--aurora-gradient);
  content: '';
  opacity: 0.82;
}

.career-layout__copy {
  position: relative;
  z-index: 1;
  max-width: 46rem;
}

.career-layout__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-3);
  color: var(--color-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: .12em;
  line-height: var(--line-height-caption);
  text-transform: uppercase;
}

.career-layout__eyebrow::before {
  width: 1.5rem;
  height: 1px;
  background: var(--aurora-gradient);
  content: '';
}

.career-layout__copy h2 {
  margin: 0 0 var(--space-3);
  font-size: clamp(1.75rem, 3vw, var(--font-size-page-title));
  font-weight: 700;
  letter-spacing: -0.025em;
  line-height: var(--line-height-page-title);
}

.career-layout__copy > p:last-child {
  max-width: 65ch;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-large);
  line-height: var(--line-height-body-large);
}

.career-layout__actions {
  position: relative;
  z-index: 1;
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.career-layout__navigation {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-1);
  padding: var(--space-1);
  margin-bottom: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: calc(var(--radius-control) + var(--space-1));
  background: var(--color-surface);
  box-shadow: 0 8px 24px color-mix(in srgb, var(--color-canvas-deep) 56%, transparent);
}

.career-layout__navigation-link {
  position: relative;
  display: inline-flex;
  min-width: 0;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 650;
  line-height: var(--line-height-label);
  text-decoration: none;
  transition:
    color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard),
    border-color var(--duration-control) var(--ease-standard);
}

.career-layout__navigation-link:hover {
  border-color: var(--color-border);
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.career-layout__navigation-link.router-link-active {
  border-color: color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.career-layout__navigation-link.router-link-active::after {
  position: absolute;
  right: var(--space-3);
  bottom: 0.3rem;
  left: var(--space-3);
  height: 2px;
  border-radius: var(--radius-pill);
  background: var(--color-primary);
  content: '';
}

.career-layout__navigation-link:active {
  border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
  background: color-mix(in srgb, var(--color-primary-soft) 76%, var(--color-surface));
}

.career-layout__navigation-link:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.career-layout__navigation-index {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 600;
  letter-spacing: .04em;
}

.career-layout__navigation-link.router-link-active .career-layout__navigation-index {
  color: var(--color-primary);
}

.career-layout__navigation-link > span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.career-layout__content {
  position: relative;
  min-width: 0;
}

@media (max-width: 1100px) {
  .career-layout__navigation-link {
    gap: var(--space-1);
    padding-inline: var(--space-2);
  }

  .career-layout__navigation-index {
    display: none;
  }
}

@media (max-width: 767px) {
  .career-layout {
    padding-top: var(--space-5);
    padding-bottom: var(--space-8);
    background:
      radial-gradient(circle at 100% 0, var(--color-aurora-cyan-soft), transparent 17rem),
      transparent;
  }

  .career-layout__header {
    min-height: 0;
    align-items: stretch;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-5);
    padding: var(--space-5);
    border-radius: var(--radius-card);
  }

  .career-layout__copy h2 {
    margin-bottom: var(--space-2);
  }

  .career-layout__copy > p:last-child {
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
  }

  .career-layout__actions,
  .career-layout__actions :deep(.el-button) {
    width: 100%;
  }

  .career-layout__actions :deep(.el-button) {
    min-height: 44px;
  }

  .career-layout__navigation {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-1);
    margin-bottom: var(--space-5);
  }

  .career-layout__navigation-link {
    min-height: 44px;
    justify-content: flex-start;
    padding-inline: var(--space-3);
  }

  .career-layout__navigation-link.router-link-active::after {
    top: var(--space-2);
    right: auto;
    bottom: var(--space-2);
    left: 0.25rem;
    width: 2px;
    height: auto;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .career-layout__header,
  .career-layout__navigation {
    background: var(--color-surface);
  }
}
</style>
