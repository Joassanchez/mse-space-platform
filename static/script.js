/**
 * ARGPLANT AI — Interactive Platform Logic
 * Full-stack dashboard connecting to all backend API endpoints.
 * Handles: Regions, Alerts, Jobs, Analysis, Geo layers, UI interactions.
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';
const API_KEY = 'dev-secret-key';
const HEADERS = {
  'X-API-Key': API_KEY,
  'Content-Type': 'application/json'
};

/* ============================================
   App Initialization
   ============================================ */
document.addEventListener('DOMContentLoaded', () => {
  initScrollAnimations();
  initKPICounters();
  initMapControls();
  initApprovalFlow();
  initModalHandlers();

  // Backend data loading
  fetchRegions();
  fetchAlerts();
  fetchAlertCount();
  fetchJobs();
  fetchAnalysis();
  fetchLatestAnalysis();
  fetchAnalysisSummary();
  initSSE();

  // Geo layers loaded after map init
  setTimeout(() => {
    loadGeoRegions();
    loadGeoAlerts();
    loadRiskZones();
  }, 500);
});

/* ============================================
   API Helper
   ============================================ */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const config = {
    headers: HEADERS,
    ...options,
  };
  const response = await fetch(url, config);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
  return response.json();
}

/* ============================================
   Regions Module
   ============================================ */
async function fetchRegions() {
  try {
    const data = await apiFetch('/regions/');
    const items = data.items || [];
    populateRegionSelector(items);
    populateFilterPills(items);
  } catch (err) {
    console.error('Error fetching regions:', err);
  }
}

function populateRegionSelector(regions) {
  const select = document.getElementById('region_id');
  if (!select) return;
  select.innerHTML = '';
  if (regions.length === 0) {
    select.innerHTML = '<option value="">No hay regiones disponibles</option>';
    return;
  }
  regions.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.id;
    opt.textContent = `${r.name} (${r.region_type || 'región'})`;
    select.appendChild(opt);
  });
}

function populateFilterPills(regions) {
  if (regions.length === 0) return;
  const firstRegion = regions[0];
  const pillsContainer = document.querySelector('.filters-pills');
  if (!pillsContainer) return;
  // Update first pill with actual region name
  const pills = pillsContainer.querySelectorAll('.pill');
  if (pills[0]) {
    pills[0].innerHTML = `<span class="material-symbols-outlined pill-icon">location_on</span> Región: ${firstRegion.name}`;
  }
}

/* ============================================
   Alerts Module
   ============================================ */
async function fetchAlerts() {
  const container = document.getElementById('alerts-list');
  if (!container) return;
  try {
    const data = await apiFetch('/alerts/?status=active&limit=10');
    renderAlerts(data.items || [], container);
    // Update badge count
    const badge = document.querySelector('.alert-badge-count');
    if (badge) badge.textContent = `${data.total} Activas`;
  } catch (err) {
    console.error('Error fetching alerts:', err);
    container.innerHTML = '<p style="padding:1rem; color:var(--on-surface-variant);">No se pudieron cargar las alertas.</p>';
  }
}

function renderAlerts(alerts, container) {
  if (alerts.length === 0) {
    container.innerHTML = '<p style="padding:1rem; color:var(--on-surface-variant);">No hay alertas activas.</p>';
    return;
  }
  container.innerHTML = alerts.map(alert => {
    const severityMap = { critical: '🔴', severe: '🟠', warning: '🟡', info: '🔵' };
    const icon = severityMap[alert.severity] || '⚪';
    const date = alert.created_at ? new Date(alert.created_at).toLocaleString() : '';
    return `
      <div class="alert-card ${alert.severity}" data-alert-id="${alert.id}">
        <div class="alert-header">
          <span class="alert-severity-icon">${icon}</span>
          <div class="alert-info">
            <span class="alert-title">${alert.title}</span>
            <span class="alert-meta">${alert.severity.toUpperCase()} · ${alert.alert_type} · ${date}</span>
          </div>
        </div>
        <p class="alert-message">${alert.message || ''}</p>
        <div class="alert-actions">
          <button class="btn-sm btn-acknowledge" onclick="acknowledgeAlert(${alert.id}, this)">
            <span class="material-symbols-outlined">check_circle</span> Aprobar
          </button>
        </div>
      </div>
    `;
  }).join('');
}

async function fetchAlertCount() {
  try {
    const data = await apiFetch('/alerts/active/count/');
    const badge = document.querySelector('.notif-badge');
    if (badge) badge.textContent = data.total || 0;
  } catch (err) {
    console.error('Error fetching alert count:', err);
  }
}

async function acknowledgeAlert(alertId, btn) {
  try {
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined">hourglass_top</span> Procesando...';
    await apiFetch(`/alerts/${alertId}/acknowledge/`, { method: 'PATCH' });
    btn.innerHTML = '<span class="material-symbols-outlined">check</span> Aprobada';
    btn.style.background = '#2e7d32';
    btn.style.color = '#fff';
    showNotification('Alerta aprobada exitosamente.', 'success');
    // Refresh alerts after a short delay
    setTimeout(() => { fetchAlerts(); fetchAlertCount(); }, 1500);
  } catch (err) {
    console.error('Error acknowledging alert:', err);
    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-outlined">check_circle</span> Aprobar';
    showNotification('Error al aprobar la alerta.', 'error');
  }
}

function initSSE() {
  try {
    const evtSource = new EventSource(`${API_BASE_URL}/alerts/stream/?X-API-Key=${API_KEY}`);
    evtSource.addEventListener('new_alert', (event) => {
      try {
        const alertData = JSON.parse(event.data);
        showNotification(`Nueva alerta: ${alertData.title || 'Alerta detectada'}`, 'info');
        fetchAlerts();
        fetchAlertCount();
      } catch (e) {
        console.warn('SSE parse error:', e);
      }
    });
    evtSource.addEventListener('heartbeat', () => { /* keep alive */ });
    evtSource.onerror = () => {
      console.warn('SSE connection lost, will retry automatically');
    };
  } catch (err) {
    console.warn('SSE not available:', err);
  }
}

/* ============================================
   Jobs / Ingestion Module
   ============================================ */
async function fetchJobs() {
  const container = document.getElementById('jobs-list');
  if (!container) return;
  try {
    const data = await apiFetch('/jobs/?limit=20');
    renderJobs(data.items || [], container);
  } catch (err) {
    console.error('Error fetching jobs:', err);
    container.innerHTML = '<p style="padding:1rem; color:var(--on-surface-variant);">No se pudieron cargar los trabajos.</p>';
  }
}

function renderJobs(jobs, container) {
  if (jobs.length === 0) {
    container.innerHTML = '<p style="padding:1rem; color:var(--on-surface-variant);">No hay trabajos de ingesta registrados.</p>';
    return;
  }
  container.innerHTML = jobs.map(job => {
    const statusClass = job.status.toLowerCase().replace(/_/g, '-');
    const date = job.created_at ? new Date(job.created_at).toLocaleString() : 'N/A';
    const dateRange = (job.date_from && job.date_to) ? `${job.date_from} → ${job.date_to}` : '';
    return `
      <div class="job-item" data-job-id="${job.id}">
        <div class="job-info">
          <span class="job-id">ID: ${job.id}</span>
          <span class="job-date">Creado: ${date} | Región: ${job.region_id || 'N/A'} ${dateRange ? '| Rango: ' + dateRange : ''}</span>
        </div>
        <div class="job-right">
          <span class="job-status ${statusClass}">${job.status}</span>
          <button class="icon-btn job-detail-btn" onclick="toggleJobDetail('${job.id}', this)" title="Ver detalle">
            <span class="material-symbols-outlined">expand_more</span>
          </button>
        </div>
      </div>
      <div class="job-detail-panel" id="job-detail-${job.id}" style="display:none;"></div>
    `;
  }).join('');
}

async function toggleJobDetail(jobId, btn) {
  const panel = document.getElementById(`job-detail-${jobId}`);
  if (!panel) return;
  if (panel.style.display === 'block') {
    panel.style.display = 'none';
    btn.querySelector('.material-symbols-outlined').textContent = 'expand_more';
    return;
  }
  panel.style.display = 'block';
  btn.querySelector('.material-symbols-outlined').textContent = 'expand_less';
  panel.innerHTML = '<p style="padding:1rem;">Cargando detalle...</p>';

  try {
    const [detail, logs] = await Promise.all([
      apiFetch(`/jobs/${jobId}`),
      apiFetch(`/jobs/${jobId}/logs/`).catch(() => [])
    ]);
    let html = `<div class="job-detail-content">`;
    html += `<div class="job-detail-grid">`;
    html += `<div><strong>Estado:</strong> ${detail.status}</div>`;
    html += `<div><strong>Región:</strong> ${detail.region_id || 'N/A'}</div>`;
    html += `<div><strong>Fecha:</strong> ${detail.date_from || ''} → ${detail.date_to || ''}</div>`;
    html += `<div><strong>Ready for ETL:</strong> ${detail.ready_for_etl ? 'Sí' : 'No'}</div>`;
    html += `<div><strong>Search Only:</strong> ${detail.search_only ? 'Sí' : 'No'}</div>`;
    if (detail.error_message) {
      html += `<div class="job-error"><strong>Error:</strong> ${detail.error_message}</div>`;
    }
    html += `</div>`;

    if (Array.isArray(logs) && logs.length > 0) {
      html += `<h4 style="margin-top:1rem; font-size:0.85rem; color:var(--on-surface-variant);">LOGS</h4>`;
      html += `<div class="job-logs">`;
      logs.forEach(log => {
        const ts = log.timestamp ? new Date(log.timestamp).toLocaleString() : '';
        html += `<div class="job-log-entry"><span class="log-time">${ts}</span> <span class="log-action">[${log.action}]</span> ${log.message || ''}</div>`;
      });
      html += `</div>`;
    } else {
      html += `<p style="font-size:0.85rem; color:var(--on-surface-variant); margin-top:0.5rem;">Sin logs disponibles.</p>`;
    }
    html += `</div>`;
    panel.innerHTML = html;
  } catch (err) {
    panel.innerHTML = `<p style="padding:1rem; color:#b71c1c;">Error cargando detalle: ${err.message}</p>`;
  }
}

async function triggerJob(formData) {
  const body = {
    region_id: formData.get('region_id'),
    date_from: formData.get('date_from'),
    date_to: formData.get('date_to')
  };
  const data = await apiFetch('/jobs/trigger/', {
    method: 'POST',
    body: JSON.stringify(body)
  });
  // Try connecting WebSocket for real-time progress
  if (data.id) {
    connectJobWS(data.id);
  }
  return data;
}

function connectJobWS(jobId) {
  try {
    const wsUrl = `ws://localhost:8000/ws/jobs/${jobId}`;
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      console.log(`WebSocket connected for job ${jobId}`);
    };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'progress') {
          showNotification(`Job ${jobId}: ${msg.progress || ''}%`, 'info');
        } else if (msg.event === 'completed') {
          showNotification(`Job ${jobId} completado.`, 'success');
          fetchJobs();
          ws.close();
        } else if (msg.event === 'failed') {
          showNotification(`Job ${jobId} falló.`, 'error');
          fetchJobs();
          ws.close();
        }
      } catch (e) { /* ignore parse errors */ }
    };
    ws.onerror = () => console.warn('WebSocket error for job', jobId);
    ws.onclose = () => console.log('WebSocket closed for job', jobId);
  } catch (err) {
    console.warn('WebSocket not available:', err);
  }
}

/* ============================================
   Analysis / Agent Executions Module
   ============================================ */
async function fetchAnalysis() {
  const container = document.getElementById('analysis-list');
  if (!container) return;
  try {
    const data = await apiFetch('/analysis/?limit=10');
    renderAnalysis(data.items || [], container);
  } catch (err) {
    console.error('Error fetching analysis:', err);
    container.innerHTML = '<p style="padding:1rem; color:var(--on-surface-variant);">No se pudieron cargar las ejecuciones IA.</p>';
  }
}

function renderAnalysis(items, container) {
  if (items.length === 0) {
    container.innerHTML = '<p style="padding:1rem; color:var(--on-surface-variant);">No hay ejecuciones de agentes IA registradas.</p>';
    return;
  }
  let html = `<table class="analysis-table">
    <thead>
      <tr>
        <th>Agente</th>
        <th>Área</th>
        <th>Estado</th>
        <th>Confianza</th>
        <th>Fecha</th>
        <th>Detalle</th>
      </tr>
    </thead>
    <tbody>`;

  items.forEach(item => {
    const confidence = item.confidence_score != null ? `${(item.confidence_score * 100).toFixed(0)}%` : 'N/A';
    const date = item.finished_at ? new Date(item.finished_at).toLocaleString() : (item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A');
    const statusClass = (item.status || 'pending').toLowerCase();
    html += `
      <tr>
        <td><code>${item.agent_code || 'N/A'}</code></td>
        <td>${item.orchestrator_area || 'N/A'}</td>
        <td><span class="analysis-status ${statusClass}">${item.status || 'N/A'}</span></td>
        <td>${confidence}</td>
        <td>${date}</td>
        <td>
          <button class="icon-btn" onclick="showAnalysisDetail('${item.execution_id}')" title="Ver detalle">
            <span class="material-symbols-outlined">visibility</span>
          </button>
        </td>
      </tr>`;
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

async function showAnalysisDetail(executionId) {
  try {
    const detail = await apiFetch(`/analysis/${executionId}`);
    const output = detail.natural_language_output || 'Sin output de lenguaje natural.';
    const structured = detail.structured_output ? JSON.stringify(detail.structured_output, null, 2) : 'N/A';
    const confidence = detail.confidence_score != null ? `${(detail.confidence_score * 100).toFixed(1)}%` : 'N/A';
    const completeness = detail.data_completeness != null ? `${(detail.data_completeness * 100).toFixed(1)}%` : 'N/A';

    // Show in a simple overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.style.display = 'flex';
    overlay.innerHTML = `
      <div class="modal-content" style="max-width:700px; max-height:80vh; overflow-y:auto;">
        <div class="modal-header">
          <h2 class="modal-title">Detalle Ejecución IA</h2>
          <button class="icon-btn modal-close" onclick="this.closest('.modal-overlay').remove()">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="modal-body" style="padding:1rem 0;">
          <div class="job-detail-grid">
            <div><strong>ID:</strong> ${detail.execution_id}</div>
            <div><strong>Agente:</strong> ${detail.agent_code || 'N/A'}</div>
            <div><strong>Área:</strong> ${detail.orchestrator_area || 'N/A'}</div>
            <div><strong>Estado:</strong> ${detail.status}</div>
            <div><strong>Confianza:</strong> ${confidence}</div>
            <div><strong>Completitud Datos:</strong> ${completeness}</div>
            <div><strong>Modelo LLM:</strong> ${detail.llm_model_used || 'N/A'}</div>
          </div>
          <h4 style="margin-top:1.5rem; font-size:0.9rem;">Síntesis del Agente</h4>
          <p style="font-size:0.9rem; line-height:1.6; margin-top:0.5rem; white-space:pre-wrap;">${output}</p>
          ${detail.error_message ? `<div class="job-error" style="margin-top:1rem;"><strong>Error:</strong> ${detail.error_message}</div>` : ''}
          <details style="margin-top:1rem;">
            <summary style="cursor:pointer; font-size:0.85rem; font-weight:600;">Output Estructurado (JSON)</summary>
            <pre style="font-size:0.75rem; background:var(--surface-variant); padding:1rem; border-radius:8px; overflow-x:auto; margin-top:0.5rem;">${structured}</pre>
          </details>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
  } catch (err) {
    showNotification(`Error cargando detalle: ${err.message}`, 'error');
  }
}

async function fetchLatestAnalysis() {
  try {
    const data = await apiFetch('/analysis/latest/');
    const synthesisEl = document.getElementById('ia-synthesis-text');
    if (synthesisEl && data.natural_language_output) {
      synthesisEl.innerHTML = data.natural_language_output;
    }
  } catch (err) {
    // 404 is expected if no completed executions exist
    console.log('No latest analysis available (expected if DB is empty)');
  }
}

async function fetchAnalysisSummary() {
  try {
    const data = await apiFetch('/analysis/summary/');
    // Update KPI if summary available
    const conditionEl = document.getElementById('kpi-condition');
    if (conditionEl && data.overall_condition) {
      conditionEl.textContent = data.overall_condition;
    }
  } catch (err) {
    console.log('No analysis summary available');
  }
}

/* ============================================
   Geo / Map Module
   ============================================ */
let map = null;
let geoLayers = {};

function initMapControls() {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  map = L.map('map').setView([-33.89, -60.57], 12);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri'
  }).addTo(map);
}

async function loadGeoRegions() {
  if (!map) return;
  try {
    const geojson = await apiFetch('/geo/regions/');
    if (geojson.features && geojson.features.length > 0) {
      if (geoLayers.regions) map.removeLayer(geoLayers.regions);
      geoLayers.regions = L.geoJSON(geojson, {
        style: { color: '#4fc3f7', weight: 2, fillOpacity: 0.1 },
        onEachFeature: (feature, layer) => {
          const props = feature.properties || {};
          layer.bindPopup(`<b>${props.name || 'Región'}</b><br>Tipo: ${props.region_type || 'N/A'}`);
        }
      }).addTo(map);
      // Fit map to region bounds
      map.fitBounds(geoLayers.regions.getBounds(), { padding: [30, 30] });
    }
  } catch (err) {
    console.warn('Could not load geo regions:', err);
    // Fallback: add static markers
    addFallbackMarkers();
  }
}

async function loadGeoAlerts() {
  if (!map) return;
  try {
    const geojson = await apiFetch('/geo/alerts/');
    if (geojson.features && geojson.features.length > 0) {
      if (geoLayers.alerts) map.removeLayer(geoLayers.alerts);
      geoLayers.alerts = L.geoJSON(geojson, {
        pointToLayer: (feature, latlng) => {
          const severity = feature.properties?.severity || 'info';
          const colors = { critical: '#ef5350', severe: '#ff9800', warning: '#fdd835', info: '#42a5f5' };
          return L.circleMarker(latlng, {
            radius: 10, fillColor: colors[severity] || '#42a5f5',
            color: '#fff', weight: 2, fillOpacity: 0.8
          });
        },
        onEachFeature: (feature, layer) => {
          const p = feature.properties || {};
          layer.bindPopup(`<b>${p.title || 'Alerta'}</b><br>Severidad: ${p.severity}<br>${p.message || ''}`);
        }
      }).addTo(map);
    }
  } catch (err) {
    console.warn('Could not load geo alerts:', err);
  }
}

async function loadRiskZones() {
  if (!map) return;
  try {
    const geojson = await apiFetch('/geo/risk-zones/');
    if (geojson.features && geojson.features.length > 0) {
      if (geoLayers.risk) map.removeLayer(geoLayers.risk);
      const riskColors = { low: '#66bb6a', medium: '#fdd835', high: '#ff9800', critical: '#ef5350' };
      geoLayers.risk = L.geoJSON(geojson, {
        style: (feature) => ({
          color: riskColors[feature.properties?.risk_level] || '#999',
          weight: 2, fillOpacity: 0.25
        }),
        onEachFeature: (feature, layer) => {
          const p = feature.properties || {};
          layer.bindPopup(`<b>Zona de Riesgo</b><br>Tipo: ${p.risk_type}<br>Nivel: ${p.risk_level}<br>${p.explanation || ''}`);
        }
      }).addTo(map);
    }
  } catch (err) {
    console.warn('Could not load risk zones:', err);
  }
}

function addFallbackMarkers() {
  if (!map) return;
  const criticalIcon = L.divIcon({
    className: 'custom-leaflet-icon',
    html: '<div class="map-marker marker-critical" style="position:static; transform:none;"><span class="material-symbols-outlined">warning</span></div>',
    iconSize: [36, 36], iconAnchor: [18, 18]
  });
  const infoIcon = L.divIcon({
    className: 'custom-leaflet-icon',
    html: '<div class="map-marker marker-info" style="position:static; transform:none;"><span class="material-symbols-outlined">sensors</span></div>',
    iconSize: [36, 36], iconAnchor: [18, 18]
  });
  L.marker([-33.885, -60.58], { icon: criticalIcon }).addTo(map)
    .bindPopup('<b>Zona Crítica</b><br>Déficit hídrico severo detectado.');
  L.marker([-33.895, -60.56], { icon: infoIcon }).addTo(map)
    .bindPopup('<b>Sensor Activo</b><br>Humedad: 18.2%');
}

/* ============================================
   Modal Handlers (Ingresar Datos)
   ============================================ */
function initModalHandlers() {
  const btnIngresar = document.getElementById('btn-ingresar');
  const modal = document.getElementById('ingreso-modal');
  const btnClose = document.getElementById('btn-close-modal');
  const btnCancel = document.getElementById('btn-cancel-modal');
  const form = document.getElementById('ingreso-form');

  const closeModal = () => {
    if (modal) modal.style.display = 'none';
    if (form) form.reset();
  };

  if (btnIngresar) {
    btnIngresar.addEventListener('click', () => {
      const predictModal = document.getElementById('predict-modal');
      if (predictModal) predictModal.style.display = 'flex';
    });
  }
  if (btnClose) btnClose.addEventListener('click', closeModal);
  if (btnCancel) btnCancel.addEventListener('click', closeModal);

  // Click outside to close
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btnSubmit = form.querySelector('button[type="submit"]');
      const originalHTML = btnSubmit.innerHTML;
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = '<span class="material-symbols-outlined">hourglass_top</span> Enviando...';

      try {
        const formData = new FormData(form);
        const result = await triggerJob(formData);
        closeModal();
        showNotification(`Ingesta iniciada: ${result.id}`, 'success');
        fetchJobs();
      } catch (err) {
        console.error('Error triggering job:', err);
        showNotification('Error al iniciar la ingesta.', 'error');
      } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = originalHTML;
      }
    });
  }
}

/* ============================================
   Approval Flow (Plan de Acción)
   ============================================ */
function initApprovalFlow() {
  const approveBtn = document.getElementById('btn-approve');
  if (!approveBtn) return;

  approveBtn.addEventListener('click', () => {
    const originalText = approveBtn.innerHTML;
    approveBtn.innerHTML = '<span class="material-symbols-outlined" style="animation: none;">check</span> Orden Aprobada';
    approveBtn.style.background = '#2e7d32';
    approveBtn.style.pointerEvents = 'none';
    showNotification('Orden de trabajo aprobada exitosamente. Se envió al equipo de campo.', 'success');
    setTimeout(() => {
      approveBtn.innerHTML = originalText;
      approveBtn.style.background = '';
      approveBtn.style.pointerEvents = '';
    }, 4000);
  });
}

/* ============================================
   Toggle Tech Details
   ============================================ */
function toggleTechDetails() {
  const details = document.getElementById('tech-evidence');
  if (!details) return;
  details.style.display = details.style.display === 'block' ? 'none' : 'block';
}

/* ============================================
   Scroll Animations
   ============================================ */
function initScrollAnimations() {
  const elements = document.querySelectorAll('[data-animate]');
  if (!elements.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  elements.forEach(el => observer.observe(el));
}

/* ============================================
   KPI Counters Animation
   ============================================ */
function initKPICounters() {
  const kpiValues = document.querySelectorAll('.kpi-value');
  kpiValues.forEach(el => {
    const target = parseInt(el.textContent, 10);
    if (isNaN(target)) return;
    let current = 0;
    const increment = Math.ceil(target / 40);
    const unit = el.querySelector('.kpi-unit');
    const unitText = unit ? unit.textContent : '';
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        current = target;
        clearInterval(timer);
      }
      el.innerHTML = current + (unitText ? `<span class="kpi-unit">${unitText}</span>` : '');
    }, 30);
  });
}

/* ============================================
   Notification Toast
   ============================================ */
function showNotification(message, type = 'info') {
  const existing = document.querySelector('.notification-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `notification-toast notification-${type}`;
  toast.innerHTML = `
    <span class="notification-text">${message}</span>
    <button class="notification-close" onclick="this.parentElement.remove()">
      <span class="material-symbols-outlined">close</span>
    </button>
  `;
  Object.assign(toast.style, {
    position: 'fixed', bottom: '24px', right: '24px', maxWidth: '440px',
    padding: '14px 20px', borderRadius: '12px', display: 'flex', alignItems: 'center',
    gap: '12px', zIndex: '9999', fontFamily: 'Inter, sans-serif', fontSize: '14px',
    lineHeight: '1.4', boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
    transform: 'translateY(20px)', opacity: '0',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  });
  const colors = {
    success: { bg: '#e8f5e9', color: '#1b5e20', border: 'rgba(46,125,50,0.2)' },
    error: { bg: '#ffdad6', color: '#93000a', border: 'rgba(186,26,26,0.2)' },
    info: { bg: '#d4e3ff', color: '#001c3a', border: 'rgba(0,86,159,0.2)' },
  };
  const c = colors[type] || colors.info;
  toast.style.background = c.bg;
  toast.style.color = c.color;
  toast.style.border = `1px solid ${c.border}`;

  const closeBtn = toast.querySelector('.notification-close');
  Object.assign(closeBtn.style, {
    background: 'none', border: 'none', cursor: 'pointer',
    color: 'inherit', opacity: '0.6', padding: '0', display: 'flex', flexShrink: '0',
  });
  closeBtn.querySelector('.material-symbols-outlined').style.fontSize = '18px';

  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.transform = 'translateY(0)';
    toast.style.opacity = '1';
  });
  setTimeout(() => {
    toast.style.transform = 'translateY(20px)';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

/* ============================================
   Notification Button Click Handler
   ============================================ */
document.getElementById('btn-notif')?.addEventListener('click', () => {
  showNotification('Alertas nuevas detectadas por el motor IA.', 'info');
});

/* ============================================
   ARGPLANT Dashboard — Full Data Integration
   ============================================ */

const API_BASE = '/api/v1';

function getPredictParams() {
  return {
    lot_id: document.getElementById('predict-lot-id')?.value || 'lote-123',
    crop: document.getElementById('predict-crop')?.value || 'soy',
    lat: parseFloat(document.getElementById('predict-lat')?.value) || -33.9278607,
    lon: parseFloat(document.getElementById('predict-lon')?.value) || -60.567172,
    date: document.getElementById('predict-date')?.value || '2026-07-21',
  };
}

async function fetchAnalysis() {
  const q = getPredictParams();
  const params = new URLSearchParams(q);
  try {
    const res = await fetch(`${API_BASE}/analysis?${params}`);
    if (!res.ok) throw new Error(`Analysis: ${res.status}`);
    return await res.json();
  } catch (err) { console.warn('Analysis:', err); return null; }
}

async function fetchPrediction() {
  try {
    const res = await fetch(`${API_BASE}/predict`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getPredictParams()),
    });
    if (!res.ok) throw new Error(`Predict: ${res.status}`);
    return await res.json();
  } catch (err) { console.warn('Predict:', err); return null; }
}

/* ── KPI 1: Soil Moisture ── */
function updateKPISoilMoisture(predict, analysis) {
  const el = document.querySelector('.kpi-card:nth-child(1) .kpi-value');
  const sub = document.querySelector('.kpi-card:nth-child(1) .kpi-subtitle');
  const bar = document.querySelector('.kpi-card:nth-child(1) .kpi-bar-fill');
  const change = document.querySelector('.kpi-card:nth-child(1) .kpi-change');

  const smValue = analysis?.satellite?.soil_moisture_value;
  if (smValue?.soil_moisture != null) {
    const pct = Math.round(smValue.soil_moisture * 100);
    if (el) el.innerHTML = `${pct}<span class="kpi-unit">%</span>`;
    if (bar) bar.style.width = `${Math.min(100, pct * 2.5)}%`;
    if (sub) sub.textContent = `Fuente: ${smValue.source || 'SMAP'} — ${smValue.acquisition_date || ''}`;
  } else {
    const anomaly = predict?.anomalies?.find(a => a.type === 'water_stress');
    if (anomaly && el) {
      const pct = anomaly.evidence?.soil_moisture_pct || 20;
      el.innerHTML = `${pct}<span class="kpi-unit">%</span>`;
      if (bar) bar.style.width = `${Math.min(100, pct * 2)}%`;
      if (sub) sub.textContent = anomaly.description;
    }
  }
  if (change && smValue && smValue.soil_moisture < 0.22) {
    change.innerHTML = `<span class="material-symbols-outlined">arrow_downward</span> Bajo`;
    change.className = 'kpi-change negative';
  }
}

/* ── KPI 2: Risk ── */
function updateKPIRisk(predict) {
  const el = document.querySelector('.kpi-card:nth-child(2) .kpi-value');
  const scoreEl = document.querySelector('.kpi-card:nth-child(2) .kpi-score');
  const sub = document.querySelector('.kpi-card:nth-child(2) .kpi-subtitle');
  const segs = document.querySelectorAll('.kpi-card:nth-child(2) .segment');

  if (!predict?.risk_assessment) return;
  const r = predict.risk_assessment;
  const labels = { critical: 'Crítico', high: 'Alto', medium: 'Medio', low: 'Bajo' };
  if (el) el.textContent = labels[r.overall] || r.overall;
  if (scoreEl) scoreEl.textContent = `Score: ${r.score}`;
  if (sub && r.factors?.length) {
    sub.textContent = `Factor principal: ${r.factors[0].name.replace('_',' ')} (${r.factors[0].score})`;
  }
  // Risk segments
  const level = r.score >= 75 ? 2 : r.score >= 40 ? 3 : r.score >= 10 ? 4 : 5;
  segs.forEach((s, i) => {
    s.className = i < level ? (i < 2 ? 'segment active-green' : i < 3 ? 'segment active-amber' : 'segment') : 'segment';
  });
}

/* ── KPI 3: Weather ── */
function updateKPIWeather(analysis) {
  const el = document.querySelector('.kpi-card:nth-child(3) .kpi-value');
  const sub = document.querySelector('.kpi-card:nth-child(3) .kpi-subtitle');
  const label = document.querySelector('.kpi-card:nth-child(3) .kpi-label');

  if (label) label.textContent = 'TEMPERATURA ACTUAL';
  const current = analysis?.agroclimate?.current;
  if (current?.temp != null) {
    if (el) el.innerHTML = `${current.temp}<span class="kpi-unit">°C</span>`;
    if (sub) sub.textContent = `Humedad: ${current.humidity || '?'}% · Viento: ${current.wind_speed || '?'} km/h`;
  } else {
    if (el) el.textContent = '—';
  }
}

/* ── KPI 4: Economy ── */
function updateKPIEconomy(analysis, predict) {
  const el = document.querySelector('.kpi-card:nth-child(4) .kpi-value');
  const sub = document.querySelector('.kpi-card:nth-child(4) .kpi-subtitle');
  const label = document.querySelector('.kpi-card:nth-child(4) .kpi-label');

  // Try prediction economic impact first
  if (predict?.economic_impact?.estimated_loss_ars > 0) {
    if (label) label.textContent = 'PÉRDIDA PROYECTADA';
    const lossM = Math.round(predict.economic_impact.estimated_loss_ars / 1000000);
    if (el) el.innerHTML = `-$${lossM}M`;
    if (sub) sub.textContent = `ARS Estimados / Campaña (${predict.economic_impact.loss_pct}% pérdida)`;
    return;
  }

  // Try analysis economy data
  const eco = analysis?.economy;
  if (eco?.latest_price?.promedio) {
    if (label) label.textContent = 'PRECIO SOJA (MAGyP)';
    if (el) el.innerHTML = `$${(eco.latest_price.promedio / 1000).toFixed(0)}K<span class="kpi-unit">/ton</span>`;
    if (sub) sub.textContent = `Fecha: ${eco.latest_price.fecha || ''} · Puerto: Rosario`;
    return;
  }

  // Economy unavailable — show info
  if (label) label.textContent = 'DATOS ECONÓMICOS';
  if (el) el.innerHTML = '—';
  if (sub) sub.textContent = 'MAGyP no disponible — configure ENABLE_MAGYP=True';
}

/* ── AI Synthesis ── */
function updateSynthesis(analysis, predict) {
  const banner = document.querySelector('#ai-synthesis .ai-synthesis-content p');
  if (!banner) return;
  const q = getPredictParams();
  const cropName = q.crop === 'soy' ? 'Soja' : 'Maíz';
  const stage = analysis?.agronomy?.current_stage;
  const current = analysis?.agroclimate?.current;
  const risk = predict?.risk_assessment?.overall || '—';
  const rec = predict?.recommendations?.[0]?.action || 'Continuar monitoreo.';

  banner.innerHTML = `
    <strong>Síntesis IA:</strong> El lote
    <span class="inline-badge">${q.lot_id} (${cropName})</span>
    ${stage ? `está en etapa <span class="inline-badge">${stage.name || stage.bbch_code} (BBCH ${stage.bbch_code})</span>` : ''}
    ${current?.temp != null ? `con <strong>${current.temp}°C</strong> y <strong>${current.humidity}%</strong> de humedad.` : '.'}
    Riesgo <strong>${risk}</strong>. ${rec}
  `;

  // Async: enrich with AI-generated insight
  enrichSynthesisWithAI(analysis, predict).then(aiText => {
    if (aiText) {
      banner.innerHTML = `
        <strong>Síntesis IA:</strong> ${aiText}
      `;
    }
  });
}

async function enrichSynthesisWithAI(analysis, predict) {
  if (!analysis && !predict) return null;
  const q = getPredictParams();
  const cropName = q.crop === 'soy' ? 'Soja' : 'Maíz';
  const stage = analysis?.agronomy?.current_stage;
  const temp = analysis?.agroclimate?.current?.temp;
  const risk = predict?.risk_assessment;
  const anomalies = predict?.anomalies || [];

  const prompt = `Sos un ingeniero agrónomo argentino. Resumí en 3 oraciones claras y accionables el estado del lote ${q.lot_id} en Pergamino, Buenos Aires.
Cultivo: ${cropName}. Fecha: ${q.date}.
${stage ? `Etapa: ${stage.name} (BBCH ${stage.bbch_code}), sensibilidad hídrica: ${stage.water_stress_sensitivity || 'normal'}.` : ''}
${temp != null ? `Temperatura actual: ${temp}°C.` : ''}
${risk ? `Riesgo general: ${risk.overall} (score ${risk.score}/100).` : ''}
${anomalies.length ? `Anomalías detectadas: ${anomalies.map(a => a.description).join(' | ')}` : 'Sin anomalías detectadas.'}
Incluí recomendación concreta si hay riesgo.`;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.response;
  } catch { return null; }
}

/* ── Technical Evidence ── */
function updateTechEvidence(analysis, predict) {
  const grid = document.querySelector('.tech-evidence-grid');
  if (!grid) return;
  const agro = analysis?.agroclimate || {};
  const sat = analysis?.satellite || {};
  const agron = analysis?.agronomy || {};
  const econ = analysis?.economy || {};
  const pred = predict || {};

  const items = [];

  // NDVI / soil moisture
  const smVal = sat.soil_moisture_value;
  if (smVal?.soil_moisture != null) {
    items.push({ label: 'Humedad Suelo (SMAP)', value: `${(smVal.soil_moisture * 100).toFixed(0)}%`, cls: smVal.soil_moisture < 0.22 ? 'error' : '' });
  }

  // Precipitation
  const hist = agro.historical || {};
  if (hist.precipitation_15d_mm != null) {
    items.push({ label: 'Precip. Acum. 15d', value: `${hist.precipitation_15d_mm} mm`, cls: hist.precipitation_15d_mm < 10 ? 'error' : '' });
  }

  // Temperature
  const cur = agro.current || {};
  if (cur.temp != null) {
    items.push({ label: 'Temperatura Actual', value: `${cur.temp}°C`, cls: cur.temp > 35 ? 'error' : '' });
  }

  // BBCH stage
  const stage = agron.current_stage;
  if (stage) {
    items.push({ label: 'Fase Fenológica', value: `${stage.name || ''} (BBCH ${stage.bbch_code})`, cls: '' });
  }

  // Yield
  if (pred.yield_prediction) {
    items.push({ label: 'Rinde Estimado', value: `${pred.yield_prediction.estimate_kg_ha} kg/ha`, cls: pred.yield_prediction.loss_pct > 10 ? 'error' : '' });
    items.push({ label: 'Pérdida vs Potencial', value: `-${pred.yield_prediction.loss_pct}%`, cls: 'error' });
  }

  // Price
  if (econ.latest_price?.promedio) {
    items.push({ label: 'Precio Soja', value: `$${econ.latest_price.promedio.toLocaleString()}/ton`, cls: '' });
  }

  // Risk score
  if (pred.risk_assessment) {
    items.push({ label: 'Score de Riesgo', value: `${pred.risk_assessment.score}/100`, cls: pred.risk_assessment.score > 50 ? 'warning-val' : '' });
  }

  // NDVI (satellite scenes count)
  if (sat.optical?.length) {
    items.push({ label: 'Escenas Sentinel-2', value: `${sat.optical.length} disponibles`, cls: '' });
  }

  grid.innerHTML = items.map(i => `
    <div class="tech-evidence-item">
      <span class="tech-evidence-label">${i.label}</span>
      <span class="tech-evidence-value${i.cls ? ' ' + i.cls : ''}">${i.value}</span>
    </div>
  `).join('');

  // Data sources
  const sources = document.querySelector('.tech-sources');
  if (sources) {
    const tags = [];
    if (agro.current) tags.push('NASA POWER');
    if (sat.soil_moisture_value) tags.push('SMAP');
    if (sat.optical?.length) tags.push('Sentinel-2');
    if (econ.latest_price) tags.push('MAGyP');
    if (agron.crop_info) tags.push('INTA/FAO');
    sources.innerHTML = tags.map(t => `<span class="tech-source-tag"><span class="material-symbols-outlined">satellite</span> ${t}</span>`).join('');
  }
}

/* ── Alerts Panel ── */
function updateAlertsPanel(data) {
  const alertsList = document.getElementById('alerts-list');
  const badge = document.querySelector('.alert-badge-count');
  if (!alertsList) return;

  if (!data?.alerts?.length) {
    alertsList.innerHTML = '<p style="padding:1rem;color:var(--on-surface-variant);">Sin alertas activas para este lote.</p>';
    if (badge) badge.textContent = '0 Nuevas';
    return;
  }

  const sevClass = { critical: 'critical', high: 'warning', medium: 'warning', low: 'info' };
  const sevBadge = { critical: 'CRÍTICO', high: 'PRECAUCIÓN', medium: 'INFO', low: 'INFO' };
  alertsList.innerHTML = data.alerts.map(a => `
    <div class="alert-card ${sevClass[a.severity] || sevClass[a.type] || 'info'}">
      <div class="alert-stripe ${sevClass[a.severity] || sevClass[a.type] || 'info'}"></div>
      <div class="alert-top"><h3 class="alert-title">${a.title}</h3><span class="severity-badge ${sevClass[a.severity] || sevClass[a.type] || 'info'}">${sevBadge[a.severity] || sevBadge[a.type] || 'INFO'}</span></div>
      <div class="alert-audience">${(a.audience || ['PRODUCTOR']).map(t => `<span class="audience-tag">${t.toUpperCase()}</span>`).join('')}</div>
      <p class="alert-description">${a.message}</p>
      ${a.evidence ? `
      <div class="expandable-section" id="alert-detail-api-${a.type}">
        <button class="expand-btn" onclick="toggleExpand('alert-detail-api-${a.type}')">
          <span class="material-symbols-outlined">expand_more</span> Detalle técnico
        </button>
        <div class="expand-content">
          <div class="tech-grid">
            ${Object.entries(a.evidence || {}).map(([k, v]) => `
              <div class="tech-item">
                <span class="tech-label">${k}</span>
                <span class="tech-value">${typeof v === 'number' ? v.toFixed(2) : v}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>` : ''}
    </div>
  `).join('');
  if (badge) badge.textContent = `${data.alerts.length} ${data.alerts.length === 1 ? 'Nueva' : 'Nuevas'}`;
}

/* ── Recommendations ── */
function updateRecommendations(predict) {
  const desc = document.querySelector('.action-plan-desc');
  const econDesc = document.querySelector('.econ-desc');
  const econValue = document.querySelector('.econ-metric-value');
  if (!predict) return;

  if (desc && predict.recommendations?.length) {
    const r = predict.recommendations[0];
    desc.innerHTML = `${r.action}.`;
  }
  if (predict.economic_impact) {
    if (econDesc) econDesc.innerHTML = `La ejecución de esta acción protege el potencial de rinde en un <strong>+${Math.round(predict.economic_impact.protected_value_ars / 1000000)}%</strong>.`;
    if (econValue) econValue.textContent = `+$${Math.round(predict.economic_impact.protected_value_ars / 1000000)}M ARS`;
  }
}

/* ── Filter Pills ── */
function updateFilterPills(q) {
  const pills = document.querySelectorAll('.filters-pills .pill');
  if (pills.length >= 4) {
    const cropName = q.crop === 'soy' ? 'Soja' : 'Maíz';
    pills[0].innerHTML = `<span class="material-symbols-outlined pill-icon">location_on</span> Lote ${q.lot_id}`;
    pills[1].innerHTML = `<span class="material-symbols-outlined pill-icon">my_location</span> ${q.lat.toFixed(4)}, ${q.lon.toFixed(4)}`;
    pills[2].innerHTML = `<span class="material-symbols-outlined pill-icon">eco</span> ${cropName}`;
    pills[3].innerHTML = `<span class="material-symbols-outlined pill-icon">calendar_today</span> ${q.date}`;
  }
  // Update breadcrumb
  const bc = document.querySelector('.breadcrumb-item.active');
  if (bc) bc.textContent = `${q.lot_id} — ${q.crop === 'soy' ? 'Soja' : 'Maíz'}`;
}

/* ── SSE ── */
function connectSSE() {
  const es = new EventSource(`${API_BASE}/alerts/stream`);
  es.addEventListener('connected', () => console.log('SSE connected'));
  es.onmessage = (e) => {
    try {
      const a = JSON.parse(e.data);
      showNotification(`🔔 ${a.title}`, a.severity === 'critical' ? 'error' : 'info');
    } catch (_) {}
  };
  es.onerror = () => console.warn('SSE disconnected');
}

/* ── Main Runner ── */
async function runPrediction() {
  const q = getPredictParams();
  showNotification(`🔄 Analizando lote ${q.lot_id} (${q.crop})...`, 'info');

  const [analysis, prediction] = await Promise.all([
    fetchAnalysis(),
    fetchPrediction(),
  ]);

  if (prediction || analysis) {
    updateFilterPills(q);
    updateKPISoilMoisture(prediction, analysis);
    updateKPIRisk(prediction);
    updateKPIWeather(analysis);
    updateKPIEconomy(analysis, prediction);
    updateSynthesis(analysis, prediction);
    updateTechEvidence(analysis, prediction);
    updateAlertsPanel(prediction);
    updateRecommendations(prediction);
  }

  showNotification('✅ Análisis completado', 'success');
}

// Modal close handlers for predict modal
document.getElementById('btn-close-predict-modal')?.addEventListener('click', () => {
  document.getElementById('predict-modal').style.display = 'none';
});
document.getElementById('btn-cancel-predict-modal')?.addEventListener('click', () => {
  document.getElementById('predict-modal').style.display = 'none';
});
document.getElementById('predict-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  document.getElementById('predict-modal').style.display = 'none';
  await runPrediction();
});

document.addEventListener('DOMContentLoaded', () => {
  setTimeout(runPrediction, 2000);
  connectSSE();
});
