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

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
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
    <div style="min-width:245px;">
      <div style="font-weight:800; margin-bottom:6px;">Distance measurement</div>

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
        The label can be dragged away from the measured line.
      </div>
    </div>
  `;
}

function buildMeasurement(start, end) {
  const distanceKm = haversineDistanceKm(start, end);
  const bearingDeg = bearingDegrees(start, end);
  const mid = midpoint(start, end);

  return {
    id: makeMeasurementId(),
    createdAt: nowIso(),
    updatedAt: nowIso(),
    start: {
      lat: Number(start.lat),
      lng: Number(start.lng),
    },
    end: {
      lat: Number(end.lat),
      lng: Number(end.lng),
    },
    label: {
      lat: Number(mid.lat),
      lng: Number(mid.lng),
    },
    distanceKm,
    bearingDeg,
  };
}

function normalizeMeasurement(item) {
  const start = {
    lat: Number(item.start.lat),
    lng: Number(item.start.lng),
  };

  const end = {
    lat: Number(item.end.lat),
    lng: Number(item.end.lng),
  };

  const mid = midpoint(start, end);

  return {
    ...item,
    start,
    end,
    label: {
      lat: Number(item?.label?.lat ?? mid.lat),
      lng: Number(item?.label?.lng ?? mid.lng),
    },
    distanceKm: Number(item.distanceKm ?? haversineDistanceKm(start, end)),
    bearingDeg: Number(item.bearingDeg ?? bearingDegrees(start, end)),
  };
}

function createEndpointIcon(number) {
  return L.divIcon({
    className: 'measurement-endpoint-icon',
    html: `
      <div style="
        width: 28px;
        height: 28px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.92);
        border: 2px solid rgba(250, 204, 21, 0.95);
        box-shadow:
          0 0 0 2px rgba(15, 23, 42, 0.65),
          0 3px 12px rgba(0,0,0,0.35);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #f8fafc;
        font-weight: 800;
        font-size: 12px;
        line-height: 1;
      ">
        ${number}
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function createLabelIcon(measurement) {
  const distance = formatDistanceKm(measurement.distanceKm);
  const bearing = formatBearing(measurement.bearingDeg);

  return L.divIcon({
    className: 'measurement-analyst-label',
    html: `
      <div style="
        min-width: 94px;
        background: rgba(15, 23, 42, 0.91);
        color: #f8fafc;
        border: 1px solid rgba(250, 204, 21, 0.72);
        border-left: 4px solid rgba(250, 204, 21, 0.96);
        border-radius: 7px;
        padding: 5px 8px;
        box-shadow:
          0 6px 18px rgba(0,0,0,0.35),
          0 0 0 1px rgba(255,255,255,0.06);
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        text-align: left;
        user-select: none;
        cursor: move;
      ">
        <div style="
          font-size: 9px;
          line-height: 1;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: rgba(203, 213, 225, 0.92);
          margin-bottom: 3px;
          font-weight: 700;
        ">
          DIST
        </div>
        <div style="
          font-size: 13px;
          line-height: 1.1;
          font-weight: 800;
          white-space: nowrap;
        ">
          ${distance}
        </div>
        <div style="
          font-size: 11px;
          line-height: 1.15;
          color: rgba(250, 204, 21, 0.96);
          margin-top: 2px;
          white-space: nowrap;
          font-weight: 700;
        ">
          BRG ${bearing}
        </div>
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
  let pendingStartMarker = null;
  let measurements = readStoredMeasurements().map(normalizeMeasurement);
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

  function getAnchorLatLng(measurement) {
    const mid = midpoint(measurement.start, measurement.end);
    return [mid.lat, mid.lng];
  }

  function getLabelLatLng(measurement) {
    const label = measurement.label || midpoint(measurement.start, measurement.end);
    return [Number(label.lat), Number(label.lng)];
  }

  function removePendingStartMarker() {
    if (pendingStartMarker) {
      layerGroup.removeLayer(pendingStartMarker);
      pendingStartMarker = null;
    }
  }

  function updateConnector(id) {
    const measurement = findMeasurement(id);
    const item = rendered.get(id);
    if (!measurement || !item?.connector) return;

    item.connector.setLatLngs([
      getAnchorLatLng(measurement),
      getLabelLatLng(measurement),
    ]);
  }

  function renderMeasurement(measurement, shouldOpen = false) {
    const normalized = normalizeMeasurement(measurement);
    const anchor = getAnchorLatLng(normalized);
    const labelPosition = getLabelLatLng(normalized);

    const line = L.polyline(
      [
        [normalized.start.lat, normalized.start.lng],
        [normalized.end.lat, normalized.end.lng],
      ],
      {
        color: '#facc15',
        weight: 3,
        opacity: 0.92,
        dashArray: '8 6',
        lineCap: 'round',
        lineJoin: 'round',
      }
    );

    const shadowLine = L.polyline(
      [
        [normalized.start.lat, normalized.start.lng],
        [normalized.end.lat, normalized.end.lng],
      ],
      {
        color: '#020617',
        weight: 6,
        opacity: 0.34,
        dashArray: '8 6',
        lineCap: 'round',
        lineJoin: 'round',
      }
    );

    const connector = L.polyline(
      [
        anchor,
        labelPosition,
      ],
      {
        color: '#e5e7eb',
        weight: 1.4,
        opacity: 0.52,
        dashArray: '3 5',
        lineCap: 'round',
      }
    );

    const startMarker = L.marker([normalized.start.lat, normalized.start.lng], {
      interactive: true,
      icon: createEndpointIcon(1),
      title: 'Measurement start point',
    });

    const endMarker = L.marker([normalized.end.lat, normalized.end.lng], {
      interactive: true,
      icon: createEndpointIcon(2),
      title: 'Measurement end point',
    });

    const label = L.marker(labelPosition, {
      draggable: true,
      interactive: true,
      icon: createLabelIcon(normalized),
      title: 'Distance measurement label',
    });

    const popupHtml = createPopupHtml(normalized);

    label.bindPopup(popupHtml);
    line.bindPopup(popupHtml);
    startMarker.bindPopup(popupHtml);
    endMarker.bindPopup(popupHtml);

    shadowLine.addTo(layerGroup);
    line.addTo(layerGroup);
    connector.addTo(layerGroup);
    startMarker.addTo(layerGroup);
    endMarker.addTo(layerGroup);
    label.addTo(layerGroup);

    label.on('drag', () => {
      const item = findMeasurement(normalized.id);
      if (!item) return;

      const latlng = label.getLatLng();
      item.label = {
        lat: Number(latlng.lat),
        lng: Number(latlng.lng),
      };

      updateConnector(normalized.id);
    });

    label.on('dragend', () => {
      const item = findMeasurement(normalized.id);
      if (!item) return;

      const latlng = label.getLatLng();
      item.label = {
        lat: Number(latlng.lat),
        lng: Number(latlng.lng),
      };
      item.updatedAt = nowIso();

      updateConnector(normalized.id);
      save();
    });

    rendered.set(normalized.id, {
      shadowLine,
      line,
      connector,
      startMarker,
      endMarker,
      label,
    });

    if (shouldOpen) {
      label.openPopup();
    }
  }

  function restoreMeasurements() {
    layerGroup.clearLayers();
    rendered.clear();
    removePendingStartMarker();

    measurements = readStoredMeasurements().map(normalizeMeasurement);

    measurements.forEach(item => {
      renderMeasurement(item, false);
    });
  }

  function addMeasurement(start, end, shouldOpen = true) {
    const measurement = buildMeasurement(start, end);
    measurements.push(measurement);
    save();
    removePendingStartMarker();
    renderMeasurement(measurement, shouldOpen);
    return measurement;
  }

  function removeMeasurement(id) {
    const item = rendered.get(id);

    if (item) {
      layerGroup.removeLayer(item.shadowLine);
      layerGroup.removeLayer(item.line);
      layerGroup.removeLayer(item.connector);
      layerGroup.removeLayer(item.startMarker);
      layerGroup.removeLayer(item.endMarker);
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
    pendingStartMarker = null;
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
    if (target.closest?.('.measurement-analyst-label')) return true;
    if (target.closest?.('.measurement-endpoint-icon')) return true;

    return false;
  }

  function renderPendingStartMarker(point) {
    removePendingStartMarker();

    pendingStartMarker = L.marker([point.lat, point.lng], {
      interactive: false,
      icon: L.divIcon({
        className: 'measurement-pending-start',
        html: `
          <div style="
            width: 30px;
            height: 30px;
            border-radius: 999px;
            background: rgba(250, 204, 21, 0.22);
            border: 2px solid rgba(250, 204, 21, 0.96);
            box-shadow:
              0 0 0 4px rgba(15, 23, 42, 0.62),
              0 0 16px rgba(250, 204, 21, 0.42);
            display:flex;
            align-items:center;
            justify-content:center;
            color:#f8fafc;
            font-weight:800;
            font-size:12px;
          ">
            1
          </div>
        `,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      }),
    });

    pendingStartMarker.addTo(layerGroup);
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
      renderPendingStartMarker(point);
      emitStatus(`Távolságmérés: kezdőpont rögzítve (${formatCoord(point.lat)}, ${formatCoord(point.lng)}). Válaszd ki a végpontot.`);
      return;
    }

    const measurement = addMeasurement(pendingStart, point, true);
    pendingStart = null;

    emitStatus(
      `Távolság: ${formatDistanceKm(measurement.distanceKm)} · irány: ${formatBearing(measurement.bearingDeg)}.`
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
      removePendingStartMarker();
      emitStatus('Távolságmérés aktív. Kattints a kezdőpontra, majd a végpontra.');
    },

    disable() {
      isEnabled = false;
      pendingStart = null;
      removePendingStartMarker();
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
      pendingStartMarker = null;
    },
  };
}
