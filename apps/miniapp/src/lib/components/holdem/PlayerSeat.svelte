<script lang="ts">
  import { base } from '$app/paths';
  import PlayingCard from './PlayingCard.svelte';
  import type { HoldemTablePlayer } from '$lib/api/holdem-table';
  export let player: HoldemTablePlayer;
  export let own = false;
  export let active = false;
  export let marker = '';
  export let reducedMotion = false;
  export let avatarUrl = '';
</script>
<article class="seat" class:own class:active class:folded={player.folded} class:quiet={reducedMotion} data-testid={`holdem-seat-${player.seat}`} aria-label={`Место ${player.seat+1}${own?' · Вы':''}`}>
  <div class="identity">
    <span class="avatar">{#if avatarUrl}<img src={avatarUrl} alt="Аватар игрока" />{:else}<img src={`${base}/icons/table-users.svg`} alt="" />{/if}</span>
    <div><b>{own?'Вы':player.nickname}</b><small>Место {player.seat+1}{marker?` · ${marker}`:''}</small></div>
    <strong>{player.stack.toLocaleString('ru')} <small>JG</small></strong>
  </div>
  <div class="hand" data-testid={own?'holdem-own':`holdem-opponent-${player.seat}`}>
    {#each player.cards as card,i}<PlayingCard {card} delay={reducedMotion?0:i*70} />{/each}
    <span class="status">{player.folded?'Пас':player.allIn?'Ва-банк':active?'Ходит':`Внесено ${player.committed} JG`}</span>
  </div>
</article>
<style>
  .seat{min-width:0;padding:10px;border:1px solid #c9a24a55;border-radius:14px;background:#170d12e8;transition:border-color .2s,background .2s}.identity{display:flex;align-items:center;gap:8px;min-width:0}.identity>div{display:grid;min-width:0;flex:1;gap:3px}.identity b{font-size:12px;overflow-wrap:anywhere}.identity small,.status{font-size:10px;color:#cebdad}.identity strong{font-size:12px;white-space:nowrap}.avatar{display:grid;place-items:center;width:30px;height:30px;flex-shrink:0;border:1px solid #c9a24a88;border-radius:50%;overflow:hidden}.avatar img{width:20px;height:20px;filter:invert(1);object-fit:cover}.avatar img[alt="Аватар игрока"]{filter:none;width:100%;height:100%}.hand{display:flex;align-items:center;gap:5px;margin-top:8px}.hand :global(.card){width:30px;font-size:16px}.status{margin-left:auto;text-align:right}.active{border-color:#ffe3a2;background:#452126;box-shadow:0 0 0 1px #ffe3a255}.own{border-color:#c9a24aaa}.own .hand :global(.card){width:42px}.folded{opacity:.58}.quiet{transition:none}.quiet :global(.card){animation:none!important}@media(prefers-reduced-motion:reduce){.seat{transition:none}}
</style>
