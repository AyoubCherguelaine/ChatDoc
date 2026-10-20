import path from "path";
import { test, expect } from "@playwright/test";

const EMAIL = `pw_${Date.now()}@docuchat.io`;
const PASSWORD = "secret123";
const SAMPLE_PDF = path.resolve(__dirname, "../../sample.pdf");

test.describe("DocuChat end-to-end", () => {
  let pageErrors: string[] = [];

  test.beforeEach(async ({ page }) => {
    test.setTimeout(180_000);
    pageErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" || msg.type() === "warning") {
        console.log(`  [page ${msg.type()}] ${msg.text()}`);
      }
    });
    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
      console.log("  [pageerror]", err.message);
    });
  });

  test("login -> drive -> upload -> create session -> chat", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Log in", exact: true }).click();
    await page.waitForURL("**/login", { timeout: 15_000 });

    await page.click("text=Don't have an account? Sign up");
    await page.fill('input[name="name"]', "Playwright Tester");
    await page.fill('input[name="email"]', EMAIL);
    await page.fill('input[name="password"]', PASSWORD);
    await page.click("text=Create account");

    await page.waitForURL("**/drive", { timeout: 30_000 });
    await expect(page).toHaveURL(/\/drive/);

    // Upload the sample PDF.
    await page.click("text=Upload document");
    await page.locator('input[type="file"]').setInputFiles(SAMPLE_PDF);
    await page.click("text=Upload & process");
    await expect(page.locator("text=sample.pdf")).toBeVisible({
      timeout: 60_000,
    });

    // Open the session picker and create a new conversation.
    const chatBtn = page.locator('button:has-text("Chat")').first();
    await chatBtn.click();
    await expect(page.locator("text=Pick a conversation")).toBeVisible();
    await page.click("text=New conversation");

    await page.waitForURL(/\/chat\//, { timeout: 30_000 });

    // Ask a question.
    await page.fill(
      'textarea[placeholder="Ask a question about your document…"]',
      "What is the budget and who is the lead of Moonshot?",
    );
    await page.click('button[title="Send"]');

    await expect(page.locator("text=Dr. Elena Vasquez")).toBeVisible({
      timeout: 60_000,
    });

    console.log("E2E completed successfully, errors:", pageErrors);
  });
});
