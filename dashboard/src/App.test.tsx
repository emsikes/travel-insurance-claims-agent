import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim, Run, Step } from "./api";
import { App } from "./App";

const claim: Claim = {
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
  decision: null,
  payout: null,
  explanation: null,
  policy_reference: null,
  attempts: 0,
  paid_amount: null,
};

const run: Run = {
  run_id: "RUN-abc123",
  cap: 4,
  status: "running",
  started_at: "2026-11-12T10:00:00+00:00",
  summary: null,
  todos: [
    { claim_id: "CLM-1001", content: "CLM-1001: hotel", status: "done" },
    { claim_id: "CLM-1002", content: "CLM-1002: bag", status: "in_progress" },
    { claim_id: "CLM-1003", content: "CLM-1003: phone", status: "to_do" },
    {
      claim_id: "CLM-1004",
      content: "CLM-1004: medical",
      status: "left_for_handler",
    },
  ],
};

const steps: Step[] = [
  {
    attempt: 1,
    kind: "tool_call",
    text: "get_claim(claim_id=CLM-1001): ok",
    created_at: "2026-11-12T10:00:01+00:00",
  },
  {
    attempt: 1,
    kind: "section_read",
    text: "Claims manual 10. Meals without receipts",
    created_at: "2026-11-12T10:00:02+00:00",
  },
  {
    attempt: 1,
    kind: "error",
    text: "TimeoutError: timed out",
    created_at: "2026-11-12T10:00:03+00:00",
  },
  {
    attempt: 2,
    kind: "section_read",
    text: "Claims manual 10. Meals without receipts",
    created_at: "2026-11-12T10:00:04+00:00",
  },
  {
    attempt: 2,
    kind: "result",
    text: "CLM-1001: approve, $245.00",
    created_at: "2026-11-12T10:00:05+00:00",
  },
];

const instructions = {
  queue: "You are the UnderCover Agent, running the queue.",
  claim: "You are the UnderCover Agent, deciding one claim.",
};

function mockApi(
  routes: {
    claims?: Claim[];
    run?: Run | null;
    steps?: Step[];
  } = {},
) {
  const responses: [RegExp, unknown][] = [
    [/\/api\/claims$/, routes.claims ?? [claim]],
    [/\/api\/runs\/latest$/, routes.run ?? null],
    [/\/api\/claims\/[^/]+\/steps$/, routes.steps ?? []],
    [/\/api\/instructions$/, instructions],
    [/\/api\/company-settings$/, { payout_approval_limit: 1000 }],
  ];
  const fetchMock = vi.fn((url: string) => {
    const match = responses.find(([pattern]) => pattern.test(url));
    return Promise.resolve(new Response(JSON.stringify(match?.[1])));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("shows the claims queue with its count, summary and amount", async () => {
  mockApi();
  render(<App />);
  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText(/Claims Queue \(1\)/)).toBeDefined();
  expect(screen.getByText("Flight home canceled by the airline")).toBeDefined();
  expect(screen.getByText("$245.00")).toBeDefined();
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

it("counts claims by status, including left for a handler", async () => {
  mockApi({
    claims: [
      { ...claim, claim_id: "CLM-1001", status: "waiting" },
      { ...claim, claim_id: "CLM-1002", status: "waiting" },
      { ...claim, claim_id: "CLM-1003", status: "in_progress" },
      { ...claim, claim_id: "CLM-1004", status: "waiting_for_signoff" },
      { ...claim, claim_id: "CLM-1005", status: "decided" },
      { ...claim, claim_id: "CLM-1006", status: "needs_handler" },
    ],
  });
  render(<App />);
  await screen.findByText("Total Claims");
  const cards = document.querySelectorAll(".summary-card");
  expect(cards).toHaveLength(6);
  const handlerCard = document.querySelector(
    ".summary-card.status-needs_handler",
  );
  expect(handlerCard?.textContent).toBe("Left for a Handler1");
  expect(screen.getAllByText("Left for a Handler")).toHaveLength(2);
});

it("shows no run panel before the first run", async () => {
  mockApi();
  render(<App />);
  await screen.findByText("CLM-1001");
  expect(screen.queryByLabelText("Current run")).toBeNull();
});

it("shows the to-do list in all four states", async () => {
  mockApi({ run });
  render(<App />);
  const panel = await screen.findByLabelText("Current run");
  expect(within(panel).getByText("Agent run in progress")).toBeDefined();
  expect(within(panel).getByText("2 of 4 done")).toBeDefined();
  expect(within(panel).getByText("RUN-abc123")).toBeDefined();
  for (const label of ["Done", "In progress", "To do", "Left for a handler"]) {
    expect(within(panel).getByText(label)).toBeDefined();
  }
  expect(within(panel).getByText("CLM-1003: phone")).toBeDefined();
});

it("shows a planning message before the agent writes its list", async () => {
  mockApi({ run: { ...run, todos: [] } });
  render(<App />);
  expect(
    await screen.findByText("The agent is planning its work."),
  ).toBeDefined();
});

it("shows the summary of a finished run", async () => {
  mockApi({
    run: { ...run, status: "finished", summary: "Four claims worked." },
  });
  render(<App />);
  expect(await screen.findByText("Last agent run")).toBeDefined();
  expect(screen.getByText("Four claims worked.")).toBeDefined();
});

function callsTo(fetchMock: ReturnType<typeof mockApi>, pattern: RegExp) {
  return fetchMock.mock.calls.filter(([url]) => pattern.test(url)).length;
}

const CLAIMS = /\/api\/claims$/;
const RUNS = /\/api\/runs\/latest$/;
const STEPS = /\/steps$/;

it("polls the claims every 2 seconds while a run is in progress", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = mockApi({ run });
  render(<App />);
  await screen.findByLabelText("Current run");
  const before = callsTo(fetchMock, CLAIMS);
  await vi.advanceTimersByTimeAsync(4000);
  expect(callsTo(fetchMock, CLAIMS)).toBe(before + 2);
});

it("stops polling the claims when no run is in progress", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = mockApi({ run: { ...run, status: "finished" } });
  render(<App />);
  await screen.findByText("Last agent run");
  const claims = callsTo(fetchMock, CLAIMS);
  const runs = callsTo(fetchMock, RUNS);
  await vi.advanceTimersByTimeAsync(10000);
  expect(callsTo(fetchMock, CLAIMS)).toBe(claims);
  expect(callsTo(fetchMock, RUNS)).toBeGreaterThan(runs);
});

it("polls nothing on the instructions page", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = mockApi({ run });
  render(<App />);
  await screen.findByLabelText("Current run");
  fireEvent.click(screen.getByText("Agent Instructions"));
  await screen.findByText("Running the Queue");
  const calls = [CLAIMS, RUNS, STEPS].map((p) => callsTo(fetchMock, p));
  await vi.advanceTimersByTimeAsync(10000);
  expect([CLAIMS, RUNS, STEPS].map((p) => callsTo(fetchMock, p))).toEqual(
    calls,
  );
});

it("shows a claim's details, steps and sections read", async () => {
  mockApi({
    claims: [{ ...claim, status: "decided", attempts: 1 }],
    steps,
  });
  render(<App />);
  fireEvent.click(await screen.findByText("CLM-1001"));
  expect(await screen.findByText("Claim Information")).toBeDefined();
  expect(screen.getByText("Items Claimed")).toBeDefined();
  expect(screen.getByText("Supporting Documents")).toBeDefined();
  expect(await screen.findByText("Agent Steps")).toBeDefined();

  const sections = document.querySelector(".sections-list");
  expect(sections?.textContent).toBe(
    "Claims manual 10. Meals without receipts",
  );
  expect(await screen.findByText("TimeoutError: timed out")).toBeDefined();
  expect(screen.getByText("Result (attempt 2)")).toBeDefined();
  expect(screen.getByText("Failed attempts:")).toBeDefined();
});

it("says when the agent has not worked a claim", async () => {
  mockApi();
  render(<App />);
  fireEvent.click(await screen.findByText("CLM-1001"));
  expect(
    await screen.findByText("The agent has not worked this claim yet."),
  ).toBeDefined();
  expect(
    screen.getByText("The agent has not read any sections yet."),
  ).toBeDefined();
});

it("shows a claim left for a handler", async () => {
  mockApi({ claims: [{ ...claim, status: "needs_handler", attempts: 2 }] });
  render(<App />);
  fireEvent.click(await screen.findByText("CLM-1001"));
  await screen.findByText("Claim Information");
  expect(screen.getByText("Left for a Handler")).toBeDefined();
});

it("shows a decision waiting for sign-off", async () => {
  mockApi({
    claims: [
      {
        ...claim,
        status: "waiting_for_signoff",
        decision: "approve",
        payout: 1500,
        explanation: "Covered delay.",
        policy_reference: "Policy wording 3. Trip Delay",
      },
    ],
  });
  render(<App />);
  fireEvent.click(await screen.findByText("CLM-1001"));
  expect(await screen.findByText("Decision: APPROVE")).toBeDefined();
  expect(screen.getByText("Payout: $1,500.00")).toBeDefined();
  expect(
    await screen.findByText(
      "Over the $1,000.00 approval limit: payment waits for sign-off.",
    ),
  ).toBeDefined();
  expect(screen.getByText("Covered delay.")).toBeDefined();
  expect(
    screen.getByText("Policy Reference: Policy wording 3. Trip Delay"),
  ).toBeDefined();
});

it("shows a paid decision", async () => {
  mockApi({
    claims: [
      {
        ...claim,
        status: "decided",
        decision: "approve",
        payout: 245,
        paid_amount: 245,
      },
    ],
  });
  render(<App />);
  fireEvent.click(await screen.findByText("CLM-1001"));
  expect(await screen.findByText("Paid: $245.00")).toBeDefined();
});

it("navigates back to the queue from a claim", async () => {
  mockApi();
  render(<App />);
  fireEvent.click(await screen.findByText("CLM-1001"));
  await screen.findByText("Claim Information");
  fireEvent.click(screen.getByText(/Back to Queue/));
  expect(await screen.findByText(/Claims Queue \(1\)/)).toBeDefined();
});

it("opens a claim from the keyboard", async () => {
  mockApi();
  render(<App />);
  const card = (await screen.findByText("CLM-1001")).closest(".claim-card");
  if (!card) throw new Error("no claim card");
  fireEvent.keyDown(card, { key: "Enter" });
  expect(await screen.findByText("Claim Information")).toBeDefined();
});

it("shows both sets of instructions from the API", async () => {
  mockApi();
  render(<App />);
  fireEvent.click(await screen.findByText("Agent Instructions"));
  expect(await screen.findByText("Running the Queue")).toBeDefined();
  expect(screen.getByText("Working a Claim")).toBeDefined();
  expect(screen.getByText(instructions.queue)).toBeDefined();
  expect(screen.getByText(instructions.claim)).toBeDefined();

  fireEvent.click(screen.getByText("Claims Queue"));
  expect(await screen.findByText("$245.00")).toBeDefined();
});
