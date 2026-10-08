// Application State
let activeJobs = [];
let loadedCertificates = [];
let pollingTimer = null;

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
  // Set default issue date to today
  document.getElementById('issue-date').value = new Date().toISOString().split('T')[0];
  
  // Prefill default 3 sample rows
  loadSampleData();
  
  // Initial jobs load
  refreshJobsList();
  
  // Start auto-refresh interval for queue status (every 3 seconds)
  pollingTimer = setInterval(refreshJobsList, 3000);
});

// Toast Notification Helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Tab Navigation
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  const activeContent = document.getElementById(tabId);
  if (activeContent) activeContent.classList.add('active');

  const btnMap = {
    'create-tab': 0,
    'jobs-tab': 1,
    'certs-tab': 2
  };
  const buttons = document.querySelectorAll('.tab-btn');
  if (buttons[btnMap[tabId]]) {
    buttons[btnMap[tabId]].classList.add('active');
  }
}

// Recipient Form Helpers
function addRecipientRow(name = '', email = '') {
  const tbody = document.getElementById('recipients-tbody');
  const rowCount = tbody.children.length;
  
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td style="color: var(--text-secondary); font-weight: 600;">${rowCount + 1}</td>
    <td>
      <input type="text" class="form-control recipient-name" placeholder="Full Name" value="${name}" required>
    </td>
    <td>
      <input type="email" class="form-control recipient-email" placeholder="email@domain.com" value="${email}" required>
    </td>
    <td style="text-align: center;">
      <button type="button" class="btn btn-danger btn-sm" onclick="removeRecipientRow(this)">🗑️</button>
    </td>
  `;
  tbody.appendChild(tr);
  updateRecipientCount();
}

function removeRecipientRow(btn) {
  const row = btn.closest('tr');
  row.remove();
  reindexRecipientRows();
  updateRecipientCount();
}

function reindexRecipientRows() {
  const rows = document.querySelectorAll('#recipients-tbody tr');
  rows.forEach((row, index) => {
    row.children[0].textContent = index + 1;
  });
}

function updateRecipientCount() {
  const count = document.querySelectorAll('#recipients-tbody tr').length;
  document.getElementById('recipient-count').textContent = count;
}

function loadSampleData() {
  const tbody = document.getElementById('recipients-tbody');
  tbody.innerHTML = '';

  const samples = [
    { name: 'Dr. Sarah Connor', email: 'sarah.connor@cyberdyne.io' },
    { name: 'Alex Mercer', email: 'alex.mercer@gentek.org' },
    { name: 'Elena Rostova', email: 'elena.rostova@aereo.cloud' },
    { name: 'Marcus Vance', email: 'marcus.vance@mit.edu' },
    { name: 'Priya Sharma', email: 'priya.sharma@tech.in' }
  ];

  samples.forEach(s => addRecipientRow(s.name, s.email));
  showToast('Loaded 5 sample recipients!', 'info');
}

// Form Submit: Create Job
document.getElementById('create-job-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const title = document.getElementById('cert-title').value.trim();
  const course = document.getElementById('course-name').value.trim();
  const eventName = document.getElementById('event-name').value.trim();
  const issuer = document.getElementById('issuer-name').value.trim();
  const issueDate = document.getElementById('issue-date').value;

  const rows = document.querySelectorAll('#recipients-tbody tr');
  const recipients = [];

  rows.forEach(row => {
    const name = row.querySelector('.recipient-name').value.trim();
    const email = row.querySelector('.recipient-email').value.trim();
    if (name && email) {
      recipients.push({ name, email });
    }
  });

  if (recipients.length === 0) {
    showToast('Please add at least one recipient!', 'error');
    return;
  }

  const payload = {
    certificate_title: title,
    course_name: course,
    event_name: eventName,
    issuer_name: issuer,
    issue_date: issueDate,
    recipients: recipients
  };

  try {
    const response = await fetch('/api/v1/certificate-jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      const errMsg = data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : 'Failed to create job';
      showToast(errMsg, 'error');
      return;
    }

    showToast(`Job ${data.job_id.substring(0, 8)}... launched successfully!`, 'success');
    switchTab('jobs-tab');
    refreshJobsList();

  } catch (err) {
    console.error(err);
    showToast('Network error while creating job', 'error');
  }
});

// Jobs Queue List
async function refreshJobsList() {
  try {
    // We poll jobs from active array or recent endpoint
    const tbody = document.getElementById('jobs-tbody');
    
    // Fetch individual active jobs if we have job IDs stored or query known ones
    // For local convenience, we maintain activeJobs in local state
    if (activeJobs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No active generation jobs found. Create one above!</td></tr>`;
      updateStats();
      return;
    }

    let updatedJobs = [];
    for (const j of activeJobs) {
      try {
        const res = await fetch(`/api/v1/certificate-jobs/${j.job_id}`);
        if (res.ok) {
          const updated = await res.json();
          updatedJobs.push(updated);
        } else {
          updatedJobs.push(j);
        }
      } catch (e) {
        updatedJobs.push(j);
      }
    }

    activeJobs = updatedJobs;
    renderJobsTable();
    updateStats();

  } catch (err) {
    console.error(err);
  }
}

function renderJobsTable() {
  const tbody = document.getElementById('jobs-tbody');
  tbody.innerHTML = '';

  activeJobs.forEach(job => {
    const tr = document.createElement('tr');
    
    const statusBadge = getStatusBadge(job.status);
    const dateStr = new Date(job.created_at).toLocaleTimeString();
    
    tr.innerHTML = `
      <td style="font-family: monospace; color: var(--accent-indigo); font-weight: 600;">${job.job_id.substring(0, 13)}...</td>
      <td>${statusBadge}</td>
      <td style="width: 180px;">
        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 0.25rem;">
          <span>${job.successful + job.failed} / ${job.total}</span>
          <span>${job.progress_percentage}%</span>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar-fill" style="width: ${job.progress_percentage}%;"></div>
        </div>
      </td>
      <td>${job.total} recipients</td>
      <td style="color: var(--text-secondary); font-size: 0.85rem;">${dateStr}</td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="viewJobCertificates('${job.job_id}')">
          👁️ View Certs
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function getStatusBadge(status) {
  switch (status) {
    case 'PENDING':
      return `<span class="badge badge-pending">⏳ PENDING</span>`;
    case 'PROCESSING':
      return `<span class="badge badge-processing">⚡ PROCESSING</span>`;
    case 'COMPLETED':
      return `<span class="badge badge-completed">✅ COMPLETED</span>`;
    case 'PARTIAL_SUCCESS':
      return `<span class="badge badge-partial">⚠️ PARTIAL</span>`;
    case 'FAILED':
      return `<span class="badge badge-failed">❌ FAILED</span>`;
    default:
      return `<span class="badge">${status}</span>`;
  }
}

// Track newly created job in frontend state
const originalFetch = window.fetch;
window.fetch = async function(...args) {
  const response = await originalFetch.apply(this, args);
  if (args[0] === '/api/v1/certificate-jobs' && response.ok) {
    const clone = response.clone();
    const data = await clone.json();
    if (data.job_id) {
      activeJobs.unshift({
        job_id: data.job_id,
        status: data.status,
        total: data.total,
        successful: 0,
        failed: 0,
        progress_percentage: 0,
        created_at: new Date().toISOString()
      });
    }
  }
  return response;
};

// View Certificates for a Job
async function viewJobCertificates(jobId) {
  try {
    const res = await fetch(`/api/v1/certificate-jobs/${jobId}/certificates`);
    if (!res.ok) {
      showToast('Could not load job certificates', 'error');
      return;
    }

    const data = await res.json();
    loadedCertificates = data.certificates || [];
    
    document.getElementById('certs-explorer-title').textContent = `Certificates for Job (${jobId.substring(0, 8)}...)`;
    renderCertificatesTable(loadedCertificates);
    switchTab('certs-tab');

  } catch (err) {
    console.error(err);
    showToast('Failed to load certificates', 'error');
  }
}

function renderCertificatesTable(certs) {
  const tbody = document.getElementById('certs-tbody');
  tbody.innerHTML = '';

  if (certs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No certificates found for this job.</td></tr>`;
    return;
  }

  certs.forEach(cert => {
    const tr = document.createElement('tr');
    const genDate = cert.generated_at ? new Date(cert.generated_at).toLocaleTimeString() : 'N/A';
    
    const downloadBtn = cert.status === 'GENERATED' && cert.download_url
      ? `<a href="${cert.download_url}" target="_blank" class="btn btn-sm btn-success" style="text-decoration: none;">📥 Download PDF</a>`
      : `<span style="color: var(--text-secondary); font-size: 0.8rem;">Not ready</span>`;

    const statusSpan = cert.status === 'GENERATED'
      ? `<span class="badge badge-completed">✅ GENERATED</span>`
      : cert.status === 'FAILED'
      ? `<span class="badge badge-failed" title="${cert.error_message || ''}">❌ FAILED</span>`
      : `<span class="badge badge-pending">⏳ PENDING</span>`;

    tr.innerHTML = `
      <td style="font-family: monospace; font-weight: 600; color: var(--accent-cyan);">${cert.certificate_number}</td>
      <td style="font-weight: 600;">${cert.recipient_name}</td>
      <td style="color: var(--text-secondary);">${cert.recipient_email}</td>
      <td>${statusSpan}</td>
      <td style="color: var(--text-secondary); font-size: 0.85rem;">${genDate}</td>
      <td>${downloadBtn}</td>
    `;
    tbody.appendChild(tr);
  });
}

function filterCertificates() {
  const query = document.getElementById('cert-search').value.toLowerCase();
  const filtered = loadedCertificates.filter(c => 
    c.recipient_name.toLowerCase().includes(query) || 
    c.recipient_email.toLowerCase().includes(query) ||
    c.certificate_number.toLowerCase().includes(query)
  );
  renderCertificatesTable(filtered);
}

function updateStats() {
  const totalJobs = activeJobs.length;
  let totalCerts = 0;
  let successCerts = 0;

  activeJobs.forEach(j => {
    totalCerts += (j.successful + j.failed);
    successCerts += j.successful;
  });

  document.getElementById('stat-total-jobs').textContent = totalJobs;
  document.getElementById('stat-total-certs').textContent = totalCerts;
  
  const rate = totalCerts > 0 ? Math.round((successCerts / totalCerts) * 100) : 100;
  document.getElementById('stat-success-rate').textContent = `${rate}%`;
}
