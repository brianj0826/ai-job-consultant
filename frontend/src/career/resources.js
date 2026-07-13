export const jobStatusOptions = [
  { value: 'saved', label: '已收藏' },
  { value: 'active', label: '跟进中' },
  { value: 'archived', label: '已归档' }
]

export const applicationStageOptions = [
  { value: 'saved', label: '待投递' },
  { value: 'applied', label: '已投递' },
  { value: 'screening', label: '筛选中' },
  { value: 'interview', label: '面试中' },
  { value: 'offer', label: '已获 Offer' },
  { value: 'rejected', label: '未通过' },
  { value: 'withdrawn', label: '已撤回' }
]

export const interviewStatusOptions = [
  { value: 'planned', label: '待开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' }
]

export const reportKindOptions = [
  { value: 'resume_analysis', label: '简历分析' },
  { value: 'job_match', label: '岗位匹配' },
  { value: 'interview_review', label: '面试复盘' },
  { value: 'career_plan', label: '职业计划' }
]

export const reportEntityOptions = [
  { value: '', label: '不关联具体项目' },
  { value: 'resume', label: '简历' },
  { value: 'job', label: '岗位' },
  { value: 'application', label: '投递' },
  { value: 'interview', label: '面试' },
  { value: 'skill', label: '技能' }
]

export const skillStatusOptions = [
  { value: 'planned', label: '待开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'paused', label: '已暂停' }
]

const text = (key, label, options = {}) => ({ key, label, type: 'text', ...options })
const textarea = (key, label, options = {}) => ({ key, label, type: 'textarea', ...options })
const select = (key, label, options, config = {}) => ({
  key,
  label,
  type: 'select',
  options,
  ...config
})

export const careerResourceDefinitions = {
  resumes: {
    routeName: 'career-resumes',
    title: '简历中心',
    eyebrow: 'RESUME LIBRARY',
    description: '沉淀可复用的简历版本，并明确每一版面向的目标岗位。',
    singular: '简历',
    createLabel: '新建简历',
    titleKey: 'title',
    subtitleKey: 'target_role',
    statusKey: 'is_primary',
    fields: [
      text('title', '版本名称', { required: true, maxlength: 255, placeholder: '例如：产品经理主简历' }),
      text('target_role', '目标岗位', { maxlength: 255, placeholder: '例如：AI 产品经理' }),
      textarea('content', '简历正文', { required: true, rows: 10, placeholder: '粘贴简历内容，后续可用于分析和版本对比。' }),
      text('source_name', '来源文件名', { maxlength: 512, placeholder: '可选，例如 resume-v3.pdf' }),
      { key: 'is_primary', label: '设为主简历', type: 'switch', default: false }
    ]
  },
  jobs: {
    routeName: 'career-jobs',
    title: '岗位库',
    eyebrow: 'TARGET ROLES',
    description: '保存目标岗位与 JD，作为投递、匹配和面试准备的统一上下文。',
    singular: '岗位',
    createLabel: '保存岗位',
    titleKey: 'title',
    subtitleKey: 'company',
    statusKey: 'status',
    statusOptions: jobStatusOptions,
    fields: [
      text('title', '岗位名称', { required: true, maxlength: 255, placeholder: '例如：高级前端工程师' }),
      text('company', '公司', { maxlength: 255, placeholder: '公司或团队名称' }),
      textarea('description', '岗位描述', { required: true, rows: 9, placeholder: '粘贴完整 JD，便于后续匹配与准备。' }),
      text('source_url', '岗位链接', { inputType: 'url', maxlength: 2048, placeholder: 'https://...' }),
      select('status', '跟进状态', jobStatusOptions, { default: 'saved' })
    ]
  },
  applications: {
    routeName: 'career-applications',
    title: '投递工作台',
    eyebrow: 'APPLICATION PIPELINE',
    description: '用明确阶段、截止日期和下一步行动管理每一次投递。',
    singular: '投递记录',
    createLabel: '添加投递',
    titleKey: 'job_title',
    fallbackTitleKey: 'next_action',
    subtitleKey: 'company',
    statusKey: 'stage',
    statusOptions: applicationStageOptions,
    fields: [
      { key: 'job_id', label: '关联岗位', type: 'relation', relation: 'jobs', required: true },
      select('stage', '当前阶段', applicationStageOptions, { default: 'saved' }),
      text('next_action', '下一步行动', { maxlength: 500, placeholder: '例如：周三前完成作品集补充' }),
      { key: 'deadline', label: '截止日期', type: 'date' },
      textarea('notes', '跟进备注', { rows: 5, placeholder: '记录联系人、面试安排或待确认事项。' })
    ]
  },
  interviews: {
    routeName: 'career-interviews',
    title: '面试中心',
    eyebrow: 'INTERVIEW PRACTICE',
    description: '围绕目标岗位组织结构化题目、回答、评分与复盘。',
    singular: '面试',
    createLabel: '创建面试',
    titleKey: 'title',
    subtitleKey: 'job_title',
    statusKey: 'status',
    statusOptions: interviewStatusOptions,
    fields: [
      { key: 'job_id', label: '关联岗位', type: 'relation', relation: 'jobs', nullable: true },
      text('title', '面试名称', { required: true, maxlength: 255, placeholder: '例如：产品经理一轮模拟面试' }),
      select('status', '面试状态', interviewStatusOptions, { default: 'planned' }),
      { key: 'overall_score', label: '综合评分', type: 'number', min: 0, max: 100, nullable: true }
    ]
  },
  reports: {
    routeName: 'career-reports',
    title: '报告中心',
    eyebrow: 'PERSISTED INSIGHTS',
    description: '集中保存简历分析、岗位匹配、面试复盘与职业计划，不再依赖临时聊天内容。',
    singular: '报告',
    createLabel: '保存报告',
    titleKey: 'title',
    subtitleKey: 'summary',
    statusKey: 'kind',
    statusOptions: reportKindOptions,
    fields: [
      select('kind', '报告类型', reportKindOptions, { required: true, default: 'resume_analysis' }),
      text('title', '报告标题', { required: true, maxlength: 255, placeholder: '例如：产品经理简历分析 · 7 月' }),
      select('entity_type', '关联类型', reportEntityOptions, { default: '', nullable: true }),
      { key: 'entity_id', label: '关联记录 ID', type: 'number', min: 1, nullable: true },
      textarea('summary', '报告摘要', { required: true, rows: 7, placeholder: '写下主要结论、证据与下一步。' }),
      textarea('payload', '结构化结果（JSON）', { type: 'json', rows: 8, default: '{}', placeholder: '{\n  "version": 1\n}' })
    ]
  },
  skills: {
    routeName: 'career-skills',
    title: '技能计划',
    eyebrow: 'GROWTH PLAN',
    description: '把岗位差距转化为有目标、有截止日期、可复盘的成长任务。',
    singular: '技能目标',
    createLabel: '添加技能',
    titleKey: 'skill',
    subtitleKey: 'target_level',
    statusKey: 'status',
    statusOptions: skillStatusOptions,
    fields: [
      text('skill', '技能名称', { required: true, maxlength: 255, placeholder: '例如：SQL 数据分析' }),
      text('target_level', '目标水平', { maxlength: 255, placeholder: '例如：能独立完成漏斗分析' }),
      select('status', '学习状态', skillStatusOptions, { default: 'planned' }),
      { key: 'progress', label: '完成进度', type: 'range', min: 0, max: 100, default: 0 },
      { key: 'due_date', label: '目标日期', type: 'date' },
      textarea('notes', '学习笔记', { rows: 6, placeholder: '记录资料、练习任务和能力证据。' })
    ]
  }
}

export const careerNavigation = [
  { routeName: 'career-resumes', label: '简历中心', resource: 'resumes' },
  { routeName: 'career-jobs', label: '岗位库', resource: 'jobs' },
  { routeName: 'career-applications', label: '投递工作台', resource: 'applications' },
  { routeName: 'career-interviews', label: '面试中心', resource: 'interviews' },
  { routeName: 'career-reports', label: '报告中心', resource: 'reports' },
  { routeName: 'career-skills', label: '技能计划', resource: 'skills' }
]

export const suggestionResourceDefinitions = {
  resumes: {
    label: '简历',
    sectionLabel: '简历中心',
    routeName: 'career-resumes',
    definition: careerResourceDefinitions.resumes,
    editableFields: ['title', 'target_role', 'content', 'source_name']
  },
  jobs: {
    label: '岗位',
    sectionLabel: '岗位库',
    routeName: 'career-jobs',
    definition: careerResourceDefinitions.jobs,
    editableFields: ['title', 'company', 'description', 'source_url']
  },
  applications: {
    label: '投递',
    sectionLabel: '投递工作台',
    routeName: 'career-applications',
    definition: careerResourceDefinitions.applications,
    editableFields: ['job_id', 'stage', 'next_action', 'deadline', 'notes']
  },
  interviews: {
    label: '面试',
    sectionLabel: '面试中心',
    routeName: 'career-interviews',
    definition: careerResourceDefinitions.interviews,
    editableFields: ['job_id', 'title']
  },
  reports: {
    label: '报告',
    sectionLabel: '报告中心',
    routeName: 'career-reports',
    definition: careerResourceDefinitions.reports,
    editableFields: ['kind', 'title', 'entity_type', 'entity_id', 'summary', 'payload']
  },
  skills: {
    label: '技能计划',
    sectionLabel: '技能计划',
    routeName: 'career-skills',
    definition: careerResourceDefinitions.skills,
    editableFields: ['skill', 'target_level', 'due_date', 'notes']
  },
  interview_questions: {
    label: '面试题',
    sectionLabel: '面试中心',
    routeName: 'career-interviews',
    editableFields: ['interview_id', 'questions']
  }
}

export const getSuggestionFields = (resourceType) => {
  const suggestion = suggestionResourceDefinitions[resourceType]
  if (!suggestion?.definition) return []
  const allowed = new Set(suggestion.editableFields)
  return suggestion.definition.fields.filter((field) => allowed.has(field.key))
}

export const getOptionLabel = (options = [], value) => (
  options.find((option) => option.value === value)?.label || value || '未设置'
)
