async function postJSON(url, payload){
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  return res.json();
}

document.getElementById('gen').onclick = async () => {
  const size = document.getElementById('size').value;
  document.getElementById('results').innerText = 'Generating...';
  const res = await fetch(`/generate/${size}`);
  const j = await res.json();
  document.getElementById('results').innerText = 'Generated: ' + j.path;
};

document.getElementById('run').onclick = async () => {
  const size = parseInt(document.getElementById('size').value);
  const mode = document.getElementById('mode').value;
  const threads = parseInt(document.getElementById('threads').value);
  
  document.getElementById('results').innerText = 'Running experiment... (may take time)';
  
  const res = await postJSON('/run_one', { size_mb: size, mode: mode, threads: threads });
  
  if (res.error) {
    document.getElementById('results').innerText = 'Error: ' + res.error;
    return;
  }

  // show result values
  let html = '';
  for (const [k, v] of Object.entries(res)) {
    html += `<div><strong>${k}:</strong> ${v}</div>`;
  }
  document.getElementById('results').innerHTML = html;

  // ✅ FIXED chart keys
  const ctx = document.getElementById('chart').getContext('2d');
  const labels = ['Serial Encrypt', 'Serial Decrypt', 'Parallel Encrypt'];
  const data = [
    res.serial_encrypt_time,
    res.serial_decrypt_time,
    res.parallel_time
  ];

  if (window.myChart) window.myChart.destroy();
  window.myChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: `${res.mode} mode (${res.threads} threads)`,
        data: data,
        backgroundColor: ['#007bff', '#28a745', '#ffc107']
      }]
    },
    options: {
      responsive: true,
      plugins: {
        title: {
          display: true,
          text: `AES ${res.mode} Performance (File: ${res.file})`
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Time (seconds)' }
        }
      }
    }
  });
};
