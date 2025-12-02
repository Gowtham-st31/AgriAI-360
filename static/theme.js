// theme.js - apply saved theme (dark/light) as early as possible
(function(){
  try{
    var t = null;
    try{ t = localStorage.getItem('agri_theme'); }catch(e){}
    if(!t){
      // default to light for wide familiarity, but allow dark as preference
      t = 'light';
    }
    if(t === 'dark'){
      try{ document.body.classList.add('dark-mode'); }catch(e){}
    } else {
      try{ document.body.classList.remove('dark-mode'); }catch(e){}
    }
  }catch(e){ /* noop */ }
})();

function toggleDarkMode() {
  try{
    const isDark = document.body.classList.toggle("dark-mode");
    localStorage.setItem('agri_theme', isDark ? 'dark' : 'light');
    // update header toggle if present
    try{ const tb = document.getElementById('theme-toggle'); if(tb) tb.textContent = isDark ? '🌙' : '☀️'; }catch(e){}
  }catch(e){}
}

// Ensure any pages that load theme.js early also get translations applied
document.addEventListener('DOMContentLoaded', ()=>{
  try{
    // load i18n early if not present so pages without header still translate
    if(!window._I18N){ const s = document.createElement('script'); s.src='/i18n.js'; s.async = true; document.head.appendChild(s); }
    // run translations if header exposes it, otherwise use local translator after i18n loads
    const tryApply = ()=> {
      try {
        if (window.applyTranslations && typeof window.applyTranslations === 'function') {
          window.applyTranslations();
          return;
        }
        // local minimal translator using window.__t if available
        if (window.__t && typeof window.__t === 'function') {
          try {
            document.querySelectorAll('[data-i18n]').forEach(el => {
              try {
                const k = el.getAttribute('data-i18n');
                const txt = window.__t(k);
                if (!txt) return;
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.placeholder = txt;
                else el.textContent = txt;
              } catch (e) {}
            });
            const map = { 'search-box':'search.placeholder','search-btn':'search.button','brand-text':'nav.brand' };
            Object.keys(map).forEach(id => {
              try {
                const el = document.getElementById(id);
                if (!el) return;
                const txt = window.__t(map[id]);
                if (!txt) return;
                if (el.tagName === 'INPUT') el.placeholder = txt;
                else el.textContent = txt;
              } catch (e) {}
            });
            document.querySelectorAll('.product-title').forEach(el => {
              try {
                const val = (el.textContent || '').trim();
                if (!val) return;
                const norm = val.toLowerCase().replace(/[^a-z0-9]+/g,'_');
                const key = 'product.' + norm;
                const txt = window.__t(key);
                if (txt && txt !== key) el.textContent = txt;
              } catch (e) {}
            });
          } catch (e) {}
        }
      } catch (e) {}
    };
    // if i18n already loaded run immediately, else wait for it
    if(window._I18N) tryApply(); else { const s = document.querySelector('script[src="/i18n.js"]'); if(s) s.addEventListener('load', tryApply); else { const s2 = document.createElement('script'); s2.src='/i18n.js'; s2.async=true; s2.onload=tryApply; document.head.appendChild(s2); } }
    // create a floating language picker if header language control is not visible
    try{
      const ensureFloating = ()=>{
        if(document.getElementById('lang-wrap')) return; // header provides control
        if(document.getElementById('floating-lang')) return; // already created
        const wrap = document.createElement('div'); wrap.id = 'floating-lang';
        wrap.innerHTML = `<div style="display:flex;gap:8px;align-items:center;padding:6px 8px"><span style="font-size:14px">🌐</span><select id="floating-lang-select" title="Language" style="padding:6px;border-radius:6px;border:0;background:rgba(255,255,255,0.02);color:inherit"></select></div>`;
        document.body.appendChild(wrap);
        const sel = document.getElementById('floating-lang-select');
        const fallback = { 'en':'English','hi':'हिन्दी','ta':'தமிழ்','kn':'ಕನ್ನಡ','ml':'മലയാളം' };
        const langs = (window._I18N && window._I18N.languages) ? window._I18N.languages : fallback;
        Object.keys(langs).forEach(k=>{ const o = document.createElement('option'); o.value=k; o.textContent = langs[k]; sel.appendChild(o) });
        sel.value = localStorage.getItem('agri_lang')||'en';
        sel.addEventListener('change', ()=>{
          const v = sel.value; localStorage.setItem('agri_lang', v);
          try{ if(window.setLanguage) window.setLanguage(v); }catch(e){}
          try{ if(window.applyTranslations) window.applyTranslations(); else tryApply(); }catch(e){}
        });
      };
      // if i18n not yet present wait a little, then ensure floating control
      if(window._I18N) ensureFloating(); else { setTimeout(ensureFloating, 600); }
    }catch(e){}
    // --- create an always-visible language FAB (button) + menu so user can change language anywhere ---
    try{
      const ensureLangFab = ()=>{
        try{
          if(!document.body) return; // wait for body
          if(document.getElementById('lang-fab')) return;
          const fab = document.createElement('div'); fab.id = 'lang-fab'; fab.className='lang-fab';
          fab.innerHTML = `<span style="font-weight:800">🌐</span><span class="label" id="fab-lang-label">${(window._I18N && window._I18N.languages && window._I18N.languages[localStorage.getItem('agri_lang')||'en']) || 'Lang'}</span>`;
          document.body.appendChild(fab);
          const menu = document.createElement('div'); menu.id='lang-menu'; menu.className='lang-menu';
          menu.innerHTML = `<div class="lang-title">Language</div><div id="lang-options"></div>`;
          document.body.appendChild(menu);

          const populate = ()=>{
            try{
              const container = document.getElementById('lang-options'); if(!container) return; container.innerHTML = '';
              const langs = (window._I18N && window._I18N.languages) ? window._I18N.languages : { 'en':'English','hi':'हिन्दी','ta':'தமிழ்','kn':'ಕನ್ನಡ','ml':'മലയാളം' };
              Object.keys(langs).forEach(k=>{
                const d = document.createElement('div'); d.className='lang-option'; d.dataset.lang = k; d.textContent = langs[k];
                d.addEventListener('click', ()=>{
                  try{ localStorage.setItem('agri_lang', k); const label = document.getElementById('fab-lang-label'); if(label) label.textContent = langs[k]; if(window.setLanguage) window.setLanguage(k); try{ if(window.applyTranslations) window.applyTranslations(); else if(window.ensureI18nLoaded) window.ensureI18nLoaded(()=>{ if(window.applyTranslations) window.applyTranslations(); }); }catch(e){};
                  menu.classList.remove('active');
                });
                container.appendChild(d);
              });
            }catch(e){}
          };

          // initial populate (or when i18n loads)
          if(window._I18N) populate(); else { const s = document.querySelector('script[src="/i18n.js"]'); if(s) s.addEventListener('load', populate); else { const s2 = document.createElement('script'); s2.src='/i18n.js'; s2.async=true; s2.onload=populate; document.head.appendChild(s2); } }

          fab.addEventListener('click', ()=>{ try{ menu.classList.toggle('active'); }catch(e){} });
          // close menu when clicking outside
          document.addEventListener('click', (ev)=>{ try{ if(!menu.contains(ev.target) && !fab.contains(ev.target)) menu.classList.remove('active'); }catch(e){} });
        }catch(e){}
      };
      // try immediately, and also after short delay
      try{ ensureLangFab(); }catch(e){}
      setTimeout(()=>{ try{ ensureLangFab(); }catch(e){} }, 300);
    }catch(e){}
  }catch(e){}
});

// If i18n data is available, load it early so pages without the header still get translations
(function(){
  try{
    if(window._I18N) return; // already loaded
    const s = document.createElement('script'); s.src = '/i18n.js'; s.async = true;
    s.onload = ()=>{
      try{
        const apply = ()=>{
          try{
            const map = {
              'search-box': 'search.placeholder',
              'search-btn': 'search.button',
              'theme-toggle': 'theme.toggle',
              'brand-text': 'nav.brand'
            };
            Object.keys(map).forEach(id=>{ const el = document.getElementById(id); if(!el) return; const txt = window.__t(map[id]); if(!txt) return; if(el.tagName==='INPUT') el.placeholder = txt; else el.textContent = txt });
            document.querySelectorAll('[data-i18n]').forEach(el=>{ const k = el.getAttribute('data-i18n'); const txt = window.__t(k); if(txt) el.textContent = txt });
          }catch(e){ /* noop */ }
        };
        apply();
      }catch(e){ }
    };
    document.head.appendChild(s);
  }catch(e){}
})();
