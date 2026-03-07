// ID helpers — support both original IDs and redesigned HTML IDs
function _el(id1, id2){ return document.getElementById(id1) || document.getElementById(id2); }

async function loadData() {
    const res = await fetch('/admin/data');
    const data = await res.json();
    loadCommodities(data.commodities);
    loadDiseases(data.diseases);
}

// -------------------- COMMODITIES --------------------
function loadCommodities(items) {
    const list = _el("commodityList", "commodities-list");
    if(!list) return;
    list.innerHTML = "";
    if(!items || !items.length){
        list.innerHTML = '<div style="color:#64748b;font-size:13px;padding:8px 0">No commodities yet.</div>';
        return;
    }
    items.forEach(name => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);margin-bottom:6px";
        row.innerHTML = `<span style="color:#e2e8f0;font-size:13px;font-weight:500">${name}</span>
            <button onclick="deleteCommodity('${name}')" style="padding:5px 12px;border-radius:7px;background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.25);color:#f87171;font-size:11px;font-weight:600;cursor:pointer;font-family:'Poppins',sans-serif;transition:background .15s" onmouseover="this.style.background='rgba(239,68,68,.25)'" onmouseout="this.style.background='rgba(239,68,68,.15)'"><i class="fa-solid fa-trash fa-xs"></i> Delete</button>`;
        list.appendChild(row);
    });
}

async function addCommodity() {
    const input = _el("commodityInput", "commodity");
    if(!input) return;
    const name = input.value.trim();
    if (!name) return;
    await fetch("/admin/add_commodity", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name})
    });
    input.value = "";
    loadData();
}

async function deleteCommodity(name) {
    await fetch("/admin/delete_commodity", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name})
    });
    loadData();
}

// -------------------- DISEASES --------------------
function loadDiseases(items) {
    const list = _el("diseaseList", "disease-list");
    if(!list) return;
    list.innerHTML = "";
    if(!items || !items.length){
        list.innerHTML = '<div style="color:#64748b;font-size:13px;padding:8px 0">No diseases yet.</div>';
        return;
    }
    items.forEach(d => {
        const row = document.createElement("div");
        row.style.cssText = "padding:12px 14px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);margin-bottom:8px";
        row.innerHTML = `<div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:4px">${d.name}</div><div style="font-size:12px;color:#94a3b8;line-height:1.5">${d.solution}</div>`;
        list.appendChild(row);
    });
}

async function addDisease() {
    const nameEl = _el("diseaseName", "disease");
    const solEl = _el("diseaseSolution", "solution");
    if(!nameEl || !solEl) return;
    const name = nameEl.value.trim();
    const solution = solEl.value.trim();
    if (!name || !solution) return;
    await fetch("/admin/add_disease", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, solution})
    });
    nameEl.value = "";
    solEl.value = "";
    loadData();
}

// Load initial data
loadData();
