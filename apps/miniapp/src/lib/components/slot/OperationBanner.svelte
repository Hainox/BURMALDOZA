<script lang="ts">
  import {base} from '$app/paths';
  import {onMount} from 'svelte';
  import {operations,multipliers,operatorForSymbol,knownOperation} from './operations';
  export let operationId = 'op1';
  export let publicState:Record<string,unknown> = {};
  let now=Date.now();
  $: operation=operations.find(op=>op.id===operationId) ?? operations[0];
  $: next=knownOperation(publicState.next_operation_id) ? operations.find(op=>op.id===publicState.next_operation_id) : null;
  $: change=typeof publicState.operation_changes_at==='string' ? Date.parse(publicState.operation_changes_at) : NaN;
  $: soon=Number.isFinite(change) && change>now && change-now<=86400000;
  onMount(()=>{const timer=setInterval(()=>now=Date.now(),60000);return()=>clearInterval(timer);});
</script>
<header class="operation" data-testid="slot-operation" data-operation-id={operation.id}><small>ОПЕРАЦИЯ</small><h3>{operation.name}</h3><span>ЗАЩИТА / АТАКА</span></header>
<div class="lineup" aria-label="Состав и множители операции">
  {#each ['D1','D2','D3','D4','A1','A2','A3','W'] as code}{@const operator=operatorForSymbol(operation.id,code)}<div class:attack={code.startsWith('A')}><img src={`${base}/slot/faces/${operator}.webp`} alt={operator ?? code} /><span>{code} ×{multipliers[code]}</span></div>{/each}
</div>
{#if soon && next}<p class="next" data-testid="slot-next-operation">Следующая операция: {next.name} · {new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(change)} МСК</p>{/if}
<style>
  .operation{display:grid;gap:8px;border-left:2px solid #9ab4c5;padding-left:12px}.operation small{font-size:8px;letter-spacing:.24em;color:#a4aeb5}.operation h3{margin:0;font:300 clamp(19px,5vw,30px)/1.25 'Arial Narrow',sans-serif;text-transform:uppercase;letter-spacing:.12em;overflow-wrap:anywhere}.operation>span{font-size:9px;letter-spacing:.2em;color:#d4e0e7}.lineup{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.lineup>div{display:grid;justify-items:center;gap:4px;padding:4px;border:1px solid #6f8b9c;background:#10171c}.lineup>div.attack{border-color:#c0a69b}.lineup img{width:100%;height:32px;object-fit:contain;filter:grayscale(1)}.lineup span{font-size:9px;color:#d3dce1;white-space:nowrap}.next{font-size:11px;line-height:1.5;color:#d8e4ea;margin:0;padding:8px;border:1px solid #a1bcc8}@media(min-width:720px){.lineup{grid-template-columns:repeat(8,minmax(0,1fr))}}
</style>
