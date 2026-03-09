// header.js - injects a site header and profile menu
// Only inject header on site pages (skip profile and admin pages)
(async function(){
  // Inject ui-kit (Tailwind + FA + Poppins + CSS) early
  try{
    if(!document.getElementById('agri-kit-css')){
      var _uks=document.createElement('script'); _uks.src='/ui-kit.js'; document.head.appendChild(_uks);
    }
  }catch(e){}

  // Apply saved theme early so pages (including those that skip header) get consistent styles
  try{
    const saved = localStorage.getItem('agri_theme');
    if(saved === 'light'){
      document.body.classList.remove('dark-mode');
    } else if(saved === 'dark'){
      document.body.classList.add('dark-mode');
    } else {
      // default to dark on first visit
      document.body.classList.add('dark-mode');
      localStorage.setItem('agri_theme', 'dark');
    }
  }catch(e){ /* ignore theme apply errors */ }

  try{
    const _path = (window.location && window.location.pathname) ? window.location.pathname.toLowerCase() : '/';
    // skip if path contains 'admin' (covers /admin/*, admin_dashboard, admin_*.html, etc.)
    if(_path.includes('/admin') || _path.indexOf('admin_')!==-1) {
      // do nothing on admin pages (but theme is already applied)
      return;
    }
  }catch(e){ /* ignore and continue to render header by default */ }
    function createHeaderHtml(){
    var LS='color:#94a3b8;text-decoration:none;padding:7px 12px;border-radius:8px;font-size:13px;font-weight:500;transition:all .15s;display:flex;align-items:center;gap:5px;white-space:nowrap';
    var LH="this.style.color='#fff';this.style.background='rgba(255,255,255,.08)'";
    var LO="this.style.color='#94a3b8';this.style.background='transparent'";
    return `
    <nav style="position:fixed;top:0;left:0;right:0;z-index:9999;background:rgba(15,23,42,.8);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,.06);font-family:'Poppins',sans-serif" id="site-nav">
      <div style="max-width:1280px;margin:0 auto;padding:0 20px;display:flex;align-items:center;justify-content:space-between;height:68px;gap:16px;position:relative">

        <a id="brand-link" href="/home" style="display:flex;align-items:center;gap:10px;text-decoration:none;flex-shrink:0">
          <div style="width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,#10b981,#3b82f6);display:flex;align-items:center;justify-content:center;color:#fff;font-size:17px;box-shadow:0 4px 12px rgba(16,185,129,.35)">
            <i class="fa-solid fa-leaf"></i>
          </div>
          <span style="font-size:18px;font-weight:700;color:#fff;letter-spacing:-.02em">Agri<span id="brand-text" style="background:linear-gradient(135deg,#34d399,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">AI-360</span></span>
        </a>

        <button class="mobile-menu-btn" id="mobile-menu-btn" type="button" style="background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.09);color:#94a3b8;width:36px;height:36px;border-radius:9px;cursor:pointer;font-size:16px;align-items:center;justify-content:center" onclick="document.getElementById('mobile-drawer').style.display=document.getElementById('mobile-drawer').style.display==='flex'?'none':'flex'"><i class="fa-solid fa-bars"></i></button>

        <div class="nav-links" style="display:flex;align-items:center;gap:2px;flex-wrap:nowrap">
          <a id="nav-home" href="/home" title="Home" style="${LS}" onmouseover="${LH}" onmouseout="${LO}"><i class="fa-solid fa-house"></i></a>
          <a id="nav-detect" href="/detect" data-i18n="nav.detect" style="${LS}" onmouseover="${LH}" onmouseout="${LO}"><i class="fa-solid fa-magnifying-glass-plus fa-xs"></i>Detect</a>
          <a id="nav-market" href="/market" data-i18n="nav.market" style="${LS}" onmouseover="${LH}" onmouseout="${LO}"><i class="fa-solid fa-store fa-xs"></i>Market</a>
          <a id="nav-weather" href="/weather" data-i18n="nav.weather" style="${LS}" onmouseover="${LH}" onmouseout="${LO}"><i class="fa-solid fa-cloud-sun fa-xs"></i>Weather</a>
          <a id="nav-buy" href="/buy.html" data-i18n="nav.buy" style="${LS}" onmouseover="${LH}" onmouseout="${LO}">Buy</a>
          <a id="nav-sell" href="/sell.html" data-i18n="nav.sell" style="${LS}" onmouseover="${LH}" onmouseout="${LO}">Sell</a>
        </div>

        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
          <style>
            @media(max-width:768px){
              #site-nav .nav-links{display:none !important}
              #site-nav .mobile-menu-btn{display:flex !important}
              #site-nav .mobile-menu-btn{position:absolute !important;left:12px !important;top:50% !important;transform:translateY(-50%) !important;z-index:2}
              #site-nav #brand-link{margin-left:52px !important}
            }
            #site-nav .mobile-menu-btn{display:none}
          </style>

          <div id="profile-block" style="position:relative"></div>
        </div>
      </div>
    </nav>
    <div id="mobile-drawer" style="display:none;position:fixed;top:68px;left:0;right:0;z-index:9998;background:rgba(15,23,42,.95);backdrop-filter:blur(20px);flex-direction:column;padding:12px 16px;gap:4px;border-bottom:1px solid rgba(255,255,255,.08);font-family:'Poppins',sans-serif">
      <a href="/home" style="padding:10px 12px;color:#94a3b8;text-decoration:none;border-radius:8px;font-size:14px;display:flex;align-items:center;gap:8px" onclick="this.parentElement.style.display='none'"><i class="fa-solid fa-house fa-xs"></i>Home</a>
      <a href="/detect" style="padding:10px 12px;color:#94a3b8;text-decoration:none;border-radius:8px;font-size:14px;display:flex;align-items:center;gap:8px" onclick="this.parentElement.style.display='none'"><i class="fa-solid fa-magnifying-glass-plus fa-xs"></i>Detect</a>
      <a href="/market" style="padding:10px 12px;color:#94a3b8;text-decoration:none;border-radius:8px;font-size:14px;display:flex;align-items:center;gap:8px" onclick="this.parentElement.style.display='none'"><i class="fa-solid fa-store fa-xs"></i>Market</a>
      <a href="/weather" style="padding:10px 12px;color:#94a3b8;text-decoration:none;border-radius:8px;font-size:14px;display:flex;align-items:center;gap:8px" onclick="this.parentElement.style.display='none'"><i class="fa-solid fa-cloud-sun fa-xs"></i>Weather</a>
      <a href="/buy.html" style="padding:10px 12px;color:#94a3b8;text-decoration:none;border-radius:8px;font-size:14px;display:flex;align-items:center;gap:8px" onclick="this.parentElement.style.display='none'"><i class="fa-solid fa-cart-shopping fa-xs"></i>Buy</a>
      <a href="/sell.html" style="padding:10px 12px;color:#94a3b8;text-decoration:none;border-radius:8px;font-size:14px;display:flex;align-items:center;gap:8px" onclick="this.parentElement.style.display='none'"><i class="fa-solid fa-tags fa-xs"></i>Sell</a>
    </div>
    <div style="height:68px"></div>
    `;
  }

  function renderProfileMenu(user){
    const p = document.getElementById('profile-block');
    if(!p) return;
    // ensure the Home link goes to /login for anonymous users
    const homeLink = document.getElementById('nav-home');
    if(!user || !user.logged){
      p.innerHTML = `<a href='/login' style='display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:9px;background:linear-gradient(135deg,#10b981,#0ea5e9);color:#fff;text-decoration:none;font-size:13px;font-weight:600;box-shadow:0 4px 12px rgba(16,185,129,.3)'>Login</a>`;
      if(homeLink) homeLink.href = '/login';
      return;
    }

    if(homeLink) homeLink.href = '/home';

    const email = (user.user && user.user.email) || 'user';
    const initial = email[0].toUpperCase();
    p.innerHTML = `
      <button id='profile-btn' style='display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);padding:6px 12px 6px 6px;border-radius:20px;cursor:pointer;color:#f1f5f9;font-weight:600;font-size:13px;font-family:Poppins,sans-serif;transition:all .15s' onmouseover="this.style.background='rgba(255,255,255,.12)'" onmouseout="this.style.background='rgba(255,255,255,.07)'">
        <span style='width:26px;height:26px;border-radius:13px;background:linear-gradient(135deg,#10b981,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff'>${initial}</span>
        ${email.split('@')[0]}
      </button>
      <div id='profile-menu' style='display:none;position:absolute;right:0;top:44px;background:#1e293b;border:1px solid rgba(255,255,255,.1);box-shadow:0 16px 40px rgba(0,0,0,.4);min-width:200px;border-radius:14px;padding:8px;z-index:9999;font-family:Poppins,sans-serif'>
        <div style='padding:10px 12px 10px;border-bottom:1px solid rgba(255,255,255,.07);margin-bottom:4px'>
          <div style='font-size:11px;color:#64748b;margin-bottom:2px'>Signed in as</div>
          <strong style='color:#f1f5f9;font-size:13px'>${email}</strong>
        </div>
        <a href='/profile' style='display:flex;align-items:center;gap:8px;padding:9px 12px;color:#cbd5e1;text-decoration:none;border-radius:8px;font-size:13px;transition:all .15s' onmouseover="this.style.background='rgba(255,255,255,.07)'" onmouseout="this.style.background='transparent'"><i class='fa-solid fa-user fa-xs' style='color:#94a3b8'></i>Profile</a>
        <a href='/buy-sell' style='display:flex;align-items:center;gap:8px;padding:9px 12px;color:#cbd5e1;text-decoration:none;border-radius:8px;font-size:13px;transition:all .15s' onmouseover="this.style.background='rgba(255,255,255,.07)'" onmouseout="this.style.background='transparent'"><i class='fa-solid fa-receipt fa-xs' style='color:#94a3b8'></i>My Orders</a>
        <button id='logout-btn' style='display:flex;align-items:center;gap:8px;width:100%;padding:9px 12px;margin-top:4px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.2);border-radius:8px;cursor:pointer;color:#f87171;font-size:13px;font-weight:600;font-family:Poppins,sans-serif;transition:all .15s' onmouseover="this.style.background='rgba(239,68,68,.2)'" onmouseout="this.style.background='rgba(239,68,68,.12)'"><i class='fa-solid fa-arrow-right-from-bracket fa-xs'></i>Logout</button>
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
      if(btn) btn.innerHTML = (t === 'dark') ? '<i class="fa-solid fa-moon"></i>' : '<i class="fa-solid fa-sun"></i>';
    }catch(e){}
  }

  function toggleTheme(){
    try{
      const isDark = document.body.classList.contains('dark-mode');
      setTheme(isDark ? 'light' : 'dark');
    }catch(e){}
  }

  // hook up theme toggle button (if present)
  try{ const tb = document.getElementById('theme-toggle'); if(tb){ tb.addEventListener('click', toggleTheme); /* init label */ const saved=localStorage.getItem('agri_theme')||'dark'; tb.innerHTML = saved==='dark'?'<i class="fa-solid fa-moon"></i>':'<i class="fa-solid fa-sun"></i>'; } }catch(e){}

  // Ensure a theme is always selected for first-time visitors
  try{ if(!localStorage.getItem('agri_theme')){ localStorage.setItem('agri_theme','dark'); document.body.classList.add('dark-mode'); } }catch(e){}

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
    const script = document.createElement('script'); script.src='/i18n.js'; document.head.appendChild(script);
    script.onload = ()=>{
      try{
        // expose helper for programmatic language changes
        window.setLanguage = function(l){ try{ if(!l) return; localStorage.setItem('agri_lang', l); document.documentElement.lang = l; ensureI18nLoaded(function(){ try{ if(typeof window.applyTranslations === 'function') window.applyTranslations(); }catch(e){} });
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
  function normalizeAvailableQuantity(item){
      const raw = item && (item.available_quantity ?? item.quantity ?? item.stock ?? null);
      const parsed = Number(raw);
      return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }
    function normalizeIconPath(icon){
      const text = (icon || '').toString().trim();
      if(!text) return '';
      if(text.startsWith('/') || /^https?:\/\//i.test(text) || /^data:/i.test(text)) return text;
      return '/icons/' + text.replace(/^\/+/, '');
    }
  window.addToCart = function(item, goToCart){ try{
      if(!item) { alert('Item not available'); return }
      const cart = window.getCart();
      const itemIcon = normalizeIconPath(item.icon);
      const availableQuantity = normalizeAvailableQuantity(item);
      // ensure a stable id exists for the cart item
      if(!item.id){ try{ item.id = ('prod_'+((item.product||'').toString().toLowerCase().replace(/[^a-z0-9]+/g,'_'))+'_'+((item.seller||'').toString().toLowerCase().replace(/[^a-z0-9]+/g,'_'))).replace(/_+$/,''); }catch(e){} }
      const existing = cart.find(c=> (c.id && item.id && c.id==item.id) || (c.product && item.product && c.product==item.product && c.seller==item.seller) );
      if(existing){
        const nextQty = (existing.qty||1) + 1;
        const limit = availableQuantity || existing.available_quantity || null;
        if(limit !== null && nextQty > limit){ alert('Only '+limit+' kg available for '+(item.product||'this product')+'.'); return }
        existing.qty = nextQty;
        if(itemIcon) existing.icon = itemIcon;
        if(limit !== null) existing.available_quantity = limit;
      }
      else {
        cart.push(Object.assign({}, { id: item.id, product: item.product, seller: item.seller, price: item.price, qty: 1, icon: itemIcon || null, available_quantity: availableQuantity }))
      }
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
