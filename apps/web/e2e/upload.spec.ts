import { test, expect } from "@playwright/test";

test.describe("Core navigation", () => {
  test("should display the upload page", async ({ page }) => {
    await page.goto("/upload");
    await expect(page).toHaveURL(/upload/);
  });

  test("should display the meetings page", async ({ page }) => {
    await page.goto("/meetings");
    await expect(page).toHaveURL(/meetings/);
  });

  test("should display the search page", async ({ page }) => {
    await page.goto("/search");
    await expect(page).toHaveURL(/search/);
  });

  test("should display the files page", async ({ page }) => {
    await page.goto("/files");
    await expect(page).toHaveURL(/files/);
  });

  test("should display the dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
  });
});
