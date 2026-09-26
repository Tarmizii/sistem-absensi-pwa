(() => {
  const analysisForm = document.querySelector("[data-once-submit]");
  if (analysisForm) {
    analysisForm.addEventListener("submit", () => {
      const submit = analysisForm.querySelector('[type="submit"]');
      if (submit) {
        submit.disabled = true;
        submit.setAttribute("aria-disabled", "true");
        submit.textContent = "Analisis sedang disiapkan…";
      }
    });
  }

  const payload = document.getElementById("kmeans-chart-data");
  if (!payload || !window.Chart) return;
  let centroids;
  try {
    centroids = JSON.parse(payload.textContent);
  } catch (_error) {
    return;
  }
  const definitions = [
    ["kmeans-attendance-chart", "attendance_percentage", "Persentase"],
    ["kmeans-late-chart", "late_count", "Hari terlambat"],
    ["kmeans-alpha-chart", "alpha_count", "Hari Alpa"],
  ];
  for (const [canvasId, field, label] of definitions) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) continue;
    new window.Chart(canvas, {
      type: "bar",
      data: {
        labels: centroids.map((row) => row.label[0].toUpperCase() + row.label.slice(1)),
        datasets: [{ label, data: centroids.map((row) => row[field]), backgroundColor: ["#7CD3AA", "#F2C879", "#ED896F"], borderRadius: 7 }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ...(field === "attendance_percentage" ? { max: 100 } : {}) } },
      },
    });
  }
})();
