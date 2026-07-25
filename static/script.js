/**
 * ARGPLANT AI — Interactive Platform Logic
 * Handles animations, expandable sections, map controls,
 * and user interactions for the decision-support dashboard.
 */

document.addEventListener('DOMContentLoaded', () => {
  initScrollAnimations();
  initKPICounters();
  initMapControls();
  initApprovalFlow();
});

/* ============================================
   Scroll-triggered Animations (Intersection Observer)
   ============================================ */
function initScrollAnimations() {
  const elements = document.querySelectorAll('[data-animate]');
  
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-in');
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.1,
      rootMargin: '0px 0px -40px 0px',
    }
  );

  elements.forEach((el) => observer.observe(el));
}

/* ============================================
   KPI Counter Animation (Count-up on load)
   ============================================ */
function initKPICounters() {
  const kpiValues = document.querySelectorAll('.kpi-value');
  
  kpiValues.forEach((el) => {
    const text = el.textContent.trim();
    
    // Extract numeric value if it's a plain number
    const match = text.match(/^(-?\$?)([\d.]+)(.*)/);
    if (!match) return;

    const prefix = match[1];
    const targetNum = parseFloat(match[2]);
    const suffix = match[3];
    
    if (isNaN(targetNum)) return;

    // Animate from 0 to target
    const duration = 1200;
    const startTime = performance.now();
    const isDecimal = match[2].includes('.');
    
    // Store original innerHTML for elements with inner spans
    const innerSpans = el.querySelectorAll('span');
    if (innerSpans.length > 0) return; // skip complex HTML content

    function updateCounter(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      const current = targetNum * eased;

      if (isDecimal) {
        el.textContent = prefix + current.toFixed(1) + suffix;
      } else {
        el.textContent = prefix + Math.round(current) + suffix;
      }

      if (progress < 1) {
        requestAnimationFrame(updateCounter);
      } else {
        el.textContent = prefix + match[2] + suffix;
      }
    }

    // Delay start by the animation delay
    const delayStr = getComputedStyle(el.closest('[data-animate]') || el).getPropertyValue('--delay');
    const delay = parseFloat(delayStr) * 1000 || 0;
    
    setTimeout(() => {
      requestAnimationFrame(updateCounter);
    }, delay + 300);
  });
}

/* ============================================
   Expandable Section Toggle
   ============================================ */
function toggleExpand(sectionId) {
  const section = document.getElementById(sectionId);
  if (!section) return;
  
  section.classList.toggle('open');
  
  // Animate icon rotation
  const btn = section.querySelector('.expand-btn');
  if (btn) {
    const icon = btn.querySelector('.material-symbols-outlined');
    if (icon) {
      // Icon rotation handled by CSS
    }
  }
}

/* ============================================
   Technical Details Panel Toggle
   ============================================ */
function toggleTechDetails() {
  const panel = document.getElementById('tech-evidence');
  const btn = document.getElementById('btn-tech-details');
  
  if (!panel || !btn) return;
  
  panel.classList.toggle('open');
  btn.classList.toggle('open');
}

/* ============================================
   Map Controls (Zoom simulation)
   ============================================ */
function initMapControls() {
  const mapImage = document.getElementById('map-image');
  const zoomIn = document.getElementById('map-zoom-in');
  const zoomOut = document.getElementById('map-zoom-out');
  
  if (!mapImage || !zoomIn || !zoomOut) return;

  let currentZoom = 1;
  const minZoom = 1;
  const maxZoom = 2.5;
  const zoomStep = 0.3;

  zoomIn.addEventListener('click', () => {
    currentZoom = Math.min(currentZoom + zoomStep, maxZoom);
    mapImage.style.transform = `scale(${currentZoom})`;
  });

  zoomOut.addEventListener('click', () => {
    currentZoom = Math.max(currentZoom - zoomStep, minZoom);
    mapImage.style.transform = `scale(${currentZoom})`;
  });
}

/* ============================================
   Approval Flow (Button interaction)
   ============================================ */
function initApprovalFlow() {
  const approveBtn = document.getElementById('btn-approve');
  if (!approveBtn) return;

  approveBtn.addEventListener('click', () => {
    // Visual feedback
    const originalText = approveBtn.innerHTML;
    approveBtn.innerHTML = `
      <span class="material-symbols-outlined" style="animation: none;">check</span>
      Orden Aprobada
    `;
    approveBtn.style.background = '#2e7d32';
    approveBtn.style.pointerEvents = 'none';

    // Show success notification
    showNotification('✅ Orden de trabajo aprobada exitosamente. Se envió al equipo de campo.', 'success');

    // Reset after delay
    setTimeout(() => {
      approveBtn.innerHTML = originalText;
      approveBtn.style.background = '';
      approveBtn.style.pointerEvents = '';
    }, 4000);
  });
}

/* ============================================
   Notification Toast
   ============================================ */
function showNotification(message, type = 'info') {
  // Remove existing notification
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

  // Styles
  Object.assign(toast.style, {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    maxWidth: '440px',
    padding: '14px 20px',
    borderRadius: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    zIndex: '9999',
    fontFamily: 'Inter, sans-serif',
    fontSize: '14px',
    lineHeight: '1.4',
    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
    transform: 'translateY(20px)',
    opacity: '0',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  });

  // Type-specific colors
  if (type === 'success') {
    toast.style.background = '#e8f5e9';
    toast.style.color = '#1b5e20';
    toast.style.border = '1px solid rgba(46, 125, 50, 0.2)';
  } else if (type === 'error') {
    toast.style.background = '#ffdad6';
    toast.style.color = '#93000a';
    toast.style.border = '1px solid rgba(186, 26, 26, 0.2)';
  } else {
    toast.style.background = '#d4e3ff';
    toast.style.color = '#001c3a';
    toast.style.border = '1px solid rgba(0, 86, 159, 0.2)';
  }

  const closeBtn = toast.querySelector('.notification-close');
  Object.assign(closeBtn.style, {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'inherit',
    opacity: '0.6',
    padding: '0',
    display: 'flex',
    flexShrink: '0',
  });
  closeBtn.querySelector('.material-symbols-outlined').style.fontSize = '18px';

  document.body.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    toast.style.transform = 'translateY(0)';
    toast.style.opacity = '1';
  });

  // Auto remove
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
  showNotification('🔔 3 alertas nuevas detectadas por el motor IA para Lote 123.', 'info');
});

/* ============================================
   ARGPLANT API Integration — Real Data
   ============================================ */

const API_BASE = '/api/v1';

/** Get current query from modal form fields. */
function getQueryParams() {
  return {
    lot_id: document.getElementById('lot-id')?.value || 'lote-123',
    crop: document.getElementById('crop-select')?.value || 'soy',
    lat: parseFloat(document.getElementById('lat-input')?.value) || -33.89,
    lon: parseFloat(document.getElementById('lon-input')?.value) || -60.57,
    date: document.getElementById('analysis-date')?.value || '2026-07-21',
  };
}

let analysisData = null;
let predictData = null;

/** Fetch unified analysis data from the orchestrator. */
async function fetchAnalysis() {
  const q = getQueryParams();
  const params = new URLSearchParams(q);
  try {
    const res = await fetch(`${API_BASE}/analysis?${params}`);
    if (!res.ok) throw new Error(`Analysis: ${res.status}`);
    analysisData = await res.json();
    return analysisData;
  } catch (err) {
    console.warn('Analysis fetch failed:', err);
    return null;
  }
}

/** Fetch prediction (anomalies, risk, yield, recommendations). */
async function fetchPrediction() {
  const q = getQueryParams();
  try {
    const res = await fetch(`${API_BASE}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(q),
    });
    if (!res.ok) throw new Error(`Predict: ${res.status}`);
    predictData = await res.json();
    return predictData;
  } catch (err) {
    console.warn('Prediction fetch failed:', err);
    return null;
  }
}

/** Update all KPI cards with real data from the prediction. */
function updateKPIs(data) {
  if (!data) return;

  // KPI 1: Soil Moisture
  const smValue = data.anomalies?.find(a => a.type === 'water_stress');
  if (smValue) {
    const smEl = document.querySelector('.kpi-card:nth-child(1) .kpi-value');
    const smSub = document.querySelector('.kpi-card:nth-child(1) .kpi-subtitle');
    const smBar = document.querySelector('.kpi-card:nth-child(1) .kpi-bar-fill');
    if (smEl) {
      const pct = smValue.evidence?.soil_moisture_pct || Math.round((smValue.evidence?.soil_moisture || 0.2) * 100);
      smEl.innerHTML = `${pct}<span class="kpi-unit">%</span>`;
    }
    if (smSub) smSub.textContent = smValue.description;
    if (smBar) smBar.style.width = `${Math.min(100, (smValue.evidence?.soil_moisture || 0.2) * 200)}%`;
  }

  // KPI 2: Risk Score
  if (data.risk_assessment) {
    const riskEl = document.querySelector('.kpi-card:nth-child(2) .kpi-value');
    const riskScore = document.querySelector('.kpi-card:nth-child(2) .kpi-score');
    const riskSub = document.querySelector('.kpi-card:nth-child(2) .kpi-subtitle');
    const segments = document.querySelectorAll('.kpi-card:nth-child(2) .segment');
    if (riskEl) riskEl.textContent = data.risk_assessment.overall === 'critical' ? 'Crítico' : 
      data.risk_assessment.overall === 'high' ? 'Alto' : 'Medio';
    if (riskScore) riskScore.textContent = `Score: ${data.risk_assessment.score}`;
    if (riskSub && data.risk_assessment.factors?.length) {
      riskSub.textContent = `Factor principal: ${data.risk_assessment.factors[0].name} (${data.risk_assessment.factors[0].score})`;
    }
  }

  // KPI 3: Affected Area (from yield loss)
  if (data.yield_prediction) {
    const lossEl = document.querySelector('.kpi-card:nth-child(3) .kpi-value');
    if (lossEl) lossEl.innerHTML = `${data.yield_prediction.loss_pct}<span class="kpi-unit">%</span>`;
  }

  // KPI 4: Economic Loss
  if (data.economic_impact) {
    const econEl = document.querySelector('.kpi-card:nth-child(4) .kpi-value');
    const lossM = Math.round(data.economic_impact.estimated_loss_ars / 1000000);
    if (econEl) econEl.innerHTML = `-$${lossM}M`;
  }
}

/** Update the AI Synthesis banner with real data. */
function updateSynthesis(data) {
  const banner = document.querySelector('#ai-synthesis .ai-synthesis-content p');
  if (!banner || !data) return;

  const q = getQueryParams();
  const crop = q.crop === 'soy' ? 'Soja' : 'Maíz';
  const risk = data.risk_assessment?.overall || 'medio';
  const anomalies = data.anomalies?.length || 0;
  
  banner.innerHTML = `
    <strong>Síntesis IA:</strong> El lote
    <span class="inline-badge">Lote 123 (${crop})</span>
    presenta riesgo <strong>${risk}</strong> con ${anomalies} anomalía(s) detectada(s).
    ${data.recommendations?.[0]?.action || 'Se recomienda continuar monitoreo.'}
  `;
}

/** Update alerts panel from prediction data. */
function updateAlerts(data) {
  const alertsList = document.getElementById('alerts-list');
  if (!alertsList || !data?.alerts?.length) return;

  const severityClass = { critical: 'critical', high: 'warning', medium: 'warning' };
  const severityBadge = { critical: 'CRÍTICO', high: 'PRECAUCIÓN', medium: 'INFO' };

  alertsList.innerHTML = data.alerts.map((a, i) => `
    <div class="alert-card ${severityClass[a.type] || 'info'}">
      <div class="alert-stripe ${severityClass[a.type] || 'info'}"></div>
      <div class="alert-top">
        <h3 class="alert-title">${a.title}</h3>
        <span class="severity-badge ${severityClass[a.type] || 'info'}">${severityBadge[a.type] || 'INFO'}</span>
      </div>
      <div class="alert-audience">
        ${(a.audience || ['PRODUCTOR']).map(t => `<span class="audience-tag">${t.toUpperCase()}</span>`).join('')}
      </div>
      <p class="alert-description">${a.message}</p>
    </div>
  `).join('');
}

/** SSE connection for real-time alerts. */
function connectSSE() {
  const evtSource = new EventSource(`${API_BASE}/alerts/stream`);
  
  evtSource.addEventListener('connected', () => {
    console.log('SSE connected');
  });

  evtSource.onmessage = (event) => {
    try {
      const alert = JSON.parse(event.data);
      showNotification(`🔔 Nueva alerta: ${alert.title}`, alert.severity === 'critical' ? 'error' : 'info');
    } catch (e) {
      // keepalive comment
    }
  };

  evtSource.onerror = () => {
    console.warn('SSE connection lost, reconnecting...');
  };
}

/** Main: load data and update UI. */
async function loadDashboard() {
  const q = getQueryParams();
  showNotification(`🔄 Analizando lote ${q.lot_id} (${q.crop})...`, 'info');

  const [analysis, prediction] = await Promise.all([
    fetchAnalysis(),
    fetchPrediction(),
  ]);

  if (prediction) {
    updateKPIs(prediction);
    updateSynthesis(prediction);
    updateAlerts(prediction);
    updatePills(q);
  }

  if (analysis) {
    console.log('Analysis data loaded:', analysis);
  }

  showNotification('✅ Dashboard actualizado con datos reales', 'success');
}

/** Wire the "Ingresar Datos" button — open modal. */
document.getElementById('btn-ingresar')?.addEventListener('click', () => {
  openModal();
});

/** Close modal on close button or overlay click. */
document.getElementById('modal-close')?.addEventListener('click', closeModal);
document.getElementById('modal-overlay')?.addEventListener('click', (e) => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});

/** Preset buttons — set coordinates. */
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('lat-input').value = btn.dataset.lat;
    document.getElementById('lon-input').value = btn.dataset.lon;
  });
});

/** Handle form submit — run analysis. */
document.getElementById('data-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  closeModal();
  await loadDashboard();
});

/** Update filter pills with current query data. */
function updatePills(q) {
  const pills = document.querySelectorAll('.filters-pills .pill');
  if (pills.length >= 4) {
    pills[0].innerHTML = `<span class="material-symbols-outlined pill-icon">location_on</span> Lote ${q.lot_id}`;
    pills[1].innerHTML = `<span class="material-symbols-outlined pill-icon">landscape</span> Lat: ${q.lat} Lon: ${q.lon}`;
    pills[2].innerHTML = `<span class="material-symbols-outlined pill-icon">eco</span> ${q.crop === 'soy' ? 'Soja' : 'Maíz'}`;
    pills[3].innerHTML = `<span class="material-symbols-outlined pill-icon">calendar_today</span> ${q.date}`;
  }
}

function openModal() {
  document.getElementById('modal-overlay').classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

// Auto-load on page open
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(loadDashboard, 1500); // delay for animations
  connectSSE();
});
