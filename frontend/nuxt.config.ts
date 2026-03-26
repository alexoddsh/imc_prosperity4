export default defineNuxtConfig({
  app: {
    head: {
      title: 'Prosperity BTX',
      link: [
        { rel: 'icon', type: 'image/png', href: '/logo.png' }
      ]
    }
  },
  
  compatibilityDate: '2026-03-26',
  
  devtools: { enabled: true },
  
  css: ['/Users/alexoddsh/prosperity/frontend/assets/css/main.css'],

  modules: ['@nuxtjs/supabase'],

  supabase: {
    redirect: false, // Prevents Nuxt from forcing a login page immediately
    url: process.env.SUPABASE_URL,
    key: process.env.SUPABASE_KEY
  }
  runtimeConfig: {
    public: {
      apiBase: process.env.NODE_ENV === 'production' 
        ? 'https://your-backend-name.up.railway.app' 
        : 'http://127.0.0.1:8000'
    }
  }
})