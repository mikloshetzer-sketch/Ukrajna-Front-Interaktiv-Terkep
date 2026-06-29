const STORAGE_KEY = 'ukraine_front_identified_objects_v1';

const OBJECT_TYPES = {
  unknown: { label: 'Selected coordinate', shortLabel: 'POINT', category: 'Coordinate', icon: '📍', color: '#6b7280' },
  airfield: { label: 'Airfield / Airbase', shortLabel: 'AIRBASE', category: 'Military', icon: '✈️', color: '#2563eb' },
  port: { label: 'Port', shortLabel: 'PORT', category: 'Infrastructure', icon: '⚓', color: '#1d4ed8' },
  bridge: { label: 'Bridge', shortLabel: 'BRIDGE', category: 'Infrastructure', icon: '🌉', color: '#7c3aed' },
  railway: { label: 'Railway / Rail node', shortLabel: 'RAIL', category: 'Infrastructure', icon: '🚂', color: '#111827' },
  warehouse: { label: 'Warehouse / Logistics point', shortLabel: 'WAREHOUSE', category: 'Logistics', icon: '📦', color: '#92400e' },
  fuel: { label: 'Fuel / Oil facility', shortLabel: 'FUEL', category: 'Logistics', icon: '🛢', color: '#ea580c' },
  industrial: { label: 'Industrial object', shortLabel: 'INDUSTRIAL', category: 'Industry', icon: '🏭', color: '#475569' },
  radar: { label: 'Radar / Communications', shortLabel: 'RADAR', category: 'Military', icon: '📡', color: '#0891b2' },
  airdefense: { label: 'Air defence', shortLabel: 'AIR DEF', category: 'Military', icon: '🛡', color: '#16a34a' },
  target: { label: 'Target', shortLabel: 'TARGET', category: 'Military', icon: '🎯', color: '#dc2626' },
};

function nowIso() { return new Date().toISOString(); }
function formatCoord(value) { return Number(value).toFixed(6); }
function makeObjectId() { return `object_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`; }
function getObjectType(type) { return OBJECT_TYPES[type] || OBJECT_TYPES.unknown; }

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function readStoredObjects() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lng)));
  } catch (error) {
    console.warn('Object identification storage read error:', error);
    return [];
  }
}

function writeStoredObjects(objects) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(objects)); }
  catch (error) { console.warn('Object identification storage write error:', error); }
}

function copyText(text) {
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).catch(() => {});
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try { document.execCommand('copy'); } catch (error) { console.warn('Clipboard fallback failed:', error); }
  document.body.removeChild(textarea);
}

function buildAnalyzeCommand(objectItem, radius = 750) {
  return `python scripts/coordinate_intelligence.py --lat ${formatCoord(objectItem.lat)} --lon ${formatCoord(objectItem.lng)} --radius ${radius}`;
}

function buildWorkflowInputText(objectItem, radius = 750) {
  return [
    'Coordinate Intelligence workflow input',
    '',
    `lat: ${formatCoord(objectItem.lat)}`,
    `lon: ${formatCoord(objectItem.lng)}`,
    `radius: ${radius}`,
    '',
    'Local command:',
    buildAnalyzeCommand(objectItem, radius),
  ].join('\n');
}

function buildWorkflowUrl() {
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  const repoName = pathParts[0] || 'Ukrajna-Front-Interaktiv-Terkep';
  return `https://github.com/mikloshetzer-sketch/${repoName}/actions/workflows/coordinate-intelligence.yml`;
}

function removeExistingAnalystPanel() {
  const existing = document.getElementById('coordinateIntelligencePanel');
  if (existing) existing.remove();
}

function normalizeFeatureLabel(value) {
  const map = {
    railway: 'Railway',
    bridge: 'Bridge',
    road: 'Road',
    warehouse: 'Warehouse',
    industrial: 'Industrial',
    power: 'Power',
    port: 'Port',
    fuel: 'Fuel',
    storage: 'Storage',
    airfield: 'Airfield',
    military: 'Military',
  };
  return map[value] || value;
}

function getIntelligenceIconAndLabel(text) {
  const value = String(text || '').toLowerCase();
  if (value.includes('railway') || value.includes('rail') || value.includes('station')) return { icon: '🚂', shortLabel: 'RAIL', color: '#111827' };
  if (value.includes('port') || value.includes('maritime') || value.includes('harbour') || value.includes('harbor')) return { icon: '⚓', shortLabel: 'PORT', color: '#1d4ed8' };
  if (value.includes('bridge') || value.includes('crossing')) return { icon: '🌉', shortLabel: 'BRIDGE', color: '#7c3aed' };
  if (value.includes('airfield') || value.includes('airbase') || value.includes('airport')) return { icon: '✈️', shortLabel: 'AIRBASE', color: '#2563eb' };
  if (value.includes('warehouse') || value.includes('logistics')) return { icon: '📦', shortLabel: 'LOGISTICS', color: '#92400e' };
  if (value.includes('industrial') || value.includes('factory')) return { icon: '🏭', shortLabel: 'INDUSTRIAL', color: '#475569' };
  if (value.includes('fuel') || value.includes('oil') || value.includes('storage')) return { icon: '🛢', shortLabel: 'FUEL', color: '#ea580c' };
  return { icon: '📍', shortLabel: 'POINT', color: '#6b7280' };
}

function getLocationTitle(data) {
  const location = data?.location || {};
  const summary = data?.summary || {};
  return location.city || summary.nearest_city || location.locality || summary.nearest_locality || location.nearest_named_place || summary.nearest_named_place || 'Selected coordinate';
}

function getLocationSubtitle(data) {
  const location = data?.location || {};
  const summary = data?.summary || {};
  return [location.region || summary.region, location.country || summary.country].filter(Boolean).join(' · ');
}

function getDetectedObject(data) {
  const summary = data?.summary || {};
  const wikidata = data?.wikidata || {};
  const nearest = wikidata.nearest || {};
  return nearest.name || summary.nearest_wikidata || summary.primary_object || summary.likely_object || 'No confirmed object';
}

function getAssessmentType(data) {
  const summary = data?.summary || {};
  const fusion = data?.fusion_profile || {};
  return summary.likely_object || fusion.type || '-';
}

function formatDateTime(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('en-GB', {
      timeZone: 'UTC',
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }) + ' UTC';
  } catch {
    return value;
  }
}

function featureCountsHtml(summary) {
  const counts = summary?.feature_counts || {};
  const entries = Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 7);
  if (!entries.length) return 'No infrastructure counts available.';
  return entries.map(([key, value]) => `${escapeHtml(normalizeFeatureLabel(key))}: <strong>${escapeHtml(value)}</strong>`).join('<br>');
}

function buildAnalysisSummary(data) {
  const summary = data?.summary || {};
  const locationTitle = getLocationTitle(data);
  const locationSubtitle = getLocationSubtitle(data);
  const detectedObject = getDetectedObject(data);
  const assessmentType = getAssessmentType(data);
  const confidence = summary.confidence || data?.fusion_profile?.confidence || '-';
  const visual = getIntelligenceIconAndLabel(`${detectedObject} ${assessmentType}`);
  return {
    generatedAt: data?.generated_at || null,
    lat: data?.coordinate?.lat,
    lon: data?.coordinate?.lon,
    locationTitle,
    locationSubtitle,
    detectedObject,
    assessmentType,
    confidence,
    assessment: data?.assessment || '',
    nearestCity: summary.nearest_city || data?.location?.city || null,
    region: summary.region || data?.location?.region || null,
    country: summary.country || data?.location?.country || null,
    nearestRoad: summary.nearest_road || data?.location?.road || null,
    nearestNamedPlace: summary.nearest_named_place || data?.location?.nearest_named_place || null,
    nearestWikidata: summary.nearest_wikidata || data?.wikidata?.nearest?.name || null,
    primaryObject: summary.primary_object || null,
    operationalEnvironment: summary.operational_environment || null,
    railwayConfidence: summary.railway_confidence || null,
    maritimeConfidence: summary.maritime_confidence || null,
    featureCounts: summary.feature_counts || {},
    icon: visual.icon,
    shortLabel: visual.shortLabel,
    color: visual.color,
  };
}

function isSameCoordinate(data, objectItem) {
  const dataLat = Number(data?.coordinate?.lat);
  const dataLon = Number(data?.coordinate?.lon);
  const itemLat = Number(objectItem?.lat);
  const itemLon = Number(objectItem?.lng);
  if (!Number.isFinite(dataLat) || !Number.isFinite(dataLon)) return false;
  if (!Number.isFinite(itemLat) || !Number.isFinite(itemLon)) return false;
  return Math.abs(dataLat - itemLat) < 0.00015 && Math.abs(dataLon - itemLon) < 0.00015;
}

function updatePanelHeaderFromAnalysis(analysis) {
  const title = document.getElementById('ciPanelLocationTitle');
  const subtitle = document.getElementById('ciPanelLocationSubtitle');
  const detected = document.getElementById('ciPanelDetectedObject');
  const assessment = document.getElementById('ciPanelAssessmentType');
  const badge = document.getElementById('ciPanelConfidenceBadge');
  if (title) title.innerHTML = `${escapeHtml(analysis.icon)} ${escapeHtml(analysis.locationTitle || 'Selected coordinate')}`;
  if (subtitle) subtitle.textContent = analysis.locationSubtitle || 'Location context unavailable';
  if (detected) detected.textContent = analysis.detectedObject || '-';
  if (assessment) assessment.textContent = analysis.assessmentType || '-';
  if (badge) badge.textContent = analysis.confidence || '-';
}

function createAnalystPanelHtml(objectItem) {
  const typeMeta = getObjectType(objectItem.objectType);
  const analysis = objectItem.analysisSummary || null;
  const lat = formatCoord(objectItem.lat);
  const lng = formatCoord(objectItem.lng);
  const panelIcon = analysis?.icon || typeMeta.icon;
  const panelTitle = analysis?.locationTitle || typeMeta.label;
  const panelSubtitle = analysis?.locationSubtitle || 'Analysis result will appear here after the workflow finishes.';
  const detectedObject = analysis?.detectedObject || 'Not analysed yet';
  const assessmentType = analysis?.assessmentType || typeMeta.category;
  const confidence = analysis?.confidence || '-';

  return `
    <div id="coordinateIntelligencePanel" style="position:fixed;right:24px;top:86px;z-index:10000;width:350px;max-width:calc(100vw - 48px);background:rgba(15,23,42,.96);color:#f8fafc;border:1px solid rgba(250,204,21,.65);border-left:4px solid rgba(250,204,21,.95);border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,.38);font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;overflow:hidden;">
      <div data-ci-drag-handle="true" style="cursor:move;padding:10px 12px;border-bottom:1px solid rgba(148,163,184,.28);background:rgba(30,41,59,.92);">
        <div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#cbd5e1;font-weight:800;">Coordinate Intelligence</div>
        <div id="ciPanelLocationTitle" style="font-size:17px;font-weight:900;margin-top:4px;line-height:1.2;">${escapeHtml(panelIcon)} ${escapeHtml(panelTitle)}</div>
        <div id="ciPanelLocationSubtitle" style="font-size:12px;color:#cbd5e1;margin-top:3px;line-height:1.25;">${escapeHtml(panelSubtitle)}</div>
        <div style="margin-top:9px;padding-top:8px;border-top:1px solid rgba(148,163,184,.25);">
          <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:800;">Detected object</div>
          <div id="ciPanelDetectedObject" style="font-size:13px;font-weight:800;color:#f8fafc;margin-top:2px;">${escapeHtml(detectedObject)}</div>
          <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:800;margin-top:8px;">Assessment</div>
          <div id="ciPanelAssessmentType" style="font-size:13px;font-weight:800;color:#facc15;margin-top:2px;">${escapeHtml(assessmentType)}</div>
          <div style="margin-top:8px;display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <span style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:800;">Confidence</span>
            <span id="ciPanelConfidenceBadge" style="font-size:11px;font-weight:900;padding:3px 7px;border-radius:999px;background:rgba(250,204,21,.16);color:#fde68a;border:1px solid rgba(250,204,21,.35);">${escapeHtml(confidence)}</span>
          </div>
        </div>
      </div>

      <div style="padding:12px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
          <div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:700;">Latitude</div><div style="font-size:13px;font-weight:800;">${lat}</div></div>
          <div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:700;">Longitude</div><div style="font-size:13px;font-weight:800;">${lng}</div></div>
        </div>

        <div style="margin-bottom:10px;">
          <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:700;margin-bottom:5px;">Search radius</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;">
            <label style="display:flex;align-items:center;gap:5px;"><input type="radio" name="ciRadius" value="250"> 250 m</label>
            <label style="display:flex;align-items:center;gap:5px;"><input type="radio" name="ciRadius" value="500"> 500 m</label>
            <label style="display:flex;align-items:center;gap:5px;"><input type="radio" name="ciRadius" value="750" checked> 750 m</label>
            <label style="display:flex;align-items:center;gap:5px;"><input type="radio" name="ciRadius" value="1000"> 1000 m</label>
          </div>
        </div>

        <div id="coordinateIntelligenceStatus" style="background:rgba(2,6,23,.44);border:1px solid rgba(148,163,184,.22);border-radius:8px;padding:8px;font-size:12px;line-height:1.35;color:#cbd5e1;margin-bottom:10px;max-height:290px;overflow:auto;">
          ${analysis ? `<strong>Last analysis</strong><br>${escapeHtml(formatDateTime(analysis.generatedAt))}<br><br><strong>Location</strong><br>${escapeHtml(analysis.locationTitle || '-')}<br>${escapeHtml(analysis.locationSubtitle || '')}<br><br><strong>Infrastructure counts</strong><br>${featureCountsHtml({feature_counts: analysis.featureCounts || {}})}` : 'Status: ready. This panel prepares the Coordinate Intelligence workflow input.'}
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
          <button type="button" data-ci-action="run" data-object-id="${escapeHtml(objectItem.id)}" style="background:#facc15;color:#111827;border:0;border-radius:6px;padding:7px 8px;font-weight:800;cursor:pointer;">Run Analysis</button>
          <button type="button" data-ci-action="close" style="background:rgba(148,163,184,.18);color:#f8fafc;border:1px solid rgba(148,163,184,.35);border-radius:6px;padding:7px 8px;font-weight:700;cursor:pointer;">Cancel</button>
        </div>
      </div>
    </div>
  `;
}

function getSelectedAnalysisRadius() {
  const selected = document.querySelector('input[name="ciRadius"]:checked');
  return Number(selected?.value || 750);
}

async function loadLatestIntelligenceResult() {
  const response = await fetch('data/intelligence/latest.json?_=' + Date.now(), { cache: 'no-store' });
  if (!response.ok) throw new Error('latest.json not available');
  return await response.json();
}

function renderLatestIntelligenceResult(data, objectItem = null) {
  const summary = data.summary || {};
  const analysis = buildAnalysisSummary(data);
  const features = (data.nearby_features || []).slice(0, 6).map(f => `• ${escapeHtml(f.name)} (${escapeHtml(f.feature_type)})`).join('<br>');
  updatePanelHeaderFromAnalysis(analysis);

  const locationLine = [analysis.locationTitle, analysis.locationSubtitle].filter(Boolean).join('<br>');

  setAnalystPanelStatus(
    `<strong>Analysis completed</strong><br>` +
    `<span style="color:#94a3b8;">${escapeHtml(formatDateTime(analysis.generatedAt))}</span><br><br>` +
    `<strong>Location</strong><br>${locationLine || '-'}<br><br>` +
    `<strong>Detected object</strong><br>${escapeHtml(analysis.detectedObject || '-')}<br><br>` +
    `<strong>Likely object</strong><br><span style="color:#facc15;font-weight:800;">${escapeHtml(summary.likely_object || '-')}</span><br>` +
    `Confidence: <strong>${escapeHtml(summary.confidence || '-')}</strong><br><br>` +
    `<strong>Nearest road / place</strong><br>${escapeHtml(analysis.nearestRoad || analysis.nearestNamedPlace || '-')}<br><br>` +
    `<strong>Infrastructure counts</strong><br>${featureCountsHtml(summary)}<br><br>` +
    `<strong>Assessment</strong><br>${escapeHtml(data.assessment || '-')}<br><br>` +
    `<strong>Nearby features</strong><br>${features || 'No nearby mapped features.'}`
  );

  return analysis;
}

function setAnalystPanelStatus(html) {
  const status = document.getElementById('coordinateIntelligenceStatus');
  if (status) status.innerHTML = html;
}

function makeAnalystPanelDraggable(panel) {
  const handle = panel.querySelector('[data-ci-drag-handle="true"]');
  if (!handle) return;

  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  handle.addEventListener('mousedown', event => {
    isDragging = true;
    startX = event.clientX;
    startY = event.clientY;
    const rect = panel.getBoundingClientRect();
    startLeft = rect.left;
    startTop = rect.top;
    panel.style.left = `${startLeft}px`;
    panel.style.top = `${startTop}px`;
    panel.style.right = 'auto';
    event.preventDefault();
  });

  document.addEventListener('mousemove', event => {
    if (!isDragging) return;
    panel.style.left = `${Math.max(8, startLeft + event.clientX - startX)}px`;
    panel.style.top = `${Math.max(8, startTop + event.clientY - startY)}px`;
  });

  document.addEventListener('mouseup', () => { isDragging = false; });
}

function downloadTextFile(filename, content, mimeType = 'application/json') {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, 0);
}

function objectToGeoJsonFeature(objectItem) {
  const typeMeta = getObjectType(objectItem.objectType);
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [Number(objectItem.lng), Number(objectItem.lat)] },
    properties: {
      id: objectItem.id,
      source: 'manual_object_identification',
      objectType: objectItem.objectType || 'unknown',
      objectTypeLabel: typeMeta.label,
      objectCategory: typeMeta.category,
      createdAt: objectItem.createdAt || null,
      updatedAt: objectItem.updatedAt || null,
      wgs84: `${formatCoord(objectItem.lat)}, ${formatCoord(objectItem.lng)}`,
      analysisSummary: objectItem.analysisSummary || null,
    },
  };
}

function createObjectIcon(objectItem) {
  const typeMeta = getObjectType(objectItem.objectType);
  const analysis = objectItem.analysisSummary || null;
  const icon = analysis?.icon || typeMeta.icon;
  const shortLabel = analysis?.shortLabel || typeMeta.shortLabel;
  const color = analysis?.color || typeMeta.color;

  return L.divIcon({
    className: 'identified-object-marker',
    html: `<div style="position:relative;min-width:54px;max-width:110px;background:rgba(17,24,39,.92);color:#fff;border:1px solid rgba(255,255,255,.28);border-top:4px solid ${color};border-radius:8px;padding:5px 7px;box-shadow:0 2px 9px rgba(0,0,0,.28);font-size:11px;line-height:1.15;text-align:center;white-space:nowrap;"><div style="font-size:14px;line-height:1;">${icon}</div><div style="font-weight:700;margin-top:2px;">${escapeHtml(shortLabel)}</div></div>`,
    iconSize: [1, 1],
    iconAnchor: [27, 16],
  });
}

function createPopupHtml(objectItem) {
  const typeMeta = getObjectType(objectItem.objectType);
  const analysis = objectItem.analysisSummary || null;
  const lat = formatCoord(objectItem.lat);
  const lng = formatCoord(objectItem.lng);
  const coordText = `${lat}, ${lng}`;
  const title = analysis?.locationTitle || typeMeta.label;
  const subtitle = analysis?.locationSubtitle || typeMeta.category;
  const icon = analysis?.icon || typeMeta.icon;
  const detectedObject = analysis?.detectedObject || 'Not analysed yet';
  const assessmentType = analysis?.assessmentType || typeMeta.shortLabel;
  const confidence = analysis?.confidence || '-';

  return `
    <div style="min-width:260px;max-width:310px;">
      <div style="font-weight:800;margin-bottom:4px;font-size:14px;line-height:1.25;">${escapeHtml(icon)} ${escapeHtml(title)}</div>
      <div style="font-size:12px;color:#555;margin-bottom:6px;line-height:1.25;">${escapeHtml(subtitle || '')}</div>
      <div><b>Detected object:</b> ${escapeHtml(detectedObject)}</div>
      <div><b>Assessment:</b> ${escapeHtml(assessmentType)}</div>
      <div><b>Confidence:</b> ${escapeHtml(confidence)}</div>
      <hr style="margin:6px 0;">
      <div><b>Latitude:</b> ${lat}</div>
      <div><b>Longitude:</b> ${lng}</div>
      <div style="font-size:12px;color:#555;margin-top:6px;">WGS84: <code>${coordText}</code></div>
      ${analysis ? `<hr style="margin:6px 0;"><div style="font-size:12px;line-height:1.35;"><b>Nearest road/place:</b><br>${escapeHtml(analysis.nearestRoad || analysis.nearestNamedPlace || '-')}</div><div style="font-size:12px;color:#555;margin-top:5px;">Last analysis: ${escapeHtml(formatDateTime(analysis.generatedAt))}</div>` : ''}
      <hr style="margin:6px 0;">
      <button type="button" data-object-action="copy" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%;margin-bottom:4px;">Copy object</button>
      <button type="button" data-object-action="export-json" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%;margin-bottom:4px;">Export object JSON</button>
      <button type="button" data-object-action="export-geojson" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%;margin-bottom:4px;">Export object GeoJSON</button>
      <button type="button" data-object-action="analyze" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%;margin-bottom:4px;background:#111827;color:#fff;border:1px solid rgba(250,204,21,.75);border-radius:4px;padding:5px 8px;font-weight:700;cursor:pointer;">Analyze Coordinate</button>
      <button type="button" data-object-action="delete" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%;">Delete object</button>
      <div style="font-size:11px;color:#777;margin-top:6px;">Drag the object marker to refine the location.</div>
    </div>
  `;
}

export function initObjectIdentificationTool({ map, layerGroup, enabled = false, getObjectTypeValue = null, onStatusChange = null } = {}) {
  if (!map || !layerGroup) throw new Error('initObjectIdentificationTool requires map and layerGroup');

  let isEnabled = Boolean(enabled);
  let objects = readStoredObjects();
  const rendered = new Map();

  function emitStatus(text) {
    if (typeof onStatusChange === 'function') onStatusChange(text);
  }

  function save() { writeStoredObjects(objects); }
  function findObject(id) { return objects.find(item => item.id === id); }
  function getObjects() { return objects.map(item => ({ ...item })); }

  function exportJson(targetObjects = objects, filename = null) {
    const payload = {
      generatedAt: nowIso(),
      source: 'ukraine_front_interactive_map',
      type: 'manual_object_identifications',
      count: targetObjects.length,
      objects: targetObjects.map(item => ({ ...item })),
    };
    downloadTextFile(filename || `identified_objects_${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(payload, null, 2), 'application/json');
    return payload;
  }

  function exportGeoJson(targetObjects = objects, filename = null) {
    const payload = {
      type: 'FeatureCollection',
      generatedAt: nowIso(),
      source: 'ukraine_front_interactive_map',
      features: targetObjects.map(objectToGeoJsonFeature),
    };
    downloadTextFile(filename || `identified_objects_${new Date().toISOString().slice(0, 10)}.geojson`, JSON.stringify(payload, null, 2), 'application/geo+json');
    return payload;
  }

  function renderObject(objectItem, shouldOpen = false) {
    const marker = L.marker([objectItem.lat, objectItem.lng], {
      draggable: true,
      title: objectItem.analysisSummary?.locationTitle || getObjectType(objectItem.objectType).label,
      icon: createObjectIcon(objectItem),
    });

    marker.bindPopup(createPopupHtml(objectItem));
    marker.on('dragend', () => updateObjectPosition(objectItem.id, marker.getLatLng()));
    marker.addTo(layerGroup);
    rendered.set(objectItem.id, marker);
    if (shouldOpen) marker.openPopup();
  }

  function restoreObjects() {
    layerGroup.clearLayers();
    rendered.clear();
    objects = readStoredObjects();
    objects.forEach(item => renderObject(item, false));
  }

  function addObject(latlng, objectType = 'unknown', shouldOpen = true) {
    const objectItem = {
      id: makeObjectId(),
      createdAt: nowIso(),
      updatedAt: nowIso(),
      lat: Number(latlng.lat),
      lng: Number(latlng.lng),
      objectType: objectType || 'unknown',
    };
    if (!Number.isFinite(objectItem.lat) || !Number.isFinite(objectItem.lng)) return null;
    objects.push(objectItem);
    save();
    renderObject(objectItem, shouldOpen);
    emitStatus(`Koordináta rögzítve: ${formatCoord(objectItem.lat)}, ${formatCoord(objectItem.lng)}.`);
    return objectItem;
  }

  function updateObjectPosition(id, latlng) {
    const item = findObject(id);
    if (!item) return;
    item.lat = Number(latlng.lat);
    item.lng = Number(latlng.lng);
    item.updatedAt = nowIso();
    item.analysisSummary = null;
    const marker = rendered.get(id);
    if (marker) {
      marker.setLatLng([item.lat, item.lng]);
      marker.setIcon(createObjectIcon(item));
      marker.bindPopup(createPopupHtml(item));
    }
    save();
  }

  function removeObject(id) {
    const marker = rendered.get(id);
    if (marker) {
      layerGroup.removeLayer(marker);
      rendered.delete(id);
    }
    objects = objects.filter(item => item.id !== id);
    save();
    emitStatus('Azonosított objektum törölve.');
  }

  function clearObjects() {
    layerGroup.clearLayers();
    rendered.clear();
    objects = [];
    save();
    emitStatus('Az azonosított objektumok törölve.');
  }

  function openAnalystPanel(objectItem) {
    removeExistingAnalystPanel();
    const wrapper = document.createElement('div');
    wrapper.innerHTML = createAnalystPanelHtml(objectItem).trim();
    const panel = wrapper.firstElementChild;
    document.body.appendChild(panel);
    makeAnalystPanelDraggable(panel);
    emitStatus(`Coordinate Intelligence panel opened.<br>Lat: <strong>${formatCoord(objectItem.lat)}</strong><br>Lon: <strong>${formatCoord(objectItem.lng)}</strong>`);
  }

  function shouldIgnoreClick(event) {
    const target = event.originalEvent?.target;
    if (!target) return false;
    const tagName = String(target.tagName || '').toLowerCase();
    if (['button', 'input', 'select', 'textarea', 'a'].includes(tagName)) return true;
    if (target.closest?.('.leaflet-popup')) return true;
    if (target.closest?.('.leaflet-control')) return true;
    if (target.closest?.('#sidebar')) return true;
    return false;
  }

  function handleMapClick(event) {
    if (!isEnabled || !event?.latlng || shouldIgnoreClick(event)) return;
    const selectedType = typeof getObjectTypeValue === 'function' ? getObjectTypeValue() : 'unknown';
    addObject(event.latlng, selectedType, true);
  }

  function handlePopupClick(event) {
    const target = event.target;
    if (!target?.dataset) return;
    const action = target.dataset.objectAction;
    const id = target.dataset.objectId;
    if (!action || !id) return;
    const item = findObject(id);
    if (!item) return;
    const typeMeta = getObjectType(item.objectType);
    const analysis = item.analysisSummary || null;

    if (action === 'copy') {
      copyText(
        `${analysis?.locationTitle || typeMeta.label}\n` +
        `Detected object: ${analysis?.detectedObject || 'n/a'}\n` +
        `Assessment: ${analysis?.assessmentType || typeMeta.category}\n` +
        `Confidence: ${analysis?.confidence || 'n/a'}\n` +
        `Coordinates: ${formatCoord(item.lat)}, ${formatCoord(item.lng)}\n` +
        `Created: ${item.createdAt || 'n/a'}`
      );
      target.textContent = 'Copied';
      setTimeout(() => { target.textContent = 'Copy object'; }, 1200);
      return;
    }

    if (action === 'export-json') { exportJson([item], `identified_object_${item.id}.json`); return; }
    if (action === 'export-geojson') { exportGeoJson([item], `identified_object_${item.id}.geojson`); return; }
    if (action === 'analyze') { openAnalystPanel(item); return; }
    if (action === 'delete') removeObject(id);
  }

  function handleAnalystPanelClick(event) {
    const target = event.target;
    if (!target?.dataset) return;
    const action = target.dataset.ciAction;
    if (!action) return;

    if (action === 'close') {
      removeExistingAnalystPanel();
      emitStatus('Coordinate Intelligence panel closed.');
      return;
    }

    if (action === 'run') {
      const id = target.dataset.objectId;
      const item = findObject(id);
      if (!item) {
        setAnalystPanelStatus('Status: object not found.');
        return;
      }

      const radius = getSelectedAnalysisRadius();
      const workflowInput = buildWorkflowInputText(item, radius);
      const workflowUrl = buildWorkflowUrl();
      copyText(workflowInput);

      setAnalystPanelStatus('Workflow input prepared.<br>Run the GitHub workflow, then click Run Analysis again to refresh the latest result.');

      loadLatestIntelligenceResult()
        .then(data => {
          if (!isSameCoordinate(data, item)) {
            setAnalystPanelStatus(
              `Workflow input copied.<br>` +
              `Radius: <strong>${radius} m</strong><br>` +
              `<a href="${workflowUrl}" target="_blank" rel="noopener noreferrer" style="color:#facc15;">Open Coordinate Intelligence workflow</a><br><br>` +
              `Latest result exists, but it belongs to a different coordinate. Run the workflow with the copied input, then click Run Analysis again.`
            );
            return;
          }

          const analysis = renderLatestIntelligenceResult(data, item);
          item.analysisSummary = analysis;
          item.updatedAt = nowIso();
          save();

          const marker = rendered.get(item.id);
          if (marker) {
            marker.setIcon(createObjectIcon(item));
            marker.bindPopup(createPopupHtml(item));
            marker.options.title = analysis.locationTitle || marker.options.title;
          }
        })
        .catch(() => {
          setAnalystPanelStatus(
            `Workflow input copied.<br>` +
            `Radius: <strong>${radius} m</strong><br>` +
            `<a href="${workflowUrl}" target="_blank" rel="noopener noreferrer" style="color:#facc15;">Open Coordinate Intelligence workflow</a><br><br>` +
            `Latest analysis result not available yet.`
          );
        });

      emitStatus(`Coordinate Intelligence előkészítve.<br>Lat: <strong>${formatCoord(item.lat)}</strong><br>Lon: <strong>${formatCoord(item.lng)}</strong><br>Radius: <strong>${radius} m</strong>`);
    }
  }

  map.on('click', handleMapClick);
  document.addEventListener('click', handlePopupClick);
  document.addEventListener('click', handleAnalystPanelClick);

  restoreObjects();

  return {
    enable() {
      isEnabled = true;
      emitStatus('Objektumazonosítás aktív. Válassz objektumtípust, majd kattints a térképre.');
    },
    disable() { isEnabled = false; },
    toggle(value) { if (value) this.enable(); else this.disable(); },
    isEnabled() { return isEnabled; },
    addObject,
    removeObject,
    clearObjects,
    getObjects,
    exportJson() { return exportJson(objects); },
    exportGeoJson() { return exportGeoJson(objects); },
    destroy() {
      map.off('click', handleMapClick);
      document.removeEventListener('click', handlePopupClick);
      document.removeEventListener('click', handleAnalystPanelClick);
      removeExistingAnalystPanel();
      layerGroup.clearLayers();
      rendered.clear();
    },
  };
}
