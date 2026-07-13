<template>
  <CareerLayout
    :title="definition.title"
    :eyebrow="definition.eyebrow"
    :description="definition.description"
  >
    <template #actions>
      <el-button type="primary" :disabled="loading" @click="openCreate">
        <el-icon aria-hidden="true"><Plus /></el-icon>
        {{ definition.createLabel }}
      </el-button>
    </template>

    <InterviewBar
      v-if="resource === 'interviews' && selectedInterview"
      :active="true"
      :title="selectedInterview.title"
      :status="selectedInterview.status"
      :current="selectedInterview.current_question || 0"
      :total="selectedInterview.total_questions || selectedInterview.questions?.length || 0"
      :score="selectedInterview.overall_score"
      @start="setInterviewStatus('in_progress')"
      @end="setInterviewStatus('completed')"
      @score="focusInterviewQuestions"
    />

    <div
      class="resource-workspace"
      :class="{ 'resource-workspace--editing': editorOpen }"
      :data-resource="resource"
    >
      <section class="resource-panel" :aria-labelledby="`${resource}-list-title`">
        <div class="resource-panel__heading">
          <div class="resource-panel__identity">
            <p class="technical-label">RESOURCE INDEX</p>
            <h3 :id="`${resource}-list-title`">{{ definition.title }}记录</h3>
            <p v-if="!loading && !error" class="resource-panel__count" aria-live="polite">
              共 <span class="tabular-nums">{{ items.length }}</span> 条
            </p>
          </div>
          <el-button
            class="resource-panel__refresh"
            text
            :loading="loading"
            aria-label="刷新列表"
            @click="loadResources"
          >
            <el-icon aria-hidden="true"><Refresh /></el-icon>
            刷新
          </el-button>
        </div>

        <div v-if="loading" class="resource-state" aria-live="polite" aria-busy="true">
          <span class="resource-state__loader" aria-hidden="true"></span>
          <strong>正在加载{{ definition.title }}</strong>
          <p>正在同步你的结构化职业数据。</p>
        </div>

        <div v-else-if="error" class="resource-state resource-state--error" role="alert">
          <el-icon aria-hidden="true"><WarningFilled /></el-icon>
          <strong>暂时无法加载{{ definition.title }}</strong>
          <p>{{ error }}</p>
          <el-button @click="loadResources">重试</el-button>
        </div>

        <div v-else-if="!items.length" class="resource-state">
          <el-icon aria-hidden="true"><FolderOpened /></el-icon>
          <strong>还没有{{ definition.singular }}</strong>
          <p>创建第一条记录后，它会持续保存在这里，供后续投递和复盘使用。</p>
          <el-button type="primary" @click="openCreate">{{ definition.createLabel }}</el-button>
        </div>

        <ul v-else class="resource-list" :aria-label="`${definition.title}记录`">
          <li
            v-for="item in items"
            :key="item.id"
            class="resource-item"
            :class="{ 'resource-item--selected': selectedInterview?.id === item.id }"
          >
            <div class="resource-item__body">
              <div class="resource-item__title-row">
                <h4>{{ getItemTitle(item) }}</h4>
                <span v-if="getStatusLabel(item)" class="resource-status">
                  {{ getStatusLabel(item) }}
                </span>
              </div>
              <p v-if="getItemSubtitle(item)" class="resource-item__summary">
                {{ getItemSubtitle(item) }}
              </p>
              <el-progress
                v-if="resource === 'skills'"
                :percentage="Number(item.progress || 0)"
                :stroke-width="6"
                color="var(--color-primary)"
              />
              <dl class="resource-item__metadata">
                <div v-if="item.deadline || item.due_date">
                  <dt>目标日期</dt>
                  <dd>{{ item.deadline || item.due_date }}</dd>
                </div>
                <div>
                  <dt>最近更新</dt>
                  <dd>{{ formatDate(item.updated_at || item.created_at) }}</dd>
                </div>
              </dl>
            </div>
            <div class="resource-item__actions">
              <el-button size="small" @click="openEdit(item, $event)">
                <el-icon aria-hidden="true"><EditPen /></el-icon>
                {{ resource === 'interviews' ? '管理' : '编辑' }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :loading="deletingId === item.id"
                :disabled="Boolean(deletingId)"
                @click="removeItem(item)"
              >
                <el-icon aria-hidden="true"><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </li>
        </ul>
      </section>

      <aside
        v-if="editorOpen"
        ref="editorRef"
        class="resource-editor"
        :aria-labelledby="`${resource}-editor-title`"
      >
        <div class="resource-editor__heading">
          <div>
            <p class="technical-label">{{ editingId ? 'EDIT RECORD' : 'NEW RECORD' }}</p>
            <h3 :id="`${resource}-editor-title`">
              {{ editingId ? `编辑${definition.singular}` : definition.createLabel }}
            </h3>
          </div>
          <button class="resource-editor__close" type="button" aria-label="关闭编辑表单" @click="closeEditor">
            <el-icon aria-hidden="true"><Close /></el-icon>
          </button>
        </div>

        <form class="resource-form" novalidate @submit.prevent="saveItem">
          <div v-if="formError" class="resource-form__error" role="alert">{{ formError }}</div>

          <div v-for="field in definition.fields" :key="field.key" class="resource-field">
            <label :for="fieldId(field)">
              {{ field.label }}
              <span v-if="field.required" aria-hidden="true">*</span>
            </label>

            <el-input
              v-if="field.type === 'textarea' || field.type === 'json'"
              :id="fieldId(field)"
              v-model="form[field.key]"
              type="textarea"
              :rows="field.rows || 5"
              :maxlength="field.maxlength"
              :placeholder="field.placeholder"
              :aria-required="field.required || undefined"
            />

            <el-select
              v-else-if="field.type === 'select'"
              :id="fieldId(field)"
              v-model="form[field.key]"
              :aria-label="field.label"
              :placeholder="`请选择${field.label}`"
            >
              <el-option
                v-for="option in field.options"
                :key="String(option.value)"
                :label="option.label"
                :value="option.value"
              />
            </el-select>

            <el-select
              v-else-if="field.type === 'relation'"
              :id="fieldId(field)"
              v-model="form[field.key]"
              clearable
              :aria-label="field.label"
              :placeholder="relatedJobs.length ? '请选择已保存岗位' : '请先在岗位库保存岗位'"
            >
              <el-option
                v-for="job in relatedJobs"
                :key="job.id"
                :label="`${job.title}${job.company ? ` · ${job.company}` : ''}`"
                :value="job.id"
              />
            </el-select>

            <el-switch
              v-else-if="field.type === 'switch'"
              :id="fieldId(field)"
              v-model="form[field.key]"
              :aria-label="field.label"
              inline-prompt
              active-text="是"
              inactive-text="否"
            />

            <div v-else-if="field.type === 'range'" class="resource-range">
              <input
                :id="fieldId(field)"
                v-model.number="form[field.key]"
                type="range"
                :min="field.min"
                :max="field.max"
              />
              <output :for="fieldId(field)" class="tabular-nums">{{ form[field.key] }}%</output>
            </div>

            <input
              v-else
              :id="fieldId(field)"
              v-model="form[field.key]"
              class="resource-native-input"
              :type="field.inputType || field.type || 'text'"
              :min="field.min"
              :max="field.max"
              :maxlength="field.maxlength"
              :placeholder="field.placeholder"
              :required="field.required"
            />

            <p v-if="field.type === 'relation' && !relatedJobs.length" class="resource-field__hint">
              <RouterLink :to="{ name: 'career-jobs' }">前往岗位库创建岗位</RouterLink>
            </p>
            <p v-else-if="field.type === 'json'" class="resource-field__hint">
              请输入合法 JSON；该内容用于保存可复用的结构化分析结果。
            </p>
          </div>

          <div class="resource-form__actions">
            <el-button native-type="button" :disabled="saving" @click="closeEditor">取消</el-button>
            <el-button native-type="submit" type="primary" :loading="saving">
              {{ editingId ? '保存修改' : `创建${definition.singular}` }}
            </el-button>
          </div>
        </form>
      </aside>
    </div>

    <section
      v-if="resource === 'interviews' && selectedInterview"
      id="interview-questions"
      ref="questionsSectionRef"
      class="interview-detail"
      aria-labelledby="interview-questions-title"
    >
      <div class="interview-detail__heading">
        <div>
          <p class="technical-label">STRUCTURED PRACTICE</p>
          <h3 id="interview-questions-title" tabindex="-1">{{ selectedInterview.title }} · 题目与复盘</h3>
        </div>
        <el-button @click="openQuestionEditor()">
          <el-icon aria-hidden="true"><Plus /></el-icon>
          添加题目
        </el-button>
      </div>

      <div v-if="detailLoading" class="interview-detail__state" aria-busy="true">正在加载面试详情…</div>
      <div v-else-if="detailError" class="interview-detail__state interview-detail__state--error" role="alert">
        {{ detailError }}
        <el-button size="small" @click="loadInterviewDetail(selectedInterview.id)">重试</el-button>
      </div>
      <div v-else-if="!selectedInterview.questions?.length" class="interview-detail__state">
        暂无题目。先添加一道题，开始形成可复盘的结构化训练记录。
      </div>
      <ol v-else class="question-list">
        <li v-for="question in selectedInterview.questions" :key="question.id" class="question-item">
          <div class="question-item__index tabular-nums">{{ question.position }}</div>
          <div class="question-item__content">
            <h4>{{ question.question }}</h4>
            <p v-if="question.reference_answer"><strong>AI 参考答案：</strong>{{ question.reference_answer }}</p>
            <p v-if="question.coaching_notes"><strong>解题思路：</strong>{{ question.coaching_notes }}</p>
            <p v-if="question.answer"><strong>回答：</strong>{{ question.answer }}</p>
            <p v-if="question.feedback"><strong>反馈：</strong>{{ question.feedback }}</p>
            <span v-if="question.score !== null && question.score !== undefined" class="question-item__score">
              评分 {{ question.score }} / 100
            </span>
          </div>
          <div class="question-item__actions">
            <el-button text size="small" @click="openQuestionEditor(question)">编辑</el-button>
            <el-button text size="small" type="danger" @click="removeQuestion(question)">删除</el-button>
          </div>
        </li>
      </ol>

      <form v-if="questionEditorOpen" class="question-form" @submit.prevent="saveQuestion">
        <div class="question-form__heading">
          <h4>{{ editingQuestionId ? '编辑题目记录' : '添加面试题目' }}</h4>
          <button type="button" aria-label="关闭题目表单" @click="closeQuestionEditor">
            <el-icon><Close /></el-icon>
          </button>
        </div>
        <div v-if="questionError" class="resource-form__error" role="alert">{{ questionError }}</div>
        <label for="interview-question">题目 <span aria-hidden="true">*</span></label>
        <el-input id="interview-question" v-model="questionForm.question" type="textarea" :rows="3" />
        <label for="interview-answer">回答</label>
        <el-input id="interview-answer" v-model="questionForm.answer" type="textarea" :rows="5" />
        <label for="interview-reference-answer">AI 参考答案</label>
        <el-input id="interview-reference-answer" v-model="questionForm.reference_answer" type="textarea" :rows="5" />
        <label for="interview-coaching-notes">解题思路与辅导建议</label>
        <el-input id="interview-coaching-notes" v-model="questionForm.coaching_notes" type="textarea" :rows="4" />
        <label for="interview-feedback">反馈</label>
        <el-input id="interview-feedback" v-model="questionForm.feedback" type="textarea" :rows="4" />
        <label for="interview-score">评分（0–100）</label>
        <input id="interview-score" v-model="questionForm.score" class="resource-native-input" type="number" min="0" max="100" />
        <div class="resource-form__actions">
          <el-button native-type="button" :disabled="questionSaving" @click="closeQuestionEditor">取消</el-button>
          <el-button native-type="submit" type="primary" :loading="questionSaving">保存题目</el-button>
        </div>
      </form>
    </section>

    <section v-if="resource === 'skills'" class="career-data" aria-labelledby="career-data-title">
      <div>
        <p class="technical-label">DATA CONTROL</p>
        <h3 id="career-data-title">职业数据管理</h3>
        <p>导出全部结构化职业数据，或在确认后清空简历、岗位、投递、面试、报告、技能记录及知识库文档。</p>
      </div>
      <div class="career-data__actions">
        <el-button :loading="exportingData" @click="downloadCareerData">
          <el-icon aria-hidden="true"><Download /></el-icon>
          导出 JSON
        </el-button>
        <el-button type="danger" plain :loading="clearingData" @click="clearCareerData">清空职业数据与知识库</el-button>
      </div>
    </section>
  </CareerLayout>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { Close, Delete, Download, EditPen, FolderOpened, Plus, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCareerResource,
  createInterviewQuestion,
  deleteCareerData,
  deleteCareerResource,
  deleteInterviewQuestion,
  exportCareerData,
  getCareerResource,
  getCareerResources,
  getErrorMessage,
  updateCareerResource,
  updateInterviewQuestion
} from '../../api'
import { careerResourceDefinitions, getOptionLabel } from '../../career/resources'
import InterviewBar from '../../components/InterviewBar.vue'
import CareerLayout from '../../layouts/CareerLayout.vue'

const props = defineProps({
  resource: {
    type: String,
    required: true,
    validator: (value) => Object.hasOwn(careerResourceDefinitions, value)
  }
})

const definition = computed(() => careerResourceDefinitions[props.resource])
const items = ref([])
const relatedJobs = ref([])
const loading = ref(false)
const error = ref('')
const editorOpen = ref(false)
const editorRef = ref(null)
const editingId = ref(null)
const saving = ref(false)
const deletingId = ref(null)
const formError = ref('')
const form = reactive({})
const selectedInterview = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const questionsSectionRef = ref(null)
const questionEditorOpen = ref(false)
const editingQuestionId = ref(null)
const questionSaving = ref(false)
const questionError = ref('')
const questionForm = reactive({
  question: '',
  answer: '',
  reference_answer: '',
  coaching_notes: '',
  feedback: '',
  score: ''
})
const exportingData = ref(false)
const clearingData = ref(false)
let loadRequestId = 0
let detailRequestId = 0
let lastEditorTrigger = null

const focusEditor = () => {
  nextTick(() => {
    editorRef.value?.scrollIntoView?.({ block: 'nearest' })
    editorRef.value?.querySelector?.(
      '.resource-form input:not([type="hidden"]):not([disabled]), .resource-form textarea:not([disabled]), .resource-form [role="combobox"]:not([aria-disabled="true"])'
    )?.focus?.()
  })
}

const unwrapItems = (response) => {
  const payload = response?.data
  if (Array.isArray(payload)) return payload
  return Array.isArray(payload?.items) ? payload.items : []
}

const defaultForm = () => Object.fromEntries(definition.value.fields.map((field) => [
  field.key,
  field.default ?? (field.type === 'switch' ? false : '')
]))

const resetForm = (item = null) => {
  const defaults = defaultForm()
  Object.keys(form).forEach((key) => delete form[key])
  Object.assign(form, defaults)
  if (!item) return
  definition.value.fields.forEach((field) => {
    let value = item[field.key]
    if (field.type === 'json') value = JSON.stringify(value || {}, null, 2)
    if (value === null || value === undefined) value = field.type === 'switch' ? false : ''
    form[field.key] = value
  })
}

const loadResources = async () => {
  const requestId = ++loadRequestId
  loading.value = true
  error.value = ''
  try {
    const needsJobs = definition.value.fields.some((field) => field.relation === 'jobs')
    const [resourceResponse, jobsResponse] = await Promise.all([
      getCareerResources(props.resource),
      needsJobs ? getCareerResources('jobs') : Promise.resolve(null)
    ])
    if (requestId !== loadRequestId) return
    items.value = unwrapItems(resourceResponse)
    relatedJobs.value = jobsResponse ? unwrapItems(jobsResponse) : []
  } catch (loadError) {
    if (requestId !== loadRequestId) return
    error.value = getErrorMessage(loadError, `加载${definition.value.title}失败，请稍后重试。`)
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

const openCreate = (event) => {
  lastEditorTrigger = event?.currentTarget || document.activeElement
  editingId.value = null
  formError.value = ''
  resetForm()
  editorOpen.value = true
  focusEditor()
}

const loadInterviewDetail = async (interviewId, { openEditor = false } = {}) => {
  const requestId = ++detailRequestId
  detailLoading.value = true
  detailError.value = ''
  try {
    const response = await getCareerResource('interviews', interviewId)
    if (requestId !== detailRequestId) return null
    selectedInterview.value = response.data
    if (openEditor) {
      editingId.value = interviewId
      resetForm(response.data)
      editorOpen.value = true
    }
    return response.data
  } catch (loadError) {
    if (requestId !== detailRequestId) return null
    detailError.value = getErrorMessage(loadError, '加载面试详情失败，请稍后重试。')
    return null
  } finally {
    if (requestId === detailRequestId) detailLoading.value = false
  }
}

const openEdit = async (item, event) => {
  lastEditorTrigger = event?.currentTarget || document.activeElement
  formError.value = ''
  if (props.resource === 'interviews') {
    selectedInterview.value = item
    await loadInterviewDetail(item.id, { openEditor: true })
    focusEditor()
    return
  }
  let detail = item
  if (props.resource === 'reports') {
    try {
      detail = (await getCareerResource('reports', item.id)).data
    } catch (loadError) {
      ElMessage.error(getErrorMessage(loadError, '加载报告详情失败。'))
      return
    }
  }
  editingId.value = item.id
  resetForm(detail)
  editorOpen.value = true
  focusEditor()
}

const closeEditor = () => {
  const shouldRestoreFocus = editorRef.value?.contains?.(document.activeElement)
  const focusTarget = lastEditorTrigger
  editorOpen.value = false
  editingId.value = null
  formError.value = ''
  lastEditorTrigger = null
  if (shouldRestoreFocus && focusTarget) {
    nextTick(() => {
      if (focusTarget.isConnected) focusTarget.focus()
    })
  }
}

const fieldId = (field) => `${props.resource}-${field.key}`

const serializedForm = () => {
  const data = {}
  for (const field of definition.value.fields) {
    let value = form[field.key]
    if (field.required && (value === '' || value === null || value === undefined)) {
      throw new Error(`请填写${field.label}。`)
    }
    if (field.type === 'json') {
      try {
        value = value ? JSON.parse(value) : {}
      } catch {
        throw new Error(`${field.label}不是合法 JSON，请检查括号、引号和逗号。`)
      }
    } else if (field.type === 'number' || field.type === 'relation' || field.type === 'range') {
      value = value === '' || value === null || value === undefined ? null : Number(value)
      if (value !== null && !Number.isFinite(value)) throw new Error(`${field.label}必须是有效数字。`)
    } else if (typeof value === 'string') {
      value = value.trim()
    }
    if (field.nullable && value === '') value = null
    data[field.key] = value
  }
  return data
}

const saveItem = async () => {
  if (saving.value) return
  formError.value = ''
  let payload
  try {
    payload = serializedForm()
  } catch (validationError) {
    formError.value = validationError.message
    return
  }
  saving.value = true
  try {
    const response = editingId.value
      ? await updateCareerResource(props.resource, editingId.value, payload)
      : await createCareerResource(props.resource, payload)
    const savedId = response.data?.id || editingId.value
    ElMessage.success(editingId.value ? '修改已保存。' : `${definition.value.singular}已创建。`)
    closeEditor()
    await loadResources()
    if (props.resource === 'interviews' && savedId) await loadInterviewDetail(savedId)
  } catch (saveError) {
    formError.value = getErrorMessage(saveError, `保存${definition.value.singular}失败，请检查后重试。`)
  } finally {
    saving.value = false
  }
}

const removeItem = async (item) => {
  if (deletingId.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除“${getItemTitle(item)}”吗？此操作不可撤销。`,
      `删除${definition.value.singular}`,
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  deletingId.value = item.id
  try {
    await deleteCareerResource(props.resource, item.id)
    if (selectedInterview.value?.id === item.id) selectedInterview.value = null
    if (editingId.value === item.id) closeEditor()
    ElMessage.success('记录已删除。')
    await loadResources()
  } catch (deleteError) {
    ElMessage.error(getErrorMessage(deleteError, '删除失败，请稍后重试。'))
  } finally {
    deletingId.value = null
  }
}

const getJob = (jobId) => relatedJobs.value.find((job) => Number(job.id) === Number(jobId))

const getItemTitle = (item) => {
  if (props.resource === 'applications') {
    return item.job_title || getJob(item.job_id)?.title || item.next_action || `投递 #${item.id}`
  }
  return item[definition.value.titleKey]
    || item[definition.value.fallbackTitleKey]
    || `${definition.value.singular} #${item.id}`
}

const getItemSubtitle = (item) => {
  if (props.resource === 'applications') {
    const job = getJob(item.job_id)
    return item.company || job?.company || item.next_action || ''
  }
  const value = item[definition.value.subtitleKey]
  if (!value) return ''
  return String(value).length > 180 ? `${String(value).slice(0, 180)}…` : value
}

const getStatusLabel = (item) => {
  const key = definition.value.statusKey
  if (!key) return ''
  if (key === 'is_primary') return item[key] ? '主简历' : ''
  return getOptionLabel(definition.value.statusOptions, item[key])
}

const formatDate = (value) => {
  if (!value) return '暂无时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }).format(date)
}

const setInterviewStatus = async (status) => {
  if (!selectedInterview.value) return
  try {
    const response = await updateCareerResource('interviews', selectedInterview.value.id, { status })
    selectedInterview.value = { ...selectedInterview.value, ...response.data }
    ElMessage.success(status === 'completed' ? '面试已结束，可继续完善评分与复盘。' : '面试已开始。')
    await loadResources()
  } catch (statusError) {
    ElMessage.error(getErrorMessage(statusError, '更新面试状态失败。'))
  }
}

const focusInterviewQuestions = () => {
  questionsSectionRef.value?.scrollIntoView({ block: 'start' })
  nextTick(() => document.getElementById('interview-questions-title')?.focus?.())
}

const openQuestionEditor = (question = null) => {
  editingQuestionId.value = question?.id || null
  questionError.value = ''
  Object.assign(questionForm, {
    question: question?.question || '',
    answer: question?.answer || '',
    reference_answer: question?.reference_answer || '',
    coaching_notes: question?.coaching_notes || '',
    feedback: question?.feedback || '',
    score: question?.score ?? ''
  })
  questionEditorOpen.value = true
  nextTick(() => document.getElementById('interview-question')?.focus())
}

const closeQuestionEditor = () => {
  questionEditorOpen.value = false
  editingQuestionId.value = null
  questionError.value = ''
}

const saveQuestion = async () => {
  if (!selectedInterview.value || questionSaving.value) return
  const question = questionForm.question.trim()
  if (!question) {
    questionError.value = '请填写面试题目。'
    return
  }
  const score = questionForm.score === '' ? null : Number(questionForm.score)
  if (score !== null && (!Number.isFinite(score) || score < 0 || score > 100)) {
    questionError.value = '评分必须在 0 到 100 之间。'
    return
  }
  const payload = {
    question,
    answer: questionForm.answer.trim(),
    reference_answer: questionForm.reference_answer.trim(),
    coaching_notes: questionForm.coaching_notes.trim(),
    feedback: questionForm.feedback.trim(),
    score
  }
  questionSaving.value = true
  questionError.value = ''
  try {
    if (editingQuestionId.value) {
      await updateInterviewQuestion(selectedInterview.value.id, editingQuestionId.value, payload)
    } else {
      await createInterviewQuestion(selectedInterview.value.id, payload)
    }
    closeQuestionEditor()
    await Promise.all([loadInterviewDetail(selectedInterview.value.id), loadResources()])
    ElMessage.success('题目记录已保存。')
  } catch (saveError) {
    questionError.value = getErrorMessage(saveError, '保存题目失败，请稍后重试。')
  } finally {
    questionSaving.value = false
  }
}

const removeQuestion = async (question) => {
  try {
    await ElMessageBox.confirm('确定删除这道面试题及其回答和反馈吗？', '删除题目', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning'
    })
  } catch {
    return
  }
  try {
    await deleteInterviewQuestion(selectedInterview.value.id, question.id)
    await Promise.all([loadInterviewDetail(selectedInterview.value.id), loadResources()])
    ElMessage.success('题目已删除。')
  } catch (deleteError) {
    ElMessage.error(getErrorMessage(deleteError, '删除题目失败。'))
  }
}

const downloadCareerData = async () => {
  if (exportingData.value) return
  exportingData.value = true
  try {
    const response = await exportCareerData()
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `career-data-${new Date().toISOString().slice(0, 10)}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success('职业数据已导出。')
  } catch (exportError) {
    ElMessage.error(getErrorMessage(exportError, '导出职业数据失败。'))
  } finally {
    exportingData.value = false
  }
}

const clearCareerData = async () => {
  try {
    await ElMessageBox.prompt('此操作会永久删除全部职业数据与知识库文档，且不可恢复。请输入 DELETE 继续。', '清空职业数据与知识库', {
      confirmButtonText: '永久清空',
      cancelButtonText: '取消',
      type: 'warning',
      inputPattern: /^DELETE$/,
      inputErrorMessage: '请输入大写 DELETE。'
    })
  } catch {
    return
  }
  clearingData.value = true
  try {
    await deleteCareerData()
    selectedInterview.value = null
    closeEditor()
    await loadResources()
    ElMessage.success('职业数据与知识库已清空。')
  } catch (deleteError) {
    ElMessage.error(getErrorMessage(deleteError, '清空职业数据与知识库失败。'))
  } finally {
    clearingData.value = false
  }
}

watch(() => props.resource, () => {
  closeEditor()
  closeQuestionEditor()
  selectedInterview.value = null
  relatedJobs.value = []
  void loadResources()
}, { immediate: true })
</script>

<style scoped>
.resource-workspace {
  position: relative;
  isolation: isolate;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-6);
}

.resource-workspace--editing {
  grid-template-columns: minmax(0, 1.12fr) minmax(22rem, .88fr);
  align-items: start;
}

.resource-panel,
.resource-editor,
.interview-detail,
.career-data {
  position: relative;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface);
}

.resource-panel::before,
.interview-detail::before {
  position: absolute;
  z-index: 1;
  top: -1px;
  right: clamp(3rem, 16vw, 14rem);
  left: clamp(1rem, 4vw, 3rem);
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-primary), var(--color-cyan), transparent);
  content: '';
  opacity: .72;
  pointer-events: none;
}

.resource-panel {
  overflow: hidden;
}

.resource-panel__heading,
.resource-editor__heading,
.interview-detail__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 5.75rem;
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-subtle);
}

.resource-panel__identity {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(0, auto) auto;
  gap: 0 var(--space-3);
  align-items: center;
}

.resource-panel__identity .technical-label {
  grid-column: 1 / -1;
  margin: 0 0 var(--space-1);
}

.resource-panel__heading h3,
.resource-editor__heading h3,
.interview-detail__heading h3,
.career-data h3 {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: var(--font-size-section-title);
  line-height: var(--line-height-section-title);
}

.resource-editor__heading > div,
.interview-detail__heading > div,
.career-data > div:first-child {
  min-width: 0;
}

.resource-panel__count {
  display: inline-flex;
  min-height: 1.75rem;
  align-items: center;
  padding: 0 var(--space-2);
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.resource-panel__count .tabular-nums {
  margin-inline: .2rem;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-weight: 700;
}

.resource-panel__refresh {
  flex: 0 0 auto;
}

.resource-panel__refresh:deep(.el-icon) {
  color: var(--color-cyan);
}

.resource-state {
  position: relative;
  isolation: isolate;
  display: grid;
  min-height: clamp(19rem, 42vh, 25rem);
  place-items: center;
  align-content: center;
  gap: var(--space-3);
  padding: clamp(var(--space-8), 6vw, var(--space-16));
  color: var(--color-text-secondary);
  text-align: center;
  overflow: hidden;
}

.resource-state::before,
.resource-state::after {
  position: absolute;
  z-index: -1;
  border: 1px solid var(--color-orbit);
  border-radius: 50%;
  content: '';
  pointer-events: none;
}

.resource-state::before {
  width: min(20rem, 66vw);
  aspect-ratio: 1;
  opacity: .7;
}

.resource-state::after {
  width: min(12rem, 42vw);
  aspect-ratio: 1;
  border-color: var(--color-orbit-strong);
  background: radial-gradient(circle, var(--color-aurora-violet-soft), transparent 68%);
}

.resource-state > .el-icon {
  display: grid;
  width: 3rem;
  height: 3rem;
  place-items: center;
  border: 1px solid var(--color-orbit-strong);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-primary-text);
  font-size: 1.25rem;
}

.resource-state strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
}

.resource-state p {
  max-width: 34rem;
  margin: 0;
  line-height: var(--line-height-body);
}

.resource-state--error > .el-icon {
  border-color: color-mix(in srgb, var(--color-danger) 32%, transparent);
  background: var(--color-danger-soft);
  color: var(--color-danger-text);
}

.resource-state--error::after {
  border-color: color-mix(in srgb, var(--color-danger) 22%, transparent);
  background: radial-gradient(circle, var(--color-danger-soft), transparent 68%);
}

.resource-state__loader {
  width: 2.5rem;
  height: 2.5rem;
  border: 2px solid var(--color-border-strong);
  border-top-color: var(--color-primary);
  border-right-color: var(--color-cyan);
  border-radius: 50%;
  animation: resource-spin .8s linear infinite;
}

@keyframes resource-spin {
  to { transform: rotate(360deg); }
}

.resource-list {
  display: grid;
  gap: 0;
  padding: 0;
  margin: 0;
  list-style: none;
}

.resource-item {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-5);
  align-items: center;
  min-height: 7.5rem;
  padding: var(--space-5) clamp(var(--space-4), 3vw, var(--space-6));
  border-bottom: 1px solid var(--color-border);
  transition:
    background-color var(--duration-control) var(--ease-standard),
    box-shadow var(--duration-control) var(--ease-standard);
}

.resource-item:last-child {
  border-bottom: 0;
}

.resource-item:hover,
.resource-item--selected {
  background: var(--color-surface-subtle);
}

.resource-item--selected {
  box-shadow: inset 3px 0 var(--color-primary), inset 0 0 3rem var(--color-primary-soft);
}

.resource-item--selected::after {
  position: absolute;
  top: 50%;
  left: 0;
  width: .45rem;
  height: .45rem;
  border-radius: 50%;
  background: var(--color-cyan);
  box-shadow: 0 0 0 4px var(--color-info-soft);
  content: '';
  transform: translate(-50%, -50%);
}

.resource-item__body {
  min-width: 0;
}

.resource-item__title-row {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.resource-item h4 {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: var(--font-size-component-title);
  line-height: var(--line-height-component-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-status,
.question-item__score {
  display: inline-flex;
  min-height: 1.625rem;
  align-items: center;
  flex: 0 0 auto;
  padding: 0 .625rem;
  border: 1px solid color-mix(in srgb, var(--color-primary) 22%, transparent);
  border-radius: var(--radius-pill);
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.resource-item__summary {
  display: -webkit-box;
  max-width: 70ch;
  margin: .375rem 0 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
  line-height: var(--line-height-body);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
}

.resource-item :deep(.el-progress) {
  max-width: 28rem;
  margin-top: var(--space-3);
}

.resource-item :deep(.el-progress-bar__outer) {
  background: var(--color-surface-hover);
}

.resource-item :deep(.el-progress-bar__inner) {
  background: var(--aurora-gradient);
}

.resource-item__metadata {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: var(--space-3) 0 0;
}

.resource-item__metadata > div {
  display: flex;
  gap: var(--space-1);
  align-items: baseline;
}

.resource-item__metadata > div + div::before {
  margin-right: var(--space-2);
  color: var(--color-border-strong);
  content: '/';
}

.resource-item__metadata dt,
.resource-item__metadata dd {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
}

.resource-item__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.resource-item__actions .el-button {
  margin: 0;
}

.resource-editor {
  position: sticky;
  top: var(--space-4);
  display: grid;
  max-height: calc(100dvh - var(--topbar-height) - var(--space-8));
  grid-template-rows: auto minmax(0, 1fr);
  scroll-margin-top: calc(48px + var(--space-5));
  overflow: hidden;
  border-color: var(--color-border-strong);
  background: var(--color-surface-elevated);
  box-shadow: var(--shadow-elevated);
}

.resource-editor::before {
  position: absolute;
  z-index: 2;
  top: -1px;
  right: 12%;
  left: 12%;
  height: 2px;
  background: var(--aurora-gradient);
  content: '';
  opacity: .88;
  pointer-events: none;
}

.resource-editor__heading .technical-label,
.interview-detail__heading .technical-label,
.career-data .technical-label {
  margin: 0 0 var(--space-1);
}

.resource-editor__close,
.question-form__heading button {
  display: inline-grid;
  width: 44px;
  height: 44px;
  place-items: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    border-color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard),
    color var(--duration-control) var(--ease-standard);
}

.resource-editor__close:hover,
.question-form__heading button:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.resource-editor__close:focus-visible,
.question-form__heading button:focus-visible {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.resource-form,
.question-form {
  display: grid;
  min-width: 0;
  gap: var(--space-5);
  padding: var(--space-6);
}

.resource-editor .resource-form {
  overflow-y: auto;
  overscroll-behavior: contain;
}

.resource-form__error {
  padding: var(--space-3) var(--space-4);
  border: 1px solid color-mix(in srgb, var(--color-danger) 35%, transparent);
  border-radius: var(--radius-control);
  background: var(--color-danger-soft);
  color: var(--color-text-primary);
}

.resource-field {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
}

.resource-field + .resource-field {
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.resource-field > label,
.question-form > label {
  color: var(--color-text-primary);
  font-size: var(--font-size-label);
  font-weight: 600;
}

.resource-field > label span,
.question-form > label span {
  color: var(--color-danger-text);
}

.resource-field :deep(.el-select) {
  width: 100%;
}

.resource-field :deep(.el-input__wrapper),
.resource-field :deep(.el-select__wrapper) {
  min-height: 44px;
}

.resource-field :deep(.el-textarea__inner) {
  padding: var(--space-3);
  line-height: var(--line-height-body);
  resize: vertical;
}

.resource-native-input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  outline: none;
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
}

.resource-native-input:focus {
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring-strong);
}

.resource-native-input:disabled {
  border-color: var(--color-border);
  background: var(--color-surface-hover);
  color: var(--color-text-disabled);
  cursor: not-allowed;
}

.resource-field__hint {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-size-caption);
  overflow-wrap: anywhere;
}

.resource-field__hint a {
  color: var(--color-primary-text);
  font-weight: 600;
  text-underline-offset: .2em;
}

.resource-field__hint a:focus-visible {
  border-radius: .2rem;
  outline: none;
  box-shadow: var(--focus-ring);
}

.resource-range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 3.5rem;
  gap: var(--space-3);
  align-items: center;
}

.resource-range input {
  width: 100%;
  min-height: 44px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.resource-range input:focus-visible {
  border-radius: var(--radius-control);
  outline: none;
  box-shadow: var(--focus-ring-strong);
}

.resource-range output {
  color: var(--color-text-primary);
  font-weight: 600;
  text-align: right;
}

.resource-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.resource-form__actions .el-button {
  min-height: 44px;
  margin: 0;
}

.interview-detail,
.career-data {
  margin-top: var(--space-8);
  overflow: hidden;
}

.interview-detail__state {
  display: flex;
  min-height: 8rem;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--color-text-secondary);
  text-align: center;
}

.interview-detail__state--error {
  border: 1px solid color-mix(in srgb, var(--color-danger) 30%, transparent);
  background: var(--color-danger-soft);
  color: var(--color-text-primary);
}

.question-list {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  margin: 0;
  list-style: none;
}

.question-item {
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr) auto;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface-subtle);
  transition:
    border-color var(--duration-control) var(--ease-standard),
    background-color var(--duration-control) var(--ease-standard);
}

.question-item:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface-hover);
}

.question-item__index {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: var(--radius-control);
  background: var(--color-primary-soft);
  color: var(--color-primary-text);
  font-size: var(--font-size-caption);
  font-weight: 700;
}

.question-item__content h4 {
  margin: 0 0 var(--space-2);
  overflow-wrap: anywhere;
  font-size: var(--font-size-component-title);
}

.question-item__content {
  min-width: 0;
}

.question-item__content p {
  margin: var(--space-2) 0;
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.question-item__score {
  margin-top: var(--space-2);
}

.question-item__actions {
  display: flex;
  align-items: flex-start;
}

.question-item__actions .el-button {
  min-height: 44px;
  margin: 0;
}

.question-form {
  max-width: 48rem;
  margin: var(--space-6);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-card);
  background: var(--color-surface-elevated);
  box-shadow: var(--shadow-card);
}

.question-form__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.question-form__heading h4 {
  margin: 0;
}

.question-form :deep(.el-textarea__inner) {
  line-height: var(--line-height-body);
  resize: vertical;
}

.career-data {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-6);
  padding: var(--space-6);
  background:
    linear-gradient(100deg, var(--color-surface-subtle), var(--color-surface) 60%),
    var(--color-surface);
}

.career-data p:last-child {
  max-width: 58rem;
  margin: var(--space-2) 0 0;
  color: var(--color-text-secondary);
}

.career-data__actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.career-data__actions .el-button {
  min-height: 44px;
  margin: 0;
}

@media (max-width: 1199px) {
  .resource-workspace--editing {
    grid-template-columns: 1fr;
  }

  .resource-editor {
    position: static;
    max-height: none;
  }

  .resource-editor .resource-form {
    overflow: visible;
  }
}

@media (max-width: 899px) {
  .resource-panel__heading,
  .resource-editor__heading,
  .interview-detail__heading,
  .career-data {
    align-items: stretch;
    flex-direction: column;
  }

  .resource-panel__refresh {
    align-self: flex-start;
  }

  .resource-editor__heading {
    align-items: center;
    flex-flow: row wrap;
  }

  .resource-editor__heading > div {
    flex: 1 1 16rem;
  }

  .career-data__actions {
    display: grid;
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .career-data__actions .el-button {
    width: 100%;
  }
}

@media (max-width: 767px) {
  .resource-panel__heading,
  .resource-editor__heading,
  .interview-detail__heading,
  .career-data {
    align-items: stretch;
    flex-direction: column;
  }

  .resource-panel__heading,
  .resource-editor__heading,
  .interview-detail__heading {
    min-height: auto;
    padding: var(--space-4);
  }

  .resource-panel__heading,
  .interview-detail__heading {
    gap: var(--space-3);
  }

  .resource-panel__refresh {
    align-self: flex-start;
  }

  .resource-item {
    grid-template-columns: 1fr;
    gap: var(--space-4);
    padding: var(--space-4);
  }

  .resource-item__actions,
  .resource-item__actions .el-button {
    width: 100%;
  }

  .resource-item__actions .el-button {
    min-height: 44px;
  }

  .resource-item__actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .resource-item__metadata {
    display: grid;
    gap: var(--space-1);
  }

  .resource-item__metadata > div + div::before {
    content: none;
  }

  .resource-form,
  .question-form {
    padding: var(--space-4);
  }

  .resource-form__actions,
  .career-data__actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .resource-form__actions .el-button,
  .career-data__actions .el-button,
  .interview-detail__heading .el-button {
    width: 100%;
    min-height: 44px;
  }

  .question-item {
    grid-template-columns: 2rem minmax(0, 1fr);
    padding: var(--space-4);
  }

  .question-item__actions {
    grid-column: 2;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .question-item__actions .el-button {
    width: 100%;
  }

  .question-form {
    margin: var(--space-4);
  }
}

@media (prefers-reduced-motion: reduce) {
  .resource-state__loader {
    animation: none;
  }

  .resource-item,
  .resource-editor__close,
  .question-form__heading button,
  .question-item {
    transition: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .resource-editor,
  .question-form {
    box-shadow: none;
  }
}
</style>
