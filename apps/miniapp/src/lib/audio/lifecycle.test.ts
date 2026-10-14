import { afterEach, expect, it, vi } from 'vitest';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function browser(switchDuringLoad = false) {
  vi.useFakeTimers();
  const gain = { value: 1, cancelScheduledValues: vi.fn(), setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() };
  const connect = vi.fn().mockReturnThis();
  const sources: { start: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn>; onended: (() => void) | null }[] = [];
  class Context {
    currentTime = 0;
    destination = {};
    resume = vi.fn().mockResolvedValue(undefined);
    suspend = vi.fn().mockResolvedValue(undefined);
    createDynamicsCompressor = () => ({ threshold: { value: 0 }, connect });
    createGain = () => ({ gain, connect });
    createMediaElementSource = () => ({ connect });
    decodeAudioData = async () => ({});
    createBufferSource = () => {
      const source = { start: vi.fn(), stop: vi.fn(), connect, buffer: null, onended: null as (() => void) | null };
      sources.push(source);
      return source;
    };
  }
  const player = { src: '', preload: '', addEventListener: vi.fn(), play: vi.fn().mockResolvedValue(undefined), pause: vi.fn() };
  const events = new Map<string, () => void>();
  const document = { hidden: false, addEventListener: (name: string, fn: () => void) => events.set(name, fn) };
  vi.stubGlobal('document', document);
  vi.stubGlobal('window', { AudioContext: Context, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() });
  vi.stubGlobal('Audio', class { constructor() { return player; } });
  const manifest = { music: { hub: [{ src: 'hub.m4a' }], holdem: [{ src: 'holdem.m4a' }] }, sfx: { 'ui-tap': { src: 'tap.m4a' }, 'holdem-intro': { src: 'intro.m4a', duration: 6.2 } }, voices: { Kazuma_Kiryu: { quip: ['kiryu.m4a'] } } };
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => {
    if (switchDuringLoad) sound.setScene('holdem');
    return manifest;
  }, arrayBuffer: async () => new ArrayBuffer(1) })));
  const { sound } = await import('./sound');
  sound.init();
  sound.setScene('hub');
  await sound.toggle();
  await vi.advanceTimersByTimeAsync(500);
  sources.length = 0;
  return { sound, sources, player, document, events };
}

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.resetModules(); });

it.each(['mute', 'scene', 'hide'] as const)('drops a loaded voice after %s', async (action) => {
  const { sound, sources, document, events } = await browser();
  const download = deferred<Response>();
  vi.mocked(fetch).mockReturnValueOnce(download.promise);
  sound.voice('Kazuma_Kiryu', 'quip');
  if (action === 'mute') await sound.toggle();
  if (action === 'scene') sound.setScene('holdem');
  if (action === 'hide') { document.hidden = true; events.get('visibilitychange')!(); }
  download.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) } as Response);
  await vi.advanceTimersByTimeAsync(0);
  expect(sources).toHaveLength(0);
});

it('stops an already playing voice on scene change', async () => {
  const { sound, sources } = await browser();
  sound.voice('Kazuma_Kiryu', 'quip');
  await vi.advanceTimersByTimeAsync(0);
  expect(sources).toHaveLength(1);
  sound.setScene('holdem');
  expect(sources[0].stop).toHaveBeenCalledOnce();
});

it.each(['mute', 'reduce', 'hide'] as const)('does not start a pending music transition after %s', async (action) => {
  const { sound, player, document, events } = await browser();
  player.play.mockClear();
  sound.setScene('holdem');
  if (action === 'mute') await sound.toggle();
  if (action === 'reduce') sound.setReducedMotion(true);
  if (action === 'hide') { document.hidden = true; events.get('visibilitychange')!(); }
  await vi.advanceTimersByTimeAsync(500);
  expect(player.play).not.toHaveBeenCalled();
});

it('starts the current scene when reduced motion is disabled', async () => {
  const { sound, player } = await browser();
  sound.setReducedMotion(true);
  sound.setScene('holdem');
  sound.setReducedMotion(false);
  await vi.advanceTimersByTimeAsync(500);
  expect(player.src).toBe('/audio/holdem.m4a');
});

it('starts the current scene if it changes while the manifest loads', async () => {
  const { player } = await browser(true);
  expect(player.src).toBe('/audio/holdem.m4a');
});

it('cancels a pending voice within the same scene when the hand ends', async () => {
  const { sound, sources } = await browser();
  const download = deferred<Response>();
  vi.mocked(fetch).mockReturnValueOnce(download.promise);
  sound.voice('Kazuma_Kiryu', 'quip');
  sound.stopEffects();
  download.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) } as Response);
  await vi.advanceTimersByTimeAsync(0);
  expect(sources).toHaveLength(0);
});

it('cancels a deferred callback on disposal or scene change', async () => {
  const { sound } = await browser();
  const callback = vi.fn();
  const cancel = sound.defer(700, callback);
  cancel();
  sound.defer(700, callback);
  sound.setScene('holdem');
  await vi.advanceTimersByTimeAsync(1000);
  expect(callback).not.toHaveBeenCalled();
});

it('waits for the actual intro ending even when downloading is slow', async () => {
  const { sound, sources } = await browser();
  sound.setScene('holdem');
  const download = deferred<Response>();
  vi.mocked(fetch).mockReturnValueOnce(download.promise);
  const voice = vi.fn();
  sound.cue('intro', voice);
  await vi.advanceTimersByTimeAsync(10000);
  expect(voice).not.toHaveBeenCalled();
  download.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) } as Response);
  await vi.advanceTimersByTimeAsync(0);
  expect(sources).toHaveLength(1);
  expect(voice).not.toHaveBeenCalled();
  sources[0].onended?.();
  expect(voice).toHaveBeenCalledOnce();
});

it('does not run the intro ending callback after disposal', async () => {
  const { sound, sources } = await browser();
  sound.setScene('holdem');
  const voice = vi.fn();
  const cancel = sound.cue('intro', voice);
  await vi.advanceTimersByTimeAsync(0);
  cancel();
  expect(sources[0].stop).toHaveBeenCalledOnce();
  sources[0].onended?.();
  expect(voice).not.toHaveBeenCalled();
});

it('does not start an intro cancelled before downloading finishes', async () => {
  const { sound, sources } = await browser();
  sound.setScene('holdem');
  const download = deferred<Response>();
  vi.mocked(fetch).mockReturnValueOnce(download.promise);
  const cancel = sound.cue('intro');
  cancel();
  download.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) } as Response);
  await vi.advanceTimersByTimeAsync(0);
  expect(sources).toHaveLength(0);
});
