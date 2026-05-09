const E: Record<string, number> = {
  USD: 2, EUR: 2, GBP: 2, AED: 2, RUB: 2, CHF: 2, CAD: 2, AUD: 2,
  CNY: 2, INR: 2, TRY: 2, PLN: 2, CZK: 2, SEK: 2,
  JPY: 0, KRW: 0,
  KWD: 3, BHD: 3, OMR: 3, TND: 3,
};

export const exp = (c: string): number => E[c.toUpperCase()] ?? 2;

export const fromMinor = (m: number, c: string): number => m / 10 ** exp(c);

export const toMinor = (n: number, c: string): number => Math.round(n * 10 ** exp(c));

export function formatAmount(m: number, c: string): string {
  const e = exp(c);
  const sign = m < 0 ? "−" : "";
  const n = Math.abs(m);
  if (e === 0) return `${sign}${n} ${c}`;
  const w = Math.floor(n / 10 ** e);
  const f = (n % 10 ** e).toString().padStart(e, "0");
  return `${sign}${w}.${f} ${c}`;
}

/** USD-style formatter for base currency: $1,234.50 */
export function formatBase(m: number, c: string): string {
  const e = exp(c);
  const sign = m < 0 ? "−" : "";
  const n = Math.abs(m);
  if (e === 0) return `${sign}${symbolFor(c)}${n.toLocaleString("en-US")}`;
  const whole = Math.floor(n / 10 ** e).toLocaleString("en-US");
  const frac = (n % 10 ** e).toString().padStart(e, "0");
  return `${sign}${symbolFor(c)}${whole}.${frac}`;
}

function symbolFor(c: string): string {
  switch (c.toUpperCase()) {
    case "USD": case "AUD": case "CAD": return "$";
    case "EUR": return "€";
    case "GBP": return "£";
    case "RUB": return "₽";
    case "JPY": case "CNY": return "¥";
    default: return "";
  }
}
