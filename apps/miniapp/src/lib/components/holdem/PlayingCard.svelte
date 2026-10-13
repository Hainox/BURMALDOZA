<script lang="ts">
  import { base } from '$app/paths';
  import type { HoldemCard } from '$lib/api/holdem';
  export let card: HoldemCard = { hidden: true };
  const suits: Record<string, string> = {S:'♠', H:'♥', D:'♦', C:'♣'};
  $: hidden = 'hidden' in card;
  $: rank = 'rank' in card ? card.rank : '';
  $: suit = 'suit' in card ? card.suit : '';
</script>
<span class="card" class:red={suit === 'H' || suit === 'D'} class:hidden aria-label={hidden ? 'Закрытая карта' : `${rank} ${suits[suit]}`}>
  {#if hidden}<img src={`${base}/holdem/card-back.svg`} alt="" />{:else}<b>{rank}</b><span>{suits[suit]}</span>{/if}
</span>
<style>
  .card{display:grid;place-items:center;width:clamp(34px,9vw,56px);aspect-ratio:5/7;background:#ece3cf;color:#1c1716;border:1px solid #c9a24a;border-radius:4px;box-shadow:0 4px 12px #0005;animation:reveal .35s ease both;font:700 20px Georgia,serif;overflow:hidden}.card b{font-size:16px}.card.red{color:#a0111d}.card.hidden{background:#0c0204}.card img{width:100%;height:100%;object-fit:cover}.card span{line-height:1}@keyframes reveal{from{opacity:0;transform:translateY(-8px) rotateY(80deg)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.card{animation:none}}
</style>
