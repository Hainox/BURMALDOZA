import { afterEach, describe, expect, it, vi } from 'vitest';
import { getTelegramWebApp } from './webapp';

// Unit tests run in Node: stub a minimal browser window with the Telegram global.
const withTelegram = (webApp: unknown) => vi.stubGlobal('window', { Telegram: { WebApp: webApp } });

describe('Telegram haptic adapter', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('maps haptics to WebApp.HapticFeedback', () => {
    const feedback = { impactOccurred: vi.fn(), notificationOccurred: vi.fn(), selectionChanged: vi.fn() };
    withTelegram({ initData: 'signed', HapticFeedback: feedback });
    const haptic = getTelegramWebApp().haptic;
    expect(haptic).toBeTypeOf('function');
    haptic?.('impact', 'heavy');
    haptic?.('notification', 'error');
    haptic?.('selection');
    haptic?.('impact', 'unknown');
    expect(feedback.impactOccurred.mock.calls).toEqual([['heavy'], ['light']]);
    expect(feedback.notificationOccurred).toHaveBeenCalledWith('error');
    expect(feedback.selectionChanged).toHaveBeenCalledTimes(1);
  });

  it('has no haptics outside Telegram or on clients without HapticFeedback', () => {
    vi.stubGlobal('window', {});
    expect(getTelegramWebApp().haptic).toBeUndefined();
    withTelegram({ initData: 'signed' });
    expect(getTelegramWebApp().haptic).toBeUndefined();
  });
});
