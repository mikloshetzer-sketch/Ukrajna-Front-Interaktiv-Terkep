function popupFromProps(props) {
  return Object.entries(props || {})
    .map(([k, v]) => `<div><b>${k}:</b> ${String(v)}</div>`)
    .join('');
}

export function createLayers(map) {
  const occupiedLayer = L.geoJSON(null, {
    style: { color: '#c0392b', weight: 1, fillColor: '#c0392b', fillOpacity: 0.33 }
  }).addTo(map);

  const deltaLayer = L.layerGroup().addTo(map);
  const borderLayer = L.geoJSON(null, {
    style: { color: '#34495e', weight: 2, fillOpacity: 0, opacity: 0.9, dashArray: '4,4' }
  }).addTo(map);
  const firmsLayer = L.layerGroup();
  const osintLayer = L.layerGroup();

  return { occupiedLayer, deltaLayer, borderLayer, firmsLayer, osintLayer };
}

export function replaceOccupiedLayer(map, layerState, data) {
  layerState.occupiedLayer.clearLayers();
  layerState.occupiedLayer.addData(data);
  try {
    const bounds = layerState.occupiedLayer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.2));
  } catch {}
}

export function replaceBorderLayer(map, layerState, data) {
  layerState.borderLayer.clearLayers();
  layerState.borderLayer.addData(data);
}

export function renderDeltaLayer(layerState, delta, currentDate, previousDate) {
  layerState.deltaLayer.clearLayers();

  delta.gained.forEach(item => {
    L.circleMarker([item.lat, item.lng], {
      radius: 8,
      color: '#8b1111',
      fillColor: '#d23030',
      fillOpacity: 0.8,
      weight: 1,
    }).bindPopup(`<b>Orosz területszerzés</b><br>${previousDate} → ${currentDate}<br>Kb. ${item.areaKm2.toFixed(2)} km²`).addTo(layerState.deltaLayer);
  });

  delta.lost.forEach(item => {
    L.circleMarker([item.lat, item.lng], {
      radius: 8,
      color: '#1246a0',
      fillColor: '#2962ff',
      fillOpacity: 0.8,
      weight: 1,
    }).bindPopup(`<b>Ukrán visszaszerzés</b><br>${previousDate} → ${currentDate}<br>Kb. ${item.areaKm2.toFixed(2)} km²`).addTo(layerState.deltaLayer);
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
    }).bindPopup(`<b>FIRMS hőanomália</b><br>${popupFromProps(point)}`).addTo(layerState.firmsLayer);
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
    }).bindPopup(`<b>${point.sourceType || 'OSINT'}</b><br>${popupFromProps(point)}`).addTo(layerState.osintLayer);
  });
}
