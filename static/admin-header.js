// admin-header.js — injects dark glass admin topbar
(function(){
  // Inject ui-kit
  if(!document.getElementById('agri-kit-css')){
    var s=document.createElement('script'); s.src='/ui-kit.js'; document.head.appendChild(s);
  }

  var NAV_STYLE='position:fixed;top:0;left:0;right:0;z-index:9999;background:rgba(15,23,42,.85);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,.07);font-family:\'Poppins\',sans-serif';
  var INNER_STYLE='max-width:1280px;margin:0 auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;height:64px';
  var LINK_STYLE='color:#94a3b8;text-decoration:none;padding:6px 12px;border-radius:8px;font-size:13px;font-weight:500;transition:all .15s;display:flex;align-items:center;gap:6px';
  var LINK_HOVER='this.style.color=\'#fff\';this.style.background=\'rgba(255,255,255,.07)\'';
  var LINK_OUT='this.style.color=\'#94a3b8\';this.style.background=\'transparent\'';

  var nav = document.createElement('nav');
  nav.style.cssText = NAV_STYLE;
  nav.innerHTML = '<div style="'+INNER_STYLE+'">'+
    '<a href="/admin/dashboard" style="display:flex;align-items:center;gap:10px;text-decoration:none">'+
      '<div style="width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#10b981,#3b82f6);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px">'+
        '<i class="fa-solid fa-leaf"></i>'+
      '</div>'+
      '<span style="font-size:16px;font-weight:700;color:#fff">Agri<span style="background:linear-gradient(135deg,#34d399,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">AI-360</span> <span style="font-size:11px;color:#64748b;font-weight:500">Admin</span></span>'+
    '</a>'+
    '<div style="display:flex;align-items:center;gap:2px">'+
      '<a href="/admin/dashboard" style="'+LINK_STYLE+'" onmouseover="'+LINK_HOVER+'" onmouseout="'+LINK_OUT+'"><i class="fa-solid fa-gauge-high fa-xs"></i>Dashboard</a>'+
      '<a href="/admin/orders" style="'+LINK_STYLE+'" onmouseover="'+LINK_HOVER+'" onmouseout="'+LINK_OUT+'"><i class="fa-solid fa-receipt fa-xs"></i>Orders</a>'+
      '<a href="/admin/products" style="'+LINK_STYLE+'" onmouseover="'+LINK_HOVER+'" onmouseout="'+LINK_OUT+'"><i class="fa-solid fa-box fa-xs"></i>Products</a>'+
      '<a href="/admin/commodities" style="'+LINK_STYLE+'" onmouseover="'+LINK_HOVER+'" onmouseout="'+LINK_OUT+'"><i class="fa-solid fa-layer-group fa-xs"></i>Commodities</a>'+
      '<a href="/admin/diseases" style="'+LINK_STYLE+'" onmouseover="'+LINK_HOVER+'" onmouseout="'+LINK_OUT+'"><i class="fa-solid fa-stethoscope fa-xs"></i>Diseases</a>'+
      '<a href="/admin/analytics" style="'+LINK_STYLE+'" onmouseover="'+LINK_HOVER+'" onmouseout="'+LINK_OUT+'"><i class="fa-solid fa-chart-bar fa-xs"></i>Analytics</a>'+
    '</div>'+
    '<a href="/admin/logout" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:9px;background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#f87171;text-decoration:none;font-size:13px;font-weight:600;transition:all .15s" onmouseover="this.style.background=\'rgba(239,68,68,.25)\'" onmouseout="this.style.background=\'rgba(239,68,68,.15)\'">'+
      '<i class="fa-solid fa-arrow-right-from-bracket fa-xs"></i>Logout'+
    '</a>'+
  '</div>';

  // Inject nav at top of body
  document.body.insertBefore(nav, document.body.firstChild);

  // Spacer
  var spacer = document.createElement('div');
  spacer.style.height = '64px';
  document.body.insertBefore(spacer, nav.nextSibling);
})();
