// MULTI-LANGUAGE
let lang = "en";

const TEXT = {
  en: {
    title: "🌾 Farmer Assistant Portal",
    toggle: "தமிழிற்கு மாற்றவும்",
    market: "📊 Daily Market Price",
    getPrice: "Get Market Price",
    disease: "🩺 Plant Disease Detection",
    analyze: "Analyze Image",
    noData: "No data found",
  },
  ta: {
    title: "🌾 விவசாய உதவியாளர் போர்டல்",
    toggle: "Switch to English",
    market: "📊 தினசரி சந்தை விலை",
    getPrice: "சந்தை விலையை காண்",
    disease: "🩺 செடி நோய் கண்டறிதல்",
    analyze: "படத்தை பகுப்பாய்வு செய்யவும்",
    noData: "தகவல் இல்லை",
  }
};

function toggleLang() {
  lang = (lang === "en") ? "ta" : "en";

  document.getElementById("title").innerText = TEXT[lang].title;
  document.getElementById("toggleLabel").innerText = TEXT[lang].toggle;
  document.getElementById("marketTitle").innerText = TEXT[lang].market;
  document.getElementById("diseaseTitle").innerText = TEXT[lang].disease;
  document.getElementById("analyzeBtn").innerText = TEXT[lang].analyze;
  document.getElementById("getPriceBtn").innerText = TEXT[lang].getPrice;
}


// COMMODITY LIST
const commodities = [
  "Tomato","Onion","Potato","Banana","Paddy","Maize","Cotton",
  "Groundnut","Sugarcane","Turmeric","Chilli","Coriander"
];

window.onload = () => {
  commodities.forEach(c => {
    document.getElementById("commodity").innerHTML += `<option value="${c}">${c}</option>`;
  });

  // Auto-load States from pre-defined list
  Object.keys(stateMarkets).forEach(st => {
    document.getElementById("state").innerHTML += `<option value="${st}">${st}</option>`;
  });
};


// STATE -> MARKET
const stateMarkets = {
  "Tamil Nadu": ["Coimbatore","Erode","Salem","Madurai","Tirunelveli"],
  "Karnataka": ["Bangalore","Mysore","Hubli"],
  "Andhra Pradesh": ["Guntur","Vijayawada"],
  "Kerala": ["Palakkad","Thrissur"],
};

document.getElementById("state").addEventListener("change", () => {
  const st = document.getElementById("state").value;
  document.getElementById("market").innerHTML = "<option>Select Market</option>";
  if (stateMarkets[st]) {
    stateMarkets[st].forEach(m => {
      document.getElementById("market").innerHTML += `<option value="${m}">${m}</option>`;
    });
  }
});


// GET PRICE
document.getElementById("checkPrice").onclick = async () => {
  const c = document.getElementById("commodity").value;
  const st = document.getElementById("state").value;
  const mk = document.getElementById("market").value;

  const params = new URLSearchParams({ commodity: c, state: st, market: mk, ai: '1' });
  const res = await fetch(`/price?${params}`);
  const data = await res.json();

  if (!data.data.length) {
    document.getElementById("priceOutput").innerHTML = TEXT[lang].noData;
    return;
  }

  // Cards
  let html = "";

  // Optional AI summary
  try {
    if (data.ai) {
      if (data.ai.enabled === true && data.ai.parsed && data.ai.parsed.recommended_modal_price != null) {
        const p = data.ai.parsed;
        const currency = p.currency || 'INR';
        const unit = p.unit || '100kg';
        const symbol = (currency === 'INR') ? '₹' : '';
        html += `
          <div class="card p-3 mt-3">
            <b>AI Recommended Price:</b> ${symbol}${p.recommended_modal_price} / ${unit}<br>
            ${p.rationale ? `<b>Why:</b> ${p.rationale}<br>` : ''}
          </div>
        `;
      } else if (data.ai.enabled === false) {
        const reason = data.ai.reason || 'AI summary unavailable';
        html += `
          <div class="card p-3 mt-3">
            <b>AI Summary:</b> ${reason}
          </div>
        `;
      }
    }
  } catch (e) {
    // ignore AI rendering errors
  }

  data.data.forEach(item => {
    html += `
      <div class="card p-3 mt-3">
        <b>Commodity:</b> ${item.commodity}<br>
        <b>State:</b> ${item.state}<br>
        <b>Market:</b> ${item.market}<br>
        <b>Modal Price:</b> ₹${item.modal_price}<br>
        <b>Date:</b> ${item.arrival_date}
      </div>
    `;
  });

  document.getElementById("priceOutput").innerHTML = html;

  // Chart
  drawPriceChart(data.data);
};


// PREDICT DISEASE
document.getElementById("predictBtn").onclick = async () => {
  const file = document.getElementById("imgFile").files[0];
  const fd = new FormData();
  fd.append("image", file);

  const res = await fetch("/predict", { method: "POST", body: fd });
  const data = await res.json();

  document.getElementById("predictOutput").innerHTML = `
    <div class="card p-3">
      <b>Disease:</b> ${data.disease}<br>
      <b>Confidence:</b> ${(data.confidence*100).toFixed(2)}%<br>
      <b>Solution:</b> ${data.solution}<br>
      <button class="btn btn-info mt-2" onclick="speakTamil('${data.solution}')">
        🔊 Speak Solution (Tamil)
      </button>
    </div>
  `;
};


// GPS DETECT LOCATION
function detectLocation() {
  navigator.geolocation.getCurrentPosition(pos => {
    alert("GPS Detected! You are near Coimbatore Market");
    document.getElementById("state").value = "Tamil Nadu";
    document.getElementById("market").value = "Coimbatore";
  });
}
