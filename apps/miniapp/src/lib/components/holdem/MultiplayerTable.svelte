<script lang="ts">
  import { base } from '$app/paths';
  import BetPicker from '$lib/components/BetPicker.svelte';
  import PlayerSeat from './PlayerSeat.svelte';
  import PlayingCard from './PlayingCard.svelte';
  import { payableHoldemCall, type HoldemTableView } from '$lib/api/holdem-table';
  export let view: HoldemTableView;
  export let busy = false;
  export let seconds = 0;
  export let reducedMotion = false;
  export let avatars: Record<number, string> = {};
  export let onAction: (name: string, fields?: Record<string, unknown>) => void;
  let raise = 0;
  let bounds = '';
  $: updateBounds(view.minimumRaise,view.maximumRaise);
  function updateBounds(min: number | null, max: number) {
    const key = `${min}:${max}`;
    if (bounds !== key) { raise = min === null ? 0 : Math.min(min,max); bounds = key; }
  }
  const names: Record<string,string> = {fold:'Пас',check:'Чек',call:'Колл',raise:'Рейз'};
  const streets: Record<string,string> = {pre_flop:'Префлоп',flop:'Флоп',turn:'Тёрн',river:'Ривер',showdown:'Шоудаун',settled:'Завершено'};
  function marker(seat: number) { return [seat===view.buttonSeat?'D':null,seat===view.smallBlindSeat?'SB':null,seat===view.bigBlindSeat?'BB':null].filter(Boolean).join(' / '); }
  $: own = view.players.find(player => player.seat === view.viewerSeat);
  $: call = payableHoldemCall(view);
  $: shortAllIn = view.minimumRaise !== null && view.maximumRaise < view.minimumRaise;
  $: validRaise = Number.isSafeInteger(raise) && raise <= view.maximumRaise && (shortAllIn ? raise === view.maximumRaise : raise >= (view.minimumRaise ?? Infinity));
</script>
<section class="multiplayer" class:quiet={reducedMotion} data-testid="holdem-multiplayer" aria-label="Общий стол Hold’em на шесть мест">
  <div class="table-heading"><span><img src={`${base}/icons/table-users.svg`} alt="" />{view.players.length} / 6 игроков</span><small>{streets[view.street]??view.street}</small></div>
  <div class="opponents">{#each view.players.filter(player=>player.seat!==view.viewerSeat) as player(player.seat)}<PlayerSeat {player} active={view.phase==='active'&&view.currentSeat===player.seat} marker={marker(player.seat)} {reducedMotion} avatarUrl={avatars[player.seat]??''} />{/each}</div>
  <div class="centre"><img class="scene" src={`${base}/holdem/scene/room.webp`} alt="" /><span class="pot-label">Общий банк</span><strong data-testid="holdem-pot">{view.pot.toLocaleString('ru')} <small>JG</small></strong><div class="board" data-testid="holdem-board">{#each view.board as card,i}<PlayingCard {card} delay={reducedMotion?0:i*80} />{/each}{#if !view.board.length}<p>{view.phase==='settled'?'Раздача завершена до открытия борда':'Ожидаем флоп'}</p>{/if}</div></div>
  {#if own}<PlayerSeat player={{...own,cards:view.own}} own active={view.phase==='active'&&view.currentSeat===view.viewerSeat} marker={marker(view.viewerSeat)} {reducedMotion} />{/if}
  {#if view.deadline&&view.phase==='active'}<p class="timer" role="status" data-testid="holdem-timer"><img src={`${base}/icons/table-timer.svg`} alt="" /><b>{seconds} с</b> · {view.currentSeat===view.viewerSeat?'Ваш ход':`Ход места ${(view.currentSeat??0)+1}`}</p>{/if}
</section>
{#if view.phase==='active'}
  <div class="actions" aria-label="Действия Hold’em">{#each view.legal.filter(action=>action!=='cancel') as name}<button data-testid={`holdem-${name}`} disabled={busy||(name==='raise'&&!validRaise)} on:click={()=>onAction(name,name==='raise'?{amount:raise}:{})}>{name==='raise'&&shortAllIn?'Ва-банк':name==='call'&&call.allIn?'Колл · ва-банк':names[name]}{#if name==='call'}<small>{call.amount} JG</small>{/if}</button>{/each}</div>
  {#if view.legal.includes('raise')}{#if shortAllIn}<p class="hint">Короткий ва-банк: {view.maximumRaise} JG. Полный рейз недоступен.</p>{:else}<div class="raise"><BetPicker bind:value={raise} min={view.minimumRaise??0} max={view.maximumRaise} presets={[{label:'Минимум',value:view.minimumRaise??0},{label:'Ва-банк',value:view.maximumRaise}]} disabled={busy} inputId="holdem-table-raise" inputLabel="Сумма рейза" label="Рейз до" /></div>{/if}{/if}
  {#if !view.legal.length}<p class="hint" role="status">Ожидаем ход другого игрока.</p>{/if}
{/if}
{#if view.result}<section class="result" data-testid="holdem-result" role="status"><h3>{view.result.netDeltas[String(view.viewerSeat)]>0?'Победа':view.result.netDeltas[String(view.viewerSeat)]<0?'Поражение':'Без изменения баланса'}</h3><p>Ваш результат: <b>{view.result.netDeltas[String(view.viewerSeat)]>0?'+':''}{view.result.netDeltas[String(view.viewerSeat)]} JG</b></p><p>Возвращено на баланс: {view.result.cashouts[String(view.viewerSeat)]} JG</p>{#each view.result.pots as pot,i}<p>{i===0?'Основной банк':`Побочный банк ${i}`}: {pot.amount} JG · {pot.winners.map(seat=>seat===view.viewerSeat?'Вы':`место ${seat+1}`).join(', ')}</p>{/each}{#if view.result.refunds[String(view.viewerSeat)]}<p>Непокрытая ставка возвращена: {view.result.refunds[String(view.viewerSeat)]} JG</p>{/if}<small>Итог подтверждён сервером</small></section>{/if}
<style>
  .multiplayer{display:grid;gap:10px;padding:12px;border:1px solid #c9a24a88;border-radius:20px;background:#160e12}.table-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;color:#e9cd84}.table-heading>span,.timer{display:flex;align-items:center;gap:7px}.table-heading img,.timer img{width:19px;height:19px;filter:invert(1)}.opponents{display:grid;gap:8px;grid-template-columns:repeat(2,minmax(0,1fr))}.centre{position:relative;isolation:isolate;overflow:hidden;display:grid;justify-items:center;gap:8px;padding:20px 8px;border-radius:18px;background:#2a131d}.scene{position:absolute;inset:0;z-index:-1;width:100%;height:100%;object-fit:cover;opacity:.15}.centre>strong{font:30px Georgia,serif;color:#efcd83}.centre strong small,.pot-label{font-size:11px}.pot-label{letter-spacing:.12em}.board{display:flex;gap:5px;min-height:60px;align-items:center}.board p,.hint{font-size:12px;color:#d8c8b6}.timer{justify-content:center;font-size:12px;margin:3px 0}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.actions button{flex:1;min-height:48px;padding:8px;border:1px solid #e9cd8499;border-radius:12px;background:linear-gradient(#741a27,#300d16);color:#f3ede2;font:inherit;cursor:pointer;transition:transform .18s}.actions button:active{transform:scale(.97)}.actions button small{display:block;font-size:10px}.actions button:disabled{opacity:.4}.actions button:focus-visible{outline:3px solid #fff1b8;outline-offset:3px}.raise{margin-top:10px;padding:10px;border:1px solid #c9a24a55;border-radius:12px;--bet-accent:#e2c06b;--bet-line:#c9a24a88;--bet-ink:#f3ede2}.result{margin-top:12px;padding:16px;border-radius:16px;background:#e9dbb9;color:#251519}.result h3{margin:0 0 8px}.result p,.result small{font-size:12px;line-height:1.5}.quiet :global(.card){animation:none!important}@media(max-width:390px){.opponents{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){.actions button{transition:none}}
</style>
