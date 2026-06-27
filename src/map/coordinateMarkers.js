const STORAGE_KEY = 'ukraine_front_coordinate_markers_v2';

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
    item.updatedAt = new Date().toISOString();

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
      createdAt: data.createdAt || new Date().toISOString(),
      updatedAt: data.updatedAt || new Date().toISOString(),
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

    clearMarkers() {
      markerMap.forEach(marker => layerGroup.removeLayer(marker));
      markerMap.clear();
      markerData = [];
      save();
    },

    getMarkers() {
      return markerData.map(item => ({ ...item }));
    },

    destroy() {
      map.off('click', handleMapClick);
      document.removeEventListener('click', handlePopupClick);
      layerGroup.clearLayers();
      markerMap.clear();
    },
  };
}
