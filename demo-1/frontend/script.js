// ------------------------------------
// GLOBAL CHART HANDLES
// ------------------------------------
window.myChart = null;
window.speedChart = null;
window.memoryChart = null;

// ------------------------------------
// POST helper
// ------------------------------------
async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ------------------------------------
// GENERATE FILE
// ------------------------------------
document.getElementById("gen").onclick = async () => {
  const size = document.getElementById("size").value;
  document.getElementById("results").innerText = "Generating...";
  const res = await fetch(`/generate/${size}`);
  const j = await res.json();
  document.getElementById("results").innerText = "Generated: " + j.path;
};

// ------------------------------------
// THREAD SWEEP → 3 graphs (time, speedup, memory)
// ------------------------------------
document.getElementById("threadSweep").onclick = async () => {
  const size = parseInt(document.getElementById("size").value);
  const mode = document.getElementById("mode").value;

  document.getElementById("results").innerText = "Running thread sweep...";

  const res = await postJSON("/run_thread_sweep", {
    size_mb: size,
    mode: mode,
  });

  document.getElementById("results").innerText = "Completed thread sweep.";

  const threads = res.map((r) => r.threads);
  const serial = res.map((r) => r.serial);
  const parallel = res.map((r) => r.parallel);

  // NEW: separate serial+parallel speedup
  const speedup_parallel = res.map((r) => r.speedup_parallel);
  const speedup_serial = res.map((r) => r.speedup_serial);

  // NEW: separate serial+parallel memory
  const memory_parallel = res.map((r) => r.memory_parallel);
  const memory_serial = res.map((r) => r.memory_serial);

  const ctx = document.getElementById("chart").getContext("2d");
  const ctx2 = document.getElementById("speedChart").getContext("2d");
  const ctx3 = document.getElementById("memoryChart").getContext("2d");

  // SAFE DESTROY
  if (window.myChart instanceof Chart) window.myChart.destroy();
  if (window.speedChart instanceof Chart) window.speedChart.destroy();
  if (window.memoryChart instanceof Chart) window.memoryChart.destroy();

  // -----------------------------
  // 1. TIME GRAPH (Serial vs Parallel)
  // -----------------------------
  window.myChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: threads,
      datasets: [
        {
          label: "Parallel Time",
          data: parallel,
          borderColor: "#007bff",
          borderWidth: 2,
        },
        {
          label: "Serial Time",
          data: serial,
          borderColor: "#28a745",
          borderWidth: 2,
        },
      ],
    },
  });

  // -----------------------------
  // 2. SPEEDUP GRAPH (Parallel vs Serial)
  // -----------------------------
  window.speedChart = new Chart(ctx2, {
    type: "line",
    data: {
      labels: threads,
      datasets: [
        {
          label: "Parallel Speedup",
          data: speedup_parallel,
          borderColor: "#ff5733",
          borderWidth: 2,
        },
        {
          label: "Serial Speedup",
          data: speedup_serial,
          borderColor: "#000000",
          borderWidth: 2,
        },
      ],
    },
  });

  // -----------------------------
  // 3. MEMORY GRAPH (Parallel vs Serial)
  // -----------------------------
  window.memoryChart = new Chart(ctx3, {
    type: "line",
    data: {
      labels: threads,
      datasets: [
        {
          label: "Parallel Memory (MB)",
          data: memory_parallel,
          borderColor: "#8e44ad",
          borderWidth: 2,
        },
        {
          label: "Serial Memory (MB)",
          data: memory_serial,
          borderColor: "#2ecc71",
          borderWidth: 2,
        },
      ],
    },
  });
};

// ------------------------------------
// RUN SINGLE EXPERIMENT (Bar chart)
// ------------------------------------
document.getElementById("run").onclick = async () => {
  const size = parseInt(document.getElementById("size").value);
  const mode = document.getElementById("mode").value;
  const threads = parseInt(document.getElementById("threads").value);

  document.getElementById("results").innerText = "Running experiment...";

  const res = await postJSON("/run_one", {
    size_mb: size,
    mode: mode,
    threads: threads,
  });

  if (res.error) {
    document.getElementById("results").innerText = "Error: " + res.error;
    return;
  }

  let html = "";
  for (const [k, v] of Object.entries(res)) {
    html += `<div><strong>${k}:</strong> ${v}</div>`;
  }
  document.getElementById("results").innerHTML = html;

  const ctx = document.getElementById("chart").getContext("2d");

  if (window.myChart instanceof Chart) window.myChart.destroy();

  window.myChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Serial Encrypt", "Serial Decrypt", "Parallel Encrypt"],
      datasets: [
        {
          label: `${res.mode} mode (${res.threads} threads)`,
          data: [
            res.serial_encrypt_time,
            res.serial_decrypt_time,
            res.parallel_time,
          ],
          backgroundColor: ["#007bff", "#28a745", "#ffc107"],
        },
      ],
    },
  });
};
