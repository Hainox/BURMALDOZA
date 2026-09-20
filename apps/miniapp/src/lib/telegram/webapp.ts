export type TelegramThemeParams = Record<string, string>;

export interface TelegramWebAppAdapter {
  initData: string;
  themeParams: TelegramThemeParams;
  safeAreaInset: Partial<Record<'top' | 'bottom' | 'left' | 'right', number>>;
  contentSafeAreaInset: Partial<Record<'top' | 'bottom' | 'left' | 'right', number>>;
  ready: () => void;
  expand: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
  haptic?: (type: 'impact' | 'notification' | 'selection', style?: string) => void;
}

type TelegramGlobal = {
  WebApp?: Partial<TelegramWebAppAdapter>;
};

const fallback: TelegramWebAppAdapter = {
  initData: '',
  themeParams: {},
  safeAreaInset: {},
  contentSafeAreaInset: {},
  ready: () => undefined,
  expand: () => undefined,
  setHeaderColor: () => undefined,
  setBackgroundColor: () => undefined
};

export function getTelegramWebApp(): TelegramWebAppAdapter {
  if (typeof window === 'undefined') return fallback;
  const webApp = (window as typeof window & { Telegram?: TelegramGlobal }).Telegram?.WebApp;
  if (!webApp) return fallback;
  return {
    initData: webApp.initData ?? '',
    themeParams: webApp.themeParams ?? {},
    safeAreaInset: webApp.safeAreaInset ?? {},
    contentSafeAreaInset: webApp.contentSafeAreaInset ?? {},
    ready: webApp.ready ?? fallback.ready,
    expand: webApp.expand ?? fallback.expand,
    setHeaderColor: webApp.setHeaderColor ?? fallback.setHeaderColor,
    setBackgroundColor: webApp.setBackgroundColor ?? fallback.setBackgroundColor,
    haptic: webApp.haptic
  };
}
