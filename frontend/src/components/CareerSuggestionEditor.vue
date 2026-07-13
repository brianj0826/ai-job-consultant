<template>
  <el-dialog
    :model-value="modelValue"
    class="suggestion-editor-dialog"
    width="min(46rem, calc(100vw - 2rem))"
    :title="`编辑${resourceMeta.label || '职业'}建议`"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @opened="focusFirstField"
  >
    <form class="suggestion-editor" novalidate @submit.prevent="submit">
      <p class="suggestion-editor__intro">
        修改只会保存为待确认草稿。点击“确认添加”前，不会写入{{ resourceMeta.sectionLabel || '职业板块' }}。
      </p>

      <div v-if="formError" class="suggestion-editor__error" role="alert">{{ formError }}</div>
      <div v-if="relationError" class="suggestion-editor__error" role="alert">
        {{ relationError }}
        <el-button text size="small" @click="loadRelations">重新加载</el-button>
      </div>

      <template v-if="suggestion.resource_type === 'interview_questions'">
        <div class="suggestion-editor__field">
          <label for="suggestion-interview-id">添加到面试 <span aria-hidden="true">*</span></label>
          <el-select
            id="suggestion-interview-id"
            v-model="form.interview_id"
            class="suggestion-editor__control"
            filterable
            :loading="relationLoading"
            placeholder="请选择已有面试"
            aria-label="添加到面试"
          >
            <el-option
              v-for="item in relationOptions"
              :key="item.id"
              :label="relationLabel(item, 'interviews')"
              :value="item.id"
            />
          </el-select>
          <p v-if="!relationLoading && !relationOptions.length" class="suggestion-editor__hint">
            还没有可关联的面试，请先到面试中心创建。
          </p>
        </div>

        <section class="question-batch" aria-labelledby="suggestion-questions-heading">
          <div class="question-batch__heading">
            <div>
              <h3 id="suggestion-questions-heading">题目批次</h3>
              <p>一次最多添加 10 题；确认时将整批写入或整批回滚。</p>
            </div>
            <el-button
              native-type="button"
              :disabled="questions.length >= 10"
              @click="addQuestion"
            >
              添加题目
            </el-button>
          </div>

          <ol class="question-batch__list">
            <li v-for="(question, index) in questions" :key="question._key" class="question-batch__item">
              <div class="question-batch__item-heading">
                <strong>第 {{ index + 1 }} 题</strong>
                <div class="question-batch__item-actions" :aria-label="`调整第 ${index + 1} 题`">
                  <el-button
                    text
                    size="small"
                    native-type="button"
                    :disabled="index === 0"
                    :aria-label="`上移第 ${index + 1} 题`"
                    @click="moveQuestion(index, -1)"
                  >
                    上移
                  </el-button>
                  <el-button
                    text
                    size="small"
                    native-type="button"
                    :disabled="index === questions.length - 1"
                    :aria-label="`下移第 ${index + 1} 题`"
                    @click="moveQuestion(index, 1)"
                  >
                    下移
                  </el-button>
                  <el-button
                    text
                    size="small"
                    type="danger"
                    native-type="button"
                    :disabled="questions.length === 1"
                    :aria-label="`删除第 ${index + 1} 题`"
                    @click="removeQuestion(index)"
                  >
                    删除
                  </el-button>
                </div>
              </div>

              <label :for="`suggestion-question-${index}`">题目 <span aria-hidden="true">*</span></label>
              <el-input
                :id="`suggestion-question-${index}`"
                v-model="question.question"
                type="textarea"
                :rows="3"
                maxlength="10000"
              />
              <label :for="`suggestion-reference-${index}`">AI 参考答案</label>
              <el-input
                :id="`suggestion-reference-${index}`"
                v-model="question.reference_answer"
                type="textarea"
                :rows="4"
                maxlength="50000"
              />
              <label :for="`suggestion-coaching-${index}`">解题思路与辅导建议</label>
              <el-input
                :id="`suggestion-coaching-${index}`"
                v-model="question.coaching_notes"
                type="textarea"
                :rows="3"
                maxlength="20000"
              />
            </li>
          </ol>
        </section>
      </template>

      <template v-else>
        <div v-for="field in fields" :key="field.key" class="suggestion-editor__field">
          <label :for="fieldId(field)">
            {{ field.label }}
            <span v-if="field.required" aria-hidden="true">*</span>
          </label>

          <el-input
            v-if="field.type === 'textarea' || field.type === 'json'"
            :id="fieldId(field)"
            v-model="form[field.key]"
            class="suggestion-editor__control"
            type="textarea"
            :rows="Math.min(field.rows || 5, 8)"
            :maxlength="field.maxlength"
            :placeholder="field.placeholder"
            :aria-required="field.required || undefined"
          />

          <el-select
            v-else-if="field.type === 'select'"
            :id="fieldId(field)"
            v-model="form[field.key]"
            class="suggestion-editor__control"
            :aria-label="field.label"
            :placeholder="`请选择${field.label}`"
            @change="field.key === 'entity_type' && handleEntityTypeChange()"
          >
            <el-option
              v-for="option in field.options"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>

          <el-select
            v-else-if="field.type === 'relation' || field.key === 'entity_id'"
            :id="fieldId(field)"
            v-model="form[field.key]"
            class="suggestion-editor__control"
            clearable
            filterable
            :loading="relationLoading"
            :disabled="field.key === 'entity_id' && !form.entity_type"
            :aria-label="field.label"
            :placeholder="relationPlaceholder(field)"
          >
            <el-option
              v-for="item in relationOptions"
              :key="item.id"
              :label="relationLabel(item, relationResource)"
              :value="item.id"
            />
          </el-select>

          <div v-else-if="field.type === 'range'" class="suggestion-editor__range">
            <input
              :id="fieldId(field)"
              v-model.number="form[field.key]"
              type="range"
              :min="field.min"
              :max="field.max"
            />
            <output :for="fieldId(field)">{{ form[field.key] }}%</output>
          </div>

          <input
            v-else
            :id="fieldId(field)"
            v-model="form[field.key]"
            class="suggestion-editor__native-input"
            :type="field.inputType || field.type || 'text'"
            :min="field.min"
            :max="field.max"
            :maxlength="field.maxlength"
            :placeholder="field.placeholder"
            :required="field.required"
          />

          <p v-if="field.type === 'json'" class="suggestion-editor__hint">
            请输入合法 JSON；该内容将作为报告的结构化结果保存。
          </p>
          <p
            v-else-if="(field.type === 'relation' || field.key === 'entity_id') && !relationLoading && !relationOptions.length"
            class="suggestion-editor__hint"
          >
            暂无可关联记录。你可以先关闭编辑器，到对应板块创建记录。
          </p>
        </div>
      </template>
    </form>

    <template #footer>
      <div class="suggestion-editor__footer">
        <el-button :disabled="saving" @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存草稿</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { getCareerResources, getErrorMessage } from '../api'
import {
  getSuggestionFields,
  suggestionResourceDefinitions
} from '../career/resources'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  suggestion: { type: Object, required: true },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'save'])
const form = reactive({})
const questions = ref([])
const relationOptions = ref([])
const relationLoading = ref(false)
const relationError = ref('')
const formError = ref('')
let relationRequestId = 0
let questionSequence = 0

const resourceMeta = computed(() => (
  suggestionResourceDefinitions[props.suggestion.resource_type] || {}
))
const fields = computed(() => getSuggestionFields(props.suggestion.resource_type))
const reportEntityResource = computed(() => ({
  resume: 'resumes',
  job: 'jobs',
  application: 'applications',
  interview: 'interviews',
  skill: 'skills'
}[form.entity_type] || ''))
const relationResource = computed(() => {
  if (props.suggestion.resource_type === 'interview_questions') return 'interviews'
  if (props.suggestion.resource_type === 'applications' || props.suggestion.resource_type === 'interviews') return 'jobs'
  if (props.suggestion.resource_type === 'reports') return reportEntityResource.value
  return ''
})

const clone = (value) => {
  if (!value || typeof value !== 'object') return value
  return JSON.parse(JSON.stringify(value))
}

const makeQuestion = (question = {}) => ({
  _key: `question-${++questionSequence}`,
  position: question.position ?? null,
  question: question.question || '',
  reference_answer: question.reference_answer || '',
  coaching_notes: question.coaching_notes || ''
})

const hydrateForm = () => {
  formError.value = ''
  Object.keys(form).forEach((key) => delete form[key])
  const payload = clone(props.suggestion.payload || {})

  if (props.suggestion.resource_type === 'interview_questions') {
    form.interview_id = payload.interview_id || ''
    const sourceQuestions = Array.isArray(payload.questions)
      ? payload.questions
      : (payload.question ? [payload] : [{}])
    questions.value = sourceQuestions.slice(0, 10).map(makeQuestion)
    return
  }

  for (const field of fields.value) {
    let value = payload[field.key]
    if (field.type === 'json') value = JSON.stringify(value || {}, null, 2)
    if (value === null || value === undefined) value = field.default ?? ''
    form[field.key] = value
  }
}

const unwrapItems = (response) => {
  const data = response?.data
  if (Array.isArray(data)) return data
  return Array.isArray(data?.items) ? data.items : []
}

const loadRelations = async () => {
  const resource = relationResource.value
  const requestId = ++relationRequestId
  relationError.value = ''
  relationOptions.value = []
  if (!resource) return
  relationLoading.value = true
  try {
    const response = await getCareerResources(resource)
    if (requestId !== relationRequestId) return
    relationOptions.value = unwrapItems(response)
  } catch (error) {
    if (requestId !== relationRequestId) return
    relationError.value = getErrorMessage(error, '关联记录加载失败，请稍后重试。')
  } finally {
    if (requestId === relationRequestId) relationLoading.value = false
  }
}

const handleEntityTypeChange = () => {
  form.entity_id = ''
  void loadRelations()
}

const relationLabel = (item, resource) => {
  if (resource === 'jobs') return `${item.title || `岗位 #${item.id}`}${item.company ? ` · ${item.company}` : ''}`
  if (resource === 'interviews') return item.title || `面试 #${item.id}`
  if (resource === 'resumes') return item.title || `简历 #${item.id}`
  if (resource === 'applications') return item.job_title || item.next_action || `投递 #${item.id}`
  if (resource === 'skills') return item.skill || `技能 #${item.id}`
  return item.title || `记录 #${item.id}`
}

const relationPlaceholder = (field) => {
  if (field.key === 'entity_id' && !form.entity_type) return '请先选择关联类型'
  if (relationLoading.value) return '正在加载关联记录'
  return relationOptions.value.length ? `请选择${field.label}` : '暂无可关联记录'
}

const fieldId = (field) => `suggestion-${props.suggestion.id}-${field.key}`

const focusFirstField = () => {
  nextTick(() => {
    document.querySelector('.suggestion-editor-dialog input:not([disabled]), .suggestion-editor-dialog textarea:not([disabled]), .suggestion-editor-dialog [role="combobox"]')?.focus?.()
  })
}

const addQuestion = () => {
  if (questions.value.length >= 10) return
  questions.value = [...questions.value, makeQuestion()]
}

const removeQuestion = (index) => {
  if (questions.value.length <= 1) return
  questions.value = questions.value.filter((_, itemIndex) => itemIndex !== index)
}

const moveQuestion = (index, direction) => {
  const target = index + direction
  if (target < 0 || target >= questions.value.length) return
  const reordered = [...questions.value]
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  questions.value = reordered
}

const serialize = () => {
  if (props.suggestion.resource_type === 'interview_questions') {
    const interviewId = Number(form.interview_id)
    if (!Number.isInteger(interviewId) || interviewId <= 0) throw new Error('请选择要添加题目的面试。')
    if (!questions.value.length || questions.value.length > 10) throw new Error('题目数量必须为 1–10 题。')
    return {
      interview_id: interviewId,
      questions: questions.value.map((item, index) => {
        if (!item.question.trim()) throw new Error(`请填写第 ${index + 1} 题的题目。`)
        return {
          question: item.question.trim(),
          reference_answer: item.reference_answer.trim(),
          coaching_notes: item.coaching_notes.trim()
        }
      })
    }
  }

  const payload = {}
  for (const field of fields.value) {
    let value = form[field.key]
    if (field.required && (value === '' || value === null || value === undefined)) {
      throw new Error(`请填写${field.label}。`)
    }
    if (field.type === 'json') {
      try {
        value = JSON.parse(value || '{}')
      } catch {
        throw new Error(`${field.label}必须是合法 JSON。`)
      }
    } else if (field.type === 'number' || field.type === 'relation' || field.key === 'entity_id') {
      value = value === '' || value === null ? null : Number(value)
    } else if (typeof value === 'string') {
      value = value.trim()
    }
    payload[field.key] = value === '' && (field.nullable || field.type === 'date') ? null : value
  }

  if (props.suggestion.resource_type === 'resumes') payload.is_primary = false
  if (props.suggestion.resource_type === 'interviews') payload.overall_score = null
  if (props.suggestion.resource_type === 'reports' && !payload.entity_type) {
    payload.entity_type = null
    payload.entity_id = null
  }
  return payload
}

const submit = () => {
  formError.value = ''
  try {
    emit('save', serialize())
  } catch (error) {
    formError.value = error.message
  }
}

watch(() => props.modelValue, (open) => {
  if (!open) {
    relationRequestId += 1
    return
  }
  hydrateForm()
  void loadRelations()
}, { immediate: true })

watch(() => props.suggestion, () => {
  if (props.modelValue) hydrateForm()
}, { deep: true })
</script>

<style scoped>
.suggestion-editor {
  display: grid;
  gap: var(--space-5);
  max-height: min(68dvh, 44rem);
  padding-right: var(--space-1);
  overflow-y: auto;
}

.suggestion-editor__intro,
.suggestion-editor__hint,
.question-batch__heading p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  line-height: 1.55;
}

.suggestion-editor__error {
  padding: var(--space-3);
  border: 1px solid var(--color-danger-border, var(--color-border-strong));
  border-radius: var(--radius-control);
  background: var(--color-danger-soft);
  color: var(--color-danger-text);
}

.suggestion-editor__field {
  display: grid;
  gap: var(--space-2);
}

.suggestion-editor__field > label,
.question-batch__item > label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-label);
  font-weight: 650;
}

.suggestion-editor__control,
.suggestion-editor__native-input {
  width: 100%;
}

.suggestion-editor__native-input {
  min-height: 2.75rem;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-control);
  background: var(--color-surface-elevated);
  color: var(--color-text-primary);
  font: inherit;
}

.suggestion-editor__native-input:focus-visible,
.suggestion-editor__range input:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.suggestion-editor__range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 3.5rem;
  align-items: center;
  gap: var(--space-3);
}

.suggestion-editor__range output {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  text-align: right;
}

.question-batch {
  display: grid;
  gap: var(--space-4);
}

.question-batch__heading,
.question-batch__item-heading,
.suggestion-editor__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.question-batch__heading h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-component-title);
}

.question-batch__list {
  display: grid;
  gap: var(--space-4);
  margin: 0;
  padding: 0;
  list-style: none;
}

.question-batch__item {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
}

.question-batch__item-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 560px) {
  .question-batch__heading,
  .question-batch__item-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .question-batch__item-actions {
    justify-content: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .suggestion-editor-dialog * {
    scroll-behavior: auto;
  }
}
</style>
