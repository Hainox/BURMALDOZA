import { afterEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

// Unit tests run in Node: окно с Telegram и localStorage подставляем вручную, Web Audio нет.
function stubBrowser() {
  const feedback = { impactOccurred: vi.fn(), notificationOccurred: vi.fn(), selectionChanged: vi.fn() };
  const store = new Map<string, string>();
  vi.stubGlobal('window', { Telegram: { WebApp: { initData: 'signed', HapticFeedback: feedback } }, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  vi.stubGlobal('document', { addEventListener: vi.fn(), hidden: false });
  vi.stubGlobal('localStorage', { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v) });
  return { feedback, store };
}

describe('sound and haptics', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  it('starts muted but still vibrates on confirmed events', async () => {
    const { feedback } = stubBrowser();
    const { sound, soundEnabled } = await import('./sound');
    sound.init();
    expect(get(soundEnabled)).toBe(false);
    sound.cue('win');
    sound.cue('card');
    sound.cue('tap');
    expect(feedback.notificationOccurred).toHaveBeenCalledWith('success');
    expect(feedback.impactOccurred).toHaveBeenCalledWith('light');
    expect(feedback.selectionChanged).toHaveBeenCalledTimes(1);
  });

  it('remembers the player choice and stays quiet without Web Audio or a sound pack', async () => {
    const { store } = stubBrowser();
    const { sound, soundEnabled } = await import('./sound');
    sound.init();
    await sound.toggle();
    expect(get(soundEnabled)).toBe(true);
    expect(store.get('burmaldoza-sound')).toBe('on');
    expect(() => { sound.cue('win-big'); sound.voice('HK416', 'greet'); sound.setScene('slot'); }).not.toThrow();
    await sound.toggle();
    expect(store.get('burmaldoza-sound')).toBe('off');
  });

  it('restores an enabled choice from a previous session', async () => {
    const { store } = stubBrowser();
    store.set('burmaldoza-sound', 'on');
    const { sound, soundEnabled } = await import('./sound');
    sound.init();
    expect(get(soundEnabled)).toBe(true);
  });
});
