/* Presentation prototype: no credentials, uploads, persistent storage or publish calls. */
(() => {
  'use strict';
  const platforms = {instagram: 'Instagram Reels', tiktok: 'TikTok', youtube: 'YouTube Shorts'};
  const labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const makeVideo = (id, title, file = null) => ({
    id, title, file, url: file ? URL.createObjectURL(file) : null,
    youtubeTitle: title, captions: {instagram: '', tiktok: '', youtube: ''},
    channels: Object.keys(platforms),
  });
  const videos = [makeVideo('demo-1', 'Урок 1 · Пример готового ролика'), makeVideo('demo-2', 'Ответ на вопрос зрителя'), makeVideo('demo-3', 'Фрагмент эфира')];
  videos[0].captions = {instagram: 'Короткий фрагмент нового урока. Полная версия — в профиле.\n\n#ВредныйИнвестор', tiktok: 'Один вопрос — одно короткое объяснение.\n\n#ВредныйИнвестор', youtube: 'Фрагмент нового урока.\nПолная версия и материалы — на канале.'};
  let selectedId = videos[0].id, selectedPlatform = 'instagram', currentView = 'library';
  let nextId = 1, toastTimer, plan = [];
  const days = new Set([0, 1, 2, 3, 4]);
  const $ = id => document.getElementById(id);
  const selected = () => videos.find(video => video.id === selectedId);
  const dayLabel = new Intl.DateTimeFormat('ru-RU', {day: 'numeric', month: 'long', timeZone: 'Europe/Moscow'});
  const weekdayLabel = new Intl.DateTimeFormat('ru-RU', {weekday: 'long', timeZone: 'Europe/Moscow'});
  const dateParts = new Intl.DateTimeFormat('en-CA', {year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Europe/Moscow'}).formatToParts(new Date());
  const part = type => dateParts.find(value => value.type === type).value;
  const today = `${part('year')}-${part('month')}-${part('day')}`;
  $('start-date').value = today;
  $('start-date').min = today;

  function showToast(message) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3500);
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function setView(view) {
    currentView = view;
    for (const name of ['library', 'schedule', 'connections']) $('view-' + name).hidden = view !== name;
    document.querySelectorAll('[data-view]').forEach(button => {
      const active = button.dataset.view === view;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    if (view === 'schedule') renderPlan();
  }
  function renderList() {
    $('nav-count').textContent = videos.length;
    $('library-count').textContent = `${videos.length} в подборке`;
    $('video-list').replaceChildren();
    videos.forEach((video, index) => {
      const row = element('div', 'video-row' + (video.id === selectedId ? ' selected' : ''));
      row.append(element('span', 'row-order', String(index + 1).padStart(2, '0')));
      const button = element('button', 'row-select');
      button.setAttribute('aria-pressed', String(video.id === selectedId));
      button.append(element('strong', '', video.title));
      button.append(element('small', '', video.file ? `${video.file.name} · ${(video.file.size / 1024 / 1024).toFixed(1)} МБ · локальный файл` : 'Демонстрационный пример · без файла'));
      const badges = element('div', 'row-channels');
      for (const channel of video.channels) badges.append(element('span', '', platforms[channel]));
      if (!video.channels.length) badges.append(element('span', '', 'Не выбраны площадки'));
      button.append(badges);
      button.addEventListener('click', () => { selectedId = video.id; renderList(); renderEditor(); });
      row.append(button);
      const move = element('div', 'move');
      for (const [offset, arrow, name] of [[-1, '↑', 'Поднять'], [1, '↓', 'Опустить']]) {
        const control = element('button', '', arrow);
        control.disabled = index + offset < 0 || index + offset >= videos.length;
        control.setAttribute('aria-label', `${name}: ${video.title}`);
        control.addEventListener('click', () => {
          [videos[index], videos[index + offset]] = [videos[index + offset], videos[index]];
          renderList();
        });
        move.append(control);
      }
      row.append(move);
      $('video-list').append(row);
    });
  }
  function renderEditor() {
    const video = selected();
    $('editor-heading').textContent = video.title;
    $('video-title').value = video.title;
    $('youtube-title').value = video.youtubeTitle;
    $('caption').value = video.captions[selectedPlatform];
    $('char-count').textContent = `${$('caption').value.length} знаков`;
    $('youtube-title-label').hidden = selectedPlatform !== 'youtube';
    document.querySelectorAll('[data-platform]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.platform === selectedPlatform)));
    document.querySelectorAll('[data-channel]').forEach(input => { input.checked = video.channels.includes(input.dataset.channel); });
    const previous = $('media-preview').querySelector('video');
    if (previous) previous.pause();
    $('media-preview').replaceChildren();
    if (video.url) {
      const preview = element('video');
      preview.src = video.url;
      preview.controls = true;
      preview.preload = 'metadata';
      preview.playsInline = true;
      preview.addEventListener('error', () => showToast('Браузер не смог воспроизвести этот MP4. Формат кодека нужно проверить.'));
      $('media-preview').append(preview);
    } else {
      const placeholder = element('div', 'media-placeholder');
      placeholder.append(element('span', 'play-mark', '▷'), element('span', '', 'Место для готового MP4 · 9:16'));
      $('media-preview').append(placeholder);
    }
  }
  function renderPlan() {
    const start = $('start-date').value, time = $('post-time').value;
    const activeVideos = videos.filter(video => video.channels.length);
    const startMoment = new Date(`${start}T${time}:00+03:00`);
    const valid = days.size && start && time && !Number.isNaN(startMoment.getTime()) && start >= today;
    plan = [];
    $('plan-list').replaceChildren();
    $('export-plan').disabled = !valid || !activeVideos.length;
    if (!valid) {
      $('plan-summary').textContent = 'Укажите дату не раньше сегодняшней, время и хотя бы один день недели';
      return;
    }
    let cursor = new Date(`${start}T00:00:00Z`);
    // Cursor is a calendar date in UTC. Offset conversion happens only when a slot is created.
    while (plan.length < activeVideos.length) {
      const weekday = (cursor.getUTCDay() + 6) % 7;
      const date = cursor.toISOString().slice(0, 10);
      const at = new Date(`${date}T${time}:00+03:00`);
      if (days.has(weekday) && at > new Date()) {
        const video = activeVideos[plan.length];
        plan.push({videoId: video.id, title: video.title, at: at.toISOString(), channels: [...video.channels], youtubeTitle: video.youtubeTitle, captions: {...video.captions}, demo: !video.file});
      }
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    const end = plan.length ? dayLabel.format(new Date(plan.at(-1).at)) : null;
    $('plan-summary').textContent = end ? `Роликов в плане: ${plan.length} · последний на ${end}` : 'Выберите площадки в карточке ролика';
    for (const item of plan) {
      const at = new Date(item.at);
      const row = element('div', 'plan-row');
      const date = element('div');
      date.append(element('strong', '', dayLabel.format(at)), element('small', '', `${weekdayLabel.format(at)} · ${time}`));
      const content = element('div');
      content.append(element('strong', '', item.title), element('small', '', item.demo ? 'Демонстрационный пример' : 'Локальный MP4 · ещё не загружен в сервис'));
      const channels = element('div', 'platforms');
      for (const channel of item.channels) channels.append(element('div', '', `${platforms[channel]} · не отправлено`));
      row.append(date, content, channels);
      $('plan-list').append(row);
    }
  }
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
  document.querySelector('.brand').addEventListener('click', event => { event.preventDefault(); setView('library'); });
  document.querySelectorAll('[data-platform]').forEach(button => button.addEventListener('click', () => { selectedPlatform = button.dataset.platform; renderEditor(); }));
  $('video-title').addEventListener('input', event => {
    selected().title = event.target.value;
    $('editor-heading').textContent = event.target.value;
    renderList();
  });
  $('youtube-title').addEventListener('input', event => { selected().youtubeTitle = event.target.value; });
  $('caption').addEventListener('input', event => {
    selected().captions[selectedPlatform] = event.target.value;
    $('char-count').textContent = `${event.target.value.length} знаков`;
  });
  $('copy-caption').addEventListener('click', () => {
    for (const key of Object.keys(platforms)) selected().captions[key] = $('caption').value;
    showToast('Подпись применена к трём площадкам в макете');
  });
  document.querySelectorAll('[data-channel]').forEach(input => input.addEventListener('change', () => {
    selected().channels = [...document.querySelectorAll('[data-channel]:checked')].map(item => item.dataset.channel);
    renderList();
  }));
  $('upload').addEventListener('click', () => $('files').click());
  $('files').addEventListener('change', event => {
    const files = [...event.target.files];
    let added = 0;
    for (const file of files) {
      if (!/\.mp4$/i.test(file.name) || file.size === 0) continue;
      const video = makeVideo('local-' + nextId++, file.name.replace(/\.mp4$/i, ''), file);
      videos.push(video);
      selectedId = video.id;
      added++;
    }
    renderList(); renderEditor();
    showToast(`${added} файлов добавлено в макет. ${files.length - added} пропущено. Передачи файлов нет.`);
    event.target.value = '';
  });
  $('show-schedule').addEventListener('click', () => setView('schedule'));
  labels.forEach((label, index) => {
    const button = element('button', '', label);
    button.setAttribute('aria-pressed', String(days.has(index)));
    button.addEventListener('click', () => {
      if (days.has(index)) days.delete(index); else days.add(index);
      button.setAttribute('aria-pressed', String(days.has(index)));
      renderPlan();
    });
    $('weekdays').append(button);
  });
  for (const id of ['start-date', 'post-time']) $(id).addEventListener('change', renderPlan);
  $('export-plan').addEventListener('click', () => {
    renderPlan();
    if (!plan.length) return;
    const blob = new Blob([JSON.stringify({prototype: true, publishingEnabled: false, timezone: 'Europe/Moscow', posts: plan}, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob), anchor = element('a');
    anchor.href = url; anchor.download = 'content-factory-example-plan.json'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  for (const [channel, name] of Object.entries(platforms)) {
    const row = element('section', 'connection');
    row.append(element('h2', '', name), element('span', 'pill', 'Не подключено'), element('p', '', channel === 'tiktok' ? 'Публичная автопубликация через своё приложение требует проверки TikTok.' : 'Подключение аккаунта проверяется через выбранный сервис публикации.'));
    $('connections-list').append(row);
  }
  window.addEventListener('beforeunload', () => { for (const video of videos) if (video.url) URL.revokeObjectURL(video.url); });
  renderList(); renderEditor(); setView(currentView);
})();
