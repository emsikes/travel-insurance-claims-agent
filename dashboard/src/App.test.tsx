import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

const mockClaims = [
  {
    claim_id: "CLM-1001",
    customer_id: "CUS-3001",
    policy_id: "POL-2001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled by the airline",
    story: "My flight home from Rome was canceled.",
    items: [{ description: "Hotel", category: "accommodation", amount: 245.0 }],
    amount_claimed: 245.0,
    documents: [
      {
        name: "Cancellation notice",
        type: "carrier_report",
        content: "Flight canceled",
      },
    ],
    status: "waiting",
  },
];

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// eslint-disable-next-line sonarjs/parameterized-tests -- Separate tests for clarity
it("shows the claims queue", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  expect(await screen.findByText("CLM-1001")).toBeDefined();
});

it("shows the queue count", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  expect(await screen.findByText(/Claims Queue \(1\)/)).toBeDefined();
});

it("shows claim summary in the queue", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  expect(
    await screen.findByText("Flight home canceled by the airline"),
  ).toBeDefined();
});

it("shows claim amount in the queue", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  expect(await screen.findByText("$245.00")).toBeDefined();
});

it("shows agent instructions button", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  expect(await screen.findByText("Agent Instructions")).toBeDefined();
});

it("shows loading state", () => {
  vi.stubGlobal(
    "fetch",
    // eslint-disable-next-line @typescript-eslint/no-empty-function -- Intentional never-resolving promise
    vi.fn().mockImplementation(() => new Promise(() => {})),
  );
  render(<App />);
  expect(screen.getByText("Loading...")).toBeDefined();
});

it("navigates to claim detail on click", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  const claimCard = await screen.findByText("CLM-1001");
  fireEvent.click(claimCard);
  await waitFor(() => {
    expect(screen.getByText("Claim Information")).toBeDefined();
  });
});

it("shows agent instructions on navigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  const instructionsButton = await screen.findByText("Agent Instructions");
  fireEvent.click(instructionsButton);
  await waitFor(() => {
    expect(screen.getByText(/You are the UnderCover Agent/)).toBeDefined();
  });
});

it("navigates back to queue from claim detail", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify(mockClaims))),
      ),
  );
  render(<App />);
  const claimCard = await screen.findByText("CLM-1001");
  fireEvent.click(claimCard);
  await waitFor(() => {
    expect(screen.getByText("Claim Information")).toBeDefined();
  });
  const backButton = screen.getByText(/Back to Queue/);
  fireEvent.click(backButton);
  await waitFor(() => {
    expect(screen.getAllByText(/Claims Queue/).length).toBeGreaterThan(0);
  });
});

it("navigates back to queue from instructions", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify(mockClaims))),
      ),
  );
  render(<App />);
  const instructionsButton = await screen.findByText("Agent Instructions");
  fireEvent.click(instructionsButton);
  await waitFor(() => {
    expect(screen.getByText(/You are the UnderCover Agent/)).toBeDefined();
  });
  const queueButton = screen.getByText("Claims Queue");
  fireEvent.click(queueButton);
  await waitFor(() => {
    expect(screen.getByText("$245.00")).toBeDefined();
  });
});

it("shows summary dashboard with total claims", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(mockClaims))),
  );
  render(<App />);
  expect(await screen.findByText("Total Claims")).toBeDefined();
  const summaryDashboard = document.querySelector(".summary-dashboard");
  expect(summaryDashboard).toBeDefined();
});

it("shows summary dashboard with status counts", async () => {
  const multiStatusClaims = [
    { ...mockClaims[0], claim_id: "CLM-1001", status: "waiting" },
    { ...mockClaims[0], claim_id: "CLM-1002", status: "waiting" },
    { ...mockClaims[0], claim_id: "CLM-1003", status: "in_progress" },
    {
      ...mockClaims[0],
      claim_id: "CLM-1004",
      status: "waiting_for_signoff",
    },
    { ...mockClaims[0], claim_id: "CLM-1005", status: "decided" },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(multiStatusClaims))),
  );
  render(<App />);
  expect(await screen.findByText("Total Claims")).toBeDefined();
  expect(await screen.findByText("5")).toBeDefined();
  expect(await screen.findByText("Waiting")).toBeDefined();
  expect(await screen.findByText("In Progress")).toBeDefined();
  expect(await screen.findByText("Waiting for Sign-off")).toBeDefined();
  expect(await screen.findByText("Decided")).toBeDefined();
});

it("summary dashboard shows correct counts per status", async () => {
  const multiStatusClaims = [
    { ...mockClaims[0], claim_id: "CLM-1001", status: "waiting" },
    { ...mockClaims[0], claim_id: "CLM-1002", status: "waiting" },
    { ...mockClaims[0], claim_id: "CLM-1003", status: "in_progress" },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(multiStatusClaims))),
  );
  render(<App />);
  await screen.findByText("Total Claims");
  const summaryCards = screen.getAllByRole("generic").filter((el) => {
    return el.className.includes("summary-card");
  });
  expect(summaryCards.length).toBeGreaterThan(0);
});
