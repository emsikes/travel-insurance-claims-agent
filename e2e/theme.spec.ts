import { expect, test } from "@playwright/test";

const LIGHT_BG = "rgb(240, 244, 245)";
const DARK_BG = "rgb(4, 35, 46)";

test.describe("Theme", () => {
  test("switches between light and dark and remembers it", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");
    const body = page.locator("body");
    await expect(body).toHaveCSS("background-color", LIGHT_BG);

    await page.getByRole("button", { name: "Dark Mode" }).click();
    await expect(body).toHaveCSS("background-color", DARK_BG);

    await page.reload();
    await expect(body).toHaveCSS("background-color", DARK_BG);

    await page.getByRole("button", { name: "Light Mode" }).click();
    await expect(body).toHaveCSS("background-color", LIGHT_BG);
  });

  test("a light choice wins over a dark system setting", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    const body = page.locator("body");
    await expect(body).toHaveCSS("background-color", DARK_BG);

    await page.getByRole("button", { name: "Light Mode" }).click();
    await expect(body).toHaveCSS("background-color", LIGHT_BG);
  });
});
