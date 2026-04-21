import { FRONT_SECTORS } from '../data/frontSectors.js';

const DELTA_LABEL_STORAGE_KEY = 'ukraine_front_delta_label_positions_v1';

function popupFromProps(props) {
  return Object.entries(props || {})
    .map(([k, v]) => `<div><b>${k}:</b> ${String(v)}</div>`)
    .join('');
}

function loadSavedLabelPositions() {
  try {
    const raw = localStorage.getItem(DELTA_LABEL_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    console.warn('Could not load saved label positions:', error);
    return {};
  }
}

function saveSavedLabelPositions(data) {
  try {
    localStorage.setItem(DELTA_LABEL_STORAGE_KEY, JSON.stringify(data));
  } catch (error) {
    console.warn('Could not save label positions:', error);
  }
}

function getDeltaItemKey(item, currentDate, previousDate, side, number) {
  const lat = Number(item.lat).toFixed(4);
  const lng = Number(item.lng).toFixed(4);
  const area = Number(item.areaKm2).toFixed(2);
  return `${previousDate}_${currentDate}_${side}_${number}_${lat}_${lng}_${area}`;
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

function buildPopupHtml(number, isGain, previousDate, currentDate, areaKm2, sectorName, nearestPlace) {
  return `
    <b>#${number} – ${isGain ? 'Russian territorial gain' : 'Ukrainian recapture'}</b><br>
    <b>Sector:</b> ${sectorName || 'Unknown sector'}<br>
    <b>Near:</b> ${nearestPlace || 'Unknown place'}<br>
    ${previousDate} → ${currentDate}<br>
    <b>Change:</b> ${areaKm2.toFixed(2)} km²
  `;
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
  const saved = layerState.savedLabelPositions[key];

  if (saved && typeof saved.lat === 'number' && typeof saved.lng === 'number') {
    return L.latLng(saved.lat, saved.lng);
  }

  return getLabelLatLngFromBase(layerState.map, baseLatLng, side, number);
}

function rememberLabelPosition(layerState, key, latlng) {
  layerState.savedLabelPositions[key] = {
    lat: latlng.lat,
    lng: latlng.lng,
  };
  saveSavedLabelPositions(layerState.savedLabelPositions);
}

function clearSavedLabelPosition(layerState, key) {
  if (layerState.savedLabelPositions[key]) {
    delete layerState.savedLabelPositions[key];
    saveSavedLabelPositions(layerState.savedLabelPositions);
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
    rememberLabelPosition(layerState, key, newLatLng);
    leader.setLatLngs([baseLatLng, newLatLng]);
  });

  label.on('contextmenu', () => {
    clearSavedLabelPosition(layerState, key);
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

export function resetAllSavedDeltaLabels(layerState) {
  layerState.savedLabelPositions = {};
  saveSavedLabelPositions(layerState.savedLabelPositions);

  if (layerState.lastDeltaPayload) {
    rebuildDeltaDynamicLayout(layerState);
  }
}

export function renderFirmsHotspotBox(layerState, summary) {
  layerState.firmsHotspotLayer.clearLayers();

  const zone = summary?.topZone;
  if (!zone || !zone.bounds) return;

  const rectangle = L.rectangle(zone.bounds, {
    color: '#ff8800',
    weight: 2,
    fillOpacity: 0,
    dashArray: '8,6',
  }).addTo(layerState.firmsHotspotLayer);

  const centerLat =
    (zone.bounds[0][0] + zone.bounds[1][0]) / 2;
  const centerLng =
    (zone.bounds[0][1] + zone.bounds[1][1]) / 2;

  const label = L.marker([centerLat, centerLng], {
    icon: L.divIcon({
      className: '',
      html: `
        <div style="
          background: rgba(255,248,235,0.96);
          border: 2px solid #ff8800;
          border-radius: 8px;
          padding: 6px 8px;
          font-size: 12px;
          line-height: 1.3;
          box-shadow: 0 2px 6px rgba(0,0,0,0.25);
          white-space: nowrap;
        ">
          <b>Most intense FIRMS zone</b><br>
          ${zone.sectorName || 'Unknown sector'}<br>
          ${zone.nearestPlace || 'Unknown place'}<br>
          Hotspots: <b>${zone.count}</b>
        </div>
      `,
      iconSize: [220, 70],
      iconAnchor: [110, 35],
    })
  }).addTo(layerState.firmsHotspotLayer);

  const popupHtml = `
    <b>Most intense FIRMS zone</b><br>
    <b>Sector:</b> ${zone.sectorName || 'Unknown sector'}<br>
    <b>Near:</b> ${zone.nearestPlace || 'Unknown place'}<br>
    <b>Hotspots:</b> ${zone.count}<br>
    <b>Window:</b> ${summary.windowDays} days
  `;

  rectangle.bindPopup(popupHtml);
  label.bindPopup(popupHtml);
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

  const layerState = {
    map,
    occupiedLayer,
    deltaLayer,
    borderLayer,
    frontSectorLayer,
    firmsLayer,
    firmsHotspotLayer,
    osintLayer,
    lastDeltaPayload: null,
    savedLabelPositions: loadSavedLabelPositions(),
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
    L.circleMarker([point.lat, point.lng], {
      radius: 5,
      color: '#cc5500',
      fillColor: '#ff7a00',
      fillOpacity: 0.7,
      weight: 1,
    }).bindPopup(`<b>FIRMS</b><br>${popupFromProps(point)}`)
      .addTo(layerState.firmsLayer);
  });
}

export function renderOsintLayer(layerState, points) {
  layerState.osintLayer.clearLayers();

  points.forEach(point => {
    L.circleMarker([point.lat, point.lng], {
      radius: 5,
      color: '#1f5f8b',
      fillColor: '#2980b9',
      fillOpacity: 0.85,
      weight: 1,
    }).bindPopup(`<b>${point.sourceType || 'OSINT'}</b><br>${popupFromProps(point)}`)
      .addTo(layerState.osintLayer);
  });
}
