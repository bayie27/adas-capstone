/// <reference types="vitest/config" />
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import path from "path"
import fs from "fs"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Only active when ADAS_TLS_CERT_DIR is set (LAN demo profile, be_audit/A1_lan_tls_drill.md).
  // Unset in plain `pnpm dev`, `pnpm build`, and the Playwright webServer config, so those
  // paths are untouched.
  server: process.env.ADAS_TLS_CERT_DIR
    ? {
        host: true,
        https: {
          key: fs.readFileSync(`${process.env.ADAS_TLS_CERT_DIR}/adas-key.pem`),
          cert: fs.readFileSync(`${process.env.ADAS_TLS_CERT_DIR}/adas-cert.pem`),
        },
      }
    : undefined,
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
})
