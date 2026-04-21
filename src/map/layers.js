const occupiedStyle = {
  color: '#c0392b',
  weight: 1,
  fillColor: '#c0392b',
  fillOpacity: 0.34,
};

const borderStyle = {
  color: '#334155',
  weight: 2,
  fillOpacity: 0,
  opacity: 0.85,
  dashArray: '5,5',
};

export function createLayers(map) {
  const occupiedLayer = L.geoJSON(null, { style: occupiedStyle }).addTo(map);
  const borderLayer = L.geoJSON(null, { style: borderStyle }).addTo(map);
  const deltaLayer = L.layerGroup().addTo(map);
  const firmsLayer = L.layerGroup();
  const osintLayer = L.layerGroup();

  return { occupiedLayer, borderLayer, deltaLayer, firmsLayer, osintLayer };
}

export function replaceOccupiedLayer(map, state, geojson) {
  map.removeLayer(state.occupiedLayer);
  state.occupiedLayer = L.geoJSON(geojson, { style: occupiedStyle }).addTo(map);
  const bounds = state.occupiedLayer.getBounds();
  if (bounds.isValid()) map.fitBounds(bounds.pad(0.7));
}

export function replaceBorderLayer(map, state, geojson) {
  map.removeLayer(state.borderLayer);
  state.borderLayer = L.geoJSON(geojson, { style: borderStyle }).addTo(map);
}

export function renderDeltaLayer(state, delta, currentDate, previousDate) {
  state.deltaLayer.clearLayers();

  const makeCircle = (entry) => {
    const [lon, lat] = entry.point;
    const isGain = entry.type === 'gain';
    const area = entry.areaKm2 ? `${entry.areaKm2.toFixed(2)} km²` : 'n/a';
    const label = isGain ? 'Orosz területszerzés' : 'Ukrán visszaszerzés';
    const color = isGain ? 'rgba(210,48,48,0.85)' : 'rgba(41,98,255,0.85)';
    const circle = L.circleMarker([lat, lon], {
      radius: 8,
      color,
      fillColor: color,
      fillOpacity: 0.7,
      weight: 1,
    });
    circle.bindPopup(`<strong>${label}</strong><br>${previousDate} → ${currentDate}<br>Becsült változás: ${area}`);
    return circle;
  };

  delta.gained.forEach(item => state.deltaLayer.addLayer(makeCircle(item)));
  delta.lost.forEach(item => state.deltaLayer.addLayer(makeCircle(item)));
}

export function renderFirmsLayer(state, featureCollection) {
  state.firmsLayer.clearLayers();
  (featureCollection?.features ?? []).forEach(feature => {
    const [lon, lat] = feature.geometry.coordinates;
    const marker = L.circleMarker([lat, lon], {
      radius: 4,
      color: '#f59e0b',
      fillColor: '#f59e0b',
      fillOpacity: 0.8,
      weight: 1,
    });
    state.firmsLayer.addLayer(marker);
  });
}

export function renderOsintLayer(state, points) {
  state.osintLayer.clearLayers();
  points.forEach(item => {
    const marker = L.circleMarker([item.lat, item.lon], {
      radius: 5,
      color: item.type === 'official' ? '#15803d' : '#7c3aed',
      fillColor: item.type === 'official' ? '#22c55e' : '#8b5cf6',
      fillOpacity: 0.9,
      weight: 1,
    });
    marker.bindPopup(`<strong>${item.title}</strong><br>${item.source}`);
    state.osintLayer.addLayer(marker);
  });
}
