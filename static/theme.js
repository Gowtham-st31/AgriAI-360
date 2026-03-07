// theme.js - apply saved theme (dark/light) as early as possible
(function(){
  try{
    var t = null;
    try{ t = localStorage.getItem('agri_theme'); }catch(e){}
    if(!t){
      // default to dark; user can switch to light later
      t = 'dark';
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
    try{ const tb = document.getElementById('theme-toggle'); if(tb) tb.textContent = isDark ? 'ðŸŒ™' : 'â˜€ï¸'; }catch(e){}
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
  }catch(e){}
});
