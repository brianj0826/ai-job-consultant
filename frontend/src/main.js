import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/element-plus.css'
import App from './App.vue'

// 初始化主题（在挂载前执行，避免闪烁）
const savedTheme = localStorage.getItem('ai_dark_mode')
const initialDarkMode = savedTheme === null
  ? window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  : savedTheme === '1'
document.documentElement.classList.toggle('dark', initialDarkMode)
document.documentElement.dataset.theme = initialDarkMode ? 'dark' : 'light'

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')
