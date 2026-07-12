import { createApp } from 'vue'
import {
  ElAlert,
  ElButton,
  ElCollapse,
  ElCollapseItem,
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElLink,
  ElLoading,
  ElOption,
  ElPagination,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElUpload
} from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/element-plus.css'
import './styles/account.css'
import './styles/admin.css'
import App from './App.vue'
import router from './router'

// 初始化主题（在挂载前执行，避免闪烁）
const savedTheme = localStorage.getItem('ai_dark_mode')
const initialDarkMode = savedTheme === null
  ? window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  : savedTheme === '1'
document.documentElement.classList.toggle('dark', initialDarkMode)
document.documentElement.dataset.theme = initialDarkMode ? 'dark' : 'light'

const app = createApp(App)
const elementComponents = [
  ElAlert,
  ElButton,
  ElCollapse,
  ElCollapseItem,
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElLink,
  ElOption,
  ElPagination,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElUpload
]
elementComponents.forEach((component) => app.component(component.name, component))
app.directive('loading', ElLoading.directive)
app.use(router)
app.mount('#app')
