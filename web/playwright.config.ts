import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  globalSetup: "./tests/global-setup.ts",
  globalTeardown: "./tests/global-teardown.ts",
  use: {
    baseURL: "http://localhost:5175",
    screenshot: "on",
  },
  webServer: {
    command: "VITE_API_TARGET=http://localhost:5002 npx vite --port 5175",
    port: 5175,
    reuseExistingServer: false,
  },
});
