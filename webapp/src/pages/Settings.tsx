import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Download, Clock, Trash2, Repeat, ChevronRight } from "lucide-react";
import { api, Account } from "@/lib/api";
import { Hr } from "@/components/Section";

// ── Button style constants ────────────────────────────────────────────────────

const btnGhost =
  "inline-flex items-center justify-between gap-1.5 px-3 py-2.5 rounded-md text-[12.5px] font-medium bg-transparent text-foreground border border-border hover:bg-neutral-50";
const btnDanger =
  "inline-flex items-center justify-between gap-1.5 px-3 py-2.5 rounded-md text-[12.5px] font-medium bg-transparent text-foreground border border-[#d4d4d4] hover:bg-neutral-50";

// ── Field row ─────────────────────────────────────────────────────────────────

function FieldRow({
  label,
  children,
  first = false,
}: {
  label: string;
  children: React.ReactNode;
  first?: boolean;
}) {
  return (
    <div
      className={
        "grid grid-cols-[88px_1fr] items-center px-3 py-2.5" +
        (first ? "" : " border-t border-[#f0f0f1]")
      }
    >
      <span className="label">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

// ── Debounced save helper ─────────────────────────────────────────────────────

function useDebouncedSave(
  delayMs: number = 500
): {
  triggerSave: (key: string, value: any) => void;
  saving: string | null;
} {
  const [saving, setSaving] = useState<string | null>(null);
  const timeoutRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const qc = useQueryClient();
  const patchMut = useMutation({
    mutationFn: (body: Record<string, any>) => api.patchSettings(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const triggerSave = (key: string, value: any) => {
    setSaving(key);
    if (timeoutRef.current[key]) clearTimeout(timeoutRef.current[key]);
    timeoutRef.current[key] = setTimeout(() => {
      patchMut.mutate({ [key]: value });
      setSaving(null);
    }, delayMs);
  };

  return { triggerSave, saving };
}

// ── Main component ────────────────────────────────────────────────────────────

const CURRENCIES = ["USD", "EUR", "AED", "GBP"];
const TIMEZONES = ["Europe/Berlin", "UTC", "America/New_York"];
const PARSE_MODELS = ["openai/gpt-4.1-mini", "openai/gpt-5", "anthropic/claude-haiku-4.5"];
const STT_MODELS = ["google/gemini-2.5-flash", "openai/gpt-4o-audio"];

export default function Settings() {
  const nav = useNavigate();

  // ── Queries ──────────────────────────────────────────────────────────────────

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.getSettings,
    staleTime: 300_000,
  });

  const accsQuery = useQuery({
    queryKey: ["accs", false],
    queryFn: () => api.listAccounts(false),
    staleTime: 30_000,
  });

  const settings = settingsQuery.data;
  const accounts: Account[] = accsQuery.data ?? [];

  // ── Regional form state ───────────────────────────────────────────────────────

  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [timezone, setTimezone] = useState("Europe/Berlin");
  const [defaultAccountId, setDefaultAccountId] = useState<number | "">("");
  const { triggerSave: saveRegional, saving: savingRegional } = useDebouncedSave();

  // Initialise regional state from settings
  useEffect(() => {
    if (settings) {
      setBaseCurrency(settings.base_currency);
      setTimezone(settings.timezone);
      setDefaultAccountId(settings.default_account_id);
    }
  }, [settings]);

  // ── Alerts form state ────────────────────────────────────────────────────────

  const [thresholds, setThresholds] = useState("0.8, 1.0");
  const [weeklyDigest, setWeeklyDigest] = useState("Sun 09:00");
  const [monthlySummary, setMonthlySummary] = useState("1st 09:00");
  const { triggerSave: _saveAlerts, saving: savingAlerts } = useDebouncedSave();

  // TODO: Initialize from API when alert fields are added to Settings schema
  // useEffect(() => {
  //   if (settings) {
  //     setThresholds(settings.alert_thresholds?.join(", ") ?? "0.8, 1.0");
  //   }
  // }, [settings]);

  // ── AI form state (visual only) ───────────────────────────────────────────────

  const [parseModel, setParseModel] = useState("openai/gpt-4.1-mini");
  const [sttModel, setSttModel] = useState("google/gemini-2.5-flash");
  const [apiKey, setApiKey] = useState("••••••••••••");

  // ── Get first letter for avatar ───────────────────────────────────────────────

  const getAvatarLetter = (): string => {
    // TODO: Read from Telegram WebApp user object when available
    return "A";
  };

  const getUserName = (): string => {
    // TODO: Read from Telegram WebApp user object when available
    return "Arthur";
  };

  const getBotUsername = (): string => {
    // TODO: Fetch from /api/me endpoint
    return "@finnackerbot";
  };

  const getOwnerTgId = (): string => {
    // TODO: Fetch from /api/me endpoint
    return "7510630531";
  };

  // ── Handlers ──────────────────────────────────────────────────────────────────

  const handleBaseCurrencyChange = (value: string) => {
    setBaseCurrency(value);
    saveRegional("base_currency", value);
  };

  const handleTimezoneChange = (value: string) => {
    setTimezone(value);
    saveRegional("timezone", value);
  };

  const handleDefaultAccountChange = (value: string) => {
    const id = value ? parseInt(value) : "";
    setDefaultAccountId(id);
    if (typeof id === "number") {
      saveRegional("default_account_id", id);
    }
  };

  const handleThresholdsChange = (value: string) => {
    setThresholds(value);
    // TODO: saveAlerts("alert_thresholds", ...)
  };

  const handleWeeklyDigestChange = (value: string) => {
    setWeeklyDigest(value);
    // TODO: saveAlerts("weekly_digest_time", ...)
  };

  const handleMonthlySummaryChange = (value: string) => {
    setMonthlySummary(value);
    // TODO: saveAlerts("monthly_summary_day_time", ...)
  };

  const handleResetData = () => {
    if (confirm("Reset all data?")) {
      // TODO: Call api.resetData() endpoint
      console.log("Reset all data (no-op for now)");
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="pb-16">
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => nav(-1)}
          className="w-8 h-8 flex items-center justify-center text-neutral-600 -ml-1"
          aria-label="Back"
        >
          <ChevronLeft size={20} strokeWidth={1.75} />
        </button>

        <span className="text-[13px] font-semibold tracking-tight">Settings</span>

        <div className="w-5" />
      </div>

      <Hr />

      {/* ── Profile section ──────────────────────────────────────────────────── */}
      <div className="px-5 py-5 flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-foreground text-background grid place-items-center text-base font-semibold shrink-0">
          {getAvatarLetter()}
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-semibold tracking-tight">
            {getUserName()}
          </div>
          <div className="num text-[10px] text-neutral-400 truncate">
            {getBotUsername()} · tg id {getOwnerTgId()}
          </div>
        </div>
      </div>

      <Hr />

      {/* ── Regional section ─────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between mb-3">
          <span className="label">Regional</span>
          {savingRegional && (
            <span className="num text-[9px] text-neutral-400">saving…</span>
          )}
        </div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Base currency" first>
            <select
              value={baseCurrency}
              onChange={(e) => handleBaseCurrencyChange(e.target.value)}
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Timezone">
            <select
              value={timezone}
              onChange={(e) => handleTimezoneChange(e.target.value)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Default acct">
            <select
              value={defaultAccountId}
              onChange={(e) => handleDefaultAccountChange(e.target.value)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="">—</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} · {a.currency}
                </option>
              ))}
            </select>
          </FieldRow>
        </div>
      </div>

      <Hr />

      {/* ── AI section ───────────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="label mb-3">AI</div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Parse model" first>
            <select
              value={parseModel}
              onChange={(e) => setParseModel(e.target.value)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {PARSE_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="STT model">
            <select
              value={sttModel}
              onChange={(e) => setSttModel(e.target.value)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {STT_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="API key">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="••••••••••••"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full font-mono"
            />
          </FieldRow>
        </div>

        <div className="num text-[10px] text-neutral-400 mt-2 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-foreground" />
          ~$0.18 spent this month · 142 calls
        </div>
      </div>

      <Hr />

      {/* ── Alerts & digest section ──────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between mb-3">
          <span className="label">Alerts &amp; digest</span>
          {savingAlerts && (
            <span className="num text-[9px] text-neutral-400">saving…</span>
          )}
        </div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Thresholds" first>
            <input
              type="text"
              value={thresholds}
              onChange={(e) => handleThresholdsChange(e.target.value)}
              placeholder="0.8, 1.0"
              className="num text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>

          <FieldRow label="Weekly digest">
            <input
              type="text"
              value={weeklyDigest}
              onChange={(e) => handleWeeklyDigestChange(e.target.value)}
              placeholder="Sun 09:00"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>

          <FieldRow label="Monthly summary">
            <input
              type="text"
              value={monthlySummary}
              onChange={(e) => handleMonthlySummaryChange(e.target.value)}
              placeholder="1st 09:00"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            />
          </FieldRow>
        </div>
      </div>

      <Hr />

      {/* ── Automation section ──────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="label mb-3">Automation</div>
        <div className="space-y-2">
          <button onClick={() => nav("/recurring")} className={btnGhost + " w-full"}>
            <span className="flex items-center gap-2">
              <Repeat size={14} strokeWidth={1.75} />
              Recurring rules
            </span>
            <ChevronRight size={14} strokeWidth={1.75} className="text-neutral-400" />
          </button>
        </div>
      </div>

      <Hr />

      {/* ── Data section ─────────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="label mb-3">Data</div>
        <div className="space-y-2">
          <button className={btnGhost + " w-full"}>
            <span className="flex items-center gap-2">
              <Download size={14} strokeWidth={1.75} />
              Export CSV
            </span>
            <span className="num text-[10px] text-neutral-400">~7 KB · 42 tx</span>
          </button>

          <button className={btnGhost + " w-full"}>
            <span className="flex items-center gap-2">
              <Clock size={14} strokeWidth={1.75} />
              Backups
            </span>
            <span className="num text-[10px] text-neutral-400">last: today 03:00 · ok</span>
          </button>

          <button
            onClick={handleResetData}
            className={btnDanger + " w-full"}
          >
            <span className="flex items-center gap-2">
              <Trash2 size={14} strokeWidth={1.75} />
              Reset all data
            </span>
          </button>
        </div>
      </div>

      <Hr />

      {/* ── App info footer ──────────────────────────────────────────────────── */}
      <div className="px-5 py-4 text-[10px] text-neutral-400 num space-y-0.5">
        <div>finance-app · v0.3.0 (phase 3)</div>
        <div>db: 12 tables · 24 KB</div>
        <div>healthz: ok · uptime 2h 14m</div>
      </div>
    </div>
  );
}
