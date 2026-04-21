function popupFromProps(props) {
  return Object.entries(props || {})
    .map(([k, v]) => `<div><b>${k}:</b> ${String(v)}</div>`)
    .join('');
}

function createSideLabelHtml({ index, isGain, areaKm2, previousDate, currentDate }) {
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
      min-width: 210px;
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
      <div><b>Change:</b> ${areaKm2.toFixed(2)} km²</div>
      <div style="color:#666;">${previousDate} → ${currentDate}</div>
    </div>
  `;
}

function getSideLabelLatLng(map, index, side) {
  const size = map.getSize();

  const startY = 110;
  const stepY = 96;
  const y = startY + (index - 1) * stepY;

  const x = side === 'left' ? 180 : size.x - 180;

  return map.containerPointToLatLng([x, y]);
}

function getLeaderColor(isGain) {
  return isGain ? '#b91c1c' : '#1d4ed8';
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

  const firmsLayer = L.layerGroup();
  const osintLayer = L.layerGroup();

  return { occupiedLayer, deltaLayer, borderLayer, firmsLayer, osintLayer };
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
  layerState.deltaLayer.clearLayers();

  const items = delta.all || [];

  const gains = items.filter(item => item.type === 'gain');
  const losses = items.filter(item => item.type === 'loss');

  let gainIndex = 1;
  let lossIndex = 1;

  gains.forEach((item) => {
    const number = gainIndex++;
    const baseLatLng = L.latLng(item.lat, item.lng);
    const labelLatLng = getSideLabelLatLng(layerState.occupiedLayer._map, number, 'right');

    const circle = L.circle(baseLatLng, {
      radius: item.radiusMeters,
      color: '#ff0000',
      fillColor: '#ff3b3b',
      fillOpacity: 0.24,
      weight: 3,
    }).addTo(layerState.deltaLayer);

    const centerNumberMarker = L.marker(baseLatLng, {
      icon: L.divIcon({
        className: '',
        html: `
          <div style="
            width: 28px;
            height: 28px;
            border-radius: 999px;
            background: #ff0000;
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
      })
    }).addTo(layerState.deltaLayer);

    const leader = L.polyline([baseLatLng, labelLatLng], {
      color: getLeaderColor(true),
      weight: 2,
      opacity: 0.75,
      dashArray: '4,4',
    }).addTo(layerState.deltaLayer);

    const label = L.marker(labelLatLng, {
      interactive: true,
      icon: L.divIcon({
        className: '',
        html: createSideLabelHtml({
          index: number,
          isGain: true,
          areaKm2: item.areaKm2,
          previousDate,
          currentDate,
        }),
        iconSize: [220, 84],
        iconAnchor: [0, 42],
      })
    }).addTo(layerState.deltaLayer);

    const popupHtml = `
      <b>#${number} – Russian territorial gain</b><br>
      ${previousDate} → ${currentDate}<br>
      Change: <b>${item.areaKm2.toFixed(2)} km²</b>
    `;

    circle.bindPopup(popupHtml);
    centerNumberMarker.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
  });

  losses.forEach((item) => {
    const number = lossIndex++;
    const baseLatLng = L.latLng(item.lat, item.lng);
    const labelLatLng = getSideLabelLatLng(layerState.occupiedLayer._map, number, 'left');

    const circle = L.circle(baseLatLng, {
      radius: item.radiusMeters,
      color: '#004dff',
      fillColor: '#3b82ff',
      fillOpacity: 0.24,
      weight: 3,
    }).addTo(layerState.deltaLayer);

    const centerNumberMarker = L.marker(baseLatLng, {
      icon: L.divIcon({
        className: '',
        html: `
          <div style="
            width: 28px;
            height: 28px;
            border-radius: 999px;
            background: #004dff;
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
      })
    }).addTo(layerState.deltaLayer);

    const leader = L.polyline([baseLatLng, labelLatLng], {
      color: getLeaderColor(false),
      weight: 2,
      opacity: 0.75,
      dashArray: '4,4',
    }).addTo(layerState.deltaLayer);

    const label = L.marker(labelLatLng, {
      interactive: true,
      icon: L.divIcon({
        className: '',
        html: createSideLabelHtml({
          index: number,
          isGain: false,
          areaKm2: item.areaKm2,
          previousDate,
          currentDate,
        }),
        iconSize: [220, 84],
        iconAnchor: [220, 42],
      })
    }).addTo(layerState.deltaLayer);

    const popupHtml = `
      <b>#${number} – Ukrainian recapture</b><br>
      ${previousDate} → ${currentDate}<br>
      Change: <b>${item.areaKm2.toFixed(2)} km²</b>
    `;

    circle.bindPopup(popupHtml);
    centerNumberMarker.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
  });
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
