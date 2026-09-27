(() => {
  'use strict';

  const REPO = 'Hainox/BURMALDOZA';
  const CACHE_KEY = 'burmaldoza-project-journal-v1';
  const seed = window.PROJECT_JOURNAL_SEED;
  const roadmapUrl = '../Development-Roadmap.md';
  const stages = [
    ['0', 'Product lock и доступы', 'pending', 'Ожидает решений по чату, ролям, доступам, доменам и поддержке.'],
    ['1', 'Foundation и окружение', 'done', 'Технический каркас собран; это не production-развёртывание.'],
    ['2', 'Domain rules и Monte Carlo', 'done', 'Skeleton трёх игр и офлайн-симуляции собраны; финальные RTP и лимиты ещё не утверждены.'],
    ['3', 'Ledger, Telegram auth и API', 'done', 'Foundation собран. Отдельные границы запуска и открытые PR требуют решения.'],
    ['4', 'Mini App и motion', 'partial', 'Foundation собран; production wiring, игровые UI и проверка на устройствах остаются.'],
    ['5', 'Manual QA и закрытая приёмка', 'pending', 'Ожидает проверок на iOS, Android и Telegram Desktop.'],
    ['6', 'Тематическое наполнение', 'pending', 'После приёмки каркаса и согласования прав на материалы.'],
    ['7', 'Закрытая beta', 'pending', 'После QA, готовности поддержки, резервирования и мониторинга.'],
    ['8', 'Public launch', 'pending', 'После beta и отдельного решения владельца.']
  ];
  const handoffs = [
    { number: 21, title: 'Локальный журнал проекта', recipient: 'Codex', model: 'gpt-6-sol', effort: 'high', dependency: 'Реализация уже подготовлена в codex/project-journal; проверить diff и статус issue/PR, не создавать параллельный diff.', scope: 'Проверь реализацию автономного журнала по критериям issue #21: roadmap, публичные Issues/PR, поиск, фильтры, кэш, ручной сценарий и границы файлов. Зафиксируй результаты проверки и риски; не публикуй сайт и не меняй Mini App/API/domain.' },
    { number: 22, title: 'Аудит launch PR', recipient: 'Claude Code через Claude Pro', model: 'Opus 5.5', effort: 'high', dependency: 'Сверить актуальный main, PR #14 (уже слит), открытые #16/#17 и CI; выполнить только read-only review.', scope: 'Проверь статус и изменения PR #14, #16 и #17 против актуального main. Для каждого дай findings с severity и путями/строками либо явно укажи, что findings не обнаружены. Зафиксируй SHA, CI, блокеры и решения владельца. Не редактируй код; структурированный отчёт оставь в issue #22; секреты не публикуй.' },
    { number: 23, title: 'Production Compose и runbook', recipient: 'Codex', model: 'gpt-6-astra', effort: 'xhigh', dependency: 'Gate: решение владельца по PR #16/#17 и результат review #22; PR #14 уже слит. Деплой не входит в задачу.', scope: 'После прохождения gate подготовь review PR для production Compose и runbook в allowlist issue. Caddy публикует только 80/443; API работает одним process/worker/replica до смены EventBus. Проверь сборку, health, backup/rollback. Не заходи на сервер, не выполняй merge или deploy.' },
    { number: 6, title: 'Blackjack room UI и motion', recipient: 'Command Code', model: 'meta/muse-spark-1.3-contributor', effort: 'high', dependency: 'Дизайн checkpoint PR #8 слит; PR #15 открыт. Сверить его статус и продолжать в назначенной ветке, не создавать конкурирующую реализацию.', scope: 'По issue #6 доведи визуальный Blackjack UI по серверному snapshot: подтверждённые legal actions, скрытая карта без раскрытия, результат и баланс только после ответа сервера. Сохрани клавиатуру, mobile и reduced motion. Работай только в allowlist issue; приложи check/test/build/Playwright.' },
    { number: 11, title: 'Wallet grants в Mini App', recipient: 'Command Code', model: 'meta/muse-spark-1.3-contributor', effort: 'high', dependency: 'PR #10 и #14 слиты; дождаться завершения Blackjack issue #6 из-за общего +page.svelte.', scope: 'После gate реализуй live Daily/Relief controls по существующему API, последовательный first-login bootstrap, idempotency UUID и баланс только из подтверждённого ответа. Demo не должен имитировать выдачу. Работай только в allowlist issue #11; приложи check/test/build/Playwright.' },
    { number: 1, title: 'Непрерывная остановка Slot', recipient: 'Command Code', model: 'meta/muse-spark-1.3-contributor', effort: 'high', dependency: 'PR #18 открыт; issue #2 дублирует #1. Сверить существующую ветку и review, не начинать второй diff.', scope: 'По issue #1 проверь непрерывное торможение трёх барабанов без snap, порядок stop и совпадение финальной сетки с подтверждённым SlotOutcome. Сохрани reduced motion и приложи Playwright timing regression. Не меняй domain/RNG/ledger/API.' }
  ];
  const $ = (id) => document.getElementById(id);
  const formatTime = (value) => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Moscow' }).format(new Date(value)) + ' МСК' : 'дата неизвестна';
  const node = (tag, className, content) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  };
  const link = (label, url) => {
    const a = node('a', '', label);
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  };
  const agentOf = (record) => {
    const label = (record.labels || []).find((value) => /^to:(codex|claude|ccode)$/.test(value));
    if (label) return label.slice(3);
    const head = record.head || '';
    return /^(codex|claude|ccode)\//.exec(head)?.[1] || 'none';
  };
  const agentName = { codex: 'Codex', claude: 'Claude Code', ccode: 'Command Code', none: 'Без маршрута' };
  const statusName = { open: 'Открыт', merged: 'Слит', closed: 'Закрыт' };
  const stageName = { done: 'Каркас завершён', partial: 'Частично', pending: 'Ожидает' };
  let current = seed;
  let source = 'snapshot';
  let detail = 'Встроенный снимок публичного GitHub. Нажмите «Обновить», чтобы сверить статус.';

  function validSnapshot(data) {
    return data && typeof data.fetchedAt === 'string' && Number.isFinite(Date.parse(data.fetchedAt))
      && (!data.mainSha || /^[0-9a-f]{40}$/.test(data.mainSha)) && Array.isArray(data.records)
      && data.records.every((record) => record && typeof record === 'object'
        && (record.type === 'issue' || record.type === 'pr')
        && Number.isInteger(record.number) && typeof record.title === 'string'
        && ['open', 'closed', 'merged'].includes(record.state)
        && typeof record.updatedAt === 'string' && Number.isFinite(Date.parse(record.updatedAt))
        && Array.isArray(record.labels) && record.labels.every((label) => typeof label === 'string')
        && (record.head === undefined || typeof record.head === 'string')
        && typeof record.url === 'string' && record.url.startsWith('https://github.com/Hainox/BURMALDOZA/'));
  }

  function readCache() {
    try { const value = JSON.parse(localStorage.getItem(CACHE_KEY)); return validSnapshot(value) ? value : null; }
    catch { return null; }
  }
  function writeCache(data) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); return true; }
    catch { return false; }
  }

  function renderStages() {
    const list = $('stage-list');
    stages.forEach(([number, title, status, description]) => {
      const item = node('li', 'stage');
      item.append(node('span', 'stage-num', number));
      const text = node('div');
      text.append(node('h3', '', title), node('p', '', description));
      item.append(text, node('span', `pill ${status}`, stageName[status]));
      list.append(item);
    });
    // The roadmap file is the evidence for all nine editorial stage summaries.
    $('roadmap-title').setAttribute('data-source', roadmapUrl);
  }

  function renderSource() {
    $('source-label').textContent = source === 'live' ? 'Данные GitHub API' : source === 'memory' ? 'Данные текущей вкладки' : source === 'cache' ? 'Локальный кэш' : 'Встроенный снимок';
    $('source-time').textContent = 'Получено: ' + formatTime(current.fetchedAt);
    $('source-detail').textContent = detail + (current.mainSha ? ` main: ${current.mainSha.slice(0, 7)}.` : '');
    $('metric-issues').textContent = current.records.filter((r) => r.type === 'issue' && r.state === 'open').length;
    $('metric-prs').textContent = current.records.filter((r) => r.type === 'pr' && r.state === 'open').length;
    $('metric-merged').textContent = current.records.filter((r) => r.type === 'pr' && r.state === 'merged').length;
  }

  function renderRecords() {
    const search = $('search').value.trim().toLocaleLowerCase('ru');
    const type = $('type-filter').value;
    const status = $('status-filter').value;
    const agent = $('agent-filter').value;
    const records = current.records.filter((record) => (type === 'all' || record.type === type)
      && (status === 'all' || record.state === status)
      && (agent === 'all' || agentOf(record) === agent)
      && (!search || `${record.title} #${record.number} ${record.head || ''}`.toLocaleLowerCase('ru').includes(search)))
      .sort((a, b) => Date.parse(b.updatedAt || 0) - Date.parse(a.updatedAt || 0));
    $('result-count').textContent = `Найдено ${records.length} из ${current.records.length} записей`;
    const list = $('record-list');
    list.replaceChildren();
    if (!records.length) { list.append(node('p', 'record-empty', 'По этим условиям ничего не найдено. Измените поиск или фильтры.')); return; }
    records.forEach((record) => {
      const item = node('article', 'record');
      const top = node('div', 'record-top');
      top.append(node('span', 'record-type', `${record.type === 'pr' ? 'PR' : 'ISSUE'} · #${record.number}`), node('span', `pill ${record.state}`, statusName[record.state]));
      const heading = node('h3');
      heading.append(link(record.title, record.url));
      const meta = node('div', 'record-meta');
      meta.append(node('span', '', agentName[agentOf(record)]), node('span', '', `Обновлено: ${formatTime(record.updatedAt)}`));
      if (record.type === 'pr' && record.head) meta.append(node('span', '', record.head));
      item.append(top, heading, meta);
      list.append(item);
    });
  }

  function handoffPrompt(item) {
    return `Репозиторий: ${REPO}\nИсточник: https://github.com/${REPO}/issues/${item.number}\nАдресат: ${item.recipient}\nМодель: ${item.model}\nEffort: ${item.effort}\nЗависимости: ${item.dependency}\n\nЗадача: ${item.scope}\n\nПеред началом прочитай dev/Vision.md → dev/BuildSpec.md → dev/ProjectLog.md → docs/Command-Code-Workflow.md → связанное issue. Проверь актуальный main, открытые PR, allowlist и требования приёмки issue. В отчёте укажи branch/commit, изменённые файлы, команды с результатами и оставшиеся риски.`;
  }

  async function copyPrompt(item, feedback, button) {
    const prompt = handoffPrompt(item);
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(prompt);
      else throw new Error('Clipboard API unavailable');
      feedback.textContent = 'Промт скопирован.';
    } catch {
      document.querySelector('.copy-panel')?.remove();
      const panel = node('div', 'copy-panel');
      const instruction = node('label', '', `Автокопирование недоступно. Выделенный промт issue #${item.number} можно скопировать Ctrl+C.`);
      const area = node('textarea');
      area.id = `copy-fallback-${item.number}`;
      instruction.htmlFor = area.id;
      area.value = prompt;
      const close = node('button', '', 'Закрыть поле копирования');
      close.type = 'button';
      const dismiss = () => { panel.remove(); button.focus(); };
      close.addEventListener('click', dismiss);
      panel.append(instruction, area, close);
      document.body.append(panel);
      area.focus(); area.select();
      try { if (document.execCommand('copy')) { feedback.textContent = 'Промт скопирован.'; dismiss(); return; } }
      catch { /* Selection remains available for manual copy. */ }
      feedback.textContent = 'Автокопирование недоступно. Используйте выделенный текст и закройте поле кнопкой.';
      panel.addEventListener('keydown', (event) => { if (event.key === 'Escape') dismiss(); });
    }
  }

  function renderHandoffs() {
    const list = $('handoff-list');
    list.replaceChildren();
    handoffs.forEach((item) => {
      const record = current.records.find((r) => r.type === 'issue' && r.number === item.number);
      if (record?.state === 'closed') return;
      const card = node('article', 'handoff');
      const body = node('div');
      body.append(node('h3', '', `#${item.number} · ${item.title}`), node('p', 'model', `${item.recipient} · ${item.model} / ${item.effort}`), node('p', '', item.dependency));
      const feedback = node('span', 'copy-feedback');
      feedback.setAttribute('role', 'status');
      body.append(feedback);
      const actions = node('div', 'actions');
      actions.append(link(`Исходное issue #${item.number} ↗`, `https://github.com/${REPO}/issues/${item.number}`));
      const copy = node('button', '', `Копировать промт #${item.number}`);
      copy.type = 'button';
      copy.addEventListener('click', () => copyPrompt(item, feedback, copy));
      actions.append(copy);
      card.append(body, actions);
      list.append(card);
    });
  }

  async function fetchPages(path, signal) {
    const result = [];
    for (let page = 1; page <= 10; page += 1) {
      const response = await fetch(`https://api.github.com/repos/${REPO}/${path}?state=all&per_page=100&page=${page}`, {
        headers: { Accept: 'application/vnd.github+json' }, signal, cache: 'no-store'
      });
      if (!response.ok) throw new Error(`GitHub API: HTTP ${response.status}`);
      const batch = await response.json();
      if (!Array.isArray(batch)) throw new Error('GitHub API вернул неожиданный формат');
      result.push(...batch);
      if (batch.length < 100) return result;
    }
    throw new Error('История превышает 1000 записей на тип; кэш не заменён неполным ответом');
  }

  async function refresh() {
    const button = $('refresh');
    button.disabled = true;
    button.textContent = 'Обновление…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const [issues, pulls, mainResponse] = await Promise.all([
        fetchPages('issues', controller.signal),
        fetchPages('pulls', controller.signal),
        fetch(`https://api.github.com/repos/${REPO}/commits/main`, { headers: { Accept: 'application/vnd.github+json' }, signal: controller.signal, cache: 'no-store' })
      ]);
      if (!mainResponse.ok) throw new Error(`GitHub API main: HTTP ${mainResponse.status}`);
      const main = await mainResponse.json();
      if (!/^[0-9a-f]{40}$/.test(main.sha || '')) throw new Error('Не удалось проверить main SHA');
      const records = [
        ...issues.filter((item) => !item.pull_request).map((item) => ({ type: 'issue', number: item.number, title: item.title, state: item.state, url: item.html_url, updatedAt: item.updated_at, closedAt: item.closed_at, labels: item.labels.map((label) => label.name) })),
        ...pulls.map((item) => ({ type: 'pr', number: item.number, title: item.title, state: item.merged_at ? 'merged' : item.state, url: item.html_url, updatedAt: item.updated_at, closedAt: item.closed_at, mergedAt: item.merged_at, head: item.head.ref, labels: item.labels.map((label) => label.name) }))
      ];
      const next = { fetchedAt: new Date().toISOString(), mainSha: main.sha, records };
      if (!validSnapshot(next)) throw new Error('Неполный ответ GitHub API');
      current = next;
      source = 'live';
      detail = writeCache(next) ? 'Свежие данные сохранены локально.' : 'Свежие данные получены; браузер запретил локальное сохранение.';
    } catch (error) {
      const cached = readCache();
      const candidates = [
        { data: current, origin: source === 'live' || source === 'memory' ? 'memory' : source },
        { data: cached, origin: 'cache' },
        { data: seed, origin: 'snapshot' }
      ].filter((candidate) => validSnapshot(candidate.data));
      const freshest = candidates.reduce((best, candidate) => Date.parse(candidate.data.fetchedAt) > Date.parse(best.data.fetchedAt) ? candidate : best);
      current = freshest.data;
      source = freshest.origin;
      const location = source === 'memory' ? 'в памяти текущей вкладки' : source === 'cache' ? 'в локальном кэше' : 'во встроенном снимке';
      detail = `Сеть недоступна или лимит API исчерпан (${error.name === 'AbortError' ? 'тайм-аут' : error.message}). Показаны последние данные ${location}.`;
    } finally {
      clearTimeout(timeout);
      button.disabled = false;
      button.textContent = 'Обновить из GitHub ↗';
      renderSource(); renderRecords(); renderHandoffs();
    }
  }

  const cached = readCache();
  if (cached && Date.parse(cached.fetchedAt) > Date.parse(seed.fetchedAt)) {
    current = cached;
    source = 'cache';
    detail = 'Последние сохранённые данные. Нажмите «Обновить», чтобы сверить статус.';
  }
  renderStages(); renderSource(); renderRecords(); renderHandoffs();
  ['search', 'type-filter', 'status-filter', 'agent-filter'].forEach((id) => $(id).addEventListener(id === 'search' ? 'input' : 'change', renderRecords));
  $('refresh').addEventListener('click', refresh);
})();
