const STORAGE_KEY = 'ukraine_front_coordinate_markers_v3';

function formatCoord(value) {
  return Number(value).toFixed(6);
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function makeMarkerId() {
  return `coord_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function readStoredMarkers() {
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
    console.warn('Coordinate marker storage read error:', error);
    return [];
  }
}

function writeStoredMarkers(markers) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(markers));
  } catch (error) {
    console.warn('Coordinate marker storage write error:', error);
  }
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

function markerToGeoJsonFeature(marker) {
  return {
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [Number(marker.lng), Number(marker.lat)],
    },
    properties: {
      id: marker.id,
      source: 'manual_coordinate_marker',
      createdAt: marker.createdAt || null,
      updatedAt: marker.updatedAt || null,
      wgs84: `${formatCoord(marker.lat)}, ${formatCoord(marker.lng)}`,
    },
  };
}

function createPopupHtml(markerData) {
  const lat = formatCoord(markerData.lat);
  const lng = formatCoord(markerData.lng);
  const coordText = `${lat}, ${lng}`;

  return `
    <div style="min-width:220px;">
      <div style="font-weight:700; margin-bottom:6px;">📍 Coordinate marker</div>

      <div><b>Latitude:</b> ${lat}</div>
      <div><b>Longitude:</b> ${lng}</div>

      <hr style="margin:6px 0;">

      <div style="font-size:12px; color:#555; margin-bottom:6px;">
        WGS84: <code>${coordText}</code>
      </div>

      <button
        type="button"
        data-coord-action="copy"
        data-coord-id="${escapeHtml(markerData.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Copy WGS84
      </button>

      <button
        type="button"
        data-coord-action="export-json"
        data-coord-id="${escapeHtml(markerData.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Export this marker JSON
      </button>

      <button
        type="button"
        data-coord-action="export-geojson"
        data-coord-id="${escapeHtml(markerData.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Export this marker GeoJSON
      </button>

      <button
        type="button"
        data-coord-action="delete"
        data-coord-id="${escapeHtml(markerData.id)}"
        style="width:100%;"
      >
        Delete marker
      </button>

      <div style="font-size:11px; color:#777; margin-top:6px;">
        Drag the marker to refine the location.
      </div>
    </div>
  `;
}

export function initCoordinateMarkers({ map, layerGroup, enabled = true } = {}) {
  if (!map || !layerGroup) {
    throw new Error('initCoordinateMarkers requires map and layerGroup');
  }

  let isEnabled = Boolean(enabled);
  const markerMap = new Map();
  let markerData = readStoredMarkers();

  function save() {
    writeStoredMarkers(markerData);
  }

  function findData(id) {
    return markerData.find(item => item.id === id);
  }

  function getMarkers() {
    return markerData.map(item => ({ ...item }));
  }

  function exportJson(targetMarkers = markerData, filename = null) {
    const payload = {
      generatedAt: nowIso(),
      source: 'ukraine_front_interactive_map',
      type: 'manual_coordinate_markers',
      count: targetMarkers.length,
      markers: targetMarkers.map(item => ({ ...item })),
    };

    const safeFilename = filename || `coordinate_markers_${new Date().toISOString().slice(0, 10)}.json`;
    downloadTextFile(safeFilename, JSON.stringify(payload, null, 2), 'application/json');

    return payload;
  }

  function exportGeoJson(targetMarkers = markerData, filename = null) {
    const payload = {
      type: 'FeatureCollection',
      generatedAt: nowIso(),
      source: 'ukraine_front_interactive_map',
      features: targetMarkers.map(markerToGeoJsonFeature),
    };

    const safeFilename = filename || `coordinate_markers_${new Date().toISOString().slice(0, 10)}.geojson`;
    downloadTextFile(safeFilename, JSON.stringify(payload, null, 2), 'application/geo+json');

    return payload;
  }

  function removeMarker(id) {
    const marker = markerMap.get(id);

    if (marker) {
      layerGroup.removeLayer(marker);
      markerMap.delete(id);
    }

    markerData = markerData.filter(item => item.id !== id);
    save();
  }

  function updateMarkerPosition(id, latlng) {
    const item = findData(id);
    if (!item) return;

    item.lat = Number(latlng.lat);
    item.lng = Number(latlng.lng);
    item.updatedAt = nowIso();

    const marker = markerMap.get(id);
    if (marker) {
      marker.bindPopup(createPopupHtml(item));
    }

    save();
  }

  function addMarker(data, shouldOpen = true) {
    const normalized = {
      id: data.id || makeMarkerId(),
      lat: Number(data.lat),
      lng: Number(data.lng),
      createdAt: data.createdAt || nowIso(),
      updatedAt: data.updatedAt || nowIso(),
    };

    if (!Number.isFinite(normalized.lat) || !Number.isFinite(normalized.lng)) {
      return null;
    }

    const marker = L.marker([normalized.lat, normalized.lng], {
      draggable: true,
      title: 'Coordinate marker',
    });

    marker.bindPopup(createPopupHtml(normalized));

    marker.on('dragend', () => {
      updateMarkerPosition(normalized.id, marker.getLatLng());
    });

    marker.addTo(layerGroup);
    markerMap.set(normalized.id, marker);

    const existingIndex = markerData.findIndex(item => item.id === normalized.id);
    if (existingIndex >= 0) {
      markerData[existingIndex] = normalized;
    } else {
      markerData.push(normalized);
    }

    save();

    if (shouldOpen) {
      marker.openPopup();
    }

    return marker;
  }

  function restoreMarkers() {
    layerGroup.clearLayers();
    markerMap.clear();

    markerData = readStoredMarkers();

    markerData.forEach(item => {
      addMarker(item, false);
    });
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

    return false;
  }

  function handleMapClick(event) {
    if (!isEnabled) return;
    if (!event?.latlng) return;
    if (shouldIgnoreClick(event)) return;

    addMarker({
      lat: event.latlng.lat,
      lng: event.latlng.lng,
    }, true);
  }

  function handlePopupClick(event) {
    const target = event.target;
    if (!target?.dataset) return;

    const action = target.dataset.coordAction;
    const id = target.dataset.coordId;

    if (!action || !id) return;

    const item = findData(id);
    if (!item) return;

    if (action === 'copy') {
      copyText(`${formatCoord(item.lat)}, ${formatCoord(item.lng)}`);
      target.textContent = 'Copied';
      setTimeout(() => {
        target.textContent = 'Copy WGS84';
      }, 1200);
      return;
    }

    if (action === 'export-json') {
      exportJson([item], `coordinate_marker_${item.id}.json`);
      return;
    }

    if (action === 'export-geojson') {
      exportGeoJson([item], `coordinate_marker_${item.id}.geojson`);
      return;
    }

    if (action === 'delete') {
      removeMarker(id);
    }
  }

  map.on('click', handleMapClick);
  document.addEventListener('click', handlePopupClick);

  restoreMarkers();

  return {
    enable() {
      isEnabled = true;
    },

    disable() {
      isEnabled = false;
    },

    toggle(value) {
      isEnabled = Boolean(value);
    },

    isEnabled() {
      return isEnabled;
    },

    addMarker,

    removeMarker,

    clearMarkers() {
      markerMap.forEach(marker => layerGroup.removeLayer(marker));
      markerMap.clear();
      markerData = [];
      save();
    },

    getMarkers,

    exportJson() {
      return exportJson(markerData);
    },

    exportGeoJson() {
      return exportGeoJson(markerData);
    },

    destroy() {
      map.off('click', handleMapClick);
      document.removeEventListener('click', handlePopupClick);
      layerGroup.clearLayers();
      markerMap.clear();
    },
  };
}
