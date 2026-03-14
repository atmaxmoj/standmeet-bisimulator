import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  use: {
    baseURL: "http://localhost:5175",
    screenshot: "on",
  },
  webServer: {
    command: "npx vite --port 5175",
    port: 5175,
    reuseExistingServer: true,
  },
});
