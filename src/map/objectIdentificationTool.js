const STORAGE_KEY = 'ukraine_front_identified_objects_v1';

const OBJECT_TYPES = {
  unknown: {
    label: 'Unknown / General point',
    shortLabel: 'UNKNOWN',
    category: 'General',
    icon: '📍',
    color: '#6b7280',
  },
  airfield: {
    label: 'Airfield / Airbase',
    shortLabel: 'AIRBASE',
    category: 'Military',
    icon: '✈️',
    color: '#2563eb',
  },
  port: {
    label: 'Port',
    shortLabel: 'PORT',
    category: 'Infrastructure',
    icon: '⚓',
    color: '#1d4ed8',
  },
  bridge: {
    label: 'Bridge',
    shortLabel: 'BRIDGE',
    category: 'Infrastructure',
    icon: '🌉',
    color: '#7c3aed',
  },
  railway: {
    label: 'Railway / Rail node',
    shortLabel: 'RAIL',
    category: 'Infrastructure',
    icon: '🚂',
    color: '#111827',
  },
  warehouse: {
    label: 'Warehouse / Logistics point',
    shortLabel: 'WAREHOUSE',
    category: 'Logistics',
    icon: '📦',
    color: '#92400e',
  },
  fuel: {
    label: 'Fuel / Oil facility',
    shortLabel: 'FUEL',
    category: 'Logistics',
    icon: '🛢',
    color: '#ea580c',
  },
  industrial: {
    label: 'Industrial object',
    shortLabel: 'INDUSTRIAL',
    category: 'Industry',
    icon: '🏭',
    color: '#475569',
  },
  radar: {
    label: 'Radar / Communications',
    shortLabel: 'RADAR',
    category: 'Military',
    icon: '📡',
    color: '#0891b2',
  },
  airdefense: {
    label: 'Air defence',
    shortLabel: 'AIR DEF',
    category: 'Military',
    icon: '🛡',
    color: '#16a34a',
  },
  target: {
    label: 'Target',
    shortLabel: 'TARGET',
    category: 'Military',
    icon: '🎯',
    color: '#dc2626',
  },
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

function getObjectType(type) {
  return OBJECT_TYPES[type] || OBJECT_TYPES.unknown;
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
    geometry: {
      type: 'Point',
      coordinates: [Number(objectItem.lng), Number(objectItem.lat)],
    },
    properties: {
      id: objectItem.id,
      source: 'manual_object_identification',
      objectType: objectItem.objectType || 'unknown',
      objectTypeLabel: typeMeta.label,
      objectCategory: typeMeta.category,
      createdAt: objectItem.createdAt || null,
      updatedAt: objectItem.updatedAt || null,
      wgs84: `${formatCoord(objectItem.lat)}, ${formatCoord(objectItem.lng)}`,
    },
  };
}

function createObjectIcon(objectItem) {
  const typeMeta = getObjectType(objectItem.objectType);

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
        border-top: 4px solid ${typeMeta.color};
        border-radius: 8px;
        padding: 5px 7px 5px 7px;
        box-shadow: 0 2px 9px rgba(0,0,0,0.28);
        font-size: 11px;
        line-height: 1.15;
        text-align: center;
        white-space: nowrap;
      ">
        <div style="font-size:14px; line-height:1;">${typeMeta.icon}</div>
        <div style="font-weight:700; margin-top:2px;">${typeMeta.shortLabel}</div>
      </div>
    `,
    iconSize: [1, 1],
    iconAnchor: [27, 16],
  });
}

function createPopupHtml(objectItem) {
  const typeMeta = getObjectType(objectItem.objectType);
  const lat = formatCoord(objectItem.lat);
  const lng = formatCoord(objectItem.lng);
  const coordText = `${lat}, ${lng}`;

  return `
    <div style="min-width:240px;">
      <div style="font-weight:700; margin-bottom:6px;">
        ${typeMeta.icon} ${escapeHtml(typeMeta.label)}
      </div>

      <div><b>Category:</b> ${escapeHtml(typeMeta.category)}</div>
      <div><b>Type:</b> ${escapeHtml(typeMeta.shortLabel)}</div>

      <hr style="margin:6px 0;">

      <div><b>Latitude:</b> ${lat}</div>
      <div><b>Longitude:</b> ${lng}</div>

      <div style="font-size:12px; color:#555; margin-top:6px;">
        WGS84: <code>${coordText}</code>
      </div>

      <hr style="margin:6px 0;">

      <button
        type="button"
        data-object-action="copy"
        data-object-id="${escapeHtml(objectItem.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Copy object
      </button>

      <button
        type="button"
        data-object-action="export-json"
        data-object-id="${escapeHtml(objectItem.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Export object JSON
      </button>

      <button
        type="button"
        data-object-action="export-geojson"
        data-object-id="${escapeHtml(objectItem.id)}"
        style="width:100%; margin-bottom:4px;"
      >
        Export object GeoJSON
      </button>

      <button
        type="button"
        data-object-action="delete"
        data-object-id="${escapeHtml(objectItem.id)}"
        style="width:100%;"
      >
        Delete object
      </button>

      <div style="font-size:11px; color:#777; margin-top:6px;">
        Drag the object marker to refine the location.
      </div>
    </div>
  `;
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
    if (typeof onStatusChange === 'function') {
      onStatusChange(text);
    }
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
      type: 'manual_object_identifications',
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
      title: getObjectType(objectItem.objectType).label,
      icon: createObjectIcon(objectItem),
    });

    marker.bindPopup(createPopupHtml(objectItem));

    marker.on('dragend', () => {
      updateObjectPosition(objectItem.id, marker.getLatLng());
    });

    marker.addTo(layerGroup);
    rendered.set(objectItem.id, marker);

    if (shouldOpen) {
      marker.openPopup();
    }
  }

  function restoreObjects() {
    layerGroup.clearLayers();
    rendered.clear();

    objects = readStoredObjects();

    objects.forEach(item => {
      renderObject(item, false);
    });
  }

  function addObject(latlng, objectType = 'unknown', shouldOpen = true) {
    const typeValue = objectType || 'unknown';

    const objectItem = {
      id: makeObjectId(),
      createdAt: nowIso(),
      updatedAt: nowIso(),
      lat: Number(latlng.lat),
      lng: Number(latlng.lng),
      objectType: typeValue,
    };

    if (!Number.isFinite(objectItem.lat) || !Number.isFinite(objectItem.lng)) {
      return null;
    }

    objects.push(objectItem);
    save();
    renderObject(objectItem, shouldOpen);

    emitStatus(`Objektum rögzítve: ${getObjectType(typeValue).label} (${formatCoord(objectItem.lat)}, ${formatCoord(objectItem.lng)}).`);

    return objectItem;
  }

  function updateObjectPosition(id, latlng) {
    const item = findObject(id);
    if (!item) return;

    item.lat = Number(latlng.lat);
    item.lng = Number(latlng.lng);
    item.updatedAt = nowIso();

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

    const selectedType =
      typeof getObjectTypeValue === 'function'
        ? getObjectTypeValue()
        : 'unknown';

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

    if (action === 'copy') {
      copyText(
        `${typeMeta.label}\n` +
        `Category: ${typeMeta.category}\n` +
        `Coordinates: ${formatCoord(item.lat)}, ${formatCoord(item.lng)}\n` +
        `Created: ${item.createdAt || 'n/a'}`
      );

      target.textContent = 'Copied';
      setTimeout(() => {
        target.textContent = 'Copy object';
      }, 1200);
      return;
    }

    if (action === 'export-json') {
      exportJson([item], `identified_object_${item.id}.json`);
      return;
    }

    if (action === 'export-geojson') {
      exportGeoJson([item], `identified_object_${item.id}.geojson`);
      return;
    }

    if (action === 'delete') {
      removeObject(id);
    }
  }

  map.on('click', handleMapClick);
  document.addEventListener('click', handlePopupClick);

  restoreObjects();

  return {
    enable() {
      isEnabled = true;
      emitStatus('Objektumazonosítás aktív. Válassz objektumtípust, majd kattints a térképre.');
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
      layerGroup.clearLayers();
      rendered.clear();
    },
  };
}
