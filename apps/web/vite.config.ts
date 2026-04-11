import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');

    return {
        define: {
            global: 'globalThis',
        },
        ...(env.USE_PROXY === 'true' && {
            server: {
                proxy: {
                    '/api': {
                        target: 'https://j3cv37qhud.execute-api.us-east-1.amazonaws.com',
                        changeOrigin: true,
                        rewrite: (path) => path.replace(/^\/api/, '/dev'),
                    },
                    '/files-api': {
                        target: 'https://4oumdscha7.execute-api.us-east-1.amazonaws.com',
                        changeOrigin: true,
                        rewrite: (path) => path.replace(/^\/files-api/, '/dev'),
                    },
                },
            },
        }),
    };
});