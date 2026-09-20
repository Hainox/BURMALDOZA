<script lang="ts">
  import type { MotionState } from '$lib/game/motion';
  import ResultBand from '$lib/components/ResultBand.svelte';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let motion: MotionState = 'idle';
  export let result: RoomResult | null = null;
  export let onAction: (action: string) => void = () => undefined;
  const community = ['A♣', '7♦', 'Q♠', '—', '—'];
</script>

<div class="game-room poker-room">
  <div class="room-intro"><div><span class="room-kicker">HEADS-UP · RGG SKELETON</span><h2>Hold’em</h2><p>Один pot, два места, только подтверждённые действия.</p></div><span class="bet-chip">100 JG</span></div>
  <section class="poker-table" class:resolving={motion === 'resolving'} aria-label="Heads-up poker table">
    <div class="poker-rail"></div><div class="player opponent"><span class="avatar">♟</span><span><b>DEALER</b><small>stack 250</small></span><i>2 cards</i></div><div class="pot">POT <strong>100</strong> <small>JG</small></div>
    <div class="community-cards">{#each community as card, index}<span class:revealed={card !== '—'} style={`--card-delay: ${index * 100}ms`}>{card}</span>{/each}</div>
    <div class="player hero"><span class="avatar">✦</span><span><b>YOU</b><small>stack 150</small></span><i>BTN</i></div>
  </section>
  <div class="action-grid"><button on:click={() => onAction('fold')} disabled={motion === 'resolving'}>FOLD</button><button on:click={() => onAction('check')} disabled={motion === 'resolving'}>CHECK</button><button class="action-primary" on:click={() => onAction('call')} disabled={motion === 'resolving'}>CALL <small>25 JG</small></button><button on:click={() => onAction('raise')} disabled={motion === 'resolving'}>RAISE</button></div>
  <ResultBand {result} {motion} />
</div>

<style>
  .game-room { position: relative; z-index: 1; display: grid; gap: 18px; } .room-intro { display: flex; justify-content: space-between; gap: 18px; } .room-kicker { color: #ce86f2; font-size: 9px; font-weight: 800; letter-spacing: 0.13em; } h2 { margin: 6px 0 5px; font-size: clamp(27px, 8vw, 38px); letter-spacing: -0.06em; } p { max-width: 250px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; } .bet-chip { height: fit-content; padding: 7px 9px; border: 1px solid rgb(206 134 242 / 35%); border-radius: 999px; color: #e0a8ff; font-size: 10px; font-weight: 800; white-space: nowrap; }
  .poker-table { position: relative; display: grid; align-content: space-between; justify-items: center; min-height: 368px; overflow: hidden; padding: 28px 20px; border: 1px solid rgb(206 134 242 / 34%); border-radius: 48% / 22%; background: radial-gradient(ellipse at center, #3c1f53, #1b162d 72%); box-shadow: inset 0 0 44px rgb(0 0 0 / 42%), 0 18px 42px rgb(0 0 0 / 25%); } .poker-rail { position: absolute; inset: 14px; border: 1px solid rgb(206 134 242 / 14%); border-radius: 48% / 22%; } .player { position: relative; z-index: 1; display: flex; align-items: center; gap: 9px; width: 100%; color: var(--ivory); } .player.opponent { justify-content: flex-start; } .player.hero { justify-content: flex-end; } .avatar { display: grid; place-items: center; width: 34px; height: 34px; border: 1px solid rgb(206 134 242 / 45%); border-radius: 50%; background: rgb(206 134 242 / 15%); color: #e0a8ff; } .player span:not(.avatar) { display: grid; gap: 2px; } .player b { font-size: 10px; letter-spacing: 0.1em; } .player small, .player i { color: var(--muted); font-size: 9px; font-style: normal; } .player i { margin-left: auto; } .hero i { margin-right: auto; margin-left: 0; color: #e0a8ff; } .pot { position: relative; z-index: 1; display: grid; justify-items: center; color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: 0.15em; } .pot strong { color: var(--brass-300); font-size: 30px; letter-spacing: -0.08em; } .pot small { color: var(--brass-300); font-size: 9px; letter-spacing: 0.08em; } .community-cards { position: relative; z-index: 1; display: flex; gap: 5px; } .community-cards span { display: grid; place-items: center; width: 43px; height: 58px; border: 1px solid rgb(255 247 237 / 16%); border-radius: 7px; background: rgb(255 247 237 / 6%); color: var(--muted); font-size: 14px; font-weight: 800; } .community-cards span.revealed { border-color: rgb(231 187 112 / 45%); background: #fff8ee; color: #3b2430; animation: revealCard 420ms cubic-bezier(.2, .8, .2, 1) var(--card-delay) both; } .action-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; } .action-grid button { min-height: 52px; border: 1px solid var(--line); border-radius: 13px; background: rgb(255 247 237 / 6%); color: var(--ivory); font: inherit; font-size: 10px; font-weight: 850; cursor: pointer; transition: border-color 160ms ease, transform 160ms ease; } .action-grid button:hover { border-color: rgb(206 134 242 / 65%); transform: translateY(-2px); } .action-grid button:disabled { opacity: 0.48; cursor: wait; } .action-grid .action-primary { border-color: rgb(206 134 242 / 55%); background: rgb(206 134 242 / 13%); color: #e0a8ff; } .action-grid small { display: block; margin-top: 3px; color: var(--muted); font-size: 8px; font-weight: 500; }
  @keyframes revealCard { from { opacity: 0; transform: translateY(-16px) rotateY(90deg); } to { opacity: 1; transform: rotateY(0); } }
</style>
