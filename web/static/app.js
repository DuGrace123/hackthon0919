const $ = (selector) => document.querySelector(selector);
const translations = {
  zh: {
    userGuide: '使用指南', guideNewTab: '使用指南（新标签页）',
    audioPreviewOnly: '音频可导入和预览；当前时间线仅支持视频。', accountMenu: '账户菜单', searchMedia: '搜索素材', mediaType: '素材类型', allMedia: '全部', audio: '音频',
    noResults: '没有找到素材', noResultsHint: '换个关键词，或查看全部类型。', clearFilters: '重置筛选',
    dropHere: '松开以导入素材', dropHint: '可拖入视频或音频文件', previewWelcome: '把灵感剪成故事',
    sourcePreview: '原素材预览', previewNote: '此处预览原素材，字幕与转场在导出视频中生效。', moreSettings: '转场与声音',
    reorderHint: '拖动片段调整顺序', scrollTimeline: '滚动时间线', previewMedia: '预览：{name}', addNamedMedia: '加入时间线：{name}',
    selectClip: '选择片段 {index}：{name}', moveLeft: '向前移动片段', moveRight: '向后移动片段',
    unsupportedPreview: '浏览器无法预览此格式，可尝试 H.264 编码的 MP4。', exportComplete: '视频已准备好',
    closeExportHint: '关闭后导出仍会继续，可再次点击导出查看进度。', exportUnavailable: '导出暂不可用，请在服务端配置 FFmpeg 后刷新。',
    pageTitle: '灵剪 · 网页剪辑台', projectName: '工程名称', ratio: '画幅', saveProject: '保存', exportMp4: '导出视频',
    connecting: '正在连接剪辑服务…', mediaLibrary: '素材库', importMedia: '导入', readingMedia: '正在读取媒体信息…',
    noMedia: '让故事从这里开始', noMediaHint: '导入视频或音频，挑选你想留下的片刻。', programMonitor: '预览',
    previewHint: '选择一个素材，开始预览', clipEditing: '片段设置', noClip: '为片段加一点细节', noClipHint: '在时间线上选择片段，即可裁剪、添加字幕和调整声音。',
    inPoint: '开始（秒）', outPoint: '结束（秒）', captions: '字幕', captionPlaceholder: '给这段画面写一句话…', transition: '转场',
    cut: '直接切换', fade: '淡入淡出', dissolve: '叠化', wipeLeft: '向左擦除', wipeRight: '向右擦除', slideUp: '向上滑动', slideDown: '向下滑动',
    sourceAudio: '原声', applyClip: '应用修改', deleteClip: '移除片段', resizeTimeline: '调整时间线高度', timeline: '时间线', zoom: '缩放',
    timelineZoom: '时间线缩放', emptyTimeline: '故事，还差第一个镜头', emptyTimelineHint: '点击素材旁的 ＋，将它加入时间线。', video: '视频', sourceAudioShort: '原声',
    timelineClips: '时间线片段', audioTimeline: '音频时间线', exporting: '正在导出视频', preparingRender: '正在准备渲染任务…', downloadExport: '下载导出文件', close: '关闭',
    switchLanguage: 'Switch to English', seconds: '{value} 秒', addTimeline: '加入时间线', captionPrefix: '字幕：{value}', noCaption: '无字幕', originalAudioTitle: '{name} 的原声',
    requestFailed: '请求失败（{status}）', inaccessibleMedia: '该片段不是通过网页上传，浏览器无法直接访问其本地路径。', addingMedia: '正在把素材加入时间线…',
    mediaAdded: '素材已加入时间线。', orderUpdated: '片段顺序已更新。', imported: '已导入 {count} 个素材。', clipApplied: '裁剪、字幕与转场修改已应用。',
    deleteConfirm: '确定从时间线删除这个片段吗？素材库中的原文件不会删除。', clipRemoved: '片段已从时间线移除。', projectSaved: '工程已保存。',
    exportDoneMessage: '导出完成，可以下载 MP4。', exportDoneBanner: 'MP4 导出完成。', exportFailed: '导出失败', waitingRender: '正在等待渲染…', rendering: '正在合成画面与声音，请稍候…', connected: '工作区已就绪', accounts: '账户管理', logout: '退出',
    aiDirector: 'AI 导演', aiSources: '选择参与剪辑的素材', aiNoSources: '素材库里还没有视频，请先导入视频文件。', aiMode: '分析模式', aiModeLocal: '本地分析（不上传素材）', aiModeCloud: '云端分析',
    aiCloudUnavailable: '服务端未配置', aiTarget: '目标时长（秒）', aiPrompt: '剪辑要求', aiPromptPlaceholder: '例如：按真实拍摄顺序，保留关键动作和结尾', aiConsent: '我了解云端分析会上传抽帧图片、音频和剪辑要求，并可能产生 API 费用。',
    aiStart: '生成方案', aiCancel: '取消分析', aiWaiting: '等待分析…', aiDiscard: '放弃方案', aiApply: '应用到时间线', aiUndo: '撤销应用', aiNew: '生成新方案', aiRetry: '返回重新设置', aiFailed: '分析失败', aiShotList: 'AI 镜头清单',
    aiSelectSources: '请至少选择一份视频素材。', aiStarted: 'AI 正在分析素材…', aiReadyBanner: 'AI 方案已生成，请在 AI 导演面板中预览并确认。', aiApplied: 'AI 方案已应用到时间线，工程已保存。', aiUndone: '已恢复应用前的时间线。', aiCancelled: '已放弃该方案，工程未改变。',
    aiAppliedMessage: '方案已应用：{summary}。时间线上的 AI 片段可以继续手动修改。', aiUndoConfirm: '再点一次确认撤销', aiPreviewShot: '点击在监视器中预览该镜头', aiExpired: 'AI 方案已失效，请重新生成。',
    aiChangeReplace: '替换当前时间线上的 {count} 个视频片段', aiChangeOverlays: '移除 {count} 个叠加层', aiChangeSfx: '移除 {count} 个音效', aiChangeMusic: '保留背景音乐设置', aiChangeSaved: '应用后工程会立即保存到磁盘，并可一键撤销', aiTransition: 'AI 转场：{value}',
    aiCloudHintAdmin: '云端模式尚未配置：在', aiCloudHintLink: '账户管理 → AI 接口', aiCloudHintAdminTail: '中填写服务地址和 API Key 后即可使用。', aiCloudHintEditor: '云端模式尚未配置，请联系管理员在「账户管理 → AI 接口」中填写 API 设置。',
    aiSourcesHint: '正片按拍摄时间推进；没有拍摄时间的素材按下面的先后顺序当作拍摄顺序，可用 ↑ ↓ 调整。', aiNoCaptureTime: '无拍摄时间', aiMoveUp: '上移', aiMoveDown: '下移', aiOpening: '开头方式', aiOpeningHook: '冷开场：先放最吸引人的镜头，再按时间推进', aiOpeningChrono: '纯时间顺序：不用冷开场',
    aiStyle: '导演风格', aiStyleAuto: '自动（按剪辑要求判断）', aiStyleTravel: '旅行叙事 · 目标—障碍—发现—回收', aiStyleFood: '美食教程 · 成品钩子后严格按步骤', aiStyleLife: '生活记录 · 小目标与阶段性回报', aiStyleDrama: '剧情短片 · 冲突—尝试—反转—回收', aiStyleDoc: '纪录片 · 尊重事件顺序与完整语义', aiStyleCinematic: '电影感 · 克制转场与留白', aiStyleTalk: '口播知识 · 语义优先并删除停顿',
    aiStoryTitle: '故事线', aiStructureTitle: '结构与顺序', aiTechniquesTitle: '运用的剪辑手法', aiSourcesTitle: '素材使用', aiChangesTitle: '应用后的改动', aiShotsTitle: '镜头清单：选了什么、为什么', aiCopyReport: '复制文字报告', aiReportCopied: '文字报告已复制到剪贴板。', aiReportCopyFailed: '无法访问剪贴板，请手动选择文字复制。',
    aiShotsUsed: '选用 {count} 个镜头 / {seconds} 秒', aiUnused: '未选用', aiReasonPrefix: '理由：{value}', aiChapterPrefix: '章节：{value}', aiTransitionPrefix: '转场：{value}', aiDuration: '{value} 秒', aiSummaryPrefix: '内容：{value}',
    roleHook: '冷开场钩子', roleSetup: '铺垫', roleDevelopment: '发展', roleClimax: '高潮', roleOutro: '收尾', roleBroll: '空镜',
    aiVerdictOk: '✓ 方案可以应用', aiVerdictBlocked: '⛔ 方案已阻止', aiEstimated: '预计 {value} 秒', aiChronology: '正文顺序一致率 {value}%', aiOpeningTitle: '高级开篇方案 · 可整套切换，无需手调蒙版', aiOpeningAbout: '约 {value} 秒',
    aiOpeningWritten: '已自动写入前 {count} 个镜头的蒙版、位置、羽化和转场；{overlays} 个独立叠加层、{sounds} 个开篇音效。', aiGlobalLine: '全片创意编排：{accents} 个重点事件 · 自动配乐 {music}。', aiApplyFull: '应用完整方案到时间线',
    aiNoteFull: '方案中的蒙版、高级转场、叠加层、音效与配乐会随镜头一起应用到时间线（已有背景音乐则保留）。确认仅替换一次时间线；之后仍可删减或在检查器修改，并可一键撤销。', aiChangeAdd: '新增 {overlays} 个叠加层与 {sfx} 个音效', aiChangeMusicSet: '自动配乐「{name}」', aiShotCards: '镜头卡片（点击可在监视器预览）',
    deleteNamedConfirm: '确定从时间线移除「{name}」吗？素材库中的原文件不会删除。',
    removeMedia: '删除素材', removeNamedMedia: '删除素材：{name}', removeMediaConfirm: '确定删除素材 {name} 吗？文件会从素材库中删除，无法恢复。', mediaRemoved: '已删除素材 {name}。', mediaInUse: '{name} 正在时间线上使用，请先从时间线移除。',
    aiMaskPrefix: '蒙版：{value}', aiMotionPrefix: '动效：{value}', aiPresetSwitching: '正在切换开篇方案…', aiPresetSwitched: '开篇方案已切换：{name}', timelineExtras: 'V2+ 叠加 {overlays} · 音效 {sfx} · 配乐 {music}', noMusic: '无',
    aiLocalNotice: '本地模式按场景和时长选片，不上传素材、不生成语音字幕。', aiCloudNotice: '云端分析会发送抽帧图片、音频和剪辑要求，可能产生 API 费用。', aiLanguageMismatch: '该方案是在另一种界面语言下生成的；重新生成即可获得当前语言的报告。'
  },
  en: {
    userGuide: 'Guide', guideNewTab: 'User guide in Chinese (opens a new tab)',
    audioPreviewOnly: 'Audio supports import and preview. The timeline currently accepts video only.', accountMenu: 'Account menu', searchMedia: 'Search media', mediaType: 'Media type', allMedia: 'All', audio: 'Audio',
    noResults: 'No matching media', noResultsHint: 'Try another keyword or check all media types.', clearFilters: 'Clear filters',
    dropHere: 'Drop to import', dropHint: 'Drop video or audio files here', previewWelcome: 'Make room for your story',
    sourcePreview: 'Source preview', previewNote: 'Source preview. Captions and transitions appear in the exported video.', moreSettings: 'Transitions & audio',
    reorderHint: 'Drag clips to reorder', scrollTimeline: 'Scroll timeline', previewMedia: 'Preview: {name}', addNamedMedia: 'Add to timeline: {name}',
    selectClip: 'Select clip {index}: {name}', moveLeft: 'Move clip earlier', moveRight: 'Move clip later',
    unsupportedPreview: 'Your browser cannot preview this format. Try an H.264 MP4.', exportComplete: 'Your video is ready',
    closeExportHint: 'Export continues when closed. Click Export again to see its progress.', exportUnavailable: 'Export unavailable. Configure FFmpeg on the server and refresh.',
    pageTitle: 'LingJian · Web Editing Studio', projectName: 'Project', ratio: 'Aspect ratio', saveProject: 'Save', exportMp4: 'Export',
    connecting: 'Connecting to the local editing service…', mediaLibrary: 'Media', importMedia: 'Import', readingMedia: 'Reading media information…',
    noMedia: 'No media yet', noMediaHint: 'Import video or audio, then add the shots you need to the timeline.', programMonitor: 'Preview',
    previewHint: 'Select media or a timeline clip to preview it', clipEditing: 'Clip settings', noClip: 'No clip selected', noClipHint: 'Select a timeline clip to trim it or adjust captions and transitions.',
    inPoint: 'In point (sec)', outPoint: 'Out point (sec)', captions: 'Caption', captionPlaceholder: 'Enter a clip caption', transition: 'Transition',
    cut: 'Cut', fade: 'Fade', dissolve: 'Dissolve', wipeLeft: 'Wipe Left', wipeRight: 'Wipe Right', slideUp: 'Slide Up', slideDown: 'Slide Down',
    sourceAudio: 'Source audio', applyClip: 'Apply changes', deleteClip: 'Remove clip', resizeTimeline: 'Resize timeline height', timeline: 'Timeline', zoom: 'Zoom',
    timelineZoom: 'Timeline zoom', emptyTimeline: 'Timeline is empty', emptyTimelineHint: 'Click + next to a media file to add your first clip.', video: 'Video', sourceAudioShort: 'Audio',
    timelineClips: 'Timeline clips', audioTimeline: 'Audio timeline', exporting: 'Exporting MP4', preparingRender: 'Preparing the render job…', downloadExport: 'Download Export', close: 'Close',
    switchLanguage: '切换到中文', seconds: '{value} sec', addTimeline: 'Add to Timeline', captionPrefix: 'Caption: {value}', noCaption: 'No caption', originalAudioTitle: '{name} source audio',
    requestFailed: 'Request failed ({status})', inaccessibleMedia: 'This clip was not uploaded through the web app, so the browser cannot access its local path.', addingMedia: 'Adding media to the timeline…',
    mediaAdded: 'Media added to the timeline.', orderUpdated: 'Clip order updated.', imported: 'Imported {count} media file(s).', clipApplied: 'Trim, caption, and transition changes applied.',
    deleteConfirm: 'Remove this clip from the timeline? The original file will remain in the media pool.', clipRemoved: 'Clip removed from the timeline.', projectSaved: 'Project saved.',
    exportDoneMessage: 'Export complete. Your MP4 is ready to download.', exportDoneBanner: 'MP4 export complete.', exportFailed: 'Export failed', waitingRender: 'Waiting to render…', rendering: 'Putting your video together. Please wait…', connected: 'Workspace ready', accounts: 'Accounts', logout: 'Sign Out',
    aiDirector: 'AI Director', aiSources: 'Choose source clips', aiNoSources: 'No video in the media pool yet. Import a video file first.', aiMode: 'Analysis mode', aiModeLocal: 'Local analysis (nothing uploaded)', aiModeCloud: 'Cloud analysis',
    aiCloudUnavailable: 'not configured on the server', aiTarget: 'Target duration (sec)', aiPrompt: 'Editing brief', aiPromptPlaceholder: 'e.g. Keep the real shooting order, keep key actions and the ending', aiConsent: 'I understand cloud analysis uploads sampled frames, audio and my brief, and may incur API charges.',
    aiStart: 'Generate Plan', aiCancel: 'Cancel analysis', aiWaiting: 'Waiting for analysis…', aiDiscard: 'Discard Plan', aiApply: 'Apply to Timeline', aiUndo: 'Undo Apply', aiNew: 'New Plan', aiRetry: 'Back to Settings', aiFailed: 'Analysis failed', aiShotList: 'AI shot list',
    aiSelectSources: 'Select at least one video source.', aiStarted: 'AI is analyzing the footage…', aiReadyBanner: 'AI plan is ready. Review and confirm it in the AI Director panel.', aiApplied: 'AI plan applied to the timeline and the project was saved.', aiUndone: 'Timeline restored to the state before the plan was applied.', aiCancelled: 'Plan discarded. The project is unchanged.',
    aiAppliedMessage: 'Plan applied: {summary}. AI clips on the timeline can still be edited by hand.', aiUndoConfirm: 'Click again to confirm undo', aiPreviewShot: 'Click to preview this shot in the monitor', aiExpired: 'The AI plan is no longer available. Generate a new one.',
    aiChangeReplace: 'Replace {count} video clip(s) on the current timeline', aiChangeOverlays: 'Remove {count} overlay(s)', aiChangeSfx: 'Remove {count} sound effect(s)', aiChangeMusic: 'Keep the background music settings', aiChangeSaved: 'The project is saved to disk right after applying and can be undone in one click', aiTransition: 'AI transition: {value}',
    aiCloudHintAdmin: 'Cloud mode is not configured yet: open ', aiCloudHintLink: 'Accounts → AI Service', aiCloudHintAdminTail: ' and enter the service URL and API key.', aiCloudHintEditor: 'Cloud mode is not configured yet. Ask an administrator to enter the API settings under Accounts → AI Service.',
    aiSourcesHint: 'The body follows capture time; clips without a capture time use the order below as their shooting order (↑ ↓ to adjust).', aiNoCaptureTime: 'no capture time', aiMoveUp: 'Move up', aiMoveDown: 'Move down', aiOpening: 'Opening', aiOpeningHook: 'Cold open: strongest shot first, then chronological', aiOpeningChrono: 'Strict chronological: no cold open',
    aiStyle: 'Directing style', aiStyleAuto: 'Auto (from the brief)', aiStyleTravel: 'Travel story · goal—obstacle—discovery—payoff', aiStyleFood: 'Food tutorial · result hook, then strict steps', aiStyleLife: 'Life vlog · small goals and payoffs', aiStyleDrama: 'Short drama · conflict—attempt—twist—payoff', aiStyleDoc: 'Documentary · respect event order and meaning', aiStyleCinematic: 'Cinematic · restrained transitions and space', aiStyleTalk: 'Talking head · meaning first, cut pauses',
    aiStoryTitle: 'Story line', aiStructureTitle: 'Structure and order', aiTechniquesTitle: 'Editing techniques used', aiSourcesTitle: 'Source usage', aiChangesTitle: 'Changes when applied', aiShotsTitle: 'Shot list: what was chosen and why', aiCopyReport: 'Copy text report', aiReportCopied: 'Text report copied to the clipboard.', aiReportCopyFailed: 'Clipboard unavailable. Select the text and copy it manually.',
    aiShotsUsed: '{count} shot(s) / {seconds} sec used', aiUnused: 'not used', aiReasonPrefix: 'Why: {value}', aiChapterPrefix: 'Chapter: {value}', aiTransitionPrefix: 'Transition: {value}', aiDuration: '{value} sec', aiSummaryPrefix: 'Content: {value}',
    roleHook: 'Cold open', roleSetup: 'Setup', roleDevelopment: 'Development', roleClimax: 'Climax', roleOutro: 'Outro', roleBroll: 'B-roll',
    aiVerdictOk: '✓ Plan can be applied', aiVerdictBlocked: '⛔ Plan blocked', aiEstimated: 'about {value} sec', aiChronology: 'body chronology {value}%', aiOpeningTitle: 'Advanced opening · switch as a set, no manual masks', aiOpeningAbout: 'about {value} sec',
    aiOpeningWritten: 'Masks, positions, feathering and transitions were written into the first {count} shot(s); {overlays} overlay layer(s), {sounds} opening sound cue(s).', aiGlobalLine: 'Whole-film treatment: {accents} accent event(s) · music {music}.', aiApplyFull: 'Apply Full Plan to Timeline',
    aiNoteFull: 'Masks, advanced transitions, overlays, sound cues and music are applied together with the shots (existing background music is kept). Confirming replaces the timeline once; you can still trim or edit in the inspector afterwards, and undo in one click.', aiChangeAdd: 'adds {overlays} overlay(s) and {sfx} sound cue(s)', aiChangeMusicSet: 'music “{name}”', aiShotCards: 'Shot cards (click to preview in the monitor)',
    deleteNamedConfirm: 'Remove “{name}” from the timeline? The original file stays in the media pool.',
    removeMedia: 'Delete media', removeNamedMedia: 'Delete media: {name}', removeMediaConfirm: 'Delete {name}? The file is removed from the media pool and cannot be recovered.', mediaRemoved: 'Deleted {name}.', mediaInUse: '{name} is on the timeline. Remove it from the timeline first.',
    aiMaskPrefix: 'Mask: {value}', aiMotionPrefix: 'Motion: {value}', aiPresetSwitching: 'Switching the opening preset…', aiPresetSwitched: 'Opening preset switched: {name}', timelineExtras: 'V2+ overlays {overlays} · SFX {sfx} · music {music}', noMusic: 'none',
    aiLocalNotice: 'Local mode picks shots by scene changes and duration; nothing is uploaded and no speech captions are generated.', aiCloudNotice: 'Cloud analysis sends sampled frames, audio and your brief to the AI service and may incur API charges.', aiLanguageMismatch: 'This plan was generated in the other interface language. Generate a new plan to get the report in the current language.'
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
  mediaFilter: 'all',
  mediaQuery: '',
  previewMediaId: null,
  previewClipId: null,
  uploading: false,
  exportJob: null,
  exportReady: false,
  loaded: false,
  selectedClipId: null,
  previewEnd: null,
  currentPreviewTitle: null,
  draggedClipId: null,
  timelineScale: Math.max(35, Math.min(150, Number(localStorage.getItem('lingjian-timeline-scale')) || 70)),
  lang: localStorage.getItem('lingjian-language') === 'en' ? 'en' : 'zh',
  csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || '',
  ai: {capabilities: null, plan: null, pollTimer: null, selected: [], order: [], sources: [], view: 'aiSetup'},
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
  if (shouldRender) {
    // Translate labels without discarding edits waiting for Apply.
    $('#timelineDuration').textContent = t('seconds', {value: Number(state.project.duration || 0).toFixed(1)});
    renderMedia();
    renderTimeline();
    renderAI();
  }
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
  if ($('#aiDialog').open) {
    $('#aiError').textContent = message;
    $('#aiError').classList.toggle('hidden', type !== 'error');
  }
  const key = Object.keys(translations[state.lang]).find((name) => translations[state.lang][name] === message);
  if (key) node.dataset.i18n = key;
  else node.removeAttribute('data-i18n');
}

function formatTime(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  return `${String(minutes).padStart(2, '0')}:${(value % 60).toFixed(3).padStart(6, '0')}`;
}

function escapeHtml(value) {
  const node = document.createElement('div');
  node.textContent = String(value ?? '');
  return node.innerHTML.replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-${name}"></use></svg>`;
}

function hydrate(data) {
  state.project = data.project;
  state.media = data.media;
  if (!state.project.clips.some((clip) => clip.id === state.selectedClipId)) state.selectedClipId = null;
  state.loaded = true;
  render();
}

function render() {
  if (document.activeElement !== $('#projectTitle')) $('#projectTitle').value = state.project.title || '';
  if (document.activeElement !== $('#projectRatio')) $('#projectRatio').value = state.project.ratio || '9:16';
  $('#saveBtn').disabled = !state.loaded;
  $('#aiBtn').disabled = !state.loaded;
  $('#exportBtn').disabled = !state.loaded || !state.exportReady || !state.project.clips.length;
  $('#clipCount').textContent = state.project.clips.length;
  $('#timelineDuration').textContent = t('seconds', {value: Number(state.project.duration || 0).toFixed(1)});
  const extras = $('#timelineExtras');
  if (extras) {
    const hasExtras = Number(state.project.overlay_count) || Number(state.project.sfx_count) || state.project.bgm_name;
    extras.classList.toggle('hidden', !hasExtras);
    if (hasExtras) extras.textContent = t('timelineExtras', {overlays: state.project.overlay_count || 0, sfx: state.project.sfx_count || 0, music: state.project.bgm_name || t('noMusic')});
  }
  renderMedia();
  renderTimeline();
  renderInspector();
}

function renderMedia() {
  const matches = state.media.filter((media) => {
    const type = media.width > 0 ? 'video' : 'audio';
    return (state.mediaFilter === 'all' || state.mediaFilter === type)
      && media.name.toLocaleLowerCase().includes(state.mediaQuery.toLocaleLowerCase().trim());
  });
  $('#mediaCount').textContent = state.media.length;
  $('#audioNotice').classList.toggle('hidden', state.mediaFilter !== 'audio');
  $('#mediaEmpty').classList.toggle('hidden', state.media.length > 0);
  $('#searchEmpty').classList.toggle('hidden', !state.media.length || matches.length > 0);
  document.querySelectorAll('[data-filter]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.filter === state.mediaFilter)));
  const grid = $('#mediaGrid');
  grid.innerHTML = matches.map((media) => `
    <article class="media-card ${media.id === state.previewMediaId ? 'previewing' : ''}" data-media-id="${escapeHtml(media.id)}">
      <button type="button" class="media-preview" aria-label="${escapeHtml(t('previewMedia', {name: media.name}))}" title="${escapeHtml(media.name)}">
        <span class="media-icon ${media.width ? '' : 'audio'}">${icon(media.width ? 'film' : 'music')}</span>
        <span class="media-info"><strong>${escapeHtml(media.name)}</strong><small>${t('seconds', {value: Number(media.duration).toFixed(1)})} · ${media.width ? `${media.width} × ${media.height}` : t('audio')}</small></span>
      </button>
      <button type="button" class="remove-media" data-action="remove-media" aria-label="${escapeHtml(t('removeNamedMedia', {name: media.name}))}" title="${escapeHtml(t('removeMedia'))}">${icon('trash')}</button>
      <button type="button" class="add-media" data-action="add-media" ${media.width ? '' : 'disabled'} aria-label="${escapeHtml(t(media.width ? 'addNamedMedia' : 'audioPreviewOnly', {name: media.name}))}" title="${t(media.width ? 'addTimeline' : 'audioPreviewOnly')}">${icon('plus')}</button>
    </article>`).join('');
  grid.querySelectorAll('.media-card').forEach((card) => {
    const media = state.media.find((item) => item.id === card.dataset.mediaId);
    card.querySelector('.media-preview').addEventListener('click', () => {
      preview(media.url, media.name, 0, media.duration, null, media.id);
      // Updating the highlight in place preserves keyboard focus.
      grid.querySelectorAll('.media-card').forEach((item) => item.classList.toggle('previewing', item === card));
    });
    const add = card.querySelector('[data-action="add-media"]');
    add.addEventListener('click', () => addMedia(media.id, add));
    card.querySelector('[data-action="remove-media"]').addEventListener('click', () => removeMedia(media));
  });
}

async function removeMedia(media) {
  const inUse = (state.project.clips || []).some((clip) => clip.media_id === media.id);
  if (inUse) return banner(t('mediaInUse', {name: media.name}), 'error');
  if (!confirm(t('removeMediaConfirm', {name: media.name}))) return;
  try {
    hydrate(await api(`/api/media/${media.id}`, {method: 'DELETE'}));
    if (state.previewMediaId === media.id) { state.previewMediaId = null; }
    banner(t('mediaRemoved', {name: media.name}), 'success');
  } catch (error) { banner(error.message, 'error'); }
}

function renderTimeline() {
  const focusedClip = document.activeElement?.closest('.timeline-clip');
  const focusedId = focusedClip?.dataset.clipId;
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
  const width = (clip) => Math.max(1, Number(clip.duration) * state.timelineScale);
  timeline.innerHTML = clips.map((clip, index) => `
    <article draggable="true" class="timeline-clip ${clip.id === state.selectedClipId ? 'selected' : ''}" data-clip-id="${escapeHtml(clip.id)}" style="--clip-width:${width(clip)}px">
      <button type="button" class="clip-select" aria-pressed="${clip.id === state.selectedClipId}" aria-label="${escapeHtml(t('selectClip', {index: index + 1, name: clip.name}))}" title="${escapeHtml(clip.name)}">
        <strong>${String(index + 1).padStart(2, '0')} · ${escapeHtml(clip.name)}${clip.ai_selected ? '<span class="ai-badge">AI</span>' : ''}</strong><small>${t('seconds', {value: Number(clip.duration).toFixed(1)})}${clip.caption ? ` · ${escapeHtml(clip.caption)}` : ''}</small>
      </button>
      <div class="timeline-actions"><button type="button" data-move="-1" aria-label="${t('moveLeft')}" ${index === 0 ? 'disabled' : ''}>${icon('left')}</button><button type="button" data-move="1" aria-label="${t('moveRight')}" ${index === clips.length - 1 ? 'disabled' : ''}>${icon('right')}</button><button type="button" class="danger" data-remove-clip aria-label="${escapeHtml(t('deleteClip'))}" title="${escapeHtml(t('deleteClip'))}">${icon('trash')}</button></div>
    </article>`).join('');
  audioTrack.innerHTML = clips.map((clip) => `<div class="audio-segment ${clip.has_audio ? '' : 'silent'}" style="--clip-width:${width(clip)}px">${clip.has_audio ? `${icon('music')}<span>${escapeHtml(clip.name)}</span>` : ''}</div>`).join('');
  updatePlayhead();
  timeline.querySelectorAll('.timeline-clip').forEach((node) => {
    node.querySelector('.clip-select').addEventListener('click', () => selectClip(node.dataset.clipId));
    node.querySelectorAll('[data-move]').forEach((button) => button.addEventListener('click', () => moveClip(node.dataset.clipId, Number(button.dataset.move))));
    node.querySelector('[data-remove-clip]').addEventListener('click', (event) => { event.stopPropagation(); removeClip(node.dataset.clipId); });
    node.addEventListener('keydown', (event) => {
      if ((event.key === 'Delete' || event.key === 'Backspace') && !event.target.closest('input, textarea')) { event.preventDefault(); removeClip(node.dataset.clipId); }
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
  if (focusedId) {
    const target = [...timeline.querySelectorAll('.timeline-clip')].find((node) => node.dataset.clipId === focusedId);
    target?.querySelector('.clip-select').focus({preventScroll: true});
  }
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

function selectClip(id) {
  const clip = state.project.clips.find((item) => item.id === id);
  if (!clip) return;
  state.selectedClipId = id;
  preview(clip.media_url, clip.name, clip.start, clip.end, id, clip.media_id);
  document.querySelectorAll('.timeline-clip').forEach((node) => {
    const selected = node.dataset.clipId === id;
    node.classList.toggle('selected', selected);
    node.querySelector('.clip-select').setAttribute('aria-pressed', String(selected));
  });
  renderInspector();
}

function preview(url, title, start = 0, end = null, clipId = null, mediaId = null) {
  if (!url) return banner(t('inaccessibleMedia'), 'error');
  const player = $('#player');
  player.pause();
  state.previewClipId = clipId;
  state.previewMediaId = mediaId;
  const seek = () => { player.currentTime = Math.max(0, Number(start) || 0); updatePlayhead(); };
  player.onloadedmetadata = seek;
  if (player.getAttribute('src') !== url) player.src = url;
  else if (player.readyState >= 1) seek();
  state.previewEnd = end == null ? null : Number(end);
  state.currentPreviewTitle = title;
  $('#playerTitle').textContent = title;
  $('#playerEmpty').classList.add('hidden');
  player.classList.remove('hidden');
  $('.player-shell').classList.add('has-media');
  $('#audioPreview').classList.toggle('hidden', Boolean(state.media.find((media) => media.id === mediaId)?.width));
  updatePlayhead();
}

function updatePlayhead() {
  const player = $('#player');
  $('#timeReadout').textContent = formatTime(player.currentTime);
  const selectedIndex = state.project.clips.findIndex((clip) => clip.id === state.previewClipId);
  $('#playhead').classList.toggle('hidden', selectedIndex < 0);
  if (selectedIndex < 0) return;
  const selected = state.project.clips[selectedIndex];
  const before = state.project.clips.slice(0, selectedIndex).reduce((sum, clip) => sum + Number(clip.duration || 0), 0);
  const relative = Math.min(Number(selected.duration), Math.max(0, player.currentTime - Number(selected.start || 0)));
  $('#playhead').style.setProperty('--playhead-x', `${(before + relative) * state.timelineScale}px`);
}

async function addMedia(mediaId, button) {
  if (button.disabled) return;
  button.disabled = true;
  try {
    banner(t('addingMedia'));
    hydrate(await api('/api/timeline/clips', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({media_id: mediaId})}));
    const added = state.project.clips.at(-1);
    if (added) selectClip(added.id);
    banner(t('mediaAdded'), 'success');
  } catch (error) { banner(error.message, 'error'); }
  finally { button.disabled = false; }
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
  // Let Save and Export stop on validation/network errors instead of reporting success.
  const data = await api('/api/project', {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: $('#projectTitle').value, ratio: $('#projectRatio').value})});
  state.project = data.project;
}

async function uploadFiles(files) {
  if (!files.length || state.uploading) return;
  state.uploading = true;
  $('#importBtn').disabled = true;
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  $('#uploadProgress').classList.remove('hidden');
  try {
    await api('/api/media/upload', {method: 'POST', body: form});
    state.mediaQuery = '';
    state.mediaFilter = 'all';
    $('#mediaSearch').value = '';
    hydrate(await api('/api/project'));
    banner(t('imported', {count: files.length}), 'success');
  } catch (error) { banner(error.message, 'error'); }
  finally {
    state.uploading = false;
    $('#importBtn').disabled = false;
    $('#uploadProgress').classList.add('hidden');
    $('#uploadInput').value = '';
  }
}

$('#uploadInput').addEventListener('change', (event) => uploadFiles([...event.target.files]));
$('#importBtn').addEventListener('click', () => $('#uploadInput').click());
document.querySelectorAll('[data-import]').forEach((button) => button.addEventListener('click', () => $('#uploadInput').click()));
$('#mediaSearch').addEventListener('input', (event) => { state.mediaQuery = event.target.value; renderMedia(); });
document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => { state.mediaFilter = button.dataset.filter; renderMedia(); }));
$('#clearSearch').addEventListener('click', () => {
  state.mediaQuery = ''; state.mediaFilter = 'all'; $('#mediaSearch').value = ''; renderMedia(); $('#mediaSearch').focus();
});
const dropzone = $('#mediaDropzone');
let dragDepth = 0;
dropzone.addEventListener('dragenter', (event) => {
  if (!event.dataTransfer.types.includes('Files')) return;
  event.preventDefault(); dragDepth += 1; dropzone.classList.add('drag-over');
});
dropzone.addEventListener('dragover', (event) => {
  if (!event.dataTransfer.types.includes('Files')) return;
  event.preventDefault(); event.dataTransfer.dropEffect = 'copy';
});
dropzone.addEventListener('dragleave', () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) dropzone.classList.remove('drag-over'); });
dropzone.addEventListener('drop', (event) => {
  event.preventDefault(); dragDepth = 0; dropzone.classList.remove('drag-over'); uploadFiles([...event.dataTransfer.files]);
});
// A missed drop should never navigate away from an unsaved project.
window.addEventListener('dragover', (event) => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); });
window.addEventListener('drop', (event) => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); });

$('#clipForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    hydrate(await api(`/api/timeline/clips/${state.selectedClipId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({start: Number($('#clipStart').value), end: Number($('#clipEnd').value), caption: $('#clipCaption').value, transition: $('#clipTransition').value, volume: Number($('#clipVolume').value)})}));
    if (state.previewClipId === state.selectedClipId) selectClip(state.selectedClipId);
    banner(t('clipApplied'), 'success');
  } catch (error) { banner(error.message, 'error'); }
});

async function removeClip(clipId) {
  const clip = (state.project.clips || []).find((item) => item.id === clipId);
  if (!clip || !confirm(t('deleteNamedConfirm', {name: clip.name}))) return;
  try {
    hydrate(await api(`/api/timeline/clips/${clipId}`, {method: 'DELETE'}));
    if (state.selectedClipId === clipId) state.selectedClipId = null;
    render(); banner(t('clipRemoved'), 'success');
  } catch (error) { banner(error.message, 'error'); }
}

$('#deleteClipBtn').addEventListener('click', () => { if (state.selectedClipId) removeClip(state.selectedClipId); });

$('#saveBtn').addEventListener('click', async () => {
  const button = $('#saveBtn'); button.disabled = true;
  try { await updateProject(); await api('/api/project/save', {method: 'POST'}); banner(t('projectSaved'), 'success'); }
  catch (error) { banner(error.message, 'error'); }
  finally { button.disabled = false; }
});

$('#projectTitle').addEventListener('change', () => updateProject().catch((error) => banner(error.message, 'error')));
$('#projectRatio').addEventListener('change', () => updateProject().catch((error) => banner(error.message, 'error')));

$('#languageToggle').addEventListener('click', () => {
  state.lang = state.lang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('lingjian-language', state.lang);
  applyLanguage();
});
$('#logoutBtn').addEventListener('click', async () => {
  try {
    await api('/api/auth/logout', {method: 'POST'});
    window.location.assign('/login');
  } catch (error) { banner(error.message, 'error'); }
});
$('#clipVolume').addEventListener('input', () => { $('#volumeValue').textContent = `${Math.round(Number($('#clipVolume').value) * 100)}%`; });
$('#player').addEventListener('timeupdate', () => {
  updatePlayhead();
  if (state.previewEnd != null && $('#player').currentTime >= state.previewEnd) $('#player').pause();
});
$('#player').addEventListener('error', () => banner(t('unsupportedPreview'), 'error'));

$('#timelineZoom').value = String(state.timelineScale);
$('#timelineZoom').addEventListener('input', (event) => {
  state.timelineScale = Number(event.target.value);
  localStorage.setItem('lingjian-timeline-scale', String(state.timelineScale));
  renderTimeline();
});

const splitter = $('#timelineSplitter');
function setTimelineHeight(value) {
  const maximum = Math.min(480, Math.max(210, window.innerHeight - 380));
  const height = Math.max(190, Math.min(maximum, Number(value) || 250));
  splitter.setAttribute('aria-valuemin', '190');
  splitter.setAttribute('aria-valuemax', String(maximum));
  splitter.setAttribute('aria-valuenow', String(Math.round(height)));
  document.documentElement.style.setProperty('--timeline-height', `${height}px`);
  localStorage.setItem('lingjian-timeline-height', String(Math.round(height)));
}
setTimelineHeight(Number(localStorage.getItem('lingjian-timeline-height') || 250));
window.addEventListener('resize', () => setTimelineHeight(localStorage.getItem('lingjian-timeline-height')));
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

function exportFailed(error) {
  state.exportJob = null;
  $('#exportSpinner').classList.add('hidden');
  $('#exportHeading').textContent = t('exportFailed');
  $('#exportMessage').textContent = error.message;
  banner(error.message, 'error');
}

async function pollExport(statusUrl) {
  // Each poll handles its own rejection, including failures after the first timer.
  try {
    const job = await api(statusUrl);
    $('#exportBar').style.width = `${Math.max(0, Math.min(100, Number(job.progress) || 0))}%`;
    if (job.status === 'error') throw new Error(job.message || t('exportFailed'));
    if (job.status === 'done') {
      state.exportJob = null;
      $('#exportSpinner').classList.add('hidden');
      $('#exportHeading').textContent = t('exportComplete');
      $('#exportMessage').textContent = t('exportDoneMessage');
      $('#downloadLink').href = job.download_url;
      $('#downloadLink').classList.remove('hidden');
      banner(t('exportDoneBanner'), 'success');
      return;
    }
    $('#exportMessage').textContent = `${t(job.status === 'queued' ? 'waitingRender' : 'rendering')} ${t('closeExportHint')}`;
    setTimeout(() => pollExport(statusUrl), 1200);
  } catch (error) { exportFailed(error); }
}

$('#exportBtn').addEventListener('click', async () => {
  $('#exportDialog').showModal();
  if (state.exportJob) return;
  state.exportJob = 'starting';
  $('#exportSpinner').classList.remove('hidden');
  $('#exportHeading').textContent = t('exporting');
  $('#exportMessage').textContent = t('preparingRender');
  $('#downloadLink').classList.add('hidden');
  $('#exportBar').style.width = '3%';
  try {
    await updateProject();
    const task = await api('/api/export', {method: 'POST'});
    state.exportJob = task.status_url;
    await pollExport(task.status_url);
  } catch (error) { exportFailed(error); }
});
$('#closeExport').addEventListener('click', () => $('#exportDialog').close());
document.addEventListener('click', (event) => { if (!event.target.closest('.account-menu')) $('.account-menu').open = false; });
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') $('.account-menu').open = false; });

// ---------------------------------------------------------------- AI director
function aiMedia() { return state.media.filter((media) => Number(media.width) > 0); }

function showAIView(name) {
  ['aiSetup', 'aiProgress', 'aiResult', 'aiDone', 'aiFailed'].forEach((id) => $(`#${id}`).classList.toggle('hidden', id !== name));
  state.ai.view = name;
}

function aiSourceInfo(id) { return state.ai.sources.find((item) => item.id === id) || {}; }

function syncAIOrder() {
  // Keep the user's manual order; new media joins sorted by capture time, then name.
  const ids = aiMedia().map((media) => media.id);
  const known = state.ai.order.filter((id) => ids.includes(id));
  const fresh = ids.filter((id) => !known.includes(id)).sort((a, b) => {
    const ta = aiSourceInfo(a).capture_time || '', tb = aiSourceInfo(b).capture_time || '';
    if (ta !== tb) return (ta === '' ? 1 : tb === '' ? -1 : ta.localeCompare(tb));
    return String(aiSourceInfo(a).name || '').localeCompare(String(aiSourceInfo(b).name || ''));
  });
  state.ai.order = [...known, ...fresh];
}

function renderAISources() {
  syncAIOrder();
  const list = $('#aiSourceList');
  const selected = new Set(state.ai.selected);
  const rows = state.ai.order.map((id, index) => {
    const media = state.media.find((item) => item.id === id) || {};
    const info = aiSourceInfo(id);
    return `
    <div class="ai-source-item" data-id="${id}">
      <input type="checkbox" value="${id}" ${selected.has(id) ? 'checked' : ''} aria-label="${escapeHtml(media.name || '')}">
      <span class="name" title="${escapeHtml(media.name || '')}">${index + 1}. ${escapeHtml(media.name || '')}</span>
      <small>${t('seconds', {value: Number(media.duration || 0).toFixed(1)})} · ${info.capture_time ? escapeHtml(info.capture_time) : t('aiNoCaptureTime')}</small>
      <span class="move"><button type="button" data-move="-1" title="${t('aiMoveUp')}" ${index === 0 ? 'disabled' : ''}>↑</button><button type="button" data-move="1" title="${t('aiMoveDown')}" ${index === state.ai.order.length - 1 ? 'disabled' : ''}>↓</button></span>
    </div>`;
  });
  list.innerHTML = rows.join('');
  $('#aiSourceEmpty').classList.toggle('hidden', state.ai.order.length > 0);
  $('#aiStart').disabled = state.ai.order.length === 0;
  list.querySelectorAll('input').forEach((input) => input.addEventListener('change', () => {
    state.ai.selected = [...list.querySelectorAll('input:checked')].map((node) => node.value);
  }));
  list.querySelectorAll('[data-move]').forEach((button) => button.addEventListener('click', () => {
    const id = button.closest('.ai-source-item').dataset.id;
    const from = state.ai.order.indexOf(id), to = from + Number(button.dataset.move);
    if (from < 0 || to < 0 || to >= state.ai.order.length) return;
    [state.ai.order[from], state.ai.order[to]] = [state.ai.order[to], state.ai.order[from]];
    renderAISources();
  }));
}

function roleLabel(role) {
  const key = `role${String(role || 'development').charAt(0).toUpperCase()}${String(role || 'development').slice(1)}`;
  return translations[state.lang]?.[key] ? t(key) : String(role || '');
}

function transitionLabel(value) {
  const map = {none: 'cut', cut: 'cut', fade: 'fade', dissolve: 'dissolve', wipe_left: 'wipeLeft', wipeleft: 'wipeLeft', wipe_right: 'wipeRight', wiperight: 'wipeRight', slide_left: 'slideUp', slide_right: 'slideDown'};
  return map[value] ? t(map[value]) : String(value || 'cut');
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
  $('#aiNotice').textContent = t(cloud ? 'aiCloudNotice' : 'aiLocalNotice');
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
  const validation = result.validation || {ok: true, blockers: [], chronology_ratio: 1, duration: result.duration};
  const verdict = $('#aiVerdict');
  verdict.className = `ai-verdict ${validation.ok ? '' : 'blocked'}`;
  verdict.innerHTML = `${escapeHtml(t(validation.ok ? 'aiVerdictOk' : 'aiVerdictBlocked'))}<small>${escapeHtml(t('aiEstimated', {value: Number(validation.duration || result.duration || 0).toFixed(1)}))} · ${escapeHtml(t('aiChronology', {value: Math.round(Number(validation.chronology_ratio ?? 1) * 100)}))} · ${escapeHtml(result.summary || '')}</small>`;
  $('#aiBlockers').innerHTML = (validation.blockers || []).map((text) => `<li>${escapeHtml(text)}</li>`).join('');
  $('#aiBlockers').classList.toggle('hidden', !(validation.blockers || []).length);

  const creative = result.creative || {};
  const presets = result.opening_presets || [];
  const select = $('#aiPreset');
  select.innerHTML = presets.map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.name)}</option>`).join('');
  select.value = creative.requested || 'smart';
  $('#aiOpeningName').textContent = creative.name || '';
  $('#aiOpeningDuration').textContent = creative.name ? t('aiOpeningAbout', {value: Number(creative.duration_hint || 0).toFixed(1)}) : '';
  $('#aiOpeningSummary').textContent = creative.summary || '';
  const direction = result.global_direction || {};
  $('#aiOpeningNote').textContent = creative.name
    ? `${t('aiOpeningWritten', {count: creative.shot_count || 0, overlays: creative.overlay_count || 0, sounds: creative.sound_count || 0})} ${t('aiGlobalLine', {accents: direction.accent_count || 0, music: direction.music_name || t('noMusic')})}`
    : '';

  const planLang = plan.language || result.report?.language || 'zh';
  $('#aiReportText').textContent = (planLang !== state.lang ? `${t('aiLanguageMismatch')}\n\n` : '') + (result.report?.report_text || '');
  const changes = result.changes || {};
  const sep = state.lang === 'en' ? ', ' : '，', stop = state.lang === 'en' ? '.' : '。';
  $('#aiApplyNote').textContent = `${t('aiNoteFull')} ${t('aiChangeReplace', {count: changes.replace_video_clips ?? 0})}${sep}${t('aiChangeAdd', {overlays: changes.add_overlays ?? 0, sfx: changes.add_sound_effects ?? 0})}${changes.preserve_background_music ? `${sep}${t('aiChangeMusic').toLowerCase()}` : changes.music ? `${sep}${t('aiChangeMusicSet', {name: changes.music})}` : ''}${stop}`;
  $('#aiApply').disabled = !validation.ok;

  $('#aiShots').innerHTML = (result.shots || []).map((shot, index) => {
    const length = Number(shot.end) - Number(shot.start);
    const meta = [
      shot.chapter ? t('aiChapterPrefix', {value: shot.chapter}) : '',
      index > 0 ? t('aiTransitionPrefix', {value: transitionLabel(shot.transition)}) : '',
      shot.mask && shot.mask !== 'none' ? t('aiMaskPrefix', {value: shot.mask}) : '',
      shot.motion_effect && shot.motion_effect !== 'none' ? t('aiMotionPrefix', {value: shot.motion_effect}) : '',
      shot.purpose ? shot.purpose : '',
    ].filter(Boolean).join(' · ');
    return `
    <article class="ai-shot" data-media-id="${escapeHtml(shot.media_id)}" data-start="${Number(shot.start)}" data-end="${Number(shot.end)}" title="${t('aiPreviewShot')}">
      <span class="index">${String(index + 1).padStart(2, '0')}</span>
      <div>
        <div class="ai-shot-head"><span class="ai-role ${escapeHtml(shot.role || '')}">${escapeHtml(roleLabel(shot.role))}</span><h4 title="${escapeHtml(shot.name)}">${escapeHtml(shot.name)}</h4><span class="range">${Number(shot.start).toFixed(2)} – ${Number(shot.end).toFixed(2)}s · ${length.toFixed(1)}s</span></div>
        ${shot.caption ? `<p class="caption">${escapeHtml(t('captionPrefix', {value: shot.caption}))}</p>` : ''}
        <p class="reason">${escapeHtml(t('aiReasonPrefix', {value: shot.reason || ''}))}</p>
        ${meta ? `<p class="meta">${escapeHtml(meta)}</p>` : ''}
      </div>
    </article>`;
  }).join('');
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
  $('#aiError').classList.add('hidden');
  $('#aiDialog').showModal();
  try {
    const [capabilities, sources] = await Promise.all([api('/api/ai/capabilities'), api('/api/ai/sources')]);
    state.ai.capabilities = capabilities;
    state.ai.sources = sources.items || [];
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
      if (action === 'undo') { state.ai.plan = null; $('#aiDialog').close(); }
    } else {
      stopAIPolling();
      state.ai.plan = null;
      banner(t('aiCancelled'));
    }
    renderAI();
  } catch (error) { banner(error.message, 'error'); }
}

$('#aiBtn').addEventListener('click', openAIDialog);
$('#aiClose').addEventListener('click', () => $('#aiDialog').close());
$('#aiMode').addEventListener('change', renderAINotice);
$('#aiSetup').addEventListener('submit', async (event) => {
  event.preventDefault();
  const mode = $('#aiMode').value;
  const selected = new Set(state.ai.selected);
  const body = {
    media_ids: state.ai.order.filter((id) => selected.has(id)),
    revision: Number(state.project.revision),
    mode,
    target_duration: Number($('#aiTarget').value),
    prompt: $('#aiPrompt').value.trim(),
    cloud_consent: mode === 'cloud' && $('#aiConsent').checked,
    opening: $('#aiOpening').value,
    style: $('#aiStyle').value,
    language: state.lang,
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
$('#aiCopyReport').addEventListener('click', async () => {
  const text = state.ai.plan?.result?.report?.report_text || '';
  try { await navigator.clipboard.writeText(text); banner(t('aiReportCopied'), 'success'); }
  catch (error) { banner(t('aiReportCopyFailed'), 'error'); }
});
$('#aiPreset').addEventListener('change', async () => {
  const plan = state.ai.plan;
  if (!plan) return;
  banner(t('aiPresetSwitching'));
  try {
    state.ai.plan = await api(`/api/ai/plans/${plan.id}/opening`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({preset: $('#aiPreset').value})});
    renderAI();
    banner(t('aiPresetSwitched', {name: state.ai.plan.result?.creative?.name || ''}), 'success');
  } catch (error) { banner(error.message, 'error'); renderAI(); }
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
render();
Promise.all([api('/api/project'), api('/api/health')]).then(([data, health]) => {
  state.exportReady = Boolean(health.export_ready);
  hydrate(data);
  banner(t(state.exportReady ? 'connected' : 'exportUnavailable'), state.exportReady ? 'success' : 'error');
  restoreAIPlan();
}).catch((error) => banner(error.message, 'error'));
