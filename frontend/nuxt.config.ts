export default defineNuxtConfig({
  app: {
    head: {
      title: 'Prosperity BTX',
      link: [
        { rel: 'icon', type: 'image/png', href: '/logo.png' }
      ]
    }
  },
  
  compatibilityDate: '2024-04-03',
  
  devtools: { enabled: false },
  
  css: ['~/assets/css/main.css'],

  modules: ['@nuxtjs/supabase'],

  supabase: {
    redirect: false
  },
  
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000'
    }
  }
})