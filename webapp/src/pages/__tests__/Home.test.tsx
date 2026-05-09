import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Home from "../Home";

vi.mock("@/lib/api", () => ({
  api: {
    getSummary: vi.fn(async () => ({
      base_currency: "USD",
      month_label: "2026-05",
      total_expense_minor: 84750,    // $847.50
      total_income_minor: 300000,    // $3,000.00
      by_category: [
        { category_id: 1, name: "Food",          expense_minor: 31240 },
        { category_id: 2, name: "Transport",     expense_minor: 18000 },
        { category_id: 3, name: "Subscriptions", expense_minor: 11500 },
      ],
      account_balances: [
        { account_id: 1, name: "Cash",   balance_minor: 120000, currency: "USD" },
        { account_id: 2, name: "ByBit",  balance_minor:  95000, currency: "USD" },
      ],
    })),
    listTransactions: vi.fn(async () => ([])),
  },
}));

vi.mock("@/lib/tg", () => ({
  tg: () => null,
  getInitData: () => "",
}));

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("Home", () => {
  it("renders net-worth, KPI strip, accounts and category ranking", async () => {
    render(wrap(<Home />));
    // Wait for the loading state to clear
    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).toBeNull();
    });
    // Net worth: Cash 1,200 + ByBit 950 = 2,150 → "$2,150" appears in the hero
    expect(await screen.findByText(/2,150/)).toBeInTheDocument();
    // KPI strip
    expect(screen.getByText(/Spent/i)).toBeInTheDocument();
    expect(screen.getByText(/Saved/i)).toBeInTheDocument();
    // Categories — ranked list contains "Food"
    expect(screen.getByText("Food")).toBeInTheDocument();
    // Accounts — both account names appear
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByText("ByBit")).toBeInTheDocument();
  });
});
