// header.js - injects a site header and profile menu
// Only inject header on site pages (skip profile and admin pages)
(async function(){
  // Apply saved theme early so pages (including those that skip header) get consistent styles
  try{
    const saved = localStorage.getItem('agri_theme');
    if(saved === 'light'){
      document.body.classList.remove('dark-mode');
    } else if(saved === 'dark'){
      document.body.classList.add('dark-mode');
    }
  }catch(e){ /* ignore theme apply errors */ }

  try{
    const _path = (window.location && window.location.pathname) ? window.location.pathname.toLowerCase() : '/';
    // skip if path contains 'profile' or 'admin' (covers /profile, /profile.html, /admin/*, admin_dashboard, admin_*.html, etc.)
    if(_path.includes('profile') || _path.includes('/admin') || _path.indexOf('admin_')!==-1) {
      // do nothing on admin/profile pages (but theme is already applied)
      return;
    }
  }catch(e){ /* ignore and continue to render header by default */ }
    function createHeaderHtml(){
    return `
    <header class="site-header">
      <div class="site-header-inner">
        <div class="header-left">
          <a id="brand-link" href="/home" class="brand">
            <img src="/icons/logo.png" alt="Agri360" onerror="this.style.display='none'">
            <span id="brand-text">Agri360</span>
          </a>
        </div>

        <div class="header-search">
          <form id="site-search" onsubmit="event.preventDefault();performSearch()" class="search-form">
            <input id="search-box" placeholder="Search products, e.g. tomato" />
            <button id="voice-btn" type="button" title="Voice search">🎤</button>
            <button id="search-btn" type="submit">Search</button>
          </form>
        </div>

        <div class="header-right">
          <nav class="header-nav">
            <a id="nav-buy" href="/buy.html" data-i18n="nav.buy">Buy</a>
            <a id="nav-sell" href="/sell.html" data-i18n="nav.sell">Sell</a>
            <a id="nav-market" href="/market" data-i18n="nav.market">Market</a>
            <a id="nav-detect" href="/detect" data-i18n="nav.detect">Detect</a>
            <a id="nav-weather" href="/weather" data-i18n="nav.weather">Weather</a>
            <a id="cart-link" href="/cart" data-i18n="nav.cart">Cart <span id="cart-count">0</span></a>
          </nav>

          <!-- left header language control removed; keep single language FAB at top-right -->

          <button id="theme-toggle" title="Toggle theme" class="theme-toggle">🌙</button>
          <div id="profile-block" class="profile-block"></div>
        </div>
      </div>

      <div class="site-subnav">
        <div class="subnav-inner">
          <a href="/market?q=fruits">Fruits</a>
          <a href="/market?q=vegetables">Vegetables</a>
          <a href="/market?q=grains">Grains</a>
          <a href="/market?q=seeds">Seeds</a>
          <a href="/detect">Detect</a>
          <a href="/weather">Weather Advice</a>
        </div>
      </div>
    </header>`;
  }

  function renderProfileMenu(user){
    const p = document.getElementById('profile-block');
    if(!p) return;
    // ensure the Home link goes to /login for anonymous users
    const homeLink = document.getElementById('nav-home');
    if(!user || !user.logged){
      p.innerHTML = `<a href='/login' style='color:#12733a;text-decoration:none;font-weight:600'>Login</a>`;
      if(homeLink) homeLink.href = '/login';
      return;
    }

    if(homeLink) homeLink.href = '/home';

    const email = (user.user && user.user.email) || 'user';
    p.innerHTML = `
      <button id='profile-btn' style='background:transparent;border:1px solid rgba(255,255,255,0.06);padding:6px 10px;border-radius:20px;cursor:pointer;color:var(--primary-contrast);font-weight:700'>${email.split('@')[0]}</button>
      <div id='profile-menu' style='display:none;position:absolute;right:0;top:38px;background:var(--surface);border:1px solid rgba(0,0,0,0.06);box-shadow:0 6px 18px rgba(0,0,0,0.08);min-width:200px;border-radius:8px;padding:8px;z-index:999;color:var(--text)'>
        <div style='padding:8px 10px;border-bottom:1px solid rgba(0,0,0,0.04)'><strong style='color:var(--text)'>${email}</strong></div>
        <a href='/profile' style='display:block;padding:8px 10px;color:var(--text);text-decoration:none'>Profile</a>
        <a href='/buy-sell' style='display:block;padding:8px 10px;color:var(--text);text-decoration:none'>My Orders</a>
        <button id='logout-btn' style='margin:8px 10px;padding:8px 10px;width:calc(100% - 20px);background:var(--surface);border:1px solid rgba(0,0,0,0.06);border-radius:6px;cursor:pointer;color:var(--text)'>Logout</button>
      </div>
    `;

    const btn = document.getElementById('profile-btn');
    const menu = document.getElementById('profile-menu');
    btn.addEventListener('click', ()=>{ menu.style.display = (menu.style.display==='none'?'block':'none') });
    document.addEventListener('click', (e)=>{ if(!p.contains(e.target)) menu.style.display='none' });

    document.getElementById('logout-btn').addEventListener('click', async ()=>{
      try{
        await fetch('/auth/logout', {method:'POST'});
        window.location.reload();
      }catch(e){ console.error(e); }
    });
  }

  // inject header placeholder
  // Ensure the header HTML is present. Some pages include an empty `#site-header` placeholder
  // (e.g. `home.html`). If the placeholder exists, fill it; otherwise create and insert it.
  try{
    const existing = document.getElementById('site-header');
    if(existing){
      existing.innerHTML = createHeaderHtml();
    } else {
      const div = document.createElement('div'); div.id='site-header'; div.innerHTML = createHeaderHtml();
      document.body.insertBefore(div, document.body.firstChild);
    }
  }catch(e){ /* ignore DOM injection errors */ }

  // Theme toggle logic: update button and persist preference
  function setTheme(t){
    try{
      if(t === 'dark'){
        document.body.classList.add('dark-mode');
        localStorage.setItem('agri_theme', 'dark');
      } else {
        document.body.classList.remove('dark-mode');
        localStorage.setItem('agri_theme', 'light');
      }
      const btn = document.getElementById('theme-toggle');
      if(btn) btn.textContent = (t === 'dark') ? '🌙' : '☀️';
    }catch(e){}
  }

  function toggleTheme(){
    try{
      const isDark = document.body.classList.contains('dark-mode');
      setTheme(isDark ? 'light' : 'dark');
    }catch(e){}
  }

  // hook up theme toggle button (if present)
  try{ const tb = document.getElementById('theme-toggle'); if(tb){ tb.addEventListener('click', toggleTheme); /* init label */ const saved=localStorage.getItem('agri_theme')||'light'; tb.textContent = saved==='dark'?'🌙':'☀️'; } }catch(e){}

  // fetch user info
  try{
    const r = await fetch('/api/user');
    const j = await r.json();
    renderProfileMenu(j);
  }catch(e){ renderProfileMenu(null); }

  // search helper
  window.performSearch = function(){
    const q = document.getElementById('search-box').value.trim();
    if(!q) return;
    try{
      // Map localized query to canonical English term when possible
      const mapped = (typeof window.localizedToCanonical === 'function') ? window.localizedToCanonical(q) : q;
      window.location.href = '/market?q=' + encodeURIComponent(mapped);
    }catch(e){
      window.location.href = '/market?q=' + encodeURIComponent(q);
    }
  }

  // Map a localized product/commodity name to canonical English using i18n translations.
  // Returns the original query if no mapping is found.
  window.localizedToCanonical = function(q){
    try{
      if(!q) return q;
      const lang = localStorage.getItem('agri_lang') || 'en';
      const trans = (window._I18N && window._I18N.translations && window._I18N.translations[lang]) || {};
      const en = (window._I18N && window._I18N.translations && window._I18N.translations['en']) || {};
      const lower = q.toString().trim().toLowerCase();

      // Exact value match in translations
      for(const key in trans){
        try{
          const val = (trans[key]||'').toString().trim().toLowerCase();
          if(!val) continue;
          if(val === lower){
            if(key.indexOf('product.')===0){
              return en[key] || key.split('.').slice(1).join(' ');
            }
            if(en[key]) return en[key];
          }
        }catch(e){}
      }

      // Partial match: localized value contains query or vice versa
      for(const key in trans){
        try{
          const val = (trans[key]||'').toString().trim().toLowerCase();
          if(!val) continue;
          if(val.indexOf(lower) !== -1 || lower.indexOf(val) !== -1){
            if(key.indexOf('product.')===0) return en[key] || key.split('.').slice(1).join(' ');
            if(en[key]) return en[key];
          }
        }catch(e){}
      }

      return q;
    }catch(e){ return q; }
  }
  
  // i18n: populate language selector and apply translations
  try{
    // populate selector with a small fallback set first so it's visible even if i18n.js fails
    const fallbackLangs = { 'en':'English', 'hi':'हिन्दी', 'ta':'தமிழ்', 'kn':'ಕನ್ನಡ', 'ml':'മലയാളം' };
    try{
      const sel = document.getElementById('lang-select');
      if(sel){
        // populate only if empty
        if(sel.options.length === 0){
          // prefer Tamil first in fallback
          const order = ['ta','hi','ml','kn','en'];
          const keys = order.concat(Object.keys(fallbackLangs).filter(k=>!order.includes(k)));
          keys.forEach(k=>{ if(!fallbackLangs[k]) return; const o = document.createElement('option'); o.value=k; o.textContent = fallbackLangs[k]; sel.appendChild(o) });
        }
        const cur = localStorage.getItem('agri_lang')||'en'; sel.value = cur;
        sel.setAttribute('aria-label','Language');
        sel.addEventListener('change', ()=>{ localStorage.setItem('agri_lang', sel.value); ensureI18nLoaded(applyTranslations); });
      }
    }catch(e){ console.error('i18n fallback init', e) }

    const script = document.createElement('script'); script.src='/i18n.js'; document.head.appendChild(script);
    script.onload = ()=>{
      try{
        const sel = document.getElementById('lang-select');
        if(!sel) return;
        // replace with canonical languages from i18n.js (prefer Tamil first)
        sel.innerHTML = '';
        const langs = window._I18N && window._I18N.languages ? window._I18N.languages : fallbackLangs;
        const order = ['ta','hi','ml','kn','en'];
        const keys = order.concat(Object.keys(langs).filter(k=>!order.includes(k)));
        keys.forEach(k=>{ if(!langs[k]) return; const o = document.createElement('option'); o.value=k; o.textContent = langs[k]; sel.appendChild(o) });
        const cur = localStorage.getItem('agri_lang')||'en'; sel.value = cur;
        // show readable current language next to selector (helps when native dropdown options are hard to style)
        try{ const lc = document.getElementById('lang-current'); if(lc) lc.textContent = (langs[cur] || cur); }catch(e){}
        // ensure previous listener isn't duplicated
        sel.replaceWith(sel.cloneNode(true));
        const fresh = document.getElementById('lang-select');
        fresh.addEventListener('change', ()=>{ localStorage.setItem('agri_lang', fresh.value); document.documentElement.lang = fresh.value; try{ const lc = document.getElementById('lang-current'); if(lc) lc.textContent = (window._I18N && window._I18N.languages && window._I18N.languages[fresh.value]) || fresh.value }catch(e){}; ensureI18nLoaded(function(){ try{ if(typeof window.applyTranslations === 'function') window.applyTranslations(); }catch(e){} }); // reload as a fallback to ensure visible change
        setTimeout(()=>{ try{ location.reload(); }catch(e){} }, 250);
        });
        // expose helper for programmatic language changes
        window.setLanguage = function(l){ try{ if(!l) return; localStorage.setItem('agri_lang', l); document.documentElement.lang = l; if(document.getElementById('lang-select')) document.getElementById('lang-select').value = l; ensureI18nLoaded(function(){ try{ if(typeof window.applyTranslations === 'function') window.applyTranslations(); }catch(e){} }); // fallback reload
        setTimeout(()=>{ try{ location.reload(); }catch(e){} }, 250);
        }catch(e){} };
        ensureI18nLoaded(applyTranslations);
      }catch(e){ console.error('i18n init', e) }
    }
    
  }catch(e){ console.error('could not load i18n.js', e) }

  function applyTranslations(){
    try{
      const lang = localStorage.getItem('agri_lang') || 'en';
      // translate known elements
      // translate known elements by id
      const map = {
        'search-box': 'search.placeholder',
        'search-btn': 'search.button',
        'theme-toggle': 'theme.toggle',
        'brand-text': 'nav.brand',
        'nav-buy': 'nav.buy',
        'nav-sell': 'nav.sell',
        'nav-market': 'nav.market',
        'nav-detect': 'nav.detect',
        'cart-link': 'nav.cart'
      };
      Object.keys(map).forEach(id=>{ const el = document.getElementById(id); if(!el) return; const txt = window.__t(map[id]); if(!txt) return; if(el.tagName==='INPUT') el.placeholder = txt; else el.textContent = txt });
      // translate nav links and labels with data-i18n
      document.querySelectorAll('[data-i18n]').forEach(el=>{ const k = el.getAttribute('data-i18n'); const txt = window.__t(k); if(txt) { if(el.tagName==='INPUT' || el.tagName==='TEXTAREA') el.placeholder = txt; else el.textContent = txt } });

      // translate dynamic product names by data-product-id or data-product-name attribute
      document.querySelectorAll('[data-product-id]').forEach(el=>{ try{ const pid = el.getAttribute('data-product-id'); if(!pid) return; const key = 'product.'+pid; const txt = window.__t(key); if(txt) el.textContent = txt; }catch(e){} });
      document.querySelectorAll('[data-product-name]').forEach(el=>{ try{ const pname = el.getAttribute('data-product-name'); if(!pname) return; const norm = pname.toString().trim().toLowerCase().replace(/[^a-z0-9]+/g,'_'); const key = 'product.'+norm; const txt = window.__t(key); if(txt && txt!==key) el.textContent = txt; }catch(e){} });

      // Fallback: translate visible product titles rendered without attributes
      document.querySelectorAll('.product-title').forEach(el=>{ try{ const val = (el.textContent||'').trim(); if(!val) return; const norm = val.toLowerCase().replace(/[^a-z0-9]+/g,'_'); const key = 'product.'+norm; const txt = window.__t(key); if(txt && txt!==key) el.textContent = txt; }catch(e){} });

      // translate market result labels if present
      document.querySelectorAll('.market-card').forEach(card=>{
        try{
          const keys = ['market','district','state','variety','grade','min_price','max_price','modal_price','date'];
          keys.forEach(k=>{
            const nodes = card.querySelectorAll('[data-label="'+k+'"]');
            nodes.forEach(n=>{
              try{
                const lbl = window.__t('label.'+k) || '';
                if(lbl){
                  const labelNode = n.querySelector('.label');
                  if(labelNode) {
                    labelNode.textContent = lbl;
                  } else {
                    n.innerHTML = '<span class="label">'+lbl+'</span> ' + (n.textContent || '');
                  }
                }
              }catch(e){}
            });
          });
        }catch(e){}
      });
    }catch(e){ console.error('applyTranslations', e) }
  }

  // Ensure i18n is available; if not, load it and call callback after load
  function ensureI18nLoaded(cb){
    try{
      if(window.__t && typeof window.__t === 'function'){
        if(cb) cb(); return;
      }
      // load script if not present
      const s = document.querySelector('script[src="/i18n.js"]');
      if(s){
        s.addEventListener('load', ()=>{ if(cb) cb(); });
        return;
      }
      const scr = document.createElement('script'); scr.src = '/i18n.js';
      scr.onload = ()=>{ try{ if(cb) cb(); }catch(e){} };
      document.head.appendChild(scr);
    }catch(e){ if(cb) cb(); }
  }

  // Header language menu intentionally disabled: using single top-right language FAB instead
  function initHeaderLanguageMenu(){ return; }

  try{ initHeaderLanguageMenu(); }catch(e){}

  // expose translation helpers so other scripts can trigger retranslation
  try{ window.applyTranslations = applyTranslations; window.ensureI18nLoaded = ensureI18nLoaded; }catch(e){}
  // listen for language changes in other tabs/windows and apply translations
  try{
    window.addEventListener('storage', (ev)=>{
      try{
        if(ev.key === 'agri_lang'){
          const newLang = localStorage.getItem('agri_lang') || 'en';
          const lc = document.getElementById('lang-current'); if(lc) lc.textContent = (window._I18N && window._I18N.languages && window._I18N.languages[newLang]) || newLang;
          ensureI18nLoaded(applyTranslations);
        }
      }catch(e){}
    });
  }catch(e){}

  // Voice search (Web Speech API) - supports whatever language code is selected; falls back gracefully
  try{
    const voiceBtn = document.getElementById('voice-btn');
    if(voiceBtn && (('webkitSpeechRecognition' in window) || ('SpeechRecognition' in window))){
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new SpeechRec();
      const speechLangMap = (k)=>({ 'en':'en-IN','hi':'hi-IN','ta':'ta-IN','kn':'kn-IN','ml':'ml-IN' })[k] || k;
      const setRecLang = ()=>{ rec.lang = speechLangMap(localStorage.getItem('agri_lang')||'en') };
      setRecLang();
      rec.interimResults = false; rec.maxAlternatives = 1;
      voiceBtn.addEventListener('click', ()=>{
        try{ setRecLang(); rec.start(); voiceBtn.textContent = '🎙️'; }catch(e){ console.error(e) }
      });
      rec.onresult = (ev)=>{ const t = ev.results[0][0].transcript; document.getElementById('search-box').value = t; performSearch(); voiceBtn.textContent = '🎤' };
      rec.onerror = (e)=>{ console.error('speech error', e); voiceBtn.textContent = '🎤' };
      // update recognition language when selector changes
      document.addEventListener('change', (e)=>{ if(e.target && e.target.id==='lang-select'){ try{ rec.lang = speechLangMap(e.target.value); }catch(e){} } });
    } else {
      // disable voice button if no support
      const vb = document.getElementById('voice-btn'); if(vb) vb.style.display='none';
    }
  }catch(e){ console.error('voice init', e) }
  // Cart helpers (store in localStorage)
  window.getCart = function(){ try{ return JSON.parse(localStorage.getItem('agri_cart')||'[]') }catch(e){ return [] } }
  window.setCart = function(c){ try{ localStorage.setItem('agri_cart', JSON.stringify(c)) }catch(e){} }
  window.updateCartCount = function(){ const el = document.getElementById('cart-count'); if(!el) return; const n = window.getCart().reduce((s,it)=>s+(it.qty||1),0); el.textContent = n; }
  window.addToCart = function(item, goToCart){ try{
      if(!item) { alert('Item not available'); return }
      const cart = window.getCart();
      // ensure a stable id exists for the cart item
      if(!item.id){ try{ item.id = ('prod_'+((item.product||'').toString().toLowerCase().replace(/[^a-z0-9]+/g,'_'))+'_'+((item.seller||'').toString().toLowerCase().replace(/[^a-z0-9]+/g,'_'))).replace(/_+$/,''); }catch(e){} }
      const existing = cart.find(c=> (c.id && item.id && c.id==item.id) || (c.product && item.product && c.product==item.product && c.seller==item.seller) );
      if(existing){ existing.qty = (existing.qty||1) + 1 } else { cart.push(Object.assign({}, { id: item.id, product: item.product, seller: item.seller, price: item.price, qty: 1 })) }
      window.setCart(cart);
      window.updateCartCount();
      // update floating cart count if present
      try{ const fc = document.getElementById('floating-cart-count'); if(fc) fc.textContent = window.getCart().reduce((s,it)=>s+(it.qty||1),0); }catch(e){}
      try{ if(goToCart) { window.location.href = '/cart'; return } }catch(e){}
      // small feedback
      const msg = (item.product?('Added "'+item.product+'" to cart'):'Added to cart');
      try{ alert(msg) }catch(e){}
    }catch(e){ console.error('addToCart', e); alert('Could not add to cart') } }

  window.contactSeller = function(seller, item){ try{
      if(!seller){ alert('Seller contact not available'); return }
      if(typeof seller === 'string' && seller.includes('@')){
        const subj = item && item.product ? encodeURIComponent('Interested in '+item.product) : 'Interested';
        window.location.href = 'mailto:' + seller + '?subject=' + subj;
        return;
      }
      // fallback: open sell page with contact param
      // include product name when available to prefill the seller contact form
      var url = '/sell.html' + (seller ? ('?contact=' + encodeURIComponent(seller)) : '');
      try{ if(item && item.product){ url += (url.indexOf('?')===-1 ? '?' : '&') + 'product=' + encodeURIComponent(item.product); } }catch(e){}
      window.location.href = url;
    }catch(e){ console.error(e); alert('Unable to contact seller') } }

  

  // initialize cart count
  try{ window.updateCartCount() }catch(e){}

  // ensure translations run after DOM load (helpful if header injected late)
  try{
    document.addEventListener('DOMContentLoaded', ()=>{ try{ ensureI18nLoaded(applyTranslations); }catch(e){} });
    // also run once now in case we're already after DOMContentLoaded
    if(document.readyState === 'interactive' || document.readyState === 'complete'){ try{ ensureI18nLoaded(applyTranslations); }catch(e){} }
  }catch(e){}
})();
