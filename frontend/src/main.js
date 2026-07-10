import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'

// 初始化暗色模式（在挂载前执行，避免闪烁）
if (localStorage.getItem('ai_dark_mode') === '1') {
  document.documentElement.classList.add('dark')
}

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')