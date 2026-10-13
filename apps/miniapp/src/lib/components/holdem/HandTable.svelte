<script lang="ts">
  import { base } from '$app/paths';
  import PlayingCard from './PlayingCard.svelte';
  import type { HoldemView } from '$lib/api/holdem';
  export let view: HoldemView;
  export let hero: {name:string;avatar:string;intro:string;title:string} | null = null;
  export let busy = false;
  export let seconds = 0;
  export let live = false;
  export let onAction: (action:string, fields?:Record<string,unknown>) => void;
  let raise = 0;
  let previousBounds = '';
  function updateBounds(minimum:number, maximum:number) {
    const bounds=`${minimum}:${maximum}`;
    if(bounds !== previousBounds) {raise=minimum;previousBounds=bounds;}
  }
  $: updateBounds(view.minimumRaise,view.maximumRaise);
  $: stamp = !view.result ? '' : view.result.winners.length === 2 ? '分' : view.result.winners.includes(view.seat) ? '勝' : '負';
  $: verdict = !view.result ? '' : view.result.winners.length === 2 ? 'Ничья' : view.result.winners.includes(view.seat) ? 'Победа' : 'Поражение';
  const names: Record<string,string> = {fold:'Пас',check:'Чек',call:'Колл',raise:'Рейз'};
  const streets: Record<string,string> = {pre_flop:'Префлоп',flop:'Флоп',turn:'Тёрн',river:'Ривер',showdown:'Шоудаун',settled:'Завершено'};
</script>
<section class="table" aria-label="Стол Hold’em" data-testid="holdem-table">
  <img class="scene" src={`${base}/holdem/scene/kamurocho-gate.webp`} alt="" />
  <div class="seat opponent">
    {#if hero}<img class="avatar" src={`${base}/holdem/${hero.avatar}`} alt="" />{:else}<span class="avatar placeholder" aria-hidden="true">♟</span>{/if}
    <div><b>{hero?.name ?? 'Живой игрок'}</b><small>Стек {view.stacks[1-view.seat]} JG</small></div>
    <div class="hand" data-testid="holdem-opponent">{#each view.opponent as card}<PlayingCard {card} />{/each}</div>
  </div>
  <div class="pot"><small>{streets[view.street] ?? view.street}</small><span>БАНК</span><strong>{view.pot} <small>JG</small></strong></div>
  <div class="board" data-testid="holdem-board">{#each Array(5) as _, i}{#if view.board[i]}<PlayingCard card={view.board[i]} />{:else}<span class="empty" aria-label="Карта борда ещё не открыта"></span>{/if}{/each}</div>
  <div class="seat own"><div><b>Ваше место</b><small>Стек {view.stacks[view.seat]} JG</small></div><div class="hand" data-testid="holdem-own">{#each view.own as card}<PlayingCard {card} />{/each}</div></div>
  {#if view.deadline && view.phase === 'active'}<div class="turn" style={`--remaining:${Math.min(1,seconds/20)}`} data-testid="holdem-timer"><b>{seconds}</b><span>{view.currentSeat === view.seat ? 'Ваш ход' : 'Ход соперника'}</span></div>{/if}
</section>
{#if view.phase === 'active'}
  <div class="actions" aria-label="Действия Hold’em">
    {#each view.legal as action}<button data-testid={`holdem-${action}`} disabled={busy || (action === 'raise' && (!Number.isInteger(raise) || raise < view.minimumRaise || raise > view.maximumRaise))} on:click={() => onAction(action, action === 'raise' ? {amount:raise} : {})}>{names[action]}{#if action === 'call'} <small>{view.call} JG</small>{/if}</button>{/each}
  </div>
  {#if view.legal.includes('raise')}<label class="raise">Рейз до <input type="number" min={view.minimumRaise} max={view.maximumRaise} step="1" bind:value={raise} disabled={busy} aria-label="Сумма рейза" /> <small>{view.minimumRaise}–{view.maximumRaise} JG</small></label>{/if}
  {#if !view.legal.length}<p role="status">Ожидаем ход соперника.</p>{/if}
{/if}
{#if view.result}<div class="result" role="status" data-testid="holdem-result"><span class="stamp" aria-hidden="true">{stamp}</span><div><h3>{verdict}</h3><p>{view.result.outcome === 'fold' ? 'Раздача завершена пасом.' : 'Карты открыты на шоудауне.'}</p><p>Возвращено {view.result.payout} JG · результат {view.result.net > 0 ? '+' : ''}{view.result.net} JG</p><small>{live ? 'Итог подтверждён сервером' : 'Демонстрационная раздача'}</small></div></div>{/if}
<style>
  .table{position:relative;isolation:isolate;display:grid;gap:18px;padding:24px 16px;overflow:hidden;border:1px solid #c9a24a;border-radius:40% / 12%;background:#100c0d;min-height:370px;box-shadow:inset 0 0 40px #000}.scene{position:absolute;z-index:-1;inset:0;width:100%;height:100%;object-fit:cover;opacity:.24;filter:grayscale(.4)}.table:before{content:'';position:absolute;inset:12px;border:1px solid #c9a24a55;border-radius:inherit;pointer-events:none}.seat{display:flex;gap:8px;align-items:center;z-index:1;min-width:0}.seat div:not(.hand){display:grid;gap:4px;min-width:0}.seat b{font-size:12px;overflow-wrap:anywhere}.seat small,.pot>small{color:#ccc3b4;font-size:11px}.avatar{width:40px;height:48px;object-fit:cover;border:1px solid #c9a24a;flex-shrink:0}.placeholder{display:grid;place-items:center;font-size:24px}.hand{display:flex;gap:4px;margin-left:auto}.pot{text-align:center;display:grid;gap:4px}.pot>span{letter-spacing:.2em;font-size:10px}.pot strong{font-size:28px;color:#e9cd84}.pot strong small{font-size:11px}.board{display:flex;justify-content:center;gap:6px}.empty{width:clamp(34px,9vw,56px);aspect-ratio:5/7;border:1px dashed #ece3cf55;border-radius:4px}.turn{display:flex;align-items:center;justify-content:center;gap:8px;font-size:12px}.turn b{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;background:radial-gradient(circle,#181212 62%,transparent 65%),conic-gradient(#c9a24a calc(var(--remaining)*360deg),#555 0)}.actions{display:flex;flex-wrap:wrap;gap:8px}.actions button{flex:1;min-height:48px;padding:8px 12px;border:1px solid #c9a24a66;background:#48141a;color:#f3ede2;font:inherit;cursor:pointer;transform:skew(-5deg)}.actions button small{display:block;font-size:10px}.actions button:disabled{opacity:.4;cursor:default}.raise{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px}.raise input{width:84px;min-height:44px;background:#ece3cf;color:#1c1716;border:1px solid #c9a24a;padding:8px;font:inherit}.result{display:flex;align-items:center;gap:16px;padding:16px;background:#ece3cf;color:#1c1716}.result h3,.result p{margin:4px 0}.result p,.result small{font-size:12px}.stamp{font:64px Georgia,serif;color:#a0111d;border:3px solid #a0111d;padding:4px;animation:stamp .3s ease-out;transform:rotate(-9deg)}button:focus-visible,input:focus-visible{outline:3px solid #fff1b8;outline-offset:3px}@keyframes stamp{from{opacity:0;transform:scale(1.8) rotate(-9deg)}to{opacity:1;transform:scale(1) rotate(-9deg)}}@media(prefers-reduced-motion:reduce){.stamp{animation:none}}
</style>
