<script lang="ts">
  import { base } from '$app/paths';
  import type { HoldemCard } from '$lib/api/holdem';
  export let card: HoldemCard;
  export let reducedMotion = false;
  const ranks=['A','2','3','4','5','6','7','8','9','10','J','Q','K'];
  const dolls:Record<string,string[]>={S:['UMP45','Vector','Welrod MkII','C-MS','P90','Grizzly','Thompson','MP5','Five-seveN','Contender','G11','UMP9','HK416'],C:['M4A1','G36','G36C','G41','FAL','TAR-21','K2','Type 95','Type 97','RO635','M4 SOPMOD II','ST AR-15','M16A1'],H:['RPK-16','Makarov','SVD','Mosin-Nagant','Suomi','PPSh-41','PPS-43','Lee-Enfield','WA2000','Kar98k','AN-94','AK-15','AK-12'],D:['Springfield','G3','Sten MkII','M1918','Negev','M1895','P7','M99','M200','G28','M1 Garand','Hecate II','OTs-14']};
  const suits:Record<string,string>={S:'♠',C:'♣',H:'♥',D:'♦'};
  $: hidden='hidden'in card;
  $: face='rank'in card?card:null;
  $: doll=face?dolls[face.suit]?.[ranks.indexOf(face.rank)]:null;
</script>
<span class="card" class:quiet={reducedMotion} class:red={face?.suit==='D'||face?.suit==='H'} aria-label={hidden?'Закрытая карта':`${face?.rank} ${suits[face?.suit??'']}`}>
  {#if hidden}<img src={`${base}/blackjack/card-back.webp`} alt="" />{:else}{#if doll}<img src={`${base}/blackjack/portraits/${encodeURIComponent(`${doll}_S.webp`)}`} alt="" />{/if}<b>{face?.rank}<span>{suits[face?.suit??'']}</span></b>{/if}
</span>
<style>
  .card{position:relative;display:block;flex-shrink:0;width:54px;aspect-ratio:5/7;border:1px solid #d8d1c3;border-radius:7px;overflow:hidden;background:#10141d;color:#fff;animation:deal .24s ease-out both}.card img{width:100%;height:100%;object-fit:cover}.card b{position:absolute;inset:0;display:flex;flex-direction:column;align-items:flex-start;padding:3px;background:linear-gradient(90deg,#060810aa,transparent 70%);font:700 16px Georgia,serif;text-shadow:0 1px 2px #000}.card span{font-size:14px}.card.red b{color:#ff9eaf}.quiet{animation:none}@keyframes deal{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.card{animation:none}}
</style>
