import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:8000";

test.describe("Agent harness", () => {
  test("shows the current run's to-do list on the queue page", async ({
    page,
    request,
  }) => {
    const run = (await (
      await request.post(`${api}/api/runs`, { data: { cap: 3 } })
    ).json()) as { run_id: string };
    await request.put(`${api}/api/runs/${run.run_id}/todos`, {
      data: [
        { claim_id: "CLM-1001", content: "CLM-1001: e2e one", status: "done" },
        {
          claim_id: "CLM-1002",
          content: "CLM-1002: e2e two",
          status: "in_progress",
        },
        {
          claim_id: "CLM-1003",
          content: "CLM-1003: e2e three",
          status: "to_do",
        },
      ],
    });

    await page.goto("/");
    const panel = page.getByLabel("Current run");
    await expect(panel.getByText(run.run_id)).toBeVisible();
    await expect(panel.getByText("1 of 3 done")).toBeVisible();
    await expect(panel.getByText("CLM-1002: e2e two")).toBeVisible();
    await expect(panel.getByText("In progress", { exact: true })).toBeVisible();

    await request.put(`${api}/api/runs/${run.run_id}/todos`, {
      data: [
        { claim_id: "CLM-1001", content: "CLM-1001: e2e one", status: "done" },
        { claim_id: "CLM-1002", content: "CLM-1002: e2e two", status: "done" },
        {
          claim_id: "CLM-1003",
          content: "CLM-1003: e2e three",
          status: "left_for_handler",
        },
      ],
    });
    await request.post(`${api}/api/runs/${run.run_id}/finish`, {
      data: { summary: "Three claims worked in the e2e run." },
    });
    await expect(panel.getByText("3 of 3 done")).toBeVisible();
    await expect(
      panel.getByText("Three claims worked in the e2e run."),
    ).toBeVisible();
  });

  test("shows a claim's steps and the sections read", async ({
    page,
    request,
  }) => {
    const text = `Claims manual 9. Repeat claims (e2e ${String(Date.now())})`;
    await request.post(`${api}/api/claims/CLM-1025/steps`, {
      data: { attempt: 1, kind: "section_read", text },
    });
    await request.post(`${api}/api/claims/CLM-1025/steps`, {
      data: { attempt: 1, kind: "tool_call", text: "get_claim(e2e): ok" },
    });

    await page.goto("/");
    await page.locator(".claim-card", { hasText: "CLM-1025" }).click();
    await expect(
      page.getByRole("heading", { name: "Agent Steps" }),
    ).toBeVisible();
    await expect(page.locator(".sections-list").getByText(text)).toBeVisible();
    await expect(
      page.locator(".steps-list").getByText("get_claim(e2e): ok").first(),
    ).toBeVisible();
  });

  test("shows both sets of instructions", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Agent Instructions" }).click();
    await expect(
      page.getByRole("heading", { name: "Running the Queue" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Working a Claim" }),
    ).toBeVisible();
    await expect(page.getByText(/list_waiting_claims/)).toBeVisible();
    await expect(page.getByText(/read_section/).first()).toBeVisible();
  });
});
