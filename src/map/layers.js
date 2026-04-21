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
}

export function replaceBorderLayer(map, layerState, data) {
  layerState.borderLayer.clearLayers();
  layerState.borderLayer.addData(data);
}

export function renderDeltaLayer(layerState, delta, currentDate, previousDate) {
  layerState.deltaLayer.clearLayers();

  const items = delta.all || [];

  items.forEach(item => {
    const isGain = item.type === 'gain';

    const circle = L.circle([item.lat, item.lng], {
      radius: item.radiusMeters,
      color: isGain ? '#8b1111' : '#1246a0',
      fillColor: isGain ? '#d23030' : '#2962ff',
      fillOpacity: 0.18,
      weight: 2,
    });

    circle.bindPopup(`
      <b>${isGain ? 'Orosz területszerzés' : 'Ukrán visszaszerzés'}</b><br>
      ${previousDate} → ${currentDate}<br>
      Változás: <b>${item.areaKm2.toFixed(2)} km²</b>
    `);

    circle.addTo(layerState.deltaLayer);
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
