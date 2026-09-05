document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-color]').forEach((item) => item.style.backgroundColor = item.dataset.color);
  const category = document.getElementById('categoryChart');
  if (category && window.Chart) {
    createChart(category, JSON.parse(category.dataset.labels),
      JSON.parse(category.dataset.values).map(Number),
      JSON.parse(category.dataset.colors), true);
  }
  const monthly = document.getElementById('monthlyChart');
  if (monthly && window.Chart) {
    const rows = JSON.parse(monthly.dataset.rows).filter((row) => Number(row.total) > 0);
    createChart(monthly, rows.map((row) => row.name),
      rows.map((row) => Number(row.total)),
      rows.map((row) => row.color), false);
  }
});

function createChart(canvas, labels, values, colors, horizontal) {
  const valueAxis = horizontal ? 'x' : 'y';
  const categoryAxis = horizontal ? 'y' : 'x';
  new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 7, borderSkipped: false }] },
    options: {
      indexAxis: horizontal ? 'y' : 'x', maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        [valueAxis]: {
          beginAtZero: true, grid: { color: '#eef2f7' },
          ticks: { callback: (value) => `₹${value}` }
        },
        [categoryAxis]: { grid: { display: false } }
      }
    }
  });
}
