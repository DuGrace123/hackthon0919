const $ = (selector) => document.querySelector(selector);
const translations = {
  zh: {
    pageTitle: '灵剪 · 网页剪辑台', projectName: '工程名称', ratio: '画幅', saveProject: '保存工程', exportMp4: '导出 MP4',
    connecting: '正在连接本地剪辑服务…', mediaLibrary: '素材库', importMedia: '＋ 导入', readingMedia: '正在读取媒体信息…',
    noMedia: '还没有素材', noMediaHint: '导入视频或音频，然后将需要的镜头加入时间线。', programMonitor: '节目监视器',
    previewHint: '选择素材或时间线片段进行预览', clipEditing: '片段编辑', noClip: '未选择片段', noClipHint: '在时间线上选择一个片段以裁剪、调整字幕和转场。',
    inPoint: '入点（秒）', outPoint: '出点（秒）', captions: '字幕', captionPlaceholder: '输入片段字幕', transition: '转场',
    cut: '直接切换', fade: '淡入淡出', dissolve: '叠化', wipeLeft: '向左擦除', wipeRight: '向右擦除', slideUp: '向上滑动', slideDown: '向下滑动',
    sourceAudio: '原声', applyClip: '应用片段修改', deleteClip: '从时间线删除', resizeTimeline: '调整时间线高度', timeline: '时间线', zoom: '缩放',
    timelineZoom: '时间线缩放', emptyTimeline: '时间线为空', emptyTimelineHint: '从素材库点击“加入时间线”开始剪辑。', video: '视频', sourceAudioShort: '原声',
    timelineClips: '时间线片段', audioTimeline: '音频时间线', exporting: '正在导出 MP4', preparingRender: '正在准备渲染任务…', downloadExport: '下载导出文件', close: '关闭',
    switchLanguage: 'Switch to English', seconds: '{value} 秒', addTimeline: '加入时间线', captionPrefix: '字幕：{value}', noCaption: '无字幕', originalAudioTitle: '{name} 的原声',
    requestFailed: '请求失败（{status}）', inaccessibleMedia: '该片段不是通过网页上传，浏览器无法直接访问其本地路径。', addingMedia: '正在把素材加入时间线…',
    mediaAdded: '素材已加入时间线。', orderUpdated: '片段顺序已更新。', imported: '已导入 {count} 个素材。', clipApplied: '裁剪、字幕与转场修改已应用。',
    deleteConfirm: '确定从时间线删除这个片段吗？素材库中的原文件不会删除。', clipRemoved: '片段已从时间线移除。', projectSaved: '工程已保存：{path}',
    exportDoneMessage: '导出完成，可以下载 MP4。', exportDoneBanner: 'MP4 导出完成。', exportFailed: '导出失败', waitingRender: '正在等待渲染…', rendering: 'FFmpeg 正在渲染时间线…', connected: '本地剪辑服务已连接。', accounts: '账户管理', logout: '退出',
    aiDirector: 'AI 导演', aiSources: '选择参与剪辑的素材', aiNoSources: '素材库里还没有视频，请先导入视频文件。', aiMode: '分析模式', aiModeLocal: '本地分析（不上传素材）', aiModeCloud: '云端分析',
    aiCloudUnavailable: '服务端未配置', aiTarget: '目标时长（秒）', aiPrompt: '剪辑要求', aiPromptPlaceholder: '例如：按真实拍摄顺序，保留关键动作和结尾', aiConsent: '我了解云端分析会上传抽帧图片、音频和剪辑要求，并可能产生 API 费用。',
    aiStart: '生成方案', aiCancel: '取消分析', aiWaiting: '等待分析…', aiDiscard: '放弃方案', aiApply: '应用到时间线', aiUndo: '撤销应用', aiNew: '生成新方案', aiRetry: '返回重新设置', aiFailed: '分析失败', aiShotList: 'AI 镜头清单',
    aiSelectSources: '请至少选择一份视频素材。', aiStarted: 'AI 正在分析素材…', aiReadyBanner: 'AI 方案已生成，请在 AI 导演面板中预览并确认。', aiApplied: 'AI 方案已应用到时间线，工程已保存。', aiUndone: '已恢复应用前的时间线。', aiCancelled: '已放弃该方案，工程未改变。',
    aiAppliedMessage: '方案已应用：{summary}。时间线上的 AI 片段可以继续手动修改。', aiUndoConfirm: '再点一次确认撤销', aiPreviewShot: '点击在监视器中预览该镜头', aiExpired: 'AI 方案已失效，请重新生成。',
    aiChangeReplace: '替换当前时间线上的 {count} 个视频片段', aiChangeOverlays: '移除 {count} 个叠加层', aiChangeSfx: '移除 {count} 个音效', aiChangeMusic: '保留背景音乐设置', aiChangeSaved: '应用后工程会立即保存到磁盘，并可一键撤销', aiTransition: 'AI 转场：{value}',
    aiCloudHintAdmin: '云端模式尚未配置：在', aiCloudHintLink: '账户管理 → AI 接口', aiCloudHintAdminTail: '中填写服务地址和 API Key 后即可使用。', aiCloudHintEditor: '云端模式尚未配置，请联系管理员在「账户管理 → AI 接口」中填写 API 设置。'
  },
  en: {
    pageTitle: 'LingJian · Web Editing Studio', projectName: 'Project', ratio: 'Aspect ratio', saveProject: 'Save Project', exportMp4: 'Export MP4',
    connecting: 'Connecting to the local editing service…', mediaLibrary: 'Media Pool', importMedia: '＋ Import', readingMedia: 'Reading media information…',
    noMedia: 'No media yet', noMediaHint: 'Import video or audio, then add the shots you need to the timeline.', programMonitor: 'Program Monitor',
    previewHint: 'Select media or a timeline clip to preview it', clipEditing: 'Clip Inspector', noClip: 'No clip selected', noClipHint: 'Select a timeline clip to trim it or adjust captions and transitions.',
    inPoint: 'In point (sec)', outPoint: 'Out point (sec)', captions: 'Caption', captionPlaceholder: 'Enter a clip caption', transition: 'Transition',
    cut: 'Cut', fade: 'Fade', dissolve: 'Dissolve', wipeLeft: 'Wipe Left', wipeRight: 'Wipe Right', slideUp: 'Slide Up', slideDown: 'Slide Down',
    sourceAudio: 'Source audio', applyClip: 'Apply Clip Changes', deleteClip: 'Remove from Timeline', resizeTimeline: 'Resize timeline height', timeline: 'Timeline', zoom: 'Zoom',
    timelineZoom: 'Timeline zoom', emptyTimeline: 'Timeline is empty', emptyTimelineHint: 'Click “Add to Timeline” in the media pool to start editing.', video: 'Video', sourceAudioShort: 'Audio',
    timelineClips: 'Timeline clips', audioTimeline: 'Audio timeline', exporting: 'Exporting MP4', preparingRender: 'Preparing the render job…', downloadExport: 'Download Export', close: 'Close',
    switchLanguage: '切换到中文', seconds: '{value} sec', addTimeline: 'Add to Timeline', captionPrefix: 'Caption: {value}', noCaption: 'No caption', originalAudioTitle: '{name} source audio',
    requestFailed: 'Request failed ({status})', inaccessibleMedia: 'This clip was not uploaded through the web app, so the browser cannot access its local path.', addingMedia: 'Adding media to the timeline…',
    mediaAdded: 'Media added to the timeline.', orderUpdated: 'Clip order updated.', imported: 'Imported {count} media file(s).', clipApplied: 'Trim, caption, and transition changes applied.',
    deleteConfirm: 'Remove this clip from the timeline? The original file will remain in the media pool.', clipRemoved: 'Clip removed from the timeline.', projectSaved: 'Project saved: {path}',
    exportDoneMessage: 'Export complete. Your MP4 is ready to download.', exportDoneBanner: 'MP4 export complete.', exportFailed: 'Export failed', waitingRender: 'Waiting to render…', rendering: 'FFmpeg is rendering the timeline…', connected: 'Local editing service connected.', accounts: 'Accounts', logout: 'Sign Out',
    aiDirector: 'AI Director', aiSources: 'Choose source clips', aiNoSources: 'No video in the media pool yet. Import a video file first.', aiMode: 'Analysis mode', aiModeLocal: 'Local analysis (nothing uploaded)', aiModeCloud: 'Cloud analysis',
    aiCloudUnavailable: 'not configured on the server', aiTarget: 'Target duration (sec)', aiPrompt: 'Editing brief', aiPromptPlaceholder: 'e.g. Keep the real shooting order, keep key actions and the ending', aiConsent: 'I understand cloud analysis uploads sampled frames, audio and my brief, and may incur API charges.',
    aiStart: 'Generate Plan', aiCancel: 'Cancel analysis', aiWaiting: 'Waiting for analysis…', aiDiscard: 'Discard Plan', aiApply: 'Apply to Timeline', aiUndo: 'Undo Apply', aiNew: 'New Plan', aiRetry: 'Back to Settings', aiFailed: 'Analysis failed', aiShotList: 'AI shot list',
    aiSelectSources: 'Select at least one video source.', aiStarted: 'AI is analyzing the footage…', aiReadyBanner: 'AI plan is ready. Review and confirm it in the AI Director panel.', aiApplied: 'AI plan applied to the timeline and the project was saved.', aiUndone: 'Timeline restored to the state before the plan was applied.', aiCancelled: 'Plan discarded. The project is unchanged.',
    aiAppliedMessage: 'Plan applied: {summary}. AI clips on the timeline can still be edited by hand.', aiUndoConfirm: 'Click again to confirm undo', aiPreviewShot: 'Click to preview this shot in the monitor', aiExpired: 'The AI plan is no longer available. Generate a new one.',
    aiChangeReplace: 'Replace {count} video clip(s) on the current timeline', aiChangeOverlays: 'Remove {count} overlay(s)', aiChangeSfx: 'Remove {count} sound effect(s)', aiChangeMusic: 'Keep the background music settings', aiChangeSaved: 'The project is saved to disk right after applying and can be undone in one click', aiTransition: 'AI transition: {value}',
    aiCloudHintAdmin: 'Cloud mode is not configured yet: open ', aiCloudHintLink: 'Accounts → AI Service', aiCloudHintAdminTail: ' and enter the service URL and API key.', aiCloudHintEditor: 'Cloud mode is not configured yet. Ask an administrator to enter the API settings under Accounts → AI Service.'
  }
};

function t(key, values = {}) {
  let value = translations[state.lang]?.[key] || translations.zh[key] || key;
  Object.entries(values).forEach(([name, replacement]) => { value = value.replace(`{${name}}`, replacement); });
  return value;
}

const state = {
  project: {clips: []},
  media: [],
  selectedClipId: null,
  previewEnd: null,
  currentPreviewTitle: null,
  draggedClipId: null,
  timelineScale: Number(localStorage.getItem('lingjian-timeline-scale') || 70),
  lang: localStorage.getItem('lingjian-language') === 'en' ? 'en' : 'zh',
  csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || '',
  ai: {capabilities: null, plan: null, pollTimer: null, selected: [], view: 'aiSetup'},
};

function applyLanguage(shouldRender = true) {
  document.documentElement.lang = state.lang === 'en' ? 'en' : 'zh-CN';
  document.title = t('pageTitle');
  document.querySelectorAll('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  document.querySelectorAll('[data-i18n-aria-label]').forEach((node) => { node.setAttribute('aria-label', t(node.dataset.i18nAriaLabel)); });
  const toggle = $('#languageToggle');
  toggle.textContent = state.lang === 'zh' ? 'EN' : '中文';
  toggle.title = t('switchLanguage');
  toggle.setAttribute('aria-label', t('switchLanguage'));
  if (state.currentPreviewTitle) $('#playerTitle').textContent = state.currentPreviewTitle;
  if (shouldRender) { render(); renderAI(); }
}

async function api(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = String(options.method || 'GET').toUpperCase();
  if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) headers.set('X-CSRF-Token', state.csrfToken);
  const response = await fetch(url, {...options, headers});
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    window.location.assign('/login');
    throw new Error(data.error || 'Authentication required');
  }
  if (!response.ok) throw new Error(data.error || t('requestFailed', {status: response.status}));
  return data;
}

function banner(message, type = '') {
  const node = $('#banner');
  node.textContent = message;
  node.className = `banner ${type}`;
}

function formatTime(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  return `${String(minutes).padStart(2, '0')}:${(value % 60).toFixed(3).padStart(6, '0')}`;
}

function escapeHtml(value) {
  const node = document.createElement('div');
  node.textContent = String(value ?? '');
  return node.innerHTML;
}

function hydrate(data) {
  state.project = data.project;
  state.media = data.media;
  if (!state.project.clips.some((clip) => clip.id === state.selectedClipId)) state.selectedClipId = null;
  render();
}

function render() {
  $('#projectTitle').value = state.project.title || '';
  $('#projectRatio').value = state.project.ratio || '9:16';
  $('#timelineDuration').textContent = t('seconds', {value: Number(state.project.duration || 0).toFixed(1)});
  renderMedia();
  renderTimeline();
  renderInspector();
}

function renderMedia() {
  $('#mediaEmpty').classList.toggle('hidden', state.media.length > 0);
  const grid = $('#mediaGrid');
  grid.innerHTML = state.media.map((media) => `
    <article class="media-card" data-media-id="${media.id}">
      <div class="media-icon">${media.width ? '▶' : '♫'}</div>
      <div><h3 title="${escapeHtml(media.name)}">${escapeHtml(media.name)}</h3><p>${t('seconds', {value: Number(media.duration).toFixed(1)})} · ${escapeHtml(media.codec)}</p></div>
      <button data-action="add-media" data-media-id="${media.id}">${t('addTimeline')}</button>
    </article>`).join('');
  grid.querySelectorAll('.media-card').forEach((card) => card.addEventListener('click', (event) => {
    if (event.target.closest('button')) return;
    const media = state.media.find((item) => item.id === card.dataset.mediaId);
    if (media) preview(media.url, media.name, 0, media.duration);
  }));
  grid.querySelectorAll('[data-action="add-media"]').forEach((button) => button.addEventListener('click', () => addMedia(button.dataset.mediaId)));
}

function renderTimeline() {
  const clips = state.project.clips || [];
  $('#timelineEmpty').classList.toggle('hidden', clips.length > 0);
  $('#timelineWorkspace').classList.toggle('hidden', clips.length === 0);
  const timeline = $('#timeline');
  const audioTrack = $('#audioTrack');
  const totalDuration = Math.max(10, Number(state.project.duration || 0));
  const contentWidth = Math.max(900, Math.ceil(totalDuration * state.timelineScale));
  document.documentElement.style.setProperty('--timeline-scale', `${state.timelineScale}px`);
  timeline.style.width = `${contentWidth}px`;
  audioTrack.style.width = `${contentWidth}px`;
  $('#timelineRuler').style.width = `${contentWidth}px`;
  const tickStep = totalDuration > 180 ? 30 : totalDuration > 60 ? 10 : totalDuration > 25 ? 5 : 1;
  $('#timelineRuler').innerHTML = Array.from({length: Math.floor(totalDuration / tickStep) + 1}, (_, index) => {
    const seconds = index * tickStep;
    return `<div class="ruler-tick" style="left:${seconds * state.timelineScale}px"><span>${formatTime(seconds).slice(0, 5)}</span></div>`;
  }).join('');
  timeline.innerHTML = clips.map((clip, index) => `
    <article draggable="true" class="timeline-clip ${clip.id === state.selectedClipId ? 'selected' : ''}" data-clip-id="${clip.id}" style="--clip-width:${Math.max(90, Number(clip.duration) * state.timelineScale)}px">
      <span class="index">V1 · ${String(index + 1).padStart(2, '0')}</span>
      <h3 title="${escapeHtml(clip.name)}">${escapeHtml(clip.name)}${clip.ai_selected ? '<span class="ai-badge">AI</span>' : ''}</h3>
      <p>${t('seconds', {value: `${Number(clip.start).toFixed(2)} – ${Number(clip.end).toFixed(2)}`})}</p>
      <p>${clip.caption ? t('captionPrefix', {value: escapeHtml(clip.caption)}) : t('noCaption')}</p>
      <div class="timeline-actions"><button data-move="-1" ${index === 0 ? 'disabled' : ''}>←</button><button data-move="1" ${index === clips.length - 1 ? 'disabled' : ''}>→</button></div>
    </article>`).join('');
  audioTrack.innerHTML = clips.map((clip) => `<div class="audio-segment" style="--clip-width:${Math.max(90, Number(clip.duration) * state.timelineScale)}px" title="${t('originalAudioTitle', {name: escapeHtml(clip.name)})}"></div>`).join('');
  timeline.querySelectorAll('.timeline-clip').forEach((node) => {
    node.addEventListener('click', (event) => {
      const clip = clips.find((item) => item.id === node.dataset.clipId);
      if (!clip) return;
      if (event.target.dataset.move) return moveClip(clip.id, Number(event.target.dataset.move));
      state.selectedClipId = clip.id;
      preview(clip.media_url, clip.name, clip.start, clip.end);
      renderTimeline();
      renderInspector();
    });
    node.addEventListener('dragstart', (event) => {
      state.draggedClipId = node.dataset.clipId;
      node.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', state.draggedClipId);
    });
    node.addEventListener('dragend', () => {
      state.draggedClipId = null;
      timeline.querySelectorAll('.timeline-clip').forEach((item) => item.classList.remove('dragging', 'drop-target'));
    });
    node.addEventListener('dragover', (event) => {
      if (!state.draggedClipId || state.draggedClipId === node.dataset.clipId) return;
      event.preventDefault();
      node.classList.add('drop-target');
    });
    node.addEventListener('dragleave', () => node.classList.remove('drop-target'));
    node.addEventListener('drop', (event) => {
      event.preventDefault();
      const sourceId = state.draggedClipId || event.dataTransfer.getData('text/plain');
      const targetId = node.dataset.clipId;
      node.classList.remove('drop-target');
      if (!sourceId || sourceId === targetId) return;
      const ids = clips.map((clip) => clip.id).filter((id) => id !== sourceId);
      let targetIndex = ids.indexOf(targetId);
      if (event.clientX > node.getBoundingClientRect().left + node.offsetWidth / 2) targetIndex += 1;
      ids.splice(targetIndex, 0, sourceId);
      reorderClips(ids);
    });
  });
}

function renderInspector() {
  const clip = state.project.clips.find((item) => item.id === state.selectedClipId);
  $('#inspectorEmpty').classList.toggle('hidden', Boolean(clip));
  $('#clipForm').classList.toggle('hidden', !clip);
  if (!clip) return;
  $('#selectedName').textContent = clip.name;
  $('#clipStart').value = clip.start;
  $('#clipEnd').value = clip.end;
  $('#clipCaption').value = clip.caption || '';
  const transitionSelect = $('#clipTransition');
  const transition = clip.transition || 'none';
  transitionSelect.querySelector('option[data-dynamic]')?.remove();
  if (![...transitionSelect.options].some((option) => option.value === transition)) {
    const option = document.createElement('option');
    option.value = transition; option.dataset.dynamic = '1'; option.textContent = t('aiTransition', {value: transition});
    transitionSelect.appendChild(option);
  }
  transitionSelect.value = transition;
  $('#clipVolume').value = clip.volume;
  $('#volumeValue').textContent = `${Math.round(Number(clip.volume) * 100)}%`;
}

function preview(url, title, start = 0, end = null) {
  if (!url) return banner(t('inaccessibleMedia'), 'error');
  const player = $('#player');
  if (player.getAttribute('src') !== url) player.src = url;
  player.addEventListener('loadedmetadata', () => { player.currentTime = Math.max(0, Number(start) || 0); }, {once: true});
  if (player.readyState >= 1) player.currentTime = Math.max(0, Number(start) || 0);
  state.previewEnd = end == null ? null : Number(end);
  state.currentPreviewTitle = title;
  $('#playerTitle').textContent = title;
  $('#playerEmpty').classList.add('hidden');
}

async function addMedia(mediaId) {
  try {
    banner(t('addingMedia'));
    hydrate(await api('/api/timeline/clips', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({media_id: mediaId})}));
    banner(t('mediaAdded'), 'success');
  } catch (error) { banner(error.message, 'error'); }
}

async function moveClip(clipId, delta) {
  const ids = state.project.clips.map((item) => item.id);
  const index = ids.indexOf(clipId), target = index + delta;
  if (index < 0 || target < 0 || target >= ids.length) return;
  [ids[index], ids[target]] = [ids[target], ids[index]];
  return reorderClips(ids);
}

async function reorderClips(ids) {
  try {
    hydrate(await api('/api/timeline/reorder', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({clip_ids: ids})}));
    banner(t('orderUpdated'), 'success');
  } catch (error) { banner(error.message, 'error'); }
}

async function updateProject() {
  try {
    hydrate(await api('/api/project', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: $('#projectTitle').value, ratio: $('#projectRatio').value})}));
  } catch (error) { banner(error.message, 'error'); }
}

$('#uploadInput').addEventListener('change', async (event) => {
  const files = [...event.target.files];
  if (!files.length) return;
  const form = new FormData(); files.forEach((file) => form.append('files', file));
  $('#uploadProgress').classList.remove('hidden');
  try {
    await api('/api/media/upload', {method: 'POST', body: form});
    hydrate(await api('/api/project'));
    banner(t('imported', {count: files.length}), 'success');
  } catch (error) { banner(error.message, 'error'); }
  finally { $('#uploadProgress').classList.add('hidden'); event.target.value = ''; }
});

$('#clipForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    hydrate(await api(`/api/timeline/clips/${state.selectedClipId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({start: Number($('#clipStart').value), end: Number($('#clipEnd').value), caption: $('#clipCaption').value, transition: $('#clipTransition').value, volume: Number($('#clipVolume').value)})}));
    banner(t('clipApplied'), 'success');
  } catch (error) { banner(error.message, 'error'); }
});

$('#deleteClipBtn').addEventListener('click', async () => {
  if (!state.selectedClipId || !confirm(t('deleteConfirm'))) return;
  try {
    hydrate(await api(`/api/timeline/clips/${state.selectedClipId}`, {method: 'DELETE'}));
    state.selectedClipId = null; render(); banner(t('clipRemoved'), 'success');
  } catch (error) { banner(error.message, 'error'); }
});

$('#saveBtn').addEventListener('click', async () => {
  try { await updateProject(); const result = await api('/api/project/save', {method: 'POST'}); banner(t('projectSaved', {path: result.path}), 'success'); }
  catch (error) { banner(error.message, 'error'); }
});

$('#projectTitle').addEventListener('change', updateProject);
$('#projectRatio').addEventListener('change', updateProject);
$('#languageToggle').addEventListener('click', () => {
  state.lang = state.lang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('lingjian-language', state.lang);
  applyLanguage();
  banner(t('connected'), 'success');
});
$('#logoutBtn').addEventListener('click', async () => {
  try {
    await api('/api/auth/logout', {method: 'POST'});
    window.location.assign('/login');
  } catch (error) { banner(error.message, 'error'); }
});
$('#clipVolume').addEventListener('input', () => { $('#volumeValue').textContent = `${Math.round(Number($('#clipVolume').value) * 100)}%`; });
$('#player').addEventListener('timeupdate', () => {
  const player = $('#player'); $('#timeReadout').textContent = formatTime(player.currentTime);
  const selectedIndex = state.project.clips.findIndex((clip) => clip.id === state.selectedClipId);
  if (selectedIndex >= 0) {
    const selected = state.project.clips[selectedIndex];
    const before = state.project.clips.slice(0, selectedIndex).reduce((sum, clip) => sum + Number(clip.duration || 0), 0);
    const timelineTime = before + Math.max(0, player.currentTime - Number(selected.start || 0));
    $('#playhead').style.setProperty('--playhead-x', `${timelineTime * state.timelineScale}px`);
  }
  if (state.previewEnd != null && player.currentTime >= state.previewEnd) player.pause();
});

$('#timelineZoom').value = String(state.timelineScale);
$('#timelineZoom').addEventListener('input', (event) => {
  state.timelineScale = Number(event.target.value);
  localStorage.setItem('lingjian-timeline-scale', String(state.timelineScale));
  renderTimeline();
});

const splitter = $('#timelineSplitter');
function setTimelineHeight(value) {
  const maximum = Math.min(560, Math.max(260, window.innerHeight * .62));
  const height = Math.max(180, Math.min(maximum, Number(value)));
  document.documentElement.style.setProperty('--timeline-height', `${height}px`);
  localStorage.setItem('lingjian-timeline-height', String(Math.round(height)));
}
setTimelineHeight(Number(localStorage.getItem('lingjian-timeline-height') || 285));
splitter.addEventListener('pointerdown', (event) => {
  const startY = event.clientY;
  const initialHeight = document.querySelector('.timeline-panel').getBoundingClientRect().height;
  splitter.setPointerCapture(event.pointerId);
  splitter.classList.add('dragging');
  document.body.classList.add('resizing-timeline');
  const move = (moveEvent) => setTimelineHeight(initialHeight + startY - moveEvent.clientY);
  const stop = () => {
    splitter.classList.remove('dragging');
    document.body.classList.remove('resizing-timeline');
    splitter.removeEventListener('pointermove', move);
    splitter.removeEventListener('pointerup', stop);
    splitter.removeEventListener('pointercancel', stop);
  };
  splitter.addEventListener('pointermove', move);
  splitter.addEventListener('pointerup', stop);
  splitter.addEventListener('pointercancel', stop);
});
splitter.addEventListener('keydown', (event) => {
  if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
  event.preventDefault();
  const current = document.querySelector('.timeline-panel').getBoundingClientRect().height;
  setTimelineHeight(current + (event.key === 'ArrowUp' ? 20 : -20));
});

$('#exportBtn').addEventListener('click', async () => {
  const modal = $('#exportDialog'); modal.classList.remove('hidden'); $('#exportMessage').textContent = t('preparingRender'); $('#downloadLink').classList.add('hidden'); $('#closeExport').classList.add('hidden'); $('#exportBar').style.width = '3%';
  try {
    await updateProject();
    const task = await api('/api/export', {method: 'POST'});
    const poll = async () => {
      const job = await api(task.status_url); $('#exportBar').style.width = `${job.progress || 0}%`;
      if (job.status === 'done') { $('#exportMessage').textContent = t('exportDoneMessage'); $('#downloadLink').href = job.download_url; $('#downloadLink').classList.remove('hidden'); $('#closeExport').classList.remove('hidden'); banner(t('exportDoneBanner'), 'success'); return; }
      if (job.status === 'error') throw new Error(job.message || t('exportFailed'));
      $('#exportMessage').textContent = job.status === 'queued' ? t('waitingRender') : t('rendering'); setTimeout(poll, 1200);
    };
    poll().catch((error) => { $('#exportMessage').textContent = error.message; $('#closeExport').classList.remove('hidden'); banner(error.message, 'error'); });
  } catch (error) { $('#exportMessage').textContent = error.message; $('#closeExport').classList.remove('hidden'); banner(error.message, 'error'); }
});
$('#closeExport').addEventListener('click', () => $('#exportDialog').classList.add('hidden'));


// ---------------------------------------------------------------- AI director
function aiMedia() { return state.media.filter((media) => Number(media.width) > 0); }

function showAIView(name) {
  ['aiSetup', 'aiProgress', 'aiResult', 'aiDone', 'aiFailed'].forEach((id) => $(`#${id}`).classList.toggle('hidden', id !== name));
  state.ai.view = name;
}

function renderAISources() {
  const media = aiMedia();
  const list = $('#aiSourceList');
  const selected = new Set(state.ai.selected);
  list.innerHTML = media.map((item) => `
    <label><input type="checkbox" value="${item.id}" ${selected.has(item.id) ? 'checked' : ''}><span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span><small>${t('seconds', {value: Number(item.duration).toFixed(1)})}</small></label>`).join('');
  $('#aiSourceEmpty').classList.toggle('hidden', media.length > 0);
  $('#aiStart').disabled = media.length === 0;
  list.querySelectorAll('input').forEach((input) => input.addEventListener('change', () => {
    state.ai.selected = [...list.querySelectorAll('input:checked')].map((node) => node.value);
  }));
}

function renderAINotice() {
  const capabilities = state.ai.capabilities;
  if (!capabilities) return;
  const cloudOption = $('#aiMode').querySelector('option[value="cloud"]');
  cloudOption.disabled = !capabilities.cloud_available;
  if (!capabilities.cloud_available) {
    cloudOption.textContent = `${t('aiModeCloud')} · ${t('aiCloudUnavailable')}`;
    if ($('#aiMode').value === 'cloud') $('#aiMode').value = 'local';
  }
  const cloud = $('#aiMode').value === 'cloud';
  $('#aiNotice').textContent = cloud ? capabilities.cloud_notice : capabilities.local_notice;
  $('#aiConsentRow').classList.toggle('hidden', !cloud);
  const hint = $('#aiCloudHint');
  hint.classList.toggle('hidden', capabilities.cloud_available);
  if (!capabilities.cloud_available) {
    hint.textContent = '';
    if (document.querySelector('a[href="/admin/accounts"]')) {
      const link = document.createElement('a');
      link.href = '/admin/accounts'; link.textContent = t('aiCloudHintLink');
      hint.append(t('aiCloudHintAdmin'), link, t('aiCloudHintAdminTail'));
    } else hint.textContent = t('aiCloudHintEditor');
  }
}

function renderAIProgress(plan) {
  $('#aiProgressMessage').textContent = plan.message || t('aiWaiting');
  $('#aiBar').style.width = `${Math.max(3, Number(plan.progress) || 0)}%`;
}

function renderAIResult(plan) {
  const result = plan.result || {};
  const changes = result.changes || {};
  $('#aiSummary').textContent = result.summary || '';
  $('#aiChanges').innerHTML = [
    t('aiChangeReplace', {count: changes.replace_video_clips ?? 0}),
    changes.remove_overlays ? t('aiChangeOverlays', {count: changes.remove_overlays}) : '',
    changes.remove_sound_effects ? t('aiChangeSfx', {count: changes.remove_sound_effects}) : '',
    changes.preserve_background_music ? t('aiChangeMusic') : '',
    t('aiChangeSaved'),
  ].filter(Boolean).map((text) => `<li>${escapeHtml(text)}</li>`).join('');
  const notes = [...(result.warnings || []), ...(result.repairs || [])];
  $('#aiWarnings').innerHTML = notes.map((text) => `<li>${escapeHtml(text)}</li>`).join('');
  $('#aiWarnings').classList.toggle('hidden', notes.length === 0);
  $('#aiShots').innerHTML = (result.shots || []).map((shot, index) => `
    <article class="ai-shot" data-media-id="${escapeHtml(shot.media_id)}" data-start="${Number(shot.start)}" data-end="${Number(shot.end)}" title="${t('aiPreviewShot')}">
      <span class="index">${String(index + 1).padStart(2, '0')}</span>
      <div><h4 title="${escapeHtml(shot.name)}">${escapeHtml(shot.name)}</h4><p>${escapeHtml(shot.caption ? t('captionPrefix', {value: shot.caption}) : t('noCaption'))} · ${escapeHtml(shot.reason || '')}</p></div>
      <span class="range">${Number(shot.start).toFixed(2)} – ${Number(shot.end).toFixed(2)}s</span>
    </article>`).join('');
  $('#aiShots').querySelectorAll('.ai-shot').forEach((node) => node.addEventListener('click', () => {
    const media = state.media.find((item) => item.id === node.dataset.mediaId);
    if (media) preview(media.url, media.name, Number(node.dataset.start), Number(node.dataset.end));
  }));
}

function renderAI() {
  if (!state.ai || !$('#aiDialog')) return;
  renderAISources();
  renderAINotice();
  const plan = state.ai.plan;
  if (!plan) return showAIView('aiSetup');
  if (['queued', 'running'].includes(plan.status)) { renderAIProgress(plan); return showAIView('aiProgress'); }
  if (plan.status === 'ready') { renderAIResult(plan); return showAIView('aiResult'); }
  if (plan.status === 'applied') {
    $('#aiDoneMessage').textContent = t('aiAppliedMessage', {summary: plan.result?.summary || ''});
    $('#aiUndo').dataset.armed = ''; $('#aiUndo').textContent = t('aiUndo');
    return showAIView('aiDone');
  }
  if (plan.status === 'failed') { $('#aiFailedMessage').textContent = plan.error?.message || plan.message || t('aiFailed'); return showAIView('aiFailed'); }
  showAIView('aiSetup');
}

function stopAIPolling() { clearTimeout(state.ai.pollTimer); state.ai.pollTimer = null; }

async function pollAIPlan() {
  stopAIPolling();
  const plan = state.ai.plan;
  if (!plan) return;
  try {
    const latest = await api(`/api/ai/plans/${plan.id}`);
    state.ai.plan = latest;
    renderAI();
    if (['queued', 'running'].includes(latest.status)) { state.ai.pollTimer = setTimeout(pollAIPlan, 1000); return; }
    if (latest.status === 'ready') banner(t('aiReadyBanner'), 'success');
    if (latest.status === 'failed') banner(latest.error?.message || t('aiFailed'), 'error');
  } catch (error) {
    state.ai.plan = null; renderAI(); banner(error.message || t('aiExpired'), 'error');
  }
}

async function restoreAIPlan() {
  try {
    const {plans} = await api('/api/ai/plans');
    const active = (plans || []).find((plan) => ['queued', 'running', 'ready', 'applied'].includes(plan.status));
    if (!active) return;
    state.ai.plan = active;
    if (['queued', 'running'].includes(active.status)) state.ai.pollTimer = setTimeout(pollAIPlan, 800);
    else if (active.status === 'ready') banner(t('aiReadyBanner'), 'success');
  } catch (error) { /* The editor works without AI status; the panel reports errors when opened. */ }
}

async function openAIDialog() {
  $('#aiDialog').classList.remove('hidden');
  try {
    state.ai.capabilities = await api('/api/ai/capabilities');
    renderAI();
  } catch (error) { banner(error.message, 'error'); }
}

async function aiPost(action, body) {
  const plan = state.ai.plan;
  if (!plan) return;
  try {
    const options = {method: 'POST', headers: {'Content-Type': 'application/json'}};
    if (body) options.body = JSON.stringify(body);
    const result = await api(`/api/ai/plans/${plan.id}/${action}`, options);
    if (action === 'apply' || action === 'undo') {
      state.ai.plan = result.plan;
      hydrate(result);
      banner(action === 'apply' ? t('aiApplied') : t('aiUndone'), 'success');
      if (action === 'undo') { state.ai.plan = null; $('#aiDialog').classList.add('hidden'); }
    } else {
      stopAIPolling();
      state.ai.plan = null;
      banner(t('aiCancelled'));
    }
    renderAI();
  } catch (error) { banner(error.message, 'error'); }
}

$('#aiBtn').addEventListener('click', openAIDialog);
$('#aiClose').addEventListener('click', () => $('#aiDialog').classList.add('hidden'));
$('#aiMode').addEventListener('change', renderAINotice);
$('#aiSetup').addEventListener('submit', async (event) => {
  event.preventDefault();
  const mode = $('#aiMode').value;
  const available = new Set(aiMedia().map((media) => media.id));
  const body = {
    media_ids: state.ai.selected.filter((id) => available.has(id)),
    revision: Number(state.project.revision),
    mode,
    target_duration: Number($('#aiTarget').value),
    prompt: $('#aiPrompt').value.trim(),
    cloud_consent: mode === 'cloud' && $('#aiConsent').checked,
  };
  if (!body.media_ids.length) return banner(t('aiSelectSources'), 'error');
  $('#aiStart').disabled = true;
  try {
    state.ai.plan = await api('/api/ai/plans', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    renderAI();
    banner(t('aiStarted'));
    state.ai.pollTimer = setTimeout(pollAIPlan, 800);
  } catch (error) { banner(error.message, 'error'); }
  finally { $('#aiStart').disabled = aiMedia().length === 0; }
});
$('#aiCancel').addEventListener('click', () => aiPost('cancel'));
$('#aiDiscard').addEventListener('click', () => aiPost('cancel'));
$('#aiApply').addEventListener('click', () => aiPost('apply', {revision: Number(state.project.revision), confirm: true}));
$('#aiUndo').addEventListener('click', () => {
  // Two-step confirmation inside the panel instead of a blocking native dialog.
  const button = $('#aiUndo');
  if (button.dataset.armed !== '1') { button.dataset.armed = '1'; button.textContent = t('aiUndoConfirm'); return; }
  aiPost('undo', {revision: Number(state.project.revision)});
});
$('#aiNew').addEventListener('click', () => { stopAIPolling(); state.ai.plan = null; renderAI(); });
$('#aiRetry').addEventListener('click', () => { state.ai.plan = null; renderAI(); });

applyLanguage(false);
api('/api/project').then((data) => { hydrate(data); banner(t('connected'), 'success'); restoreAIPlan(); }).catch((error) => banner(error.message, 'error'));
