import { expect, test } from "@playwright/test";

test.describe("Dashboard", () => {
  test("shows the claims queue", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "UnderCover" }),
    ).toBeVisible();
    await expect(page.getByText(/Claims Queue \(\d+\)/)).toBeVisible();
  });

  test("shows summary dashboard with statistics", async ({ page }) => {
    await page.goto("/");

    // Wait for summary dashboard to load
    await expect(page.locator(".summary-dashboard")).toBeVisible();

    // Verify all summary cards are present
    await expect(page.getByText("Total Claims", { exact: true })).toBeVisible();
    await expect(page.getByText("Waiting", { exact: true })).toBeVisible();
    await expect(page.getByText("In Progress", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Waiting for Sign-off", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Decided", { exact: true })).toBeVisible();

    // Verify summary cards have values
    const summaryCards = page.locator(".summary-card");
    await expect(summaryCards).toHaveCount(5);
  });

  test("displays claim cards in the queue", async ({ page }) => {
    await page.goto("/");

    // Wait for the panel to load
    await expect(page.locator(".panel")).toBeVisible();
    await expect(page.locator(".claims-grid")).toBeVisible();

    // Wait for claims to load
    await expect(page.locator(".claim-card").first()).toBeVisible({
      timeout: 10000,
    });

    // Verify claim card has expected elements
    const firstCard = page.locator(".claim-card").first();
    await expect(firstCard.locator(".claim-id")).toBeVisible();
    await expect(firstCard.locator(".status-badge")).toBeVisible();
  });

  test("navigates to claim detail view", async ({ page }) => {
    await page.goto("/");

    // Wait for claims to load and click first claim
    const firstCard = page.locator(".claim-card").first();
    await firstCard.click();

    // Verify we're on claim detail page
    await expect(page.getByText("Claim Information")).toBeVisible();
    await expect(page.getByText("Items Claimed")).toBeVisible();
    await expect(page.getByText("Supporting Documents")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Back to Queue/ }),
    ).toBeVisible();
  });

  test("shows claim details correctly", async ({ page }) => {
    await page.goto("/");

    // Click first claim
    await page.locator(".claim-card").first().click();

    // Verify detail sections are present
    await expect(page.getByText("Customer ID")).toBeVisible();
    await expect(page.getByText("Policy ID")).toBeVisible();
    await expect(page.getByText("Claim Type")).toBeVisible();
    await expect(page.getByText("Submitted On")).toBeVisible();
    await expect(page.getByText("Incident Date")).toBeVisible();
    await expect(page.getByText("Incident Location")).toBeVisible();
    await expect(page.getByText("Summary")).toBeVisible();
    await expect(page.getByText("Customer Story")).toBeVisible();
  });

  test("navigates back to queue from claim detail", async ({ page }) => {
    await page.goto("/");

    // Click first claim
    await page.locator(".claim-card").first().click();
    await expect(page.getByText("Claim Information")).toBeVisible();

    // Click back button
    await page.getByRole("button", { name: /Back to Queue/ }).click();

    // Verify we're back at queue
    await expect(page.getByText(/Claims Queue \(\d+\)/)).toBeVisible();
    await expect(page.locator(".claim-card").first()).toBeVisible();
  });

  test("shows agent instructions", async ({ page }) => {
    await page.goto("/");

    // Click Agent Instructions button
    await page.getByRole("button", { name: "Agent Instructions" }).click();

    // Verify instructions content
    await expect(page.getByText(/You are the UnderCover Agent/)).toBeVisible();
    await expect(
      page.getByText(/deciding travel insurance claims/),
    ).toBeVisible();
  });

  test("navigates between all views", async ({ page }) => {
    await page.goto("/");

    // Start at queue
    await expect(page.getByText(/Claims Queue \(\d+\)/)).toBeVisible();

    // Go to instructions
    await page.getByRole("button", { name: "Agent Instructions" }).click();
    await expect(page.getByText(/You are the UnderCover Agent/)).toBeVisible();

    // Go back to queue
    await page.getByRole("button", { name: "Claims Queue" }).click();
    await expect(page.locator(".claim-card").first()).toBeVisible();

    // Go to claim detail
    await page.locator(".claim-card").first().click();
    await expect(page.getByText("Claim Information")).toBeVisible();

    // Go to instructions from claim detail
    await page.getByRole("button", { name: "Agent Instructions" }).click();
    await expect(page.getByText(/You are the UnderCover Agent/)).toBeVisible();
  });

  test("displays status badges with correct styling", async ({ page }) => {
    await page.goto("/");

    // Wait for claims to load
    await expect(page.locator(".claim-card").first()).toBeVisible();

    // Verify status badge exists and has a status class
    const badge = page.locator(".status-badge").first();
    await expect(badge).toBeVisible();

    // Check that badge has one of the expected status classes
    const badgeClass = await badge.getAttribute("class");
    expect(badgeClass).toMatch(
      /status-(waiting|in_progress|waiting_for_signoff|decided)/,
    );
  });

  test("keyboard navigation works for claim cards", async ({ page }) => {
    await page.goto("/");

    // Wait for claims to load
    const firstCard = page.locator(".claim-card").first();
    await firstCard.waitFor({ state: "visible" });

    // Focus and press Enter
    await firstCard.focus();
    await page.keyboard.press("Enter");

    // Should navigate to claim detail
    await expect(page.getByText("Claim Information")).toBeVisible();
  });
});
