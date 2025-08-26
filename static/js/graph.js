document.addEventListener("DOMContentLoaded", function () {
    // Utility: Open modal and initialize chart.
    function openModal(modalId, initializeChartFn) {
      const modal = document.getElementById(modalId);
      modal.style.display = "block";
      initializeChartFn();
    }
    
    // Utility: Close modal.
    function closeModal(modalId) {
      const modal = document.getElementById(modalId);
      modal.style.display = "none";
    }
    
    // Attach event listeners to all close buttons.
    document.querySelectorAll(".modal .close").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const modalId = btn.getAttribute("data-modal");
        closeModal(modalId);
      });
    });
    
    // Close modal when clicking outside the modal content.
    window.addEventListener("click", function (event) {
      if (event.target.classList.contains("modal")) {
        event.target.style.display = "none";
      }
    });
    
    // Common animation and grid options for Chart.js charts.
    const commonOptions = {
      responsive: true,
      animation: {
        duration: 1500,
        easing: "easeInOutQuart"
      },
      plugins: {
        legend: {
          display: true,
          labels: { font: { size: 14 } }
        }
      },
      scales: {
        x: {
          grid: { display: true, color: "rgba(0,0,0,0.1)" },
          title: {
            display: true,
            text: "Date",
            font: { size: 16, weight: "bold" }
          }
        }
      }
    };
  
    // Initialize CTR Chart (Chart.js).
    function initializeCtrChart() {
      const dates = perfData.map(item => item.date);
      const ctrValues = perfData.map(item => item.ctr);
      const ctx = document.getElementById("ctrChart").getContext("2d");
      new Chart(ctx, {
        type: "line",
        data: {
          labels: dates,
          datasets: [{
            label: "CTR",
            data: ctrValues,
            fill: false,
            borderColor: "rgb(75, 192, 192)",
            backgroundColor: "rgba(75,192,192,0.2)",
            tension: 0.3,
            pointRadius: 6,
            pointHoverRadius: 8,
            pointBackgroundColor: "rgb(75, 192, 192)"
          }]
        },
        options: Object.assign({}, commonOptions, {
          plugins: {
            tooltip: {
              callbacks: {
                label: context => `CTR: ${(context.parsed.y * 100).toFixed(2)}%`
              },
              titleFont: { size: 16 },
              bodyFont: { size: 14 }
            },
            title: {
              display: true,
              text: "CTR Over Time",
              font: { size: 18, weight: "bold" }
            }
          },
          scales: {
            ...commonOptions.scales,
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: "CTR (%)",
                font: { size: 16, weight: "bold" }
              },
              ticks: {
                callback: value => (value * 100).toFixed(0) + "%"
              }
            }
          }
        })
      });
    }
    
    // Initialize Clicks & Impressions Chart (Chart.js).
    function initializeClicksImpressionsChart() {
      const dates = perfData.map(item => item.date);
      const clicks = perfData.map(item => item.clicks);
      const impressions = perfData.map(item => item.impressions);
      const ctx = document.getElementById("clicksImpressionsChart").getContext("2d");
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: dates,
          datasets: [
            { label: "Clicks", data: clicks, backgroundColor: "rgba(54, 162, 235, 0.7)" },
            { label: "Impressions", data: impressions, backgroundColor: "rgba(255, 99, 132, 0.7)" }
          ]
        },
        options: Object.assign({}, commonOptions, {
          plugins: {
            tooltip: {
              callbacks: {
                label: context => `${context.dataset.label}: ${context.parsed.y}`
              },
              titleFont: { size: 16 },
              bodyFont: { size: 14 }
            },
            title: {
              display: true,
              text: "Clicks & Impressions Over Time",
              font: { size: 18, weight: "bold" }
            }
          },
          scales: {
            ...commonOptions.scales,
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: "Count",
                font: { size: 16, weight: "bold" }
              }
            }
          }
        })
      });
    }
    
    // Initialize Average Position Chart (Chart.js).
    function initializePositionChart() {
      const dates = perfData.map(item => item.date);
      const positions = perfData.map(item => item.position);
      const ctx = document.getElementById("positionChart").getContext("2d");
      new Chart(ctx, {
        type: "line",
        data: {
          labels: dates,
          datasets: [{
            label: "Average Position",
            data: positions,
            fill: false,
            borderColor: "rgb(153, 102, 255)",
            backgroundColor: "rgba(153,102,255,0.2)",
            tension: 0.3,
            pointRadius: 6,
            pointHoverRadius: 8,
            pointBackgroundColor: "rgb(153, 102, 255)"
          }]
        },
        options: Object.assign({}, commonOptions, {
          plugins: {
            tooltip: {
              callbacks: {
                label: context => `Avg. Position: ${context.parsed.y.toFixed(2)}`
              },
              titleFont: { size: 16 },
              bodyFont: { size: 14 }
            },
            title: {
              display: true,
              text: "Average Position Over Time",
              font: { size: 18, weight: "bold" }
            }
          },
          scales: {
            ...commonOptions.scales,
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: "Position",
                font: { size: 16, weight: "bold" }
              }
            }
          }
        })
      });
    }
    
    // Initialize 3D Chart using Plotly.
    function initialize3dChart() {
      const dates = perfData.map(item => item.date);
      const clicks = perfData.map(item => item.clicks);
      const impressions = perfData.map(item => item.impressions);
      const ctr = perfData.map(item => item.ctr);
      
      // Define trace for a 3D scatter plot.
      const trace = {
        x: dates,
        y: clicks,
        z: impressions,
        mode: 'markers',
        marker: {
          size: 8,
          color: ctr,
          colorscale: 'Viridis',
          colorbar: { title: 'CTR' },
          opacity: 0.8
        },
        type: 'scatter3d'
      };
      
      const data = [trace];
      
      const layout = {
        title: '3D Scatter Plot of Performance',
        scene: {
          xaxis: { title: 'Date', gridcolor: 'rgba(0,0,0,0.1)' },
          yaxis: { title: 'Clicks', gridcolor: 'rgba(0,0,0,0.1)' },
          zaxis: { title: 'Impressions', gridcolor: 'rgba(0,0,0,0.1)' }
        },
        margin: { l: 0, r: 0, b: 0, t: 30 },
        autosize: true
      };
      
      Plotly.newPlot('plotly3dChart', data, layout, {responsive: true});
    }
    
    // Attach event listeners to the graph buttons.
    document.getElementById("openModalCtr").addEventListener("click", function () {
      openModal("modalCtr", initializeCtrChart);
    });
    
    document.getElementById("openModalClicks").addEventListener("click", function () {
      openModal("modalClicks", initializeClicksImpressionsChart);
    });
    
    document.getElementById("openModalPosition").addEventListener("click", function () {
      openModal("modalPosition", initializePositionChart);
    });
    
    document.getElementById("openModal3d").addEventListener("click", function () {
      openModal("modal3d", initialize3dChart);
    });
  });
  