import { getInitData } from "./tg";

const API_BASE = "/api";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(API_BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
      ...(init.headers ?? {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  if (r.status === 204) return undefined as unknown as T;
  return r.json() as Promise<T>;
}

export type Tx = {
  id: number;
  group_id: string | null;
  occurred_at: string;
  account_id: number;
  category_id: number | null;
  kind: string;
  amount_minor: number;
  currency: string;
  base_amount_minor: number;
  fx_rate: number | null;
  merchant: string | null;
  note: string | null;
  source: string | null;
  raw_input: string | null;
  confidence: number | null;
  deleted_at: string | null;
};

export type Account = {
  id: number;
  name: string;
  kind: string;
  currency: string;
  archived: number;
  opening_balance_minor: number;
};

export type Category = {
  id: number;
  name: string;
  parent_id: number | null;
  kind: string;
  emoji: string | null;
  archived: number;
};

export type Summary = {
  base_currency: string;
  month_label: string;
  total_expense_minor: number;
  total_income_minor: number;
  by_category: { category_id: number | null; name: string; expense_minor: number }[];
  account_balances: {
    account_id: number;
    name: string;
    balance_minor: number;
    balance_30d_ago_minor: number;
    currency: string;
  }[];
};

export type Settings = {
  base_currency: string;
  timezone: string;
  default_account_id: number;
  alert_thresholds_default: number[];
};

export type Budget = {
  id: number;
  category_id: number;
  amount_minor: number;
  currency: string;
  alert_thresholds: number[];
  starts_on?: string | null;
  ends_on?: string | null;
};

export type BudgetProgress = {
  budget_id: number;
  category_id: number;
  amount_minor: number;
  spent_minor: number;
  currency: string;
  fraction: number;
};

export type Goal = {
  id: number;
  name: string;
  target_minor: number;
  currency: string;
  progress_mode: "account_linked" | "contribution_tagged";
  account_id: number | null;
  target_date?: string | null;
};

export type GoalProgress = {
  id: number;
  name: string;
  target_minor: number;
  currency: string;
  progress_minor: number;
  fraction: number;
  projected_hit_date: string | null;
  target_date: string | null;
};

export type Recurring = {
  id: number;
  name: string;
  rrule: string;
  template_json: string;
  next_run_at: string | null;
  last_run_at: string | null;
  active: number;
};

export type AskResponse = {
  answer: string;
};

export type ForecastResponse = {
  avg_daily_minor: number;
  eom_net_minor: number;
  runway_months: number | null;
  days_to_goal: Record<string, number | null>;
  month_label: string;
};

export const api = {
  // transactions
  listTransactions: (includeDeleted = false) =>
    req<Tx[]>(`/transactions?include_deleted=${includeDeleted}`),
  getTransaction: (id: number) => req<Tx>(`/transactions/${id}`),
  patchTransaction: (id: number, body: Partial<Tx>) =>
    req<Tx>(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTransaction: (id: number) =>
    req<void>(`/transactions/${id}`, { method: "DELETE" }),
  restoreTransaction: (id: number) =>
    req<void>(`/transactions/${id}/restore`, { method: "POST" }),
  splitTransaction: (id: number, splits: { category_id: number; amount_minor: number; note?: string }[]) =>
    req<Tx[]>(`/transactions/${id}/split`, { method: "POST", body: JSON.stringify({ splits }) }),

  // accounts
  listAccounts: (includeArchived = false) =>
    req<Account[]>(`/accounts?include_archived=${includeArchived}`),
  createAccount: (b: Omit<Account, "id" | "archived">) =>
    req<Account>("/accounts", { method: "POST", body: JSON.stringify(b) }),
  archiveAccount: (id: number) =>
    req<void>(`/accounts/${id}/archive`, { method: "POST" }),
  deleteAccount: (id: number) =>
    req<void>(`/accounts/${id}`, { method: "DELETE" }),

  // categories
  listCategories: (includeArchived = false) =>
    req<Category[]>(`/categories?include_archived=${includeArchived}`),
  createCategory: (b: { name: string; parent_id?: number | null; kind: string; emoji?: string | null }) =>
    req<Category>("/categories", { method: "POST", body: JSON.stringify(b) }),
  archiveCategory: (id: number) =>
    req<void>(`/categories/${id}/archive`, { method: "POST" }),

  // summary
  getSummary: () => req<Summary>("/summary"),
  getNetworthSeries: (days = 30) =>
    req<{ base_currency: string; points: { date: string; value_minor: number }[] }>(
      `/summary/networth_series?days=${days}`
    ),

  // settings
  getSettings: () => req<Settings>("/settings"),
  patchSettings: (b: Partial<Settings>) =>
    req<Settings>("/settings", { method: "PATCH", body: JSON.stringify(b) }),

  // budgets
  listBudgets: () => req<Budget[]>("/budgets"),
  createBudget: (b: Omit<Budget, "id">) =>
    req<Budget>("/budgets", { method: "POST", body: JSON.stringify(b) }),
  deleteBudget: (id: number) =>
    req<void>(`/budgets/${id}`, { method: "DELETE" }),
  budgetProgress: () => req<BudgetProgress[]>("/budgets/progress"),

  // goals
  listGoals: () => req<Goal[]>("/goals"),
  createGoal: (b: Omit<Goal, "id">) =>
    req<Goal>("/goals", { method: "POST", body: JSON.stringify(b) }),
  archiveGoal: (id: number) =>
    req<void>(`/goals/${id}/archive`, { method: "POST" }),
  goalProgress: () => req<GoalProgress[]>("/goals/progress"),

  // ai
  ask: (question: string) =>
    req<AskResponse>("/ask", { method: "POST", body: JSON.stringify({ question }) }),
  getForecast: () => req<ForecastResponse>("/forecast"),

  // recurring
  listRecurring: () => req<Recurring[]>("/recurring"),
  createRecurring: (b: { name: string; rrule: string; template_json: string; next_run_at?: string | null }) =>
    req<Recurring>("/recurring", { method: "POST", body: JSON.stringify(b) }),
  pauseRecurring: (id: number) =>
    req<void>(`/recurring/${id}/pause`, { method: "POST" }),
  resumeRecurring: (id: number) =>
    req<void>(`/recurring/${id}/resume`, { method: "POST" }),
  deleteRecurring: (id: number) =>
    req<void>(`/recurring/${id}`, { method: "DELETE" }),
};
