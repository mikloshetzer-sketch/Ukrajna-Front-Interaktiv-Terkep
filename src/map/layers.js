function popupFromProps(props) {
  return Object.entries(props || {})
    .map(([k, v]) => `<div><b>${k}:</b> ${String(v)}</div>`)
    .join('');
}

function metersToLatLngOffset(lat, offsetX, offsetY) {
  const latOffset = offsetY / 111320;
  const lngOffset = offsetX / (111320 * Math.cos((lat * Math.PI) / 180));
  return { latOffset, lngOffset };
}

function buildDeltaLabelHtml({ index, isGain, areaKm2, previousDate, currentDate }) {
  return `
    <div style="
      background: rgba(255,255,255,0.97);
      padding: 8px 10px;
      border-radius: 10px;
      border: 2px solid ${isGain ? '#ff0000' : '#004dff'};
      font-size: 12px;
      line-height: 1.35;
      box-shadow: 0 2px 8px rgba(0,0,0,0.28);
      min-width: 180px;
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
          background:${isGain ? '#ff0000' : '#004dff'};
          color:#fff;
          font-weight:bold;
          font-size:12px;
        ">${index}</span>
        <b>${isGain ? 'Orosz területszerzés' : 'Ukrán visszaszerzés'}</b>
      </div>
      <div><b>Változás:</b> ${areaKm2.toFixed(2)} km²</div>
      <div style="color:#666;">${previousDate} → ${currentDate}</div>
    </div>
  `;
}

function rectanglesOverlap(a, b) {
  return !(
    a.right < b.left ||
    a.left > b.right ||
    a.bottom < b.top ||
    a.top > b.bottom
  );
}

function buildCandidateOffsets(baseRadius) {
  const r = Math.max(baseRadius + 12000, 28000);

  return [
    { x: r, y: -r * 0.35 },
    { x: r * 0.9, y: r * 0.45 },
    { x: -r, y: -r * 0.35 },
    { x: -r * 0.9, y: r * 0.45 },
    { x: 0, y: -r },
    { x: 0, y: r },
    { x: r * 1.25, y: 0 },
    { x: -r * 1.25, y: 0 },
    { x: r * 1.1, y: -r * 0.8 },
    { x: -r * 1.1, y: -r * 0.8 },
    { x: r * 1.1, y: r * 0.8 },
    { x: -r * 1.1, y: r * 0.8 },
  ];
}

function estimateLabelRect(map, latlng, widthPx = 190, heightPx = 82) {
  const p = map.latLngToContainerPoint(latlng);
  return {
    left: p.x - widthPx / 2,
    right: p.x + widthPx / 2,
    top: p.y - heightPx / 2,
    bottom: p.y + heightPx / 2,
  };
}

function chooseBestLabelPosition(map, baseLatLng, radiusMeters, placedRects) {
  const candidates = buildCandidateOffsets(radiusMeters);

  for (const candidate of candidates) {
    const { latOffset, lngOffset } = metersToLatLngOffset(baseLatLng.lat, candidate.x, candidate.y);

    const labelLatLng = L.latLng(
      baseLatLng.lat + latOffset,
      baseLatLng.lng + lngOffset
    );

    const rect = estimateLabelRect(map, labelLatLng);

    const collides = placedRects.some(existing => rectanglesOverlap(rect, existing));
    if (!collides) {
      placedRects.push(rect);
      return { labelLatLng, candidate };
    }
  }

  const fallback = candidates[candidates.length - 1];
  const { latOffset, lngOffset } = metersToLatLngOffset(baseLatLng.lat, fallback.x, fallback.y);

  const labelLatLng = L.latLng(
    baseLatLng.lat + latOffset,
    baseLatLng.lng + lngOffset
  );

  placedRects.push(estimateLabelRect(map, labelLatLng));
  return { labelLatLng, candidate: fallback };
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
  const placedRects = [];
  let sequence = 1;

  items.forEach((item) => {
    const isGain = item.type === 'gain';
    const number = sequence++;
    const baseLatLng = L.latLng(item.lat, item.lng);

    const { labelLatLng, candidate } = chooseBestLabelPosition(
      layerState.occupiedLayer._map,
      baseLatLng,
      item.radiusMeters,
      placedRects
    );

    const circle = L.circle(baseLatLng, {
      radius: item.radiusMeters,
      color: isGain ? '#ff0000' : '#004dff',
      fillColor: isGain ? '#ff3b3b' : '#3b82ff',
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
            background: ${isGain ? '#ff0000' : '#004dff'};
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
      color: isGain ? '#b91c1c' : '#1d4ed8',
      weight: 2,
      opacity: 0.78,
      dashArray: '4,4',
    }).addTo(layerState.deltaLayer);

    const label = L.marker(labelLatLng, {
      icon: L.divIcon({
        className: '',
        html: buildDeltaLabelHtml({
          index: number,
          isGain,
          areaKm2: item.areaKm2,
          previousDate,
          currentDate,
        }),
        iconSize: [190, 82],
        iconAnchor: [
          candidate.x >= 0 ? 0 : 190,
          41
        ],
      })
    }).addTo(layerState.deltaLayer);

    const popupHtml = `
      <b>#${number} – ${isGain ? 'Orosz területszerzés' : 'Ukrán visszaszerzés'}</b><br>
      ${previousDate} → ${currentDate}<br>
      Változás: <b>${item.areaKm2.toFixed(2)} km²</b>
    `;

    circle.bindPopup(popupHtml);
    centerNumberMarker.bindPopup(popupHtml);
    label.bindPopup(popupHtml);
    leader.bindPopup(popupHtml);
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
