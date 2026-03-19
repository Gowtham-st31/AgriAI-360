// ui-kit.js — injects Tailwind CDN, Font Awesome 6, Poppins, and global SaaS CSS
(function(){
  var h = document.head || document.documentElement;
  function addScript(src){ if(!document.querySelector('script[src="'+src+'"]')){ var s=document.createElement('script'); s.src=src; h.appendChild(s); } }
  function addLink(href){ if(!document.querySelector('link[href="'+href+'"]')){ var l=document.createElement('link'); l.rel='stylesheet'; l.href=href; h.appendChild(l); } }
  addScript('https://cdn.tailwindcss.com');
  addLink('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css');
  addLink('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
  if(!document.getElementById('agri-kit-css')){
    var s=document.createElement('style'); s.id='agri-kit-css';
    s.textContent=[
      '*,*::before,*::after{box-sizing:border-box}',
      'body{font-family:\'Poppins\',sans-serif!important;background:#0f172a;color:#f1f5f9}',
      '.glass-panel{background:rgba(255,255,255,.03);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,.08);box-shadow:0 4px 30px rgba(0,0,0,.12)}',
      '.glass-nav{background:rgba(15,23,42,.75);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,.05)}',
      '.gradient-text{background:linear-gradient(135deg,#34d399 0%,#3b82f6 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}',
      '@keyframes sblob{0%{transform:translate(0,0) scale(1)}33%{transform:translate(30px,-50px) scale(1.1)}66%{transform:translate(-20px,20px) scale(.9)}100%{transform:translate(0,0) scale(1)}}',
      '.animate-blob{animation:sblob 7s infinite}.delay-2s{animation-delay:2s}.delay-4s{animation-delay:4s}',
      '@keyframes sfadeUp{0%{opacity:0;transform:translateY(12px)}100%{opacity:1;transform:translateY(0)}}.fade-in{animation:sfadeUp .5s ease-out forwards}',
      '.file-drop-area.dragover{background:rgba(16,185,129,.1)!important;border-color:#10b981!important;transform:scale(1.02)}',
      // Keep padding in a zero-specificity selector so Tailwind utilities like
      // `pl-10` can override it (prevents icons/logos overlapping input text).
      ':where(.agri-input){padding:10px 14px}',
      '.agri-input{width:100%;border-radius:10px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#f1f5f9;font-size:14px;outline:none;transition:border-color .2s,box-shadow .2s;font-family:\'Poppins\',sans-serif}',
      '.agri-input:focus{border-color:#34d399;box-shadow:0 0 0 3px rgba(52,211,153,.15)}.agri-input::placeholder{color:rgba(255,255,255,.3)}',
      '.agri-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:10px 20px;border-radius:10px;border:none;cursor:pointer;font-size:14px;font-weight:600;font-family:\'Poppins\',sans-serif;transition:all .2s}',
      '.agri-btn-primary{background:linear-gradient(135deg,#10b981,#0ea5e9);color:#fff;box-shadow:0 4px 14px rgba(16,185,129,.3)}.agri-btn-primary:hover{opacity:.9;transform:translateY(-1px)}',
      '.agri-btn-danger{background:#ef4444;color:#fff}.agri-btn-danger:hover{background:#dc2626}',
      '.agri-btn-sm{padding:6px 14px;font-size:12px;border-radius:8px}.agri-btn-ghost{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);color:#f1f5f9}',
      '.agri-btn-ghost:hover{background:rgba(255,255,255,.12)}',
      '.agri-table{width:100%;border-collapse:collapse}.agri-table th{background:rgba(255,255,255,.04);color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,255,255,.07)}',
      '.agri-table td{padding:10px 14px;color:#cbd5e1;border-bottom:1px solid rgba(255,255,255,.05);font-size:13px;vertical-align:middle}.agri-table tr:hover td{background:rgba(255,255,255,.025)}',
      '.agri-badge-green{display:inline-block;padding:2px 10px;border-radius:999px;background:rgba(16,185,129,.15);color:#34d399;font-size:11px;font-weight:600}',
      '.agri-badge-gray{display:inline-block;padding:2px 10px;border-radius:999px;background:rgba(255,255,255,.07);color:#94a3b8;font-size:11px;font-weight:600}',
      '@keyframes agriBump{0%{transform:scale(1)}30%{transform:scale(1.22)}60%{transform:scale(.96)}100%{transform:scale(1)}}.agri-bump{animation:agriBump .35s ease-out}',
      '@keyframes agriToastIn{0%{opacity:0;transform:translateY(10px) scale(.98)}100%{opacity:1;transform:translateY(0) scale(1)}}',
      '@keyframes agriToastOut{0%{opacity:1;transform:translateY(0) scale(1)}100%{opacity:0;transform:translateY(6px) scale(.98)}}',
      '.agri-toast-host{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:10000;display:flex;flex-direction:column;gap:8px;pointer-events:none}',
      '.agri-toast{pointer-events:none;min-width:220px;max-width:min(92vw,420px);padding:10px 12px;border-radius:12px;background:rgba(15,23,42,.92);border:1px solid rgba(255,255,255,.12);box-shadow:0 12px 32px rgba(0,0,0,.35);color:#e2e8f0;font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px;animation:agriToastIn .18s ease-out both}',
      '.agri-toast.out{animation:agriToastOut .18s ease-in both}',
      '.agri-toast i{font-size:14px}',
      '.agri-toast-success i{color:#34d399}',
      '.agri-toast-error i{color:#f87171}',
      '.agri-small-input{width:90px;padding:6px 10px;border-radius:8px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#f1f5f9;font-size:12px;outline:none;font-family:\'Poppins\',sans-serif}',
      '.agri-small-input:focus{border-color:#34d399}'
    ].join('');
    h.appendChild(s);
  }
})();
