import { FRONT_SECTORS } from '../data/frontSectors.js';

const DELTA_LABEL_STORAGE_KEY = 'ukraine_front_delta_label_positions_v1';
const FIRMS_LABEL_STORAGE_KEY = 'ukraine_front_firms_box_positions_v1';
const OSINT_LABEL_STORAGE_KEY = 'ukraine_front_osint_box_positions_v1';

function popupFromProps(props) {
  return Object.entries(props || {})
    .map(([k, v]) => `<div><b>${k}:</b> ${String(v)}</div>`)
    .join('');
}

function loadSavedJson(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    console.warn(`Could not load saved JSON for ${key}:`, error);
    return {};
  }
}

function saveSavedJson(key, data) {
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.warn(`Could not save JSON for ${key}:`, error);
  }
}

function getDeltaItemKey(item, currentDate, previousDate, side, number) {
  const lat = Number(item.lat).toFixed(4);
  const lng = Number(item.lng).toFixed(4);
  const area = Number(item.areaKm2).toFixed(2);
  return `${previousDate}_${currentDate}_${side}_${number}_${lat}_${lng}_${area}`;
}

function getFirmsZoneKey(zone, windowDays) {
  if (!zone) return null;
  return `${windowDays}_${zone.category}_${zone.key}_${zone.count}`;
}

function getOsintItemKey(item, index) {
  const lat = Number(item.lat).toFixed(4);
  const lng = Number(item.lng).toFixed(4);
  return `${index}_${item.sourceType || 'OSINT'}_${item.date || 'nodate'}_${lat}_${lng}_${item.title || 'untitled'}`;
}

function createSideLabelHtml({ index, isGain, areaKm2, previousDate, currentDate, sectorName, nearestPlace }) {
  const borderColor = isGain ? '#ff0000' : '#004dff';
  const badgeColor = isGain ? '#ff0000' : '#004dff';
  const title = isGain ? 'Russian territorial gain' : 'Ukrainian recapture';

  return `
    <div style="
      background: rgba(255,255,255,0.97);
      padding: 8px 10px;
      border-radius: 10px;
      border: 2px solid ${borderColor};
      font-size: 12px;
      line-height: 1.35;
      box-shadow: 0 2px 8px rgba(0,0,0,0.28);
      min-width: 220px;
      color: #111;
      white-space: normal;
    ">
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
        <span style="
          display:inline-flex;
          align-items:center;
          justify-content:center;
          width:20px;
          height:20px;
          border-radius:999px;
          background:${badgeColor};
          color:#fff;
          font-weight:bold;
          font-size:12px;
          flex: 0 0 20px;
        ">${index}</span>
        <b>${title}</b>
      </div>
      <div><b>Sector:</b> ${sectorName || 'Unknown sector'}</div>
      <div><b>Near:</b> ${nearestPlace || 'Unknown place'}</div>
      <div><b>Change:</b> ${areaKm2.toFixed(2)} km²</div>
      <div style="color:#666;">${previousDate} → ${currentDate}</div>
    </div>
  `;
}

function createNumberIcon(number, color) {
  return L.divIcon({
    className: '',
    html: `
      <div style="
        width: 28px;
        height: 28px;
        border-radius: 999px;
        background: ${color};
        color: white;
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight:bold;
        font-size:13px;
        border: 2px solid white;
        box-shadow: 0 1px 6px rgba(0,0,0,0.35);
      ">${number}</div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function createLabelIcon({ index, isGain, areaKm2, previousDate, currentDate, side, sectorName, nearestPlace }) {
  return L.divIcon({
    className: '',
    html: createSideLabelHtml({
      index,
      isGain,
      areaKm2,
      previousDate,
      currentDate,
      sectorName,
      nearestPlace,
    }),
    iconSize: [230, 102],
    iconAnchor: side === 'left' ? [230, 51] : [0, 51],
  });
}

function createSectorLabelIcon(name) {
  return L.divIcon({
    className: '',
    html: `
      <div style="
        background: rgba(255,255,255,0.82);
        border: 1px solid rgba(60,60,60,0.35);
        border-radius: 8px;
        padding: 4px 8px;
        font-size: 13px;
        font-weight: bold;
        color: #1f2937;
        box-shadow: 0 1px 4px rgba(0,0,0,0.15);
        white-space: nowrap;
      ">${name}</div>
    `,
    iconSize: [120, 24],
    iconAnchor: [60, 12],
  });
}

function createOsintBoxIcon(item, index, color) {
  return L.divIcon({
    className: '',
    html: `
      <div style="
        background: rgba(255,255,255,0.97);
        border: 2px solid ${color};
        border-radius: 10px;
        padding: 8px 10px;
        font-size: 12px;
        line-height: 1.35;
        box-shadow: 0 2px 8px rgba(0,0,0,0.28);
        min-width: 245px;
        color: #111;
        white-space: normal;
      ">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
          <span style="
            display:inline-flex;
            align-items:center;
            justify-content:center;
            width:20px;
            height:20px;
            border-radius:999px;
            background:${color};
            color:#fff;
            font-weight:bold;
            font-size:12px;
            flex: 0 0 20px;
          ">${index}</span>
          <b>${item.sourceType || 'OSINT'}</b>
        </div>
        <div><b>${item.title || 'Untitled cluster'}</b></div>
        <div>${item.date || 'Unknown date'}</div>
        <div><b>Sector:</b> ${item.sectorName || 'Unknown sector'}</div>
        <div><b>Near:</b> ${item.nearestPlace || 'Unknown place'}</div>
        <div><b>Reports:</b> ${item.reportCount || 1}</div>
        <div><b>Top category:</b> ${item.category || 'general military update'}</div>
        <div style="color:#444;">Latest: ${item.latestTitle || item.title || 'Untitled'}</div>
      </div>
    `,
    iconSize: [255, 145],
    iconAnchor: [0, 72],
  });
}

function getPixelOffsetForSide(map, side, rowIndex) {
  const zoom = map.getZoom();

  let baseX;
  if (zoom <= 6) baseX = 260;
  else if (zoom === 7) baseX = 220;
  else if (zoom === 8) baseX = 180;
  else if (zoom === 9) baseX = 145;
  else if (zoom === 10) baseX = 115;
  else if (zoom === 11) baseX = 90;
  else baseX = 70;

  const x = side === 'left' ? -baseX : baseX;
  const rowSpacing = 110;
  const y = (rowIndex - 1) * rowSpacing - 45;

  return { x, y };
}

function getLabelLatLngFromBase(map, baseLatLng, side, rowIndex) {
  const basePoint = map.latLngToContainerPoint(baseLatLng);
  const offset = getPixelOffsetForSide(map, side, rowIndex);
  const labelPoint = L.point(basePoint.x + offset.x, basePoint.y + offset.y);
  return map.containerPointToLatLng(labelPoint);
}

function getLeaderColor(isGain) {
  return isGain ? '#b91c1c' : '#1d4ed8';
}

function getOsintColor(sourceType) {
  if (sourceType === 'ISW') return '#7c3aed';
  if (sourceType === 'Ukrainian official') return '#15803d';
  return '#1f5f8b';
}

function buildPopupHtml(number, isGain, previousDate, currentDate, areaKm2, sectorName, nearestPlace) {
  return `
    <b>#${number} – ${isGain ? 'Russian territorial gain' : 'Ukrainian recapture'}</b><br>
    <b>Sector:</b> ${sectorName || 'Unknown sector'}<br>
    <b>Near:</b> ${nearestPlace || 'Unknown place'}<br>
    ${previousDate} → ${currentDate}<br>
    <b>Change:</b> ${areaKm2.toFixed(2)} km²
  `;
}

function rebuildFrontSectorLayer(layerState) {
  layerState.frontSectorLayer.clearLayers();

  const sectorPolygons = L.geoJSON(FRONT_SECTORS, {
    style: {
      color: '#555',
      weight: 1.5,
      opacity: 0.55,
      fillOpacity: 0,
      dashArray: '6,4',
    },
    onEachFeature: (feature, layer) => {
      layer.bindPopup(`<b>${feature.properties.name}</b>`);
    }
  });

  sectorPolygons.addTo(layerState.frontSectorLayer);

  FRONT_SECTORS.features.forEach((feature) => {
    const marker = L.marker(
      [feature.properties.labelLat, feature.properties.labelLng],
      { icon: createSectorLabelIcon(feature.properties.name) }
    );
    marker.addTo(layerState.frontSectorLayer);
  });
}

function getSavedOrDefaultLabelLatLng(layerState, item, currentDate, previousDate, side, number, baseLatLng) {
  const key = getDeltaItemKey(item, currentDate, previousDate, side, number);
  const saved = layerState.savedDeltaLabelPositions[key];

  if (saved && typeof saved.lat === 'number' && typeof saved.lng === 'number') {
    return L.latLng(saved.lat, saved.lng);
  }

  return getLabelLatLngFromBase(layerState.map, baseLatLng, side, number);
}

function rememberDeltaLabelPosition(layerState, key, latlng) {
  layerState.savedDeltaLabelPositions[key] = {
    lat: latlng.lat,
    lng: latlng.lng,
  };
  saveSavedJson(DELTA_LABEL_STORAGE_KEY, layerState.savedDeltaLabelPositions);
}

function clearSavedDeltaLabelPosition(layerState, key) {
  if (layerState.savedDeltaLabelPositions[key]) {
    delete layerState.savedDeltaLabelPositions[key];
    saveSavedJson(DELTA_LABEL_STORAGE_KEY, layerState.savedDeltaLabelPositions);
  }
}

function attachDragPersistence(layerState, { label, leader, baseLatLng, item, currentDate, previousDate, side, number }) {
  const key = getDeltaItemKey(item, currentDate, previousDate, side, number);

  label.on('drag', (event) => {
    const newLatLng = event.target.getLatLng();
    leader.setLatLngs([baseLatLng, newLatLng]);
  });

  label.on('dragend', (event) => {
    const newLatLng = event.target.getLatLng();
    rememberDeltaLabelPosition(layerState, key, newLatLng);
    leader.setLatLngs([baseLatLng, newLatLng]);
  });

  label.on('contextmenu', () => {
    clearSavedDeltaLabelPosition(layerState, key);
    const defaultLatLng = getLabelLatLngFromBase(layerState.map, baseLatLng, side, number);
    label.setLatLng(defaultLatLng);
    leader.setLatLngs([baseLatLng, defaultLatLng]);
  });
}

function rebuildDeltaDynamicLayout(layerState) {
  const map = layerState.map;
  if (!map || !layerState.lastDeltaPayload) return;

  layerState.deltaLayer.clearLayers();

  const { delta, currentDate, previousDate } = layerState.lastDeltaPayload;
  const items = delta.all || [];

  const gains = items.filter(item => item.type === 'gain');
  const losses = items.filter(item => item.type === 'loss');

  gains.forEach((item, idx) => {
    const number = idx + 1;
    const side = 'right';
    const baseLatLng = L.latLng(item.lat, item.lng);
    const labelLatLng = getSavedOrDefaultLabelLatLng(
      layerState, item, currentDate, previousDate, side, number, baseLatLng
    );

    const circle = L.circle(baseLatLng, {
      radius: item.radiusMeters,
      color: '#ff0000',
      fillColor: '#ff3b3b',
      fillOpacity: 0.24,
      weight: 3,
    }).addTo(layerState.deltaLayer);

    const centerNumberMarker = L.marker(baseLatLng, {
      icon: createNumberIcon(number, '#ff0000')
    }).addTo(layerState.deltaLayer);

    const leader = L.polyline([baseLatLng, labelLatLng], {
      color: getLeaderColor(true),
      weight: 2,
      opacity: 0.75,
      dashArray: '4,4',
    }).addTo(layerState.deltaLayer);

    const label = L.marker(labelLatLng, {
      interactive: true,
      draggable: true,
      icon: createLabelIcon({
        index: number,
        isGain: true,
        areaKm2: item.areaKm2,
        previousDate,
        currentDate,
        side,
        sectorName: item.sectorName,
        nearestPlace: item.nearestPlace,
      })
    }).addTo(layerState.deltaLayer);

    attachDragPersistence(layerState, {
      label,
      leader,
      baseLatLng,
      item,
      currentDate,
      previousDate,
      side,
      number,
    });

    const popupHtml = buildPopupHtml(
      number,
      true,
      previousDate,
      currentDate,
      item.areaKm2,
      item.sectorName,
      item.nearestPlace
    );

    circle.bindPopup(popupHtml);
    centerNumberMarker.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
  });

  losses.forEach((item, idx) => {
    const number = idx + 1;
    const side = 'left';
    const baseLatLng = L.latLng(item.lat, item.lng);
    const labelLatLng = getSavedOrDefaultLabelLatLng(
      layerState, item, currentDate, previousDate, side, number, baseLatLng
    );

    const circle = L.circle(baseLatLng, {
      radius: item.radiusMeters,
      color: '#004dff',
      fillColor: '#3b82ff',
      fillOpacity: 0.24,
      weight: 3,
    }).addTo(layerState.deltaLayer);

    const centerNumberMarker = L.marker(baseLatLng, {
      icon: createNumberIcon(number, '#004dff')
    }).addTo(layerState.deltaLayer);

    const leader = L.polyline([baseLatLng, labelLatLng], {
      color: getLeaderColor(false),
      weight: 2,
      opacity: 0.75,
      dashArray: '4,4',
    }).addTo(layerState.deltaLayer);

    const label = L.marker(labelLatLng, {
      interactive: true,
      draggable: true,
      icon: createLabelIcon({
        index: number,
        isGain: false,
        areaKm2: item.areaKm2,
        previousDate,
        currentDate,
        side,
        sectorName: item.sectorName,
        nearestPlace: item.nearestPlace,
      })
    }).addTo(layerState.deltaLayer);

    attachDragPersistence(layerState, {
      label,
      leader,
      baseLatLng,
      item,
      currentDate,
      previousDate,
      side,
      number,
    });

    const popupHtml = buildPopupHtml(
      number,
      false,
      previousDate,
      currentDate,
      item.areaKm2,
      item.sectorName,
      item.nearestPlace
    );

    circle.bindPopup(popupHtml);
    centerNumberMarker.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
  });
}

function getCategoryColor(category) {
  if (category === 'front') {
    return { stroke: '#cc5500', fill: '#ff7a00', box: '#ff8800' };
  }
  if (category === 'ukrainian_rear') {
    return { stroke: '#c99200', fill: '#ffd54a', box: '#e0a800' };
  }
  if (category === 'russian_rear') {
    return { stroke: '#8b1e3f', fill: '#d63384', box: '#b4235a' };
  }
  return { stroke: '#666666', fill: '#999999', box: '#777777' };
}

export function resetAllSavedDeltaLabels(layerState) {
  layerState.savedDeltaLabelPositions = {};
  saveSavedJson(DELTA_LABEL_STORAGE_KEY, layerState.savedDeltaLabelPositions);

  if (layerState.lastDeltaPayload) {
    rebuildDeltaDynamicLayout(layerState);
  }
}

export function renderFirmsHotspotBox(layerState, summary) {
  layerState.firmsHotspotLayer.clearLayers();

  const zones = summary?.topThreeZones || [];
  if (!zones.length) return;

  zones.forEach((zone, idx) => {
    const colors = getCategoryColor(zone.category);
    const zoneKey = getFirmsZoneKey(zone, summary.windowDays);
    const saved = zoneKey ? layerState.savedFirmsBoxPositions[zoneKey] : null;

    const rectangle = L.rectangle(zone.bounds, {
      color: colors.box,
      weight: 2,
      fillOpacity: 0,
      dashArray: '8,6',
    }).addTo(layerState.firmsHotspotLayer);

    const centerLat = (zone.bounds[0][0] + zone.bounds[1][0]) / 2;
    const centerLng = (zone.bounds[0][1] + zone.bounds[1][1]) / 2;
    const centerLatLng = L.latLng(centerLat, centerLng);

    const centerPoint = layerState.map.latLngToContainerPoint(centerLatLng);
    const defaultPoint = L.point(centerPoint.x + 120, centerPoint.y - 90 - idx * 80);
    const defaultLabelLatLng = layerState.map.containerPointToLatLng(defaultPoint);

    const labelLatLng = saved ? L.latLng(saved.lat, saved.lng) : defaultLabelLatLng;

    const leader = L.polyline([centerLatLng, labelLatLng], {
      color: colors.box,
      weight: 2,
      opacity: 0.75,
      dashArray: '4,4',
    }).addTo(layerState.firmsHotspotLayer);

    const label = L.marker(labelLatLng, {
      draggable: true,
      interactive: true,
      icon: L.divIcon({
        className: '',
        html: `
          <div style="
            background: rgba(255,248,235,0.96);
            border: 2px solid ${colors.box};
            border-radius: 8px;
            padding: 6px 8px;
            font-size: 12px;
            line-height: 1.3;
            box-shadow: 0 2px 6px rgba(0,0,0,0.25);
            white-space: nowrap;
          ">
            <b>FIRMS zone #${idx + 1}</b><br>
            ${zone.categoryLabel}<br>
            ${zone.sectorName || 'Unknown sector'}<br>
            ${zone.nearestPlace || 'Unknown place'}<br>
            Hotspots: <b>${zone.count}</b>
          </div>
        `,
        iconSize: [245, 88],
        iconAnchor: [122, 44],
      })
    }).addTo(layerState.firmsHotspotLayer);

    if (zoneKey) {
      label.on('drag', (event) => {
        const newLatLng = event.target.getLatLng();
        leader.setLatLngs([centerLatLng, newLatLng]);
      });

      label.on('dragend', (event) => {
        const newLatLng = event.target.getLatLng();
        layerState.savedFirmsBoxPositions[zoneKey] = {
          lat: newLatLng.lat,
          lng: newLatLng.lng,
        };
        saveSavedJson(FIRMS_LABEL_STORAGE_KEY, layerState.savedFirmsBoxPositions);
        leader.setLatLngs([centerLatLng, newLatLng]);
      });

      label.on('contextmenu', () => {
        delete layerState.savedFirmsBoxPositions[zoneKey];
        saveSavedJson(FIRMS_LABEL_STORAGE_KEY, layerState.savedFirmsBoxPositions);
        label.setLatLng(defaultLabelLatLng);
        leader.setLatLngs([centerLatLng, defaultLabelLatLng]);
      });
    }

    const popupHtml = `
      <b>FIRMS zone #${idx + 1}</b><br>
      <b>Category:</b> ${zone.categoryLabel}<br>
      <b>Sector:</b> ${zone.sectorName || 'Unknown sector'}<br>
      <b>Near:</b> ${zone.nearestPlace || 'Unknown place'}<br>
      <b>Hotspots:</b> ${zone.count}<br>
      <b>Window:</b> ${summary.windowDays} days
    `;

    rectangle.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
  });
}

export function renderOsintHighlights(layerState, osintSummary) {
  layerState.osintHighlightLayer.clearLayers();

  const items = osintSummary?.topFive || [];
  if (!items.length) return;

  items.forEach((item, idx) => {
    const number = idx + 1;
    const color = getOsintColor(item.sourceType);
    const key = getOsintItemKey(item, number);

    const baseLatLng = L.latLng(item.lat, item.lng);
    const basePoint = layerState.map.latLngToContainerPoint(baseLatLng);
    const sideX = basePoint.x < layerState.map.getSize().x / 2 ? 110 : -270;
    const defaultPoint = L.point(basePoint.x + sideX, basePoint.y - 70 + idx * 18);
    const defaultLabelLatLng = layerState.map.containerPointToLatLng(defaultPoint);

    const saved = layerState.savedOsintBoxPositions[key];
    const labelLatLng = saved ? L.latLng(saved.lat, saved.lng) : defaultLabelLatLng;

    const marker = L.circleMarker(baseLatLng, {
      radius: 8,
      color,
      fillColor: color,
      fillOpacity: 0.9,
      weight: 2,
    }).addTo(layerState.osintHighlightLayer);

    const numberMarker = L.marker(baseLatLng, {
      icon: createNumberIcon(number, color)
    }).addTo(layerState.osintHighlightLayer);

    const leader = L.polyline([baseLatLng, labelLatLng], {
      color,
      weight: 2,
      opacity: 0.75,
      dashArray: '4,4',
    }).addTo(layerState.osintHighlightLayer);

    const label = L.marker(labelLatLng, {
      draggable: true,
      interactive: true,
      icon: createOsintBoxIcon(item, number, color)
    }).addTo(layerState.osintHighlightLayer);

    label.on('drag', (event) => {
      const newLatLng = event.target.getLatLng();
      leader.setLatLngs([baseLatLng, newLatLng]);
    });

    label.on('dragend', (event) => {
      const newLatLng = event.target.getLatLng();
      layerState.savedOsintBoxPositions[key] = {
        lat: newLatLng.lat,
        lng: newLatLng.lng,
      };
      saveSavedJson(OSINT_LABEL_STORAGE_KEY, layerState.savedOsintBoxPositions);
      leader.setLatLngs([baseLatLng, newLatLng]);
    });

    label.on('contextmenu', () => {
      delete layerState.savedOsintBoxPositions[key];
      saveSavedJson(OSINT_LABEL_STORAGE_KEY, layerState.savedOsintBoxPositions);
      label.setLatLng(defaultLabelLatLng);
      leader.setLatLngs([baseLatLng, defaultLabelLatLng]);
    });

    const popupHtml = `
      <b>${item.sourceType || 'OSINT'} #${number}</b><br>
      <b>Cluster title:</b> ${item.title || 'Untitled'}<br>
      <b>Date:</b> ${item.date || 'Unknown'}<br>
      <b>Sector:</b> ${item.sectorName || 'Unknown sector'}<br>
      <b>Near:</b> ${item.nearestPlace || 'Unknown place'}<br>
      <b>Reports:</b> ${item.reportCount || 1}<br>
      <b>Top category:</b> ${item.category || 'general military update'}<br>
      <b>Latest:</b> ${item.latestTitle || item.title || 'Untitled'}<br>
      ${item.urls?.length ? item.urls.map((url, i) => `<div><a href="${url}" target="_blank" rel="noopener noreferrer">Open source ${i + 1}</a></div>`).join('') : ''}
    `;

    marker.bindPopup(popupHtml);
    numberMarker.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
  });
}

export function createLayers(map) {
  const occupiedLayer = L.geoJSON(null, {
    style: {
      color: '#c0392b',
      weight: 1,
      fillColor: '#c0392b',
      fillOpacity: 0.33
    }
  }).addTo(map);

  const deltaLayer = L.layerGroup().addTo(map);

  const borderLayer = L.geoJSON(null, {
    style: {
      color: '#34495e',
      weight: 2,
      fillOpacity: 0,
      opacity: 0.9,
      dashArray: '4,4'
    }
  }).addTo(map);

  const frontSectorLayer = L.layerGroup().addTo(map);
  const firmsLayer = L.layerGroup();
  const firmsHotspotLayer = L.layerGroup();
  const osintLayer = L.layerGroup();
  const osintHighlightLayer = L.layerGroup();

  const layerState = {
    map,
    occupiedLayer,
    deltaLayer,
    borderLayer,
    frontSectorLayer,
    firmsLayer,
    firmsHotspotLayer,
    osintLayer,
    osintHighlightLayer,
    lastDeltaPayload: null,
    savedDeltaLabelPositions: loadSavedJson(DELTA_LABEL_STORAGE_KEY),
    savedFirmsBoxPositions: loadSavedJson(FIRMS_LABEL_STORAGE_KEY),
    savedOsintBoxPositions: loadSavedJson(OSINT_LABEL_STORAGE_KEY),
  };

  rebuildFrontSectorLayer(layerState);

  map.on('zoomend moveend resize', () => {
    if (layerState.lastDeltaPayload && map.hasLayer(layerState.deltaLayer)) {
      rebuildDeltaDynamicLayout(layerState);
    }
  });

  return layerState;
}

export function replaceOccupiedLayer(map, layerState, data) {
  layerState.occupiedLayer.clearLayers();
  layerState.occupiedLayer.addData(data);
}

export function replaceBorderLayer(map, layerState, data) {
  layerState.borderLayer.clearLayers();
  layerState.borderLayer.addData(data);
}

export function renderDeltaLayer(layerState, delta, currentDate, previousDate) {
  layerState.lastDeltaPayload = { delta, currentDate, previousDate };
  rebuildDeltaDynamicLayout(layerState);
}

export function renderFirmsLayer(layerState, points) {
  layerState.firmsLayer.clearLayers();

  points.forEach(point => {
    const colors = getCategoryColor(point.category);

    L.circleMarker([point.lat, point.lng], {
      radius: 5,
      color: colors.stroke,
      fillColor: colors.fill,
      fillOpacity: 0.75,
      weight: 1,
    }).bindPopup(`
      <b>FIRMS</b><br>
      <b>Category:</b> ${point.categoryLabel || 'Unknown'}<br>
      <b>Sector:</b> ${point.sectorName || 'Unknown sector'}<br>
      <b>Near:</b> ${point.nearestPlace || 'Unknown place'}<br>
      <b>Distance to front:</b> ${Number(point.distanceToFrontKm || 0).toFixed(1)} km<br>
      ${popupFromProps({
        acq_date: point.acq_date,
        acq_time: point.acq_time,
        confidence: point.confidence,
        frp: point.frp,
        source: point.source,
        satellite: point.satellite,
        daynight: point.daynight,
      })}
    `).addTo(layerState.firmsLayer);
  });
}

export function renderOsintLayer(layerState, points) {
  layerState.osintLayer.clearLayers();

  points.forEach(point => {
    const color = getOsintColor(point.sourceType);

    L.circleMarker([point.lat, point.lng], {
      radius: 5,
      color,
      fillColor: color,
      fillOpacity: 0.55,
      weight: 1,
    }).bindPopup(`
      <b>${point.sourceType || 'OSINT'}</b><br>
      <b>Title:</b> ${point.title || 'Untitled'}<br>
      <b>Date:</b> ${point.date || 'Unknown'}<br>
      <b>Sector:</b> ${point.sectorName || 'Unknown sector'}<br>
      <b>Near:</b> ${point.nearestPlace || 'Unknown place'}<br>
      <b>Category:</b> ${point.category || 'general military update'}<br>
      ${point.url ? `<div><a href="${point.url}" target="_blank" rel="noopener noreferrer">Open source</a></div>` : ''}
    `).addTo(layerState.osintLayer);
  });
}
