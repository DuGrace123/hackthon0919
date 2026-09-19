const words = {
  zh: {
    pageTitle: '灵剪 · 登录', headline: '你的本地智能剪辑工作区', subhead: '项目、媒体和账户数据保存在本机。登录后即可继续剪辑。',
    localData: '本地数据', localDataHint: '密码经过单向加密，账户保存于本地 SQLite 数据库。', username: '用户名', password: '密码', confirmPassword: '确认密码',
    loginTitle: '登录灵剪', loginDescription: '输入账户信息以打开剪辑工作区。', loginAction: '登录', setupEyebrow: 'FIRST-TIME SETUP', setupTitle: '创建管理员账户',
    setupDescription: '这是首次启动。请创建第一个管理员；以后可在账户管理中添加其他用户。', setupAction: '创建管理员并进入', privacy: '仅在可信设备上保持登录。关闭浏览器不会删除本地工程。', switchLanguage: 'Switch to English', requestFailed: '请求失败'
  },
  en: {
    pageTitle: 'LingJian · Sign In', headline: 'Your local intelligent editing workspace', subhead: 'Projects, media, and account data stay on this computer. Sign in to continue editing.',
    localData: 'Local data', localDataHint: 'Passwords are one-way hashed and accounts are stored in a local SQLite database.', username: 'Username', password: 'Password', confirmPassword: 'Confirm password',
    loginTitle: 'Sign in to LingJian', loginDescription: 'Enter your account details to open the editing workspace.', loginAction: 'Sign In', setupEyebrow: 'FIRST-TIME SETUP', setupTitle: 'Create an administrator',
    setupDescription: 'This is the first launch. Create the first administrator; you can add other users later in Account Management.', setupAction: 'Create Admin and Continue', privacy: 'Stay signed in only on a trusted device. Closing the browser does not delete local projects.', switchLanguage: '切换到中文', requestFailed: 'Request failed'
  }
};

const state = { lang: localStorage.getItem('lingjian-language') === 'en' ? 'en' : 'zh', csrf: '', setup: false };
const $ = (selector) => document.querySelector(selector);
const t = (key) => words[state.lang][key] || key;

function applyLanguage() {
  document.documentElement.lang = state.lang === 'en' ? 'en' : 'zh-CN';
  document.title = t('pageTitle');
  document.querySelectorAll('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll('.language-switch button').forEach((button) => {
    const active = button.dataset.lang === state.lang;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  $('#formEyebrow').textContent = state.setup ? t('setupEyebrow') : 'WELCOME BACK';
  $('#formTitle').textContent = t(state.setup ? 'setupTitle' : 'loginTitle');
  $('#formDescription').textContent = t(state.setup ? 'setupDescription' : 'loginDescription');
  $('#submitBtn').textContent = t(state.setup ? 'setupAction' : 'loginAction');
}

function showError(message) { $('#authBanner').textContent = message; $('#authBanner').classList.remove('hidden'); }

async function request(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', state.csrf);
  const response = await fetch(url, {...options, headers});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || t('requestFailed'));
  return data;
}

document.querySelectorAll('.language-switch button').forEach((button) => button.addEventListener('click', () => {
  state.lang = button.dataset.lang === 'en' ? 'en' : 'zh';
  localStorage.setItem('lingjian-language', state.lang);
  applyLanguage();
}));

$('#authForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('#authBanner').classList.add('hidden');
  $('#submitBtn').disabled = true;
  const payload = {username: $('#username').value, password: $('#password').value};
  if (state.setup) payload.confirm_password = $('#confirmPassword').value;
  try {
    const result = await request(state.setup ? '/api/auth/setup' : '/api/auth/login', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    state.csrf = result.csrf_token;
    window.location.assign('/');
  } catch (error) {
    showError(error.message);
    $('#submitBtn').disabled = false;
  }
});

applyLanguage();
request('/api/auth/status').then((data) => {
  if (data.authenticated) return window.location.assign('/');
  state.csrf = data.csrf_token;
  state.setup = data.setup_required;
  $('#confirmRow').classList.toggle('hidden', !state.setup);
  $('#confirmPassword').required = state.setup;
  $('#password').autocomplete = state.setup ? 'new-password' : 'current-password';
  applyLanguage();
}).catch((error) => showError(error.message));
