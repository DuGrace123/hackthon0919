(() => {
  const key = 'lingjian-language';
  const valid = value => value === 'en' || value === 'zh';
  function get() {
    try {
      const stored = localStorage.getItem(key);
      if (valid(stored)) return stored;
    } catch (_) { /* Preferences still work for this page when storage is blocked. */ }
    const cookie = document.cookie.split('; ').find(item => item.startsWith(`${key}=`))?.split('=')[1];
    return valid(cookie) ? cookie : 'en';
  }
  function set(language) {
    const value = valid(language) ? language : 'en';
    try { localStorage.setItem(key, value); } catch (_) { /* Storage is optional. */ }
    document.cookie = `${key}=${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === 'https:' ? '; Secure' : ''}`;
    document.querySelectorAll('[data-guide-link]').forEach(link => {
      const url = new URL(link.href, location.href);
      url.searchParams.set('lang', value);
      link.href = url.href;
    });
  }
  window.LingJianLanguage = {get, set};
})();
