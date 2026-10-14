<script lang="ts">
  import { base } from '$app/paths';
  import type { HoldemCard } from '$lib/api/holdem';
  export let card: HoldemCard = { hidden: true };
  export let delay = 0;
  let wasHidden = false;
  let flipped = false;
  $: trackHidden(hidden);
  function trackHidden(next: boolean) {
    flipped = wasHidden && !next;
    wasHidden = next;
  }
  const suits: Record<string, string> = {S:'♠', H:'♥', D:'♦', C:'♣'};
  $: hidden = 'hidden' in card;
  $: rank = 'rank' in card ? card.rank : '';
  $: suit = 'suit' in card ? card.suit : '';
</script>
<span class="card" class:flipped class:red={suit === 'H' || suit === 'D'} class:hidden style={`--deal-delay:${delay}ms`} aria-label={hidden ? 'Закрытая карта' : `${rank} ${suits[suit]}`}>
  <span class="front">{#if !hidden}<b>{rank}</b><span>{suits[suit]}</span>{/if}</span>
  <img class="back" src={`${base}/holdem/card-back.svg`} alt="" aria-hidden="true" />
</span>
<style>
  .card{display:grid;place-items:center;width:clamp(34px,9vw,56px);aspect-ratio:5/7;background:#ece3cf;color:#1c1716;border:1px solid #c9a24a;border-radius:4px;box-shadow:0 4px 12px #0005;animation:reveal .35s ease both;font:700 20px Georgia,serif;overflow:hidden}.card b{font-size:16px}.card.red{color:#a0111d}.card.hidden{background:#0c0204}.card img{width:100%;height:100%;object-fit:cover}.card span{line-height:1}@keyframes reveal{from{opacity:0;transform:translateY(-8px) rotateY(80deg)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.card{animation:none}}

  .card { animation-delay: var(--deal-delay); }
  .card.flipped { animation: opponentFlip 560ms ease var(--deal-delay) both; }
  .card { position: relative; transform-style: preserve-3d; overflow: visible; background: transparent; }
  .card.hidden { background: transparent; }
  .front, .card .back { position: absolute; inset: 0; width: 100%; height: 100%; border-radius: inherit; backface-visibility: hidden; }
  .front { display: grid; place-items: center; background: #ece3cf; }
  .card .back { transform: rotateY(180deg); }
  .card.hidden .back { transform: none; }
  .card.hidden .front { visibility: hidden; }
  @keyframes opponentFlip { from { transform: rotateY(-180deg); } to { transform: rotateY(0); } }

  @media(prefers-reduced-motion:reduce) { .card, .card.flipped { animation: none; } }
</style>
