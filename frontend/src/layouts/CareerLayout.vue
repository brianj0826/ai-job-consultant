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
        v-for="item in careerNavigation"
        :key="item.routeName"
        class="career-layout__navigation-link"
        :to="{ name: item.routeName }"
      >
        {{ item.label }}
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
  min-height: 100%;
  padding: clamp(var(--space-5), 4vw, var(--space-10)) var(--page-padding) var(--space-12);
  overflow-y: auto;
  background: var(--color-canvas);
}

.career-layout__header,
.career-layout__navigation,
.career-layout__content {
  width: min(100%, var(--content-max-width));
  margin-inline: auto;
}

.career-layout__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}

.career-layout__copy {
  max-width: 46rem;
}

.career-layout__eyebrow {
  margin: 0 0 var(--space-2);
  color: var(--color-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 700;
  letter-spacing: .1em;
}

.career-layout__copy h2 {
  margin: 0 0 var(--space-2);
  font-size: clamp(1.65rem, 3vw, var(--font-size-page-title));
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
  display: flex;
  flex: 0 0 auto;
  gap: var(--space-2);
}

.career-layout__navigation {
  display: flex;
  gap: var(--space-1);
  padding-bottom: var(--space-2);
  margin-bottom: var(--space-6);
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
  scrollbar-width: none;
}

.career-layout__navigation::-webkit-scrollbar {
  display: none;
}

.career-layout__navigation-link {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  flex: 0 0 auto;
  padding: var(--space-2) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 600;
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
  border-color: color-mix(in srgb, var(--color-primary) 24%, transparent);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.career-layout__navigation-link:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

@media (max-width: 767px) {
  .career-layout {
    padding-top: var(--space-6);
  }

  .career-layout__header {
    align-items: stretch;
    flex-direction: column;
    gap: var(--space-4);
  }

  .career-layout__actions,
  .career-layout__actions :deep(.el-button) {
    width: 100%;
  }

  .career-layout__actions :deep(.el-button) {
    min-height: 44px;
  }
}
</style>
