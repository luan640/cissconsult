(function () {
  const chartInstances = [];
  const destroyCharts = () => {
    while (chartInstances.length) {
      const chart = chartInstances.pop();
      if (chart) {
        chart.destroy();
      }
    }
  };

  const initDashboardCharts = () => {
    const dataNode = document.getElementById('dashboard-chart-data');
    if (!dataNode || typeof Chart === 'undefined') {
      return;
    }

    destroyCharts();

    Chart.defaults.font.family = '"Plus Jakarta Sans", "Segoe UI", sans-serif';
    Chart.defaults.font.size = 13;
    Chart.defaults.color = '#334155';

    const palette = {
      text: '#334155',
      grid: 'rgba(100, 116, 139, 0.16)',
      emerald: '#10b981',
      teal: '#14b8a6',
      cyan: '#06b6d4',
      blue: '#3b82f6',
      indigo: '#6366f1',
      violet: '#8b5cf6',
      amber: '#f59e0b',
      rose: '#f43f5e',
      slate: '#64748b',
    };

    const chartData = JSON.parse(dataNode.textContent);
  const createVerticalGradient = (context, fromColor, toColor) => {
    const chart = context.chart;
    const { chartArea } = chart;
    if (!chartArea) {
      return fromColor;
    }
    const gradient = chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, fromColor);
    gradient.addColorStop(1, toColor);
    return gradient;
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 420,
      easing: 'easeOutQuart',
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          pointStyle: 'circle',
          boxWidth: 8,
          boxHeight: 8,
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.92)',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        cornerRadius: 10,
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
          drawBorder: false,
        },
        ticks: {
          color: palette.text,
        },
      },
      y: {
        beginAtZero: true,
        grid: {
          display: false,
          drawBorder: false,
        },
        ticks: {
          color: palette.text,
          precision: 0,
        },
      },
    },
  };

    const byId = (id) => document.getElementById(id);

    const moodCanvas = byId('chartMoodDistribution');
    if (moodCanvas) {
      chartInstances.push(new Chart(moodCanvas, {
      type: 'doughnut',
      data: {
        labels: chartData.mood_distribution.labels,
        datasets: [
          {
            data: chartData.mood_distribution.values,
            backgroundColor: [palette.emerald, palette.teal, palette.blue, palette.amber, palette.rose],
            borderColor: '#ffffff',
            borderWidth: 2,
            hoverOffset: 8,
          },
        ],
      },
      options: {
        ...chartOptions,
        scales: undefined,
        cutout: '62%',
      },
      }));
    }

    const timelineCanvas = byId('chartTimeline');
    if (timelineCanvas) {
      chartInstances.push(new Chart(timelineCanvas, {
      type: 'line',
      data: {
        labels: chartData.timeline.labels,
        datasets: [
          {
            label: 'Humor',
            data: chartData.timeline.mood_values,
            borderColor: palette.emerald,
            backgroundColor: (context) =>
              createVerticalGradient(context, 'rgba(16, 185, 129, 0.35)', 'rgba(16, 185, 129, 0.02)'),
            pointBackgroundColor: palette.emerald,
            pointBorderColor: '#ffffff',
            pointRadius: 3,
            pointHoverRadius: 5,
            fill: true,
            borderWidth: 2.5,
            tension: 0.3,
          },
          {
            label: 'Denuncias',
            data: chartData.timeline.complaint_values,
            borderColor: palette.violet,
            backgroundColor: (context) =>
              createVerticalGradient(context, 'rgba(139, 92, 246, 0.25)', 'rgba(139, 92, 246, 0.02)'),
            pointBackgroundColor: palette.violet,
            pointBorderColor: '#ffffff',
            pointRadius: 3,
            pointHoverRadius: 5,
            fill: true,
            borderWidth: 2.5,
            tension: 0.3,
          },
        ],
      },
      options: chartOptions,
      }));
    }

    const weekdayCanvas = byId('chartWeekday');
    if (weekdayCanvas) {
      chartInstances.push(new Chart(weekdayCanvas, {
      type: 'bar',
      data: {
        labels: chartData.weekday_frequency.labels,
        datasets: [
          {
            label: 'Usos',
            data: chartData.weekday_frequency.values,
            backgroundColor: [palette.cyan, palette.blue, palette.indigo, palette.teal, palette.emerald, palette.amber, palette.rose],
            borderRadius: 10,
            borderSkipped: false,
            maxBarThickness: 36,
          },
        ],
      },
      options: {
        ...chartOptions,
        layout: {
          padding: { left: 10, right: 10 },
        },
        scales: {
          ...chartOptions.scales,
          x: {
            ...chartOptions.scales.x,
            offset: true,
          },
        },
      },
      }));
    }

    const comparisonCanvas = byId('chartPeriodComparison');
    if (comparisonCanvas) {
      chartInstances.push(new Chart(comparisonCanvas, {
      type: 'bar',
      data: {
        labels: chartData.period_comparison.labels,
        datasets: [
          {
            label: 'Registros totais',
            data: chartData.period_comparison.values,
            backgroundColor: [palette.indigo, palette.slate],
            borderRadius: 12,
            borderSkipped: false,
            maxBarThickness: 44,
          },
        ],
      },
      options: {
        ...chartOptions,
        layout: {
          padding: { left: 10, right: 10 },
        },
        scales: {
          ...chartOptions.scales,
          x: {
            ...chartOptions.scales.x,
            offset: true,
          },
        },
      },
      }));
    }

    const totemUsageCanvas = byId('chartTotemUsage');
    if (totemUsageCanvas) {
      chartInstances.push(new Chart(totemUsageCanvas, {
      type: 'bar',
      data: {
        labels: chartData.totem_usage.labels,
        datasets: [
          {
            label: 'Registros por totem',
            data: chartData.totem_usage.values,
            backgroundColor: [palette.teal, palette.cyan, palette.blue, palette.indigo, palette.violet, palette.emerald],
            borderRadius: 10,
            borderSkipped: false,
            maxBarThickness: 38,
          },
        ],
      },
      options: {
        ...chartOptions,
        layout: {
          padding: { left: 10, right: 10 },
        },
        scales: {
          ...chartOptions.scales,
          x: {
            ...chartOptions.scales.x,
            offset: true,
          },
        },
      },
      }));
    }

    const moodByDepartmentCanvas = byId('chartMoodByDepartment');
    if (moodByDepartmentCanvas) {
      const moodDistributionSets = chartData.mood_distribution_by_department.datasets || [];
      const moodColors = [palette.emerald, palette.teal, palette.cyan, palette.blue, palette.amber];
      chartInstances.push(new Chart(moodByDepartmentCanvas, {
      type: 'bar',
      data: {
        labels: chartData.mood_distribution_by_department.labels,
        datasets: moodDistributionSets.map((item, idx) => ({
          label: item.label,
          data: item.values,
          backgroundColor: moodColors[idx % moodColors.length],
          borderRadius: 6,
          borderSkipped: false,
          maxBarThickness: 38,
        })),
      },
      options: {
        ...chartOptions,
        plugins: {
          ...chartOptions.plugins,
          legend: {
            ...chartOptions.plugins.legend,
            position: 'bottom',
          },
        },
        layout: {
          padding: { left: 10, right: 10 },
        },
        scales: {
          ...chartOptions.scales,
          x: {
            ...chartOptions.scales.x,
            offset: true,
            stacked: true,
          },
          y: {
            ...chartOptions.scales.y,
            stacked: true,
          },
        },
      },
      }));
    }

    const complaintByDepartmentCanvas = byId('chartComplaintByDepartment');
    if (complaintByDepartmentCanvas) {
      chartInstances.push(new Chart(complaintByDepartmentCanvas, {
      type: 'bar',
      data: {
        labels: chartData.complaint_by_department.labels,
        datasets: [
          {
            label: 'Denuncia por setor',
            data: chartData.complaint_by_department.values,
            backgroundColor: [palette.violet, palette.indigo, palette.blue, palette.cyan, palette.teal, palette.rose],
            borderRadius: 10,
            borderSkipped: false,
            maxBarThickness: 38,
          },
        ],
      },
      options: {
        ...chartOptions,
        layout: {
          padding: { left: 10, right: 10 },
        },
        scales: {
          ...chartOptions.scales,
          x: {
            ...chartOptions.scales.x,
            offset: true,
          },
        },
      },
      }));
    }

    const complaintByTypeCanvas = byId('chartComplaintByType');
    if (complaintByTypeCanvas) {
      chartInstances.push(new Chart(complaintByTypeCanvas, {
      type: 'bar',
      data: {
        labels: chartData.complaint_by_type.labels,
        datasets: [
          {
            label: 'Denuncia por tipo',
            data: chartData.complaint_by_type.values,
            backgroundColor: [palette.rose, palette.amber, palette.violet, palette.indigo, palette.blue, palette.teal],
            borderRadius: 10,
            borderSkipped: false,
            maxBarThickness: 38,
          },
        ],
      },
      options: {
        ...chartOptions,
        layout: {
          padding: { left: 10, right: 10 },
        },
        scales: {
          ...chartOptions.scales,
          x: {
            ...chartOptions.scales.x,
            offset: true,
          },
        },
      },
      }));
    }
  };

  window.initDashboardCharts = initDashboardCharts;
  initDashboardCharts();
})();
