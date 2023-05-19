import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteRequire } from 'vite-require'

export default defineConfig({
    server: {
        proxy: {
            '/api': {
                target: 'http://backend',
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api/, '')
            }
        }
    },
    plugins: [
        viteRequire(),
        react({
            jsxRuntime: 'classic',
            babel: {
                plugins: [
                    '@babel/plugin-proposal-do-expressions',
                    [
                        'extensible-destructuring',
                        { mode: 'optout', impl: 'immutable' }
                    ]
                ]
            }
        })
    ]
})
