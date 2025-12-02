let chart;

function drawPriceChart(data) {
  const ctx = document.getElementById("priceChart").getContext("2d");

  const dates = data.map(x => x.arrival_date).reverse();
  const prices = data.map(x => parseInt(x.modal_price)).reverse();

  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: dates,
      datasets: [{
        label: "Modal Price (₹)",
        data: prices,
        borderWidth: 3,
        tension: 0.4
      }]
    },
    options: { responsive: true }
  });
}
