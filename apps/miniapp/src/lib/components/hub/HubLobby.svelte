<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { fade } from 'svelte/transition';
  import SoundToggle from '$lib/components/SoundToggle.svelte';
  import { sound } from '$lib/audio/sound';
  import type { GameType } from '$lib/state/room.svelte';
  import type { ConnectionStatus } from '$lib/state/session.svelte';

  export let balance = 0;
  export let balanceReady = false;
  export let currencyCode = 'JOKERGEM';
  export let connection: ConnectionStatus = 'demo';
  export let live = false;
  export let busy = false;
  export let apiError: string | null = null;
  export let reducedMotion = false;
  export let paused = false;
  export let activity: GameType = 'slot';
  export let panel: 'play' | 'ranking' | 'history' = 'play';
  export let onOpen: (game: GameType) => void | Promise<void>;
  let visible = true;

  const activities: Array<{game:GameType;name:string;subtitle:string;art:string}> = [
    {game:'slot',name:'Tachanka’s Luck',subtitle:'Быстрый раунд',art:'slot-portal.webp'},
    {game:'blackjack',name:'Blackjack',subtitle:'Girls’ Frontline',art:'blackjack-portal.webp'},
    {game:'holdem',name:'Hold’em',subtitle:'Kamurocho 神室町 · Два игрока',art:'holdem-portal.webp'}
  ];
  const navigation = [
    {id:'play' as const,label:'Играть',icon:'cards'},
    {id:'ranking' as const,label:'Рейтинг',icon:'trophy'},
    {id:'history' as const,label:'История',icon:'history'}
  ];
  const status: Record<ConnectionStatus,string> = {
    demo:'DEMO',connecting:'Подключаемся',connected:'LIVE',syncing:'Синхронизация',offline:'Нет связи'
  };
  $: quiet = reducedMotion || paused;
  $: chosen = activities.find(item => item.game === activity)!;
  function navigate(next: typeof panel) {
    panel = next;
    document.getElementById('hub-main')?.scrollIntoView({block:'start',behavior:quiet ? 'auto' : 'smooth'});
  }
  onMount(() => {
    const update = () => {visible = document.visibilityState !== 'hidden';};
    update(); document.addEventListener('visibilitychange',update);
    return () => document.removeEventListener('visibilitychange',update);
  });
</script>

<main class="hub" class:quiet class:background-paused={!visible || quiet} data-testid="dashboard" data-motion-paused={quiet}>
  <div class="backdrop" aria-hidden="true"><img src={`${base}/hub/atrium.webp`} alt="" width="1400" height="1994" /></div>
  <div class="backdrop-shade" aria-hidden="true"></div>
  <header class="masthead">
    <a class="brand" href="https://t.me/Burmaldoza_bot" target="_blank" rel="noreferrer" aria-label="Бурмалдоза в Telegram">
      <img src={`${base}/hub/brand-cat.webp`} width="44" height="44" alt="" />
      <span><strong>BURMALDOZA</strong><small>AFTER-HOURS CLUB</small></span>
    </a>
    <div class="balance" data-testid="balance-pill" aria-label={`Баланс ${balanceReady ? balance : 'загружается'} ${currencyCode}`}>
      <img src={`${base}/hub/icons/diamond.svg`} width="22" height="22" alt="" />
      <span><small>Баланс · {status[connection]}</small><strong>{balanceReady ? balance.toLocaleString('ru-RU') : '—'} <span>{currencyCode === 'JOKERGEM' ? 'JG' : currencyCode}</span></strong></span>
    </div>
    <SoundToggle />
    <button class="motion-toggle" type="button" on:click={() => paused=!paused} disabled={reducedMotion} aria-pressed={paused || reducedMotion} aria-label={reducedMotion ? 'Анимация отключена настройками устройства' : paused ? 'Включить анимацию' : 'Остановить анимацию'} title={paused || reducedMotion ? 'Декоративная анимация выключена' : 'Остановить декоративную анимацию'} data-testid="hub-motion-toggle">
      <img src={`${base}/hub/icons/settings-pause.svg`} width="22" height="22" alt="" />
    </button>
  </header>

  <div class="hub-main" id="hub-main">
    <section class="home" hidden={panel !== 'play'} aria-labelledby="lounge-title">
      <div class="reception" data-testid="hub-mascots">
        <img src={`${base}/hub/welcome.webp`} width="1400" height="1099" alt="Три маскота Бурмалдозы встречают у входа в клуб" fetchpriority="high" />
      </div>
      <div class="welcome-copy">
        <h1 id="lounge-title">Где сегодня сливаем хату?</h1>
        <p>ТРИ КОМНАТЫ. ВЕЗДЕ ДИЛЕР МУДАК.</p>
      </div>
      <section class="activity-section" aria-label="Выбор активности">
        <div class="portals">
          {#each activities as item}
            <button type="button" class="portal" class:selected={activity === item.game} on:click={() => activity=item.game} disabled={busy} aria-pressed={activity === item.game} aria-label={`Выбрать ${item.name}. ${item.subtitle}`} data-testid={`room-card-${item.game}`}>
              <img src={`${base}/hub/${item.art}`} alt="" width="640" height="1280" />
              <span class="sr-only">{item.name}</span>
            </button>
          {/each}
        </div>
        <p class="sr-only" aria-live="polite">{chosen.name}. {chosen.subtitle}</p>
        <button class="open-room" type="button" on:click={() => { sound.cue('confirm'); void onOpen(activity); }} disabled={busy} data-testid="hub-open-room" aria-label={`Открыть комнату ${chosen.name}`}>
          <img src={`${base}/hub/icons/poker-chip.svg`} width="28" height="28" alt="" />
          <span>{busy ? 'Открываем комнату…' : 'Открыть комнату'}</span>
          <img src={`${base}/hub/icons/arrow-right.svg`} width="24" height="24" alt="" />
        </button>
      </section>
    </section>

    <section class="hub-panel" hidden={panel !== 'ranking'} aria-label="Рейтинг клуба"><slot name="ranking" /></section>
    <section class="hub-panel" hidden={panel !== 'history'} aria-label="История игр"><slot name="history" /></section>

    <details class="bonus" hidden={panel !== 'play'}>
      <summary data-testid="hub-bonus-toggle"><img src={`${base}/hub/icons/diamond.svg`} width="30" height="30" alt="" /><span><strong>Бонус дня</strong><small>{live ? 'Выдачи Jokergem · условия внутри' : 'Доступен после входа через Telegram'}</small></span><img class="bonus-arrow" src={`${base}/hub/icons/arrow-right.svg`} width="22" height="22" alt="" /></summary>
      <div class="bonus-content" transition:fade={{duration:quiet ? 0 : 180}}>
        {#if live}<slot name="bonus" />{:else}<p>В демо бонусы не начисляются.</p><a href="https://t.me/Burmaldoza_bot" target="_blank" rel="noreferrer">Открыть бота в Telegram</a>{/if}
      </div>
    </details>
    {#if apiError}<p class="api-error" role="alert">{apiError}</p>{/if}
    <aside class="boundary" data-testid="demo-banner" role="status">
      {#if live}<strong>{connection === 'connected' ? 'LIVE · данные сервера' : status[connection]}</strong><span>Jokergem без вывода и денежной ценности.</span>{:else}<strong>ДЕМО-КОНТУР</strong><span>Демонстрация · Jokergem без денежной ценности.</span>{/if}
    </aside>
  </div>
  <nav class="navigation" aria-label="Активности клуба">
    {#each navigation as item}
      <button type="button" on:click={() => navigate(item.id)} aria-current={panel === item.id ? 'page' : undefined} data-testid={`hub-nav-${item.id}`}><img src={`${base}/hub/icons/${item.icon}.svg`} width="25" height="25" alt="" /><span>{item.label}</span></button>
    {/each}
  </nav>
</main>

<style>
  .hub{position:relative;isolation:isolate;min-height:100dvh;color:#fff4d9;padding:0 max(14px,env(safe-area-inset-right)) max(116px,calc(100px + env(safe-area-inset-bottom))) max(14px,env(safe-area-inset-left));font-family:Inter,system-ui,sans-serif;}
  .backdrop,.backdrop-shade{position:fixed;inset:0;z-index:-2;pointer-events:none;}
  .backdrop{overflow:hidden;background:#080b0e;}
  .backdrop img{width:100%;height:100%;object-fit:cover;opacity:.65;animation:atrium-drift 26s ease-in-out infinite;}
  .backdrop-shade{z-index:-1;background:#06090d;opacity:.24;}
  .masthead{position:relative;z-index:3;max-width:940px;margin:auto;height:76px;padding-top:env(safe-area-inset-top);display:flex;align-items:center;gap:9px;}
  .brand{display:flex;align-items:center;gap:7px;color:#f8d38b;text-decoration:none;min-width:0;}
  .brand>img{width:38px;height:38px;object-fit:contain;}
  .brand>span{display:grid;gap:3px;}
  .brand strong{font:700 clamp(13px,3.5vw,22px)/1 Georgia,'Times New Roman',serif;letter-spacing:-.02em;}
  .brand small{font-size:7px;font-weight:600;letter-spacing:.2em;white-space:nowrap;}
  .balance{margin-left:auto;flex-shrink:0;display:flex;gap:8px;align-items:center;padding:8px 10px;border:1px solid #b8955d;border-radius:22px;background:#0c0f16e6;}
  .balance>span{display:grid;gap:4px;}
  .balance small{font-size:8px;color:#d8d1da;letter-spacing:.06em;}
  .balance strong{font-size:17px;line-height:1;white-space:nowrap;}
  .balance strong span{font-size:12px;color:#f8d38b;}
  .motion-toggle{display:grid;place-items:center;flex-shrink:0;width:44px;height:44px;background:#0a0e14c9;border:1px solid #b8955d;border-radius:50%;cursor:pointer;}
  .motion-toggle[aria-pressed="true"]{background:#302319;}
  .hub-main{max-width:600px;margin:0 auto;scroll-margin-top:10px;}
  .home[hidden],.hub-panel[hidden],.bonus[hidden]{display:none;}
  .reception{height:280px;margin:-76px -14px 0;overflow:hidden;}
  .reception img{width:100%;height:100%;object-fit:cover;object-position:center 57%;animation:welcome-breath 9s ease-in-out infinite;}
  .welcome-copy{text-align:center;padding:12px 0 6px;}
  h1{font:500 clamp(25px,8.4vw,41px)/1.07 Georgia,'Times New Roman',serif;margin:0;color:#fff1ca;letter-spacing:-.055em;}
  .welcome-copy>p{margin:14px 0 12px;color:#d0cdd4;font-size:10px;letter-spacing:.19em;font-weight:600;}
  .portals{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;align-items:end;padding-top:8px;}
  .portal{position:relative;padding:0;min-width:0;min-height:44px;border:0;background:none;cursor:pointer;transform-origin:bottom center;transition:transform .28s ease,filter .28s ease;filter:brightness(.88) saturate(.9);}
  .portal img{display:block;width:100%;height:auto;aspect-ratio:1/2;object-fit:contain;}
  .portal.selected{transform:translateY(-7px) scale(1.035);filter:brightness(1.08) saturate(1.03);}
  .portal:hover{filter:brightness(1.12);}
  .portal:active{transform:translateY(-3px) scale(.99);}
  .portal:focus-visible{outline:2px solid #fff0bc;outline-offset:3px;}
  .open-room{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;min-height:52px;margin-top:12px;padding:12px 20px;border:1px solid #fff0bc;border-radius:30px;background:#efc06b;color:#111015;font:700 18px/1.2 Inter,system-ui,sans-serif;box-shadow:0 4px 20px #d5903b42;cursor:pointer;transition:transform .2s ease,background .2s ease,box-shadow .2s ease;}
  .open-room>img{filter:brightness(.08);flex-shrink:0;}
  .open-room:hover{background:#ffdc93;box-shadow:0 3px 26px #d5903b88;transform:translateY(-2px);}
  .open-room:active{transform:translateY(1px) scale(.985);}
  button:disabled{cursor:wait;opacity:.55;}
  .motion-toggle:disabled{cursor:default;}
  .bonus{margin-top:18px;border:1px solid #8b795954;border-radius:26px;background:#11131ccc;}
  summary{display:flex;align-items:center;gap:12px;padding:13px 18px;min-height:64px;cursor:pointer;list-style:none;}
  summary::-webkit-details-marker{display:none;}
  summary>span{display:grid;gap:5px;}
  summary strong{font-size:17px;}
  summary small{font-size:11px;color:#ccc7cf;line-height:1.35;}
  .bonus-arrow{margin-left:auto;transition:transform .25s ease;}
  details[open] .bonus-arrow{transform:rotate(90deg);}
  .bonus-content{padding:0 14px 16px;font-size:14px;line-height:1.5;}
  .bonus-content a{color:#ffe2a0;display:inline-block;padding:8px 0;min-height:44px;}
  .hub-panel{padding-top:28px;min-height:70dvh;}
  .boundary{display:flex;justify-content:center;gap:5px;flex-wrap:wrap;margin:22px 0 0;color:#a9a5aa;font-size:10px;line-height:1.5;text-align:center;}
  .boundary strong{font-weight:600;}
  .api-error{font-size:14px;color:#ffafbd;line-height:1.5;}
  .navigation{position:fixed;z-index:5;bottom:0;left:50%;transform:translateX(-50%);width:min(100%,640px);display:grid;grid-template-columns:repeat(3,1fr);padding:10px 8px max(14px,env(safe-area-inset-bottom));background:#080b11f2;border-top:1px solid #79613b;backdrop-filter:blur(16px);}
  .navigation button{display:grid;justify-items:center;gap:6px;min-height:56px;border:0;border-bottom:2px solid transparent;background:none;color:#bbb6b8;font-size:13px;cursor:pointer;transition:background .2s ease,color .2s ease;}
  .navigation button>img{opacity:.56;}
  .navigation button[aria-current="page"]{color:#ffe0a0;border-bottom-color:#e5b462;}
  .navigation button[aria-current="page"]>img{opacity:1;}
  .navigation button:hover{background:#b7955c18;color:#fff1cf;}
  .sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;}
  .hub :global(button:focus-visible),.hub :global(summary:focus-visible),.hub :global(a:focus-visible){outline:2px solid #fff0bc;outline-offset:3px;}
  .background-paused .backdrop img,.background-paused .reception img{animation-play-state:paused;}
  .quiet .portal,.quiet .open-room,.quiet .bonus-arrow,.quiet .navigation button{transition:none;}
  @keyframes atrium-drift{0%,100%{transform:scale(1.04) translateY(0);}50%{transform:scale(1.07) translateY(-12px);}}
  @keyframes welcome-breath{0%,100%{transform:scale(1.005);}50%{transform:scale(1.025);}}
  @media(max-width:359px){.masthead{gap:5px;}.brand>img{width:29px;height:29px;}.brand{gap:3px;}.brand strong{font-size:11px;}.brand small{font-size:5.5px;}.balance{padding:8px 7px;gap:5px;}.balance>img{width:17px;}.balance strong{font-size:14px;}.motion-toggle{width:44px;}.reception{height:260px;}.welcome-copy>p{font-size:9px;letter-spacing:.14em;}.open-room{font-size:16px;}}
  @media(min-width:620px){.masthead{height:88px;gap:16px;}.brand>img{width:50px;height:50px;}.brand strong{font-size:25px;}.brand small{font-size:10px;}.balance{padding:10px 18px;}.balance small{font-size:10px;}.balance strong{font-size:22px;}.reception{height:390px;margin-top:-88px;}.welcome-copy>p{font-size:12px;}.portals{gap:9px;}.open-room{min-height:60px;font-size:22px;}.bonus summary strong{font-size:20px;}}
  @media(prefers-reduced-motion:reduce){.backdrop img,.reception img{animation:none;}.portal,.open-room,.bonus-arrow,.navigation button{transition:none;}}
</style>
