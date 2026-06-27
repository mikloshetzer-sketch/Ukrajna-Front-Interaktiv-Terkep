const STORAGE_KEY = 'ukraine_front_measurements_v2';

function nowIso() {
  return new Date().toISOString();
}

function formatCoord(value) {
  return Number(value).toFixed(6);
}

function formatDistanceKm(value) {
  return `${Number(value).toFixed(2)} km`;
}

function formatBearing(value) {
  return `${Math.round(Number(value))}°`;
}

function makeMeasurementId() {
  return `measure_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function toRadians(degrees) {
  return Number(degrees) * Math.PI / 180;
}

function toDegrees(radians) {
  return Number(radians) * 180 / Math.PI;
}

function haversineDistanceKm(a, b) {
  const earthRadiusKm = 6371.0088;

  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);

  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);

  const h =
    sinLat * sinLat +
    Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;

  return 2 * earthRadiusKm * Math.asin(Math.min(1, Math.sqrt(h)));
}

function bearingDegrees(a, b) {
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const dLng = toRadians(b.lng - a.lng);

  const y = Math.sin(dLng) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);

  return (toDegrees(Math.atan2(y, x)) + 360) % 360;
}

function midpoint(a, b) {
  return {
    lat: (Number(a.lat) + Number(b.lat)) / 2,
    lng: (Number(a.lng) + Number(b.lng)) / 2,
  };
}

function normalizePoint(point) {
  return {
    lat: Number(point.lat),
    lng: Number(point.lng),
  };
}

function readStoredMeasurements() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(item =>
      Number.isFinite(Number(item?.start?.lat)) &&
      Number.isFinite(Number(item?.start?.lng)) &&
      Number.isFinite(Number(item?.end?.lat)) &&
      Number.isFinite(Number(item?.end?.lng))
    );
  } catch (error) {
    console.warn('Measurement storage read error:', error);
    return [];
  }
}

function writeStoredMeasurements(measurements) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(measurements));
  } catch (error) {
    console.warn('Measurement storage write error:', error);
  }
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
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

function createPopupHtml(measurement) {
  const start = measurement.start;
  const end = measurement.end;
  const distance = formatDistanceKm(measurement.distanceKm);
  const bearing = formatBearing(measurement.bearingDeg);

  return `
    <div style="min-width:240px;">
      <div style="font-weight:700; margin-bottom:6px;">📏 Distance measurement</div>

      <div><b>Distance:</b> ${distance}</div>
      <div><b>Bearing:</b> ${bearing}</div>

      <hr style="margin:6px 0;">

      <div style="font-size:12px;">
        <b>Start:</b><br>
        ${formatCoord(start.lat)}, ${formatCoord(start.lng)}
      </div>

      <div style="font-size:12px; margin-top:4px;">
        <b>End:</b><br>
        ${formatCoord(end.lat)}, ${formatCoord(end.lng)}
      </div>

      <hr style="margin:6px 0;">

      <button
        type="button"
        data-measure-action="copy"
        data-measure-id="${escapeHtml(measurement.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Copy measurement
      </button>

      <button
        type="button"
        data-measure-action="delete"
        data-measure-id="${escapeHtml(measurement.id)}"
        style="width:100%;"
      >
        Delete measurement
      </button>

      <div style="font-size:11px; color:#777; margin-top:6px;">
        A mérési címke egérrel húzható, hogy ne takarja az objektumot.
      </div>
    </div>
  `;
}

function buildMeasurement(start, end) {
  const normalizedStart = normalizePoint(start);
  const normalizedEnd = normalizePoint(end);
  const distanceKm = haversineDistanceKm(normalizedStart, normalizedEnd);
  const bearingDeg = bearingDegrees(normalizedStart, normalizedEnd);
  const mid = midpoint(normalizedStart, normalizedEnd);

  return {
    id: makeMeasurementId(),
    createdAt: nowIso(),
    updatedAt: nowIso(),
    start: normalizedStart,
    end: normalizedEnd,
    labelPosition: mid,
    distanceKm,
    bearingDeg,
  };
}

function createLabelIcon(measurement) {
  return L.divIcon({
    className: 'measurement-label',
    html: `
      <div style="
        background: rgba(17, 24, 39, 0.92);
        color: #fff;
        padding: 5px 8px;
        border-radius: 7px;
        border: 1px solid rgba(250, 204, 21, 0.9);
        font-size: 12px;
        white-space: nowrap;
        box-shadow: 0 2px 8px rgba(0,0,0,0.28);
        cursor: move;
        user-select: none;
      ">
        📏 ${formatDistanceKm(measurement.distanceKm)} · ${formatBearing(measurement.bearingDeg)}
      </div>
    `,
    iconSize: [1, 1],
    iconAnchor: [0, 0],
  });
}

export function initMeasureTool({ map, layerGroup, enabled = false, onStatusChange = null } = {}) {
  if (!map || !layerGroup) {
    throw new Error('initMeasureTool requires map and layerGroup');
  }

  let isEnabled = Boolean(enabled);
  let pendingStart = null;
  let measurements = readStoredMeasurements();
  const rendered = new Map();

  function emitStatus(text) {
    if (typeof onStatusChange === 'function') {
      onStatusChange(text);
    }
  }

  function save() {
    writeStoredMeasurements(measurements);
  }

  function findMeasurement(id) {
    return measurements.find(item => item.id === id);
  }

  function ensureLabelPosition(measurement) {
    if (
      !measurement.labelPosition ||
      !Number.isFinite(Number(measurement.labelPosition.lat)) ||
      !Number.isFinite(Number(measurement.labelPosition.lng))
    ) {
      measurement.labelPosition = midpoint(measurement.start, measurement.end);
    }

    measurement.labelPosition = normalizePoint(measurement.labelPosition);
  }

  function updateMeasurementLabelPosition(id, latlng) {
    const measurement = findMeasurement(id);
    if (!measurement) return;

    measurement.labelPosition = normalizePoint(latlng);
    measurement.updatedAt = nowIso();
    save();

    const item = rendered.get(id);
    if (!item) return;

    const mid = midpoint(measurement.start, measurement.end);
    item.connector.setLatLngs([
      [mid.lat, mid.lng],
      [measurement.labelPosition.lat, measurement.labelPosition.lng],
    ]);

    item.label.bindPopup(createPopupHtml(measurement));
    item.line.bindPopup(createPopupHtml(measurement));
    item.connector.bindPopup(createPopupHtml(measurement));
  }

  function renderMeasurement(measurement, shouldOpen = false) {
    ensureLabelPosition(measurement);

    const line = L.polyline(
      [
        [measurement.start.lat, measurement.start.lng],
        [measurement.end.lat, measurement.end.lng],
      ],
      {
        color: '#facc15',
        weight: 3,
        opacity: 0.95,
        dashArray: '8 6',
      }
    );

    const mid = midpoint(measurement.start, measurement.end);

    const connector = L.polyline(
      [
        [mid.lat, mid.lng],
        [measurement.labelPosition.lat, measurement.labelPosition.lng],
      ],
      {
        color: '#facc15',
        weight: 1.5,
        opacity: 0.55,
        dashArray: '3 5',
      }
    );

    const label = L.marker([measurement.labelPosition.lat, measurement.labelPosition.lng], {
      draggable: true,
      interactive: true,
      icon: createLabelIcon(measurement),
      title: 'Measurement label',
      zIndexOffset: 900,
    });

    label.bindPopup(createPopupHtml(measurement));
    line.bindPopup(createPopupHtml(measurement));
    connector.bindPopup(createPopupHtml(measurement));

    label.on('dragend', () => {
      updateMeasurementLabelPosition(measurement.id, label.getLatLng());
      emitStatus(`Mérési címke áthelyezve: ${formatDistanceKm(measurement.distanceKm)} · ${formatBearing(measurement.bearingDeg)}.`);
    });

    line.addTo(layerGroup);
    connector.addTo(layerGroup);
    label.addTo(layerGroup);

    rendered.set(measurement.id, { line, connector, label });

    if (shouldOpen) {
      label.openPopup();
    }
  }

  function restoreMeasurements() {
    layerGroup.clearLayers();
    rendered.clear();

    measurements = readStoredMeasurements();

    measurements.forEach(item => {
      renderMeasurement(item, false);
    });
  }

  function addMeasurement(start, end, shouldOpen = true) {
    const measurement = buildMeasurement(start, end);
    measurements.push(measurement);
    save();
    renderMeasurement(measurement, shouldOpen);
    return measurement;
  }

  function removeMeasurement(id) {
    const item = rendered.get(id);

    if (item) {
      layerGroup.removeLayer(item.line);
      layerGroup.removeLayer(item.connector);
      layerGroup.removeLayer(item.label);
      rendered.delete(id);
    }

    measurements = measurements.filter(measurement => measurement.id !== id);
    save();
  }

  function clearMeasurements() {
    layerGroup.clearLayers();
    rendered.clear();
    measurements = [];
    pendingStart = null;
    save();
    emitStatus('Távolságmérések törölve.');
  }

  function getMeasurements() {
    return measurements.map(item => ({ ...item }));
  }

  function shouldIgnoreClick(event) {
    const target = event.originalEvent?.target;

    if (!target) return false;

    const tagName = String(target.tagName || '').toLowerCase();

    if (['button', 'input', 'select', 'textarea', 'a'].includes(tagName)) {
      return true;
    }

    if (target.closest?.('.leaflet-popup')) return true;
    if (target.closest?.('.leaflet-control')) return true;
    if (target.closest?.('#sidebar')) return true;
    if (target.closest?.('.measurement-label')) return true;

    return false;
  }

  function handleMapClick(event) {
    if (!isEnabled) return;
    if (!event?.latlng) return;
    if (shouldIgnoreClick(event)) return;

    const point = {
      lat: Number(event.latlng.lat),
      lng: Number(event.latlng.lng),
    };

    if (!pendingStart) {
      pendingStart = point;
      emitStatus(`Távolságmérés: kezdőpont rögzítve (${formatCoord(point.lat)}, ${formatCoord(point.lng)}). Válaszd ki a végpontot.`);
      return;
    }

    const measurement = addMeasurement(pendingStart, point, true);
    pendingStart = null;

    emitStatus(
      `Távolság: ${formatDistanceKm(measurement.distanceKm)} · irány: ${formatBearing(measurement.bearingDeg)}. A címke egérrel mozgatható.`
    );
  }

  function handlePopupClick(event) {
    const target = event.target;
    if (!target?.dataset) return;

    const action = target.dataset.measureAction;
    const id = target.dataset.measureId;

    if (!action || !id) return;

    const measurement = findMeasurement(id);
    if (!measurement) return;

    if (action === 'copy') {
      copyText(
        `Distance: ${formatDistanceKm(measurement.distanceKm)}\n` +
        `Bearing: ${formatBearing(measurement.bearingDeg)}\n` +
        `Start: ${formatCoord(measurement.start.lat)}, ${formatCoord(measurement.start.lng)}\n` +
        `End: ${formatCoord(measurement.end.lat)}, ${formatCoord(measurement.end.lng)}`
      );

      target.textContent = 'Copied';
      setTimeout(() => {
        target.textContent = 'Copy measurement';
      }, 1200);
      return;
    }

    if (action === 'delete') {
      removeMeasurement(id);
      emitStatus('Távolságmérés törölve.');
    }
  }

  map.on('click', handleMapClick);
  document.addEventListener('click', handlePopupClick);

  restoreMeasurements();

  return {
    enable() {
      isEnabled = true;
      pendingStart = null;
      emitStatus('Távolságmérés aktív. Kattints a kezdőpontra, majd a végpontra.');
    },

    disable() {
      isEnabled = false;
      pendingStart = null;
    },

    toggle(value) {
      if (value) this.enable();
      else this.disable();
    },

    isEnabled() {
      return isEnabled;
    },

    clearMeasurements,

    getMeasurements,

    destroy() {
      map.off('click', handleMapClick);
      document.removeEventListener('click', handlePopupClick);
      layerGroup.clearLayers();
      rendered.clear();
    },
  };
}
