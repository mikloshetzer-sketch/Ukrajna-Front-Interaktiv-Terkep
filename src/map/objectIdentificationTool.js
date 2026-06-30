const STORAGE_KEY = 'ukraine_front_identified_objects_v1';

const SELECTION_MARKER = {
  label: 'Selected coordinate',
  shortLabel: 'POINT',
  category: 'Coordinate',
  icon: '📍',
  color: '#6b7280',
};

function nowIso() {
  return new Date().toISOString();
}

function formatCoord(value) {
  return Number(value).toFixed(6);
}

function makeObjectId() {
  return `object_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

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

    return parsed.filter(item =>
      Number.isFinite(Number(item.lat)) &&
      Number.isFinite(Number(item.lng))
    );
  } catch (error) {
    console.warn('Object identification storage read error:', error);
    return [];
  }
}

function writeStoredObjects(objects) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(objects));
  } catch (error) {
    console.warn('Object identification storage write error:', error);
  }
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

  try {
    document.execCommand('copy');
  } catch (error) {
    console.warn('Clipboard fallback failed:', error);
  }

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

function getSelectedAnalysisRadius() {
  const selected = document.querySelector('input[name="ciRadius"]:checked');
  return Number(selected?.value || 750);
}

async function loadLatestIntelligenceResult() {
  const response = await fetch('data/intelligence/latest.json?_=' + Date.now(), { cache: 'no-store' });
  if (!response.ok) throw new Error('latest.json not available');
  return await response.json();
}

function isSameCoordinate(data, objectItem) {
  const dataLat = Number(data?.coordinate?.lat);
  const dataLon = Number(data?.coordinate?.lon);
  const itemLat = Number(objectItem?.lat);
  const itemLon = Number(objectItem?.lng);

  if (!Number.isFinite(dataLat) || !Number.isFinite(dataLon)) return false;
  if (!Number.isFinite(itemLat) || !Number.isFinite(itemLon)) return false;

  return (
    Math.abs(dataLat - itemLat) < 0.00015 &&
    Math.abs(dataLon - itemLon) < 0.00015
  );
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

function featureCountsHtml(summary) {
  const counts = summary?.feature_counts || {};
  const entries = Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 7);

  if (!entries.length) return 'No infrastructure counts available.';

  return entries
    .map(([key, value]) => `${escapeHtml(normalizeFeatureLabel(key))}: <strong>${escapeHtml(value)}</strong>`)
    .join('<br>');
}

function buildAnalysisSummary(data) {
  const summary = data?.summary || {};
  const location = data?.location || {};
  const wikidata = data?.wikidata || {};
  const nearest = wikidata.nearest || {};

  const locationTitle =
    location.city ||
    summary.nearest_city ||
    location.locality ||
    summary.nearest_locality ||
    location.nearest_named_place ||
    summary.nearest_named_place ||
    'Location context unavailable';

  const locationSubtitle = [
    location.region || summary.region,
    location.country || summary.country,
  ].filter(Boolean).join(' · ');

  const detectedObject =
    nearest.name ||
    summary.nearest_wikidata ||
    summary.nearest_named_place ||
    location.nearest_named_place ||
    'No named object identified';

  const detectedObjectType =
    nearest.type ||
    summary.primary_object ||
    'Mapped / inferred object';

  const functionalAssessment =
    summary.likely_object ||
    data?.fusion_profile?.type ||
    summary.operational_environment ||
    '-';

  return {
    generatedAt: data?.generated_at || null,
    locationTitle,
    locationSubtitle,
    detectedObject,
    detectedObjectType,
    functionalAssessment,
    confidence: summary.confidence || data?.fusion_profile?.confidence || '-',
    primaryObject: summary.primary_object || '-',
    primaryConfidence: summary.primary_confidence || '-',
    operationalEnvironment: summary.operational_environment || '-',
    environmentConfidence: summary.environment_confidence || '-',
    nearestRoad: summary.nearest_road || location.road || '-',
    nearestNamedPlace: summary.nearest_named_place || location.nearest_named_place || '-',
    nearestWikidata: summary.nearest_wikidata || nearest.name || '-',
    railwayConfidence: summary.railway_confidence || '-',
    maritimeConfidence: summary.maritime_confidence || '-',
    featureCounts: summary.feature_counts || {},
    assessment: data?.assessment || '-',
    lat: data?.coordinate?.lat,
    lon: data?.coordinate?.lon,
    raw: data,
  };
}

function createObjectIcon() {
  return L.divIcon({
    className: 'identified-object-marker',
    html: `
      <div style="
        position: relative;
        min-width: 54px;
        max-width: 92px;
        background: rgba(17, 24, 39, 0.92);
        color: #ffffff;
        border: 1px solid rgba(255,255,255,0.28);
        border-top: 4px solid ${SELECTION_MARKER.color};
        border-radius: 8px;
        padding: 5px 7px 5px 7px;
        box-shadow: 0 2px 9px rgba(0,0,0,0.28);
        font-size: 11px;
        line-height: 1.15;
        text-align: center;
        white-space: nowrap;
      ">
        <div style="font-size:14px; line-height:1;">${SELECTION_MARKER.icon}</div>
        <div style="font-weight:700; margin-top:2px;">${SELECTION_MARKER.shortLabel}</div>
      </div>
    `,
    iconSize: [1, 1],
    iconAnchor: [27, 16],
  });
}

function objectToGeoJsonFeature(objectItem) {
  return {
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [Number(objectItem.lng), Number(objectItem.lat)],
    },
    properties: {
      id: objectItem.id,
      source: 'manual_coordinate_selection',
      objectType: 'selected_coordinate',
      objectTypeLabel: SELECTION_MARKER.label,
      objectCategory: SELECTION_MARKER.category,
      createdAt: objectItem.createdAt || null,
      updatedAt: objectItem.updatedAt || null,
      analysisUpdatedAt: objectItem.analysisUpdatedAt || null,
      wgs84: `${formatCoord(objectItem.lat)}, ${formatCoord(objectItem.lng)}`,
      analysisSummary: objectItem.analysisSummary || null,
      analysisResult: objectItem.analysisResult || null,
    },
  };
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

function createPopupHtml(objectItem) {
  const lat = formatCoord(objectItem.lat);
  const lng = formatCoord(objectItem.lng);
  const coordText = `${lat}, ${lng}`;
  const hasAnalysis = Boolean(objectItem.analysisSummary);

  return `
    <div style="min-width:250px; max-width:300px;">
      <div style="font-weight:800; margin-bottom:6px; font-size:14px;">
        ${SELECTION_MARKER.icon} Selected Coordinate
      </div>

      <div style="font-size:12px; color:#555; margin-bottom:6px;">
        Manual map point. Run Coordinate Intelligence to identify the location and nearby infrastructure.
      </div>

      <hr style="margin:6px 0;">

      <div><b>Latitude:</b> ${lat}</div>
      <div><b>Longitude:</b> ${lng}</div>

      <div style="font-size:12px; color:#555; margin-top:6px;">
        WGS84: <code>${coordText}</code>
      </div>

      <div style="font-size:12px; color:#555; margin-top:6px;">
        Created: ${escapeHtml(formatDateTime(objectItem.createdAt))}
      </div>

      ${hasAnalysis ? `
        <div style="font-size:12px; color:#166534; margin-top:6px; font-weight:700;">
          Saved analysis available
        </div>
      ` : ''}

      <hr style="margin:6px 0;">

      <button type="button" data-object-action="copy" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%; margin-bottom:4px;">
        Copy coordinate
      </button>

      <button type="button" data-object-action="export-json" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%; margin-bottom:4px;">
        Export JSON
      </button>

      <button type="button" data-object-action="export-geojson" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%; margin-bottom:4px;">
        Export GeoJSON
      </button>

      <button
        type="button"
        data-object-action="analyze"
        data-object-id="${escapeHtml(objectItem.id)}"
        style="
          width:100%;
          margin-bottom:4px;
          background:#111827;
          color:#ffffff;
          border:1px solid rgba(250, 204, 21, 0.75);
          border-radius:4px;
          padding:5px 8px;
          font-weight:700;
          cursor:pointer;
        "
      >
        ${hasAnalysis ? 'Open saved analysis' : 'Analyze Coordinate'}
      </button>

      <button type="button" data-object-action="delete" data-object-id="${escapeHtml(objectItem.id)}" style="width:100%;">
        Delete coordinate
      </button>

      <div style="font-size:11px; color:#777; margin-top:6px;">
        Drag the marker to refine the coordinate. Moving it clears the saved analysis.
      </div>
    </div>
  `;
}

function renderAnalysisStatusHtml(analysis) {
  return `
    <strong>Analysis completed</strong><br>
    <span style="color:#94a3b8;">${escapeHtml(formatDateTime(analysis.generatedAt))}</span><br><br>

    <strong>Location</strong><br>
    ${escapeHtml(analysis.locationTitle || '-')}<br>
    ${escapeHtml(analysis.locationSubtitle || '-')}<br><br>

    <strong>Nearest mapped object</strong><br>
    ${escapeHtml(analysis.detectedObject || '-')}<br>
    <span style="color:#94a3b8;">${escapeHtml(analysis.detectedObjectType || '')}</span><br><br>

    <strong>Functional assessment</strong><br>
    <span style="color:#facc15; font-weight:800;">${escapeHtml(analysis.functionalAssessment || '-')}</span><br>
    Confidence: <strong>${escapeHtml(analysis.confidence || '-')}</strong><br><br>

    <strong>Operational environment</strong><br>
    ${escapeHtml(analysis.operationalEnvironment || '-')}<br>
    Confidence: <strong>${escapeHtml(analysis.environmentConfidence || '-')}</strong><br><br>

    <strong>Nearest road / place</strong><br>
    ${escapeHtml(analysis.nearestRoad || analysis.nearestNamedPlace || '-')}<br><br>

    <strong>Infrastructure counts</strong><br>
    ${featureCountsHtml({ feature_counts: analysis.featureCounts || {} })}<br><br>

    <strong>Assessment text</strong><br>
    ${escapeHtml(analysis.assessment || '-')}
  `;
}

function createAnalystPanelHtml(objectItem) {
  const lat = formatCoord(objectItem.lat);
  const lng = formatCoord(objectItem.lng);
  const analysis = objectItem.analysisSummary || null;

  return `
    <div
      id="coordinateIntelligencePanel"
      style="
        position: fixed;
        right: 24px;
        top: 86px;
        z-index: 10000;
        width: 360px;
        max-width: calc(100vw - 48px);
        background: rgba(15, 23, 42, 0.96);
        color: #f8fafc;
        border: 1px solid rgba(250, 204, 21, 0.65);
        border-left: 4px solid rgba(250, 204, 21, 0.95);
        border-radius: 10px;
        box-shadow: 0 12px 30px rgba(0,0,0,0.38);
        font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        overflow: hidden;
      "
    >
      <div
        data-ci-drag-handle="true"
        style="
          cursor: move;
          padding: 10px 12px;
          border-bottom: 1px solid rgba(148, 163, 184, 0.28);
          background: rgba(30, 41, 59, 0.92);
        "
      >
        <div style="font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:#cbd5e1; font-weight:800;">
          Coordinate Intelligence
        </div>

        <div id="ciPanelLocationTitle" style="font-size:17px; font-weight:900; margin-top:4px; line-height:1.2;">
          ${analysis ? escapeHtml(analysis.locationTitle) : 'Selected coordinate'}
        </div>

        <div id="ciPanelLocationSubtitle" style="font-size:12px; color:#cbd5e1; margin-top:3px; line-height:1.25;">
          ${analysis ? escapeHtml(analysis.locationSubtitle || '') : 'Run the workflow to identify this coordinate.'}
        </div>
      </div>

      <div style="padding:12px;">
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-bottom:10px;">
          <div>
            <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700;">Latitude</div>
            <div style="font-size:13px; font-weight:800;">${lat}</div>
          </div>
          <div>
            <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700;">Longitude</div>
            <div style="font-size:13px; font-weight:800;">${lng}</div>
          </div>
        </div>

        <div style="margin-bottom:10px;">
          <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;">
            Search radius
          </div>

          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:6px; font-size:12px;">
            <label style="display:flex; align-items:center; gap:5px;"><input type="radio" name="ciRadius" value="250"> 250 m</label>
            <label style="display:flex; align-items:center; gap:5px;"><input type="radio" name="ciRadius" value="500"> 500 m</label>
            <label style="display:flex; align-items:center; gap:5px;"><input type="radio" name="ciRadius" value="750" checked> 750 m</label>
            <label style="display:flex; align-items:center; gap:5px;"><input type="radio" name="ciRadius" value="1000"> 1000 m</label>
          </div>
        </div>

        <div
          id="coordinateIntelligenceStatus"
          style="
            background: rgba(2, 6, 23, 0.44);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 8px;
            padding: 8px;
            font-size: 12px;
            line-height: 1.35;
            color: #cbd5e1;
            margin-bottom: 10px;
            max-height: 310px;
            overflow:auto;
          "
        >
          ${analysis ? renderAnalysisStatusHtml(analysis) : 'Status: ready. This panel prepares the Coordinate Intelligence workflow input.'}
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
          <button type="button" data-ci-action="run" data-object-id="${escapeHtml(objectItem.id)}" style="background:#facc15;color:#111827;border:0;border-radius:6px;padding:7px 8px;font-weight:800;cursor:pointer;">
            Run Analysis
          </button>

          <button type="button" data-ci-action="close" style="background:rgba(148, 163, 184, 0.18);color:#f8fafc;border:1px solid rgba(148, 163, 184, 0.35);border-radius:6px;padding:7px 8px;font-weight:700;cursor:pointer;">
            Close
          </button>
        </div>
      </div>
    </div>
  `;
}

function updatePanelFromAnalysis(analysis) {
  const title = document.getElementById('ciPanelLocationTitle');
  const subtitle = document.getElementById('ciPanelLocationSubtitle');

  if (title) title.textContent = analysis.locationTitle || 'Location context unavailable';
  if (subtitle) subtitle.textContent = analysis.locationSubtitle || '';

  setAnalystPanelStatus(renderAnalysisStatusHtml(analysis));
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

  handle.addEventListener('mousedown', (event) => {
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

  document.addEventListener('mousemove', (event) => {
    if (!isDragging) return;

    const nextLeft = startLeft + event.clientX - startX;
    const nextTop = startTop + event.clientY - startY;

    panel.style.left = `${Math.max(8, nextLeft)}px`;
    panel.style.top = `${Math.max(8, nextTop)}px`;
  });

  document.addEventListener('mouseup', () => {
    isDragging = false;
  });
}

export function initObjectIdentificationTool({
  map,
  layerGroup,
  enabled = false,
  getObjectTypeValue = null,
  onStatusChange = null,
} = {}) {
  if (!map || !layerGroup) {
    throw new Error('initObjectIdentificationTool requires map and layerGroup');
  }

  let isEnabled = Boolean(enabled);
  let objects = readStoredObjects();
  const rendered = new Map();

  function emitStatus(text) {
    if (typeof onStatusChange === 'function') onStatusChange(text);
  }

  function save() {
    writeStoredObjects(objects);
  }

  function findObject(id) {
    return objects.find(item => item.id === id);
  }

  function getObjects() {
    return objects.map(item => ({ ...item }));
  }

  function exportJson(targetObjects = objects, filename = null) {
    const payload = {
      generatedAt: nowIso(),
      source: 'ukraine_front_interactive_map',
      type: 'manual_coordinate_selections',
      count: targetObjects.length,
      objects: targetObjects.map(item => ({ ...item })),
    };

    const safeFilename = filename || `identified_objects_${new Date().toISOString().slice(0, 10)}.json`;
    downloadTextFile(safeFilename, JSON.stringify(payload, null, 2), 'application/json');

    return payload;
  }

  function exportGeoJson(targetObjects = objects, filename = null) {
    const payload = {
      type: 'FeatureCollection',
      generatedAt: nowIso(),
      source: 'ukraine_front_interactive_map',
      features: targetObjects.map(objectToGeoJsonFeature),
    };

    const safeFilename = filename || `identified_objects_${new Date().toISOString().slice(0, 10)}.geojson`;
    downloadTextFile(safeFilename, JSON.stringify(payload, null, 2), 'application/geo+json');

    return payload;
  }

  function renderObject(objectItem, shouldOpen = false) {
    const marker = L.marker([objectItem.lat, objectItem.lng], {
      draggable: true,
      title: SELECTION_MARKER.label,
      icon: createObjectIcon(),
    });

    marker.bindPopup(createPopupHtml(objectItem));

    marker.on('dragend', () => {
      updateObjectPosition(objectItem.id, marker.getLatLng());
    });

    marker.addTo(layerGroup);
    rendered.set(objectItem.id, marker);

    if (shouldOpen) marker.openPopup();
  }

  function refreshRenderedObject(objectItem) {
    const marker = rendered.get(objectItem.id);
    if (!marker) return;

    marker.setIcon(createObjectIcon());
    marker.bindPopup(createPopupHtml(objectItem));
    marker.options.title = SELECTION_MARKER.label;
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
      objectType: 'selected_coordinate',
      originalObjectType: objectType || 'unknown',
      analysisSummary: null,
      analysisResult: null,
      analysisUpdatedAt: null,
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
    item.analysisResult = null;
    item.analysisUpdatedAt = null;

    const marker = rendered.get(id);
    if (marker) {
      marker.setLatLng([item.lat, item.lng]);
      refreshRenderedObject(item);
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
    emitStatus('Koordináta törölve.');
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

    emitStatus(
      `Coordinate Intelligence panel opened.<br>` +
      `Lat: <strong>${formatCoord(objectItem.lat)}</strong><br>` +
      `Lon: <strong>${formatCoord(objectItem.lng)}</strong>`
    );
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
    if (!isEnabled) return;
    if (!event?.latlng) return;
    if (shouldIgnoreClick(event)) return;

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

    if (action === 'copy') {
      copyText(
        `Selected Coordinate\n` +
        `Latitude: ${formatCoord(item.lat)}\n` +
        `Longitude: ${formatCoord(item.lng)}\n` +
        `WGS84: ${formatCoord(item.lat)}, ${formatCoord(item.lng)}\n` +
        `Created: ${item.createdAt || 'n/a'}`
      );

      target.textContent = 'Copied';
      setTimeout(() => {
        target.textContent = 'Copy coordinate';
      }, 1200);
      return;
    }

    if (action === 'export-json') {
      exportJson([item], `selected_coordinate_${item.id}.json`);
      return;
    }

    if (action === 'export-geojson') {
      exportGeoJson([item], `selected_coordinate_${item.id}.geojson`);
      return;
    }

    if (action === 'analyze') {
      openAnalystPanel(item);
      return;
    }

    if (action === 'delete') {
      removeObject(id);
    }
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

      setAnalystPanelStatus(
        `Workflow input copied.<br>` +
        `Radius: <strong>${radius} m</strong><br>` +
        `<a href="${workflowUrl}" target="_blank" rel="noopener noreferrer" style="color:#facc15;">Open Coordinate Intelligence workflow</a><br><br>` +
        `After the workflow finishes, click Run Analysis again to load the result.`
      );

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

          const analysis = buildAnalysisSummary(data);

          item.analysisSummary = analysis;
          item.analysisResult = data;
          item.analysisUpdatedAt = nowIso();
          item.updatedAt = nowIso();

          save();
          refreshRenderedObject(item);
          updatePanelFromAnalysis(analysis);

          emitStatus(
            `Coordinate Intelligence betöltve.<br>` +
            `<strong>${escapeHtml(analysis.locationTitle || '-')}</strong><br>` +
            `${escapeHtml(analysis.functionalAssessment || '-')}`
          );
        })
        .catch(() => {
          setAnalystPanelStatus(
            `Workflow input copied.<br>` +
            `Radius: <strong>${radius} m</strong><br>` +
            `<a href="${workflowUrl}" target="_blank" rel="noopener noreferrer" style="color:#facc15;">Open Coordinate Intelligence workflow</a><br><br>` +
            `Latest analysis result not available yet.`
          );
        });

      emitStatus(
        `Coordinate Intelligence előkészítve.<br>` +
        `Lat: <strong>${formatCoord(item.lat)}</strong><br>` +
        `Lon: <strong>${formatCoord(item.lng)}</strong><br>` +
        `Radius: <strong>${radius} m</strong>`
      );
    }
  }

  map.on('click', handleMapClick);
  document.addEventListener('click', handlePopupClick);
  document.addEventListener('click', handleAnalystPanelClick);

  restoreObjects();

  return {
    enable() {
      isEnabled = true;
      emitStatus('Koordinátakijelölés aktív. Kattints a térképre egy elemzendő pont rögzítéséhez.');
    },

    disable() {
      isEnabled = false;
    },

    toggle(value) {
      if (value) this.enable();
      else this.disable();
    },

    isEnabled() {
      return isEnabled;
    },

    addObject,
    removeObject,
    clearObjects,
    getObjects,

    exportJson() {
      return exportJson(objects);
    },

    exportGeoJson() {
      return exportGeoJson(objects);
    },

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
