async function loadData() {
    const res = await fetch('/admin/data');
    const data = await res.json();

    loadCommodities(data.commodities);
    loadDiseases(data.diseases);
}

// -------------------- COMMODITIES --------------------
function loadCommodities(items) {
    let list = document.getElementById("commodityList");
    list.innerHTML = "";

    items.forEach(name => {
        let li = document.createElement("li");
        li.innerHTML = `${name} 
            <button class="deleteBtn" onclick="deleteCommodity('${name}')">Delete</button>`;
        list.appendChild(li);
    });
}

async function addCommodity() {
    let name = document.getElementById("commodityInput").value.trim();
    if (!name) return;

    await fetch("/admin/add_commodity", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name})
    });

    document.getElementById("commodityInput").value = "";
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
    let list = document.getElementById("diseaseList");
    list.innerHTML = "";

    items.forEach(d => {
        let li = document.createElement("li");
        li.innerHTML = `<b>${d.name}</b>: ${d.solution}`;
        list.appendChild(li);
    });
}

async function addDisease() {
    let name = document.getElementById("diseaseName").value.trim();
    let solution = document.getElementById("diseaseSolution").value.trim();

    if (!name || !solution) return;

    await fetch("/admin/add_disease", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, solution})
    });

    document.getElementById("diseaseName").value = "";
    document.getElementById("diseaseSolution").value = "";

    loadData();
}

// Load initial data
loadData();
