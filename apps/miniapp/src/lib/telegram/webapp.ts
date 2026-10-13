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

export type HapticImpactStyle = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';
export type HapticNotificationType = 'error' | 'success' | 'warning';

/** Telegram WebApp.HapticFeedback (Bot API 6.1+). */
interface TelegramHapticFeedback {
  impactOccurred: (style: HapticImpactStyle) => unknown;
  notificationOccurred: (type: HapticNotificationType) => unknown;
  selectionChanged: () => unknown;
}

type TelegramGlobal = {
  WebApp?: Partial<Omit<TelegramWebAppAdapter, 'haptic'>> & { HapticFeedback?: TelegramHapticFeedback };
};

const IMPACT_STYLES: readonly string[] = ['light', 'medium', 'heavy', 'rigid', 'soft'];
const NOTIFICATION_TYPES: readonly string[] = ['error', 'success', 'warning'];

function hapticFrom(feedback: TelegramHapticFeedback | undefined): TelegramWebAppAdapter['haptic'] {
  if (!feedback) return undefined;
  return (type, style) => {
    if (type === 'impact') {
      feedback.impactOccurred((style && IMPACT_STYLES.includes(style) ? style : 'light') as HapticImpactStyle);
    } else if (type === 'notification') {
      feedback.notificationOccurred(
        (style && NOTIFICATION_TYPES.includes(style) ? style : 'success') as HapticNotificationType
      );
    } else {
      feedback.selectionChanged();
    }
  };
}

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
    haptic: hapticFrom(webApp.HapticFeedback)
  };
}
