<template>
  <article
    class="suggestion-card"
    :class="`suggestion-card--${localSuggestion.status || 'pending'}`"
    :aria-labelledby="titleId"
    :aria-busy="loading ? 'true' : 'false'"
  >
    <div class="suggestion-card__accent" aria-hidden="true"></div>
    <header class="suggestion-card__header">
      <div class="suggestion-card__identity">
        <span class="suggestion-card__icon" aria-hidden="true">
          <el-icon><component :is="resourceIcon" /></el-icon>
        </span>
        <div>
          <p>{{ resourceMeta.sectionLabel || '职业计划' }}建议</p>
          <h3 :id="titleId">{{ localSuggestion.title }}</h3>
        </div>
      </div>
      <span class="suggestion-card__status">{{ statusLabel }}</span>
    </header>

    <p v-if="localSuggestion.reason" class="suggestion-card__reason">
      {{ localSuggestion.reason }}
    </p>

    <dl v-if="previewItems.length" class="suggestion-card__preview">
      <div v-for="item in previewItems" :key="item.key">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>

    <div v-if="relationHintLabels.length" class="suggestion-card__relations" aria-label="建议关联记录">
      <span>关联建议</span>
      <el-tag v-for="hint in relationHintLabels" :key="hint" size="small" effect="plain">
        {{ hint }}
      </el-tag>
    </div>

    <details v-if="hasLongPreview" class="suggestion-card__details">
      <summary>查看完整建议内容</summary>
      <pre>{{ formattedPayload }}</pre>
    </details>

    <div v-if="error" class="suggestion-card__error" role="alert">
      <span>{{ error }}</span>
      <el-button v-if="retryAction" text size="small" :disabled="loading" @click="retry">重试</el-button>
    </div>

    <p class="sr-only" aria-live="polite" aria-atomic="true">{{ announcement }}</p>

    <footer class="suggestion-card__actions">
      <template v-if="localSuggestion.status === 'pending'">
        <el-button :disabled="loading" @click="editorOpen = true">编辑</el-button>
        <el-button :disabled="loading" @click="performDismiss">忽略</el-button>
        <el-button type="primary" :loading="loading && activeAction === 'accept'" :disabled="loading" @click="handlePrimaryAction">
          {{ requiresRelationSelection ? '先选择关联记录' : '确认添加' }}
        </el-button>
      </template>

      <template v-else-if="localSuggestion.status === 'dismissed'">
        <span>这条建议已忽略，不会写入职业数据。</span>
        <el-button :loading="loading" :disabled="loading" @click="performRestore">恢复建议</el-button>
      </template>

      <template v-else-if="localSuggestion.status === 'accepted'">
        <span class="suggestion-card__accepted-copy">
          <el-icon aria-hidden="true"><CircleCheckFilled /></el-icon>
          已添加到{{ resourceMeta.sectionLabel || '职业板块' }}
        </span>
        <el-button
          v-if="resourceMeta.routeName"
          class="suggestion-card__resource-link"
          text
          :loading="loading && activeAction === 'open'"
          :disabled="loading"
          @click="openCreatedResource"
        >
          查看记录
        </el-button>
      </template>
    </footer>

    <CareerSuggestionEditor
      v-model="editorOpen"
      :suggestion="localSuggestion"
      :saving="loading && activeAction === 'save'"
      @save="saveDraft"
    />
  </article>
</template>

<script setup>
import { computed, markRaw, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Briefcase,
  CircleCheckFilled,
  Collection,
  DataAnalysis,
  Document,
  List,
  Medal
} from '@element-plus/icons-vue'
import {
  acceptCareerSuggestion,
  dismissCareerSuggestion,
  getCareerResource,
  getErrorMessage,
  restoreCareerSuggestion,
  updateCareerSuggestion
} from '../api'
import {
  getOptionLabel,
  getSuggestionFields,
  suggestionResourceDefinitions
} from '../career/resources'
import CareerSuggestionEditor from './CareerSuggestionEditor.vue'

const props = defineProps({
  suggestion: { type: Object, required: true }
})

const emit = defineEmits(['update'])
const router = useRouter()
const localSuggestion = ref({ ...props.suggestion })
const loading = ref(false)
const activeAction = ref('')
const error = ref('')
const announcement = ref('')
const editorOpen = ref(false)
const retryAction = ref(null)
let mounted = true

const resourceIcons = {
  resumes: markRaw(Document),
  jobs: markRaw(Briefcase),
  applications: markRaw(List),
  interviews: markRaw(Collection),
  reports: markRaw(DataAnalysis),
  skills: markRaw(Medal),
  interview_questions: markRaw(Collection)
}

const resourceMeta = computed(() => (
  suggestionResourceDefinitions[localSuggestion.value.resource_type] || {}
))
const resourceIcon = computed(() => resourceIcons[localSuggestion.value.resource_type] || Document)
const titleId = computed(() => `career-suggestion-${localSuggestion.value.id}-title`)
const statusLabel = computed(() => ({
  pending: '待确认',
  accepted: '已添加',
  dismissed: '已忽略'
}[localSuggestion.value.status] || '待确认'))
const formattedPayload = computed(() => JSON.stringify(localSuggestion.value.payload || {}, null, 2))
const hasLongPreview = computed(() => formattedPayload.value.length > 180)
const requiresRelationSelection = computed(() => {
  const payload = localSuggestion.value.payload || {}
  if (localSuggestion.value.resource_type === 'applications') return !payload.job_id
  if (localSuggestion.value.resource_type === 'interview_questions') return !payload.interview_id
  return false
})

const routeQuery = computed(() => {
  if (localSuggestion.value.resource_type === 'interview_questions') {
    const interviewId = localSuggestion.value.payload?.interview_id
    return interviewId ? { highlight: String(interviewId) } : undefined
  }
  const created = localSuggestion.value.created_resource
  const id = created?.id || created?.ids?.[0]
  return id ? { highlight: String(id) } : undefined
})
const stringValue = (value, field = null) => {
  if (value === null || value === undefined || value === '') return '未设置'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return `${value.length} 项`
  if (typeof value === 'object') return JSON.stringify(value)
  if (field?.options) return getOptionLabel(field.options, value)
  const text = String(value).replace(/\s+/g, ' ').trim()
  return text.length > 90 ? `${text.slice(0, 90)}…` : text
}

const previewItems = computed(() => {
  const payload = localSuggestion.value.payload || {}
  if (localSuggestion.value.resource_type === 'interview_questions') {
    const questions = Array.isArray(payload.questions) ? payload.questions : (payload.question ? [payload] : [])
    return [
      { key: 'interview_id', label: '目标面试', value: payload.interview_title || `面试 #${payload.interview_id || '待选择'}` },
      { key: 'question_count', label: '题目数量', value: `${questions.length} 题` },
      ...(questions[0]?.question
        ? [{ key: 'first_question', label: '首题', value: stringValue(questions[0].question) }]
        : [])
    ]
  }

  const fields = getSuggestionFields(localSuggestion.value.resource_type)
  return fields
    .filter((field) => payload[field.key] !== null && payload[field.key] !== undefined && payload[field.key] !== '')
    .slice(0, 4)
    .map((field) => ({
      key: field.key,
      label: field.label,
      value: stringValue(payload[field.key], field)
    }))
})

const relationHintLabels = computed(() => {
  const hints = localSuggestion.value.relation_hints
  if (!hints || typeof hints !== 'object') return []
  return Object.values(hints)
    .flatMap((hint) => Array.isArray(hint) ? hint : [hint])
    .filter(Boolean)
    .map((hint) => typeof hint === 'string' ? hint : (hint.label || hint.title || hint.name))
    .filter(Boolean)
})

const unwrapSuggestion = (response) => response?.data?.suggestion || response?.data || response

const applyAuthoritativeSuggestion = (next) => {
  if (!next || typeof next !== 'object' || !next.id) throw new Error('服务器未返回有效的建议状态。')
  localSuggestion.value = { ...localSuggestion.value, ...next }
  emit('update', localSuggestion.value)
}

const runAction = async (action, request, successMessage, { closeEditor = false } = {}) => {
  if (loading.value) return
  loading.value = true
  activeAction.value = action
  error.value = ''
  announcement.value = ''
  retryAction.value = () => runAction(action, request, successMessage, { closeEditor })
  try {
    const response = await request()
    if (!mounted) return
    applyAuthoritativeSuggestion(unwrapSuggestion(response))
    if (closeEditor) editorOpen.value = false
    retryAction.value = null
    announcement.value = successMessage
  } catch (requestError) {
    if (!mounted) return
    error.value = getErrorMessage(requestError, '建议操作失败，请稍后重试。')
    announcement.value = error.value
  } finally {
    if (mounted) {
      loading.value = false
      activeAction.value = ''
    }
  }
}

const saveDraft = (payload) => runAction(
  'save',
  () => updateCareerSuggestion(localSuggestion.value.id, localSuggestion.value.revision, payload),
  '建议草稿已保存。',
  { closeEditor: true }
)

const performAccept = () => runAction(
  'accept',
  () => acceptCareerSuggestion(localSuggestion.value.id, localSuggestion.value.revision),
  `已添加到${resourceMeta.value.sectionLabel || '职业板块'}。`
)

const handlePrimaryAction = () => {
  if (requiresRelationSelection.value) {
    editorOpen.value = true
    return
  }
  void performAccept()
}

const performDismiss = () => runAction(
  'dismiss',
  () => dismissCareerSuggestion(localSuggestion.value.id, localSuggestion.value.revision),
  '建议已忽略。'
)

const performRestore = () => runAction(
  'restore',
  () => restoreCareerSuggestion(localSuggestion.value.id, localSuggestion.value.revision),
  '建议已恢复，确认前不会写入职业数据。'
)

const openCreatedResource = async () => {
  if (loading.value) return
  const created = localSuggestion.value.created_resource || {}
  const isQuestionBatch = localSuggestion.value.resource_type === 'interview_questions'
  const resource = isQuestionBatch ? 'interviews' : localSuggestion.value.resource_type
  const id = isQuestionBatch
    ? localSuggestion.value.payload?.interview_id
    : (created.id || created.ids?.[0])

  loading.value = true
  activeAction.value = 'open'
  error.value = ''
  try {
    if (id) await getCareerResource(resource, id)
    if (!mounted) return
    await router.push({ name: resourceMeta.value.routeName, query: routeQuery.value })
  } catch (requestError) {
    if (!mounted) return
    error.value = requestError?.status === 404 || requestError?.response?.status === 404
      ? '这条建议创建的记录已被删除，无法继续查看。'
      : getErrorMessage(requestError, '暂时无法打开记录，请稍后重试。')
    announcement.value = error.value
  } finally {
    if (mounted) {
      loading.value = false
      activeAction.value = ''
    }
  }
}

const retry = () => retryAction.value?.()

watch(() => props.suggestion, (suggestion) => {
  localSuggestion.value = { ...suggestion }
}, { deep: true })

onBeforeUnmount(() => {
  mounted = false
})
</script>

<style scoped>
.suggestion-card {
  position: relative;
  display: grid;
  gap: var(--space-4);
  max-width: 48rem;
  margin: var(--space-4) 0 var(--space-2) var(--space-8);
  padding: var(--space-5);
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
  border-radius: var(--radius-card);
  background:
    linear-gradient(135deg, var(--color-primary-soft), transparent 42%),
    var(--color-surface-elevated);
  box-shadow: var(--shadow-card);
}

.suggestion-card--accepted {
  border-color: color-mix(in srgb, var(--color-success-text) 32%, var(--color-border));
  background:
    linear-gradient(135deg, var(--color-success-soft), transparent 44%),
    var(--color-surface-elevated);
}

.suggestion-card--dismissed {
  border-color: var(--color-border);
  background: var(--color-surface-subtle);
}

.suggestion-card__accent {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 3px;
  background: var(--aurora-gradient);
}

.suggestion-card--accepted .suggestion-card__accent {
  background: var(--color-success-text);
}

.suggestion-card--dismissed .suggestion-card__accent {
  background: var(--color-text-muted);
}

.suggestion-card__header,
.suggestion-card__identity,
.suggestion-card__relations,
.suggestion-card__actions,
.suggestion-card__accepted-copy {
  display: flex;
  align-items: center;
}

.suggestion-card__header {
  justify-content: space-between;
  gap: var(--space-4);
}

.suggestion-card__identity {
  min-width: 0;
  gap: var(--space-3);
}

.suggestion-card__identity p,
.suggestion-card__identity h3,
.suggestion-card__reason {
  margin: 0;
}

.suggestion-card__identity p {
  color: var(--color-cyan);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  font-weight: 650;
  letter-spacing: .06em;
}

.suggestion-card__identity h3 {
  margin-top: var(--space-1);
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
  line-height: 1.35;
}

.suggestion-card__icon {
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--radius-control);
  background: var(--color-primary-soft);
  color: var(--color-cyan);
}

.suggestion-card__status {
  flex: 0 0 auto;
  padding: .25rem .6rem;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-pill);
  color: var(--color-text-secondary);
  font-size: var(--font-size-caption);
  font-weight: 650;
}

.suggestion-card__reason {
  color: var(--color-text-secondary);
  line-height: 1.65;
}

.suggestion-card__preview {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
  margin: 0;
}

.suggestion-card__preview > div {
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--color-surface) 82%, transparent);
}

.suggestion-card__preview dt {
  margin-bottom: var(--space-1);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.suggestion-card__preview dd {
  margin: 0;
  overflow-wrap: anywhere;
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  line-height: 1.5;
}

.suggestion-card__relations {
  flex-wrap: wrap;
  gap: var(--space-2);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.suggestion-card__details summary {
  color: var(--color-electric-blue);
  font-size: var(--font-size-label);
  font-weight: 650;
  cursor: pointer;
}

.suggestion-card__details summary:focus-visible {
  border-radius: var(--radius-control);
  outline: none;
  box-shadow: var(--focus-ring);
}

.suggestion-card__details pre {
  max-height: 18rem;
  margin: var(--space-3) 0 0;
  padding: var(--space-3);
  overflow: auto;
  border-radius: var(--radius-control);
  background: var(--color-canvas-deep);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.suggestion-card__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-control);
  background: var(--color-danger-soft);
  color: var(--color-danger-text);
  font-size: var(--font-size-label);
}

.suggestion-card__actions {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.suggestion-card__actions > span:first-child {
  margin-right: auto;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.suggestion-card__accepted-copy {
  gap: var(--space-2);
  color: var(--color-success-text) !important;
  font-weight: 650;
}

.suggestion-card__resource-link {
  --el-button-text-color: var(--color-electric-blue);
  --el-button-hover-text-color: var(--color-cyan);
  --el-button-hover-bg-color: var(--color-primary-soft);
  min-height: 2.5rem;
  padding: .65rem var(--space-3);
  border-radius: var(--radius-control);
  font-size: var(--font-size-label);
  font-weight: 650;
}

@media (max-width: 680px) {
  .suggestion-card {
    margin-left: 0;
    padding: var(--space-4);
  }

  .suggestion-card__header {
    align-items: flex-start;
  }

  .suggestion-card__preview {
    grid-template-columns: minmax(0, 1fr);
  }

  .suggestion-card__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .suggestion-card__actions > span:first-child {
    margin: 0 0 var(--space-2);
  }

  .suggestion-card__actions :deep(.el-button),
  .suggestion-card__resource-link {
    width: 100%;
    margin: 0 !important;
    text-align: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .suggestion-card,
  .suggestion-card * {
    scroll-behavior: auto;
    transition-duration: .01ms !important;
  }
}
</style>
