import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("header shows engine status", async ({ page }) => {
    await page.goto("/");
    const header = page.getByTestId("header");
    await expect(header).toContainText("BISIMULATOR");
    await expect(page.getByTestId("engine-status")).toBeVisible();
    await expect(page.getByTestId("episode-count")).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: "tests/screenshots/header.png", fullPage: false });
  });

  test("Capture tab shows frames or empty state", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Capture" }).click();
    const panel = page.getByTestId("frames-panel");
    await expect(panel).toBeVisible({ timeout: 10000 });
    await expect(panel.getByTestId("page-indicator")).toBeVisible();
    await page.screenshot({ path: "tests/screenshots/capture.png", fullPage: true });
  });

  test("Audio tab loads", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Audio" }).click();
    const panel = page.getByTestId("audio-panel");
    await expect(panel).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: "tests/screenshots/audio.png", fullPage: true });
  });

  test("Episodes tab loads", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Episodes" }).click();
    const panel = page.getByTestId("episodes-panel");
    await expect(panel).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: "tests/screenshots/episodes.png", fullPage: true });
  });

  test("Playbook tab loads", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Playbook" }).click();
    const panel = page.getByTestId("playbooks-panel");
    await expect(panel).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Run Distill" })).toBeVisible();
    await page.screenshot({ path: "tests/screenshots/playbook.png", fullPage: true });
  });

  test("Usage tab shows cost summary", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Usage" }).click();
    const panel = page.getByTestId("usage-panel");
    await expect(panel).toBeVisible({ timeout: 10000 });
    await expect(panel.getByText("Total Cost")).toBeVisible();
    await expect(panel.getByText("Input Tokens")).toBeVisible();
    await expect(panel.getByText("Output Tokens")).toBeVisible();
    await expect(panel.getByText("API Calls")).toBeVisible();
    await page.screenshot({ path: "tests/screenshots/usage.png", fullPage: true });
  });

  test("tab switching works", async ({ page }) => {
    await page.goto("/");
    for (const tab of ["Capture", "Audio", "Episodes", "Playbook", "Usage"]) {
      await page.getByRole("tab", { name: tab }).click();
      await expect(page.getByRole("tab", { name: tab })).toHaveAttribute(
        "aria-selected",
        "true"
      );
    }
  });
});
