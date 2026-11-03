import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "apple-touch-icon.png", "mask-icon.svg"],
      manifest: {
        name: "Airtel Udyam Digital",
        short_name: "Udyam Digital",
        description: "AI-Assisted SME Connectivity & Digital Transformation Platform",
        theme_color: "#E40000",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
        ],
      },
      workbox: {
        // PWA Caching Boundary: Cache ONLY static app shell. NEVER cache API, KYC, or presigned URLs.
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/kyc\//, /^\/docs\//, /^\/health/],
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/") || url.pathname.startsWith("/kyc/"),
            handler: "NetworkOnly", // Strictly forbid caching sensitive identifiers or documents
          },
        ],
      },
    }),
  ],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
