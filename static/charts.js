document.addEventListener("DOMContentLoaded", () => {
    // Category dots
    document.querySelectorAll("[data-color]").forEach((item) => {
        item.style.backgroundColor = item.dataset.color;
    });

    // Current month category chart
    const category = document.getElementById("categoryChart");
    if (category && window.Chart) {
        createBarChart(
            category,
            JSON.parse(category.dataset.labels),
            JSON.parse(category.dataset.values).map(Number),
            JSON.parse(category.dataset.colors),
            true
        );
    }

    // Monthly report chart
    const monthly = document.getElementById("monthlyChart");
    if (monthly && window.Chart) {
        const rows = JSON.parse(monthly.dataset.rows).filter((row) => Number(row.total) > 0);
        createBarChart(
            monthly,
            rows.map((row) => row.name),
            rows.map((row) => Number(row.total)),
            rows.map((row) => row.color),
            false
        );
    }

    // Six month trend
    const trend = document.getElementById("trendChart");
    if (trend && window.Chart) {
        const rows = JSON.parse(trend.dataset.rows);
        createTrendChart(
            trend,
            rows.map((row) => formatMonth(row.month)),
            rows.map((row) => Number(row.total))
        );
    }
});

// Format month
function formatMonth(value) {
    const [year, month] = value.split("-");
    return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-IN", {
        month: "short",
        year: "numeric"
    });
}

// Bar chart
function createBarChart(canvas, labels, values, colors, horizontal) {
    const valueAxis = horizontal ? "x" : "y";
    const categoryAxis = horizontal ? "y" : "x";
    new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderRadius: 7,
                borderSkipped: false
            }]
        },
        options: {
            indexAxis: horizontal ? "y" : "x",
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                [valueAxis]: {
                    beginAtZero: true,
                    grid: {
                        color: "#eef2f7"
                    },
                    ticks: {
                        callback: (value) => `₹${Number(value).toLocaleString("en-IN")}`
                    }
                },
                [categoryAxis]: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Trend chart
function createTrendChart(canvas, labels, values) {
    new Chart(canvas, {
        type: "line",
        data: {
            labels,
            datasets: [{
                data: values,
                borderWidth: 3,
                tension: 0.35,
                fill: false,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: "#eef2f7"
                    },
                    ticks: {
                        callback: (value) => `₹${Number(value).toLocaleString("en-IN")}`
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}