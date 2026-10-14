// Звук и вибрация Mini App (docs/Sound-Design.md).
// Музыка и сэмплы — из пакета владельца, который лежит только на сервере (/audio/manifest.json);
// нет пакета (демо на Pages) — остаются синтезированные короткие сигналы и вибрация.
// Звук по умолчанию выключен, вибрация включена. Исход звучит только после подтверждения —
// события вызывают те же места, что запускают подтверждённую анимацию.
import { writable } from 'svelte/store';
import { getTelegramWebApp } from '$lib/telegram/webapp';

export type Scene = 'hub' | 'slot' | 'blackjack' | 'holdem';
export type Cue =
  | 'tap' | 'confirm' | 'intro' | 'card' | 'flip' | 'chip' | 'spin' | 'reel-stop' | 'stamp'
  | 'return' | 'win-small' | 'win' | 'win-big' | 'lose';
export type VoiceGroup = 'greet' | 'dealer_win' | 'dealer_lose';

type Track = { src: string; title: string; duration: number };
type Manifest = {
  music: Partial<Record<Scene, Track[]>>;
  sfx: Record<string, { src: string }>;
  voices: Record<string, Partial<Record<VoiceGroup, string[]>>>;
};

const STORAGE_KEY = 'burmaldoza-sound';
const AUDIO_ROOT = '/audio/';
const MUSIC_LEVEL = 0.35;
const SFX_LEVEL = 0.8;

function storedEnabled(): boolean {
  try { return localStorage.getItem(STORAGE_KEY) === 'on'; } catch { return false; }
}

export const soundEnabled = writable(false);

class SoundEngine {
  private ctx: AudioContext | null = null;
  private musicGain: GainNode | null = null;
  private sfxGain: GainNode | null = null;
  private player: HTMLAudioElement | null = null;
  private manifest: Manifest | null = null;
  private manifestLoad: Promise<Manifest | null> | null = null;
  private buffers = new Map<string, Promise<AudioBuffer | null>>();
  private scene: Scene | null = null;
  private trackIndex = 0;
  private enabled = false;
  private reduced = false;
  private started = false;

  /** Восстанавливает выбор игрока; контекст звука создаётся только по касанию (правило iOS/Android). */
  init() {
    if (this.started || typeof window === 'undefined') return;
    this.started = true;
    this.enabled = storedEnabled();
    soundEnabled.set(this.enabled);
    if (this.enabled) {
      const unlock = () => { void this.wake(); window.removeEventListener('pointerdown', unlock); };
      window.addEventListener('pointerdown', unlock);
    }
    document.addEventListener('visibilitychange', () => {
      // Свернули Mini App — музыка и эффекты замолкают, вернули — продолжают.
      if (!this.ctx) return;
      if (document.hidden) { void this.ctx.suspend(); this.player?.pause(); }
      else if (this.enabled) { void this.ctx.resume(); this.resumeMusic(); }
    });
  }

  /** Переключатель в шапке: вызывать из обработчика нажатия. */
  async toggle() {
    this.enabled = !this.enabled;
    soundEnabled.set(this.enabled);
    try { localStorage.setItem(STORAGE_KEY, this.enabled ? 'on' : 'off'); } catch { /* приватный режим — только на сессию */ }
    if (this.enabled) { await this.wake(); this.cue('tap'); }
    else { this.player?.pause(); void this.ctx?.suspend(); }
  }

  setReducedMotion(reduced: boolean) {
    // «Уменьшить движение» убирает фоновые петли, короткие сигналы остаются.
    this.reduced = reduced;
    if (reduced) this.player?.pause(); else this.resumeMusic();
  }

  setScene(scene: Scene | null) {
    if (scene === this.scene) return;
    this.scene = scene;
    this.trackIndex = Math.floor(Math.random() * 8);
    void this.playSceneMusic();
  }

  /** Событие игры: вибрация всегда (если Telegram её поддерживает), звук — если включён. */
  cue(name: Cue) {
    this.vibrate(name);
    if (!this.enabled || !this.ctx || !this.sfxGain) return;
    const sample = this.sampleFor(name);
    if (sample) { void this.playSample(sample); return; }
    this.synth(name);
  }

  voice(doll: string, group: VoiceGroup) {
    if (!this.enabled || !this.ctx) return;
    const clips = this.manifest?.voices[doll]?.[group];
    if (!clips?.length) return;
    void this.playSample(clips[Math.floor(Math.random() * clips.length)]);
  }

  private async wake() {
    if (typeof window === 'undefined') return;
    if (!this.ctx) {
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      this.ctx = new Ctx();
      const limiter = this.ctx.createDynamicsCompressor();
      limiter.threshold.value = -10;
      limiter.connect(this.ctx.destination);
      this.musicGain = this.ctx.createGain();
      this.musicGain.gain.value = 0;
      this.musicGain.connect(limiter);
      this.sfxGain = this.ctx.createGain();
      this.sfxGain.gain.value = SFX_LEVEL;
      this.sfxGain.connect(limiter);
    }
    await this.ctx.resume().catch(() => undefined);
    await this.loadManifest();
    void this.playSceneMusic();
  }

  private loadManifest(): Promise<Manifest | null> {
    this.manifestLoad ??= fetch(`${AUDIO_ROOT}manifest.json`, { cache: 'no-cache' })
      .then((response) => (response.ok ? (response.json() as Promise<Manifest>) : null))
      .catch(() => null)
      .then((manifest) => {
        this.manifest = manifest;
        if (!manifest) console.info('[sound] пакет звуков недоступен — только синтез и вибрация');
        return manifest;
      });
    return this.manifestLoad;
  }

  private ensurePlayer(): HTMLAudioElement | null {
    if (this.player || !this.ctx || !this.musicGain) return this.player;
    const player = new Audio();
    player.preload = 'auto';
    player.addEventListener('ended', () => { this.trackIndex += 1; void this.playSceneMusic(); });
    // Громкость через Web Audio: у HTMLAudioElement на iOS свойство volume не работает.
    this.ctx.createMediaElementSource(player).connect(this.musicGain);
    this.player = player;
    return player;
  }

  private async playSceneMusic() {
    if (!this.enabled || this.reduced || !this.ctx || !this.musicGain || !this.scene) {
      this.fadeMusic(0);
      return;
    }
    const tracks = this.manifest?.music[this.scene];
    const player = this.ensurePlayer();
    if (!tracks?.length || !player) { this.fadeMusic(0); return; }
    const next = AUDIO_ROOT + tracks[this.trackIndex % tracks.length].src;
    this.fadeMusic(0, 0.4);
    await new Promise((resolve) => setTimeout(resolve, 420));
    if (!player.src.endsWith(next)) player.src = next;
    try {
      await player.play();
      this.fadeMusic(MUSIC_LEVEL, 1.2);
    } catch (error) {
      console.info('[sound] музыка не запустилась', error);
    }
  }

  private resumeMusic() {
    if (!this.enabled || this.reduced || !this.player?.src) return;
    void this.player.play().then(() => this.fadeMusic(MUSIC_LEVEL, 0.8)).catch(() => undefined);
  }

  private fadeMusic(target: number, seconds = 0.3) {
    if (!this.ctx || !this.musicGain) return;
    const gain = this.musicGain.gain;
    gain.cancelScheduledValues(this.ctx.currentTime);
    gain.setValueAtTime(gain.value, this.ctx.currentTime);
    gain.linearRampToValueAtTime(target, this.ctx.currentTime + seconds);
  }

  private sampleFor(name: Cue): string | null {
    if (!this.manifest) return null;
    // Нажатия и подтверждения — звуки интерфейса GFL во всех сценах.
    if (name === 'tap' || name === 'confirm') return this.manifest.sfx[name === 'tap' ? 'ui-tap' : 'ui-confirm']?.src ?? null;
    // Заставка «новая глава» Yakuza — представление соперника в Hold'em.
    if (name === 'intro') return this.scene === 'holdem' ? this.manifest.sfx['holdem-intro']?.src ?? null : null;
    // Сэмплы R6 — только в слоте; остальное синтезируется.
    if (this.scene !== 'slot') return null;
    const key = name === 'spin' ? 'slot-spin' : name === 'win' ? 'slot-win' : name === 'win-big' ? 'slot-big-win' : null;
    return key ? this.manifest.sfx[key]?.src ?? null : null;
  }

  private async playSample(src: string) {
    if (!this.ctx || !this.sfxGain) return;
    let pending = this.buffers.get(src);
    if (!pending) {
      const ctx = this.ctx;
      pending = fetch(AUDIO_ROOT + src)
        .then((response) => (response.ok ? response.arrayBuffer() : Promise.reject(new Error(String(response.status)))))
        .then((data) => ctx.decodeAudioData(data))
        .catch((error) => { console.info('[sound] не загрузился', src, error); return null; });
      this.buffers.set(src, pending);
    }
    const buffer = await pending;
    if (!buffer || !this.ctx || !this.sfxGain) return;
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.sfxGain);
    source.start();
  }

  // --- Синтез коротких сигналов: 0 КБ файлов, работает и в демо. ---
  private tone(freq: number, start: number, length: number, level: number, type: OscillatorType = 'sine', endFreq?: number) {
    const ctx = this.ctx!;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const t = ctx.currentTime + start;
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    if (endFreq) osc.frequency.exponentialRampToValueAtTime(endFreq, t + length);
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(level, t + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + length);
    osc.connect(gain).connect(this.sfxGain!);
    osc.start(t);
    osc.stop(t + length + 0.02);
  }

  private noise(start: number, length: number, level: number, filterFreq: number, type: BiquadFilterType = 'bandpass') {
    const ctx = this.ctx!;
    const frames = Math.max(1, Math.floor(ctx.sampleRate * length));
    const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < frames; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / frames);
    const source = ctx.createBufferSource();
    const filter = ctx.createBiquadFilter();
    const gain = ctx.createGain();
    source.buffer = buffer;
    filter.type = type;
    filter.frequency.value = filterFreq;
    gain.gain.value = level;
    source.connect(filter).connect(gain).connect(this.sfxGain!);
    source.start(ctx.currentTime + start);
  }

  private synth(name: Cue) {
    switch (name) {
      case 'tap': this.tone(880, 0, 0.04, 0.12); break;
      case 'confirm': this.tone(988, 0, 0.06, 0.14, 'triangle'); this.tone(1319, 0.06, 0.09, 0.14, 'triangle'); break;
      case 'card': this.noise(0, 0.07, 0.5, 2600); break;
      case 'flip': this.noise(0, 0.05, 0.35, 1800); this.noise(0.06, 0.06, 0.45, 3200); break;
      case 'chip': this.tone(2400, 0, 0.03, 0.18, 'triangle'); this.tone(3100, 0.045, 0.03, 0.14, 'triangle'); break;
      case 'spin': this.noise(0, 0.25, 0.25, 900, 'lowpass'); break;
      case 'reel-stop': this.tone(140, 0, 0.09, 0.4, 'sine', 70); this.noise(0, 0.03, 0.3, 1200); break;
      case 'intro': this.tone(110, 0, 0.35, 0.6, 'sine', 55); this.tone(110, 0.32, 0.5, 0.7, 'sine', 50); this.noise(0.32, 0.12, 0.4, 500, 'lowpass'); break;
      case 'stamp': this.tone(90, 0, 0.22, 0.6, 'sine', 45); this.noise(0, 0.08, 0.5, 700, 'lowpass'); break;
      case 'return': this.tone(660, 0, 0.18, 0.14, 'triangle'); break;
      case 'win-small': [784, 988, 1175].forEach((f, i) => this.tone(f, i * 0.07, 0.18, 0.16, 'triangle')); break;
      case 'win': [659, 784, 988, 1319].forEach((f, i) => this.tone(f, i * 0.08, 0.26, 0.2, 'triangle')); break;
      case 'win-big': [523, 659, 784, 1047, 1319, 1568].forEach((f, i) => this.tone(f, i * 0.09, 0.4, 0.22, 'triangle')); break;
      case 'lose': this.tone(330, 0, 0.16, 0.08, 'sine', 300); break;
    }
  }

  private vibrate(name: Cue) {
    const haptic = getTelegramWebApp().haptic;
    if (!haptic) return;
    if (name === 'tap') haptic('selection');
    else if (name === 'confirm') haptic('impact', 'light');
    else if (name === 'card' || name === 'chip' || name === 'reel-stop' || name === 'flip') haptic('impact', 'light');
    else if (name === 'stamp' || name === 'spin' || name === 'intro') haptic('impact', 'medium');
    else if (name === 'win' || name === 'win-big' || name === 'win-small') haptic('notification', 'success');
  }
}

export const sound = new SoundEngine();
