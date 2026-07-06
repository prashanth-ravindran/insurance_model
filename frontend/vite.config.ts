import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://0.0.0.0:8000',
      '/health': 'http://0.0.0.0:8000'
    }
  }
});
