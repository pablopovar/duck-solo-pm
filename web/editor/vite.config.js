import { defineConfig } from 'vite'
import { resolve } from 'node:path'

export default defineConfig({
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(
        import.meta.dirname,
        'src/editor.js',
      ),
      output: {
        entryFileNames: 'editor.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: (assetInfo) => (
          assetInfo.name?.endsWith('.css')
            ? 'editor.css'
            : 'assets/[name]-[hash][extname]'
        ),
      },
    },
  },
})
