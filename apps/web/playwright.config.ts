import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    launchOptions: {
      executablePath: process.env.CHROME_PATH || "/opt/google/chrome/chrome",
      args: ["--no-sandbox"],
    },
    screenshot: "only-on-failure",
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../../.runtime/playwright-results.json" }],
  ],
});
