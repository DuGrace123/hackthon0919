(() => {
  const url = new URL(location.href);
  const requested = url.searchParams.get('lang');
  const language = ['en', 'zh'].includes(requested) ? requested : LingJianLanguage.get();
  const rendered = document.documentElement.lang === 'en' ? 'en' : 'zh';
  function navigate(value) {
    url.searchParams.set('lang', value);
    location.replace(url.href);
  }
  // Migrate an existing browser preference when a direct guide link has no language.
  if (language !== rendered) {
    navigate(language);
    return;
  }
  LingJianLanguage.set(language);
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-guide-language]');
    if (link) LingJianLanguage.set(link.dataset.guideLanguage);
  });
  window.addEventListener('storage', event => {
    if (event.key === 'lingjian-language' && ['en', 'zh'].includes(event.newValue) && event.newValue !== rendered) {
      navigate(event.newValue);
    }
  });
})();
