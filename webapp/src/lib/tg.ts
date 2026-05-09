type WebApp = {
  initData: string;
  ready: () => void;
  expand: () => void;
  themeParams?: Record<string, string>;
  colorScheme?: "light" | "dark";
};
declare global {
  interface Window { Telegram?: { WebApp: WebApp } }
}
export const tg = (): WebApp | null => window.Telegram?.WebApp ?? null;
export const getInitData = (): string => tg()?.initData ?? "";
