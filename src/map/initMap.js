export function initMap() {
  const map = L.map('map', { zoomControl: true }).setView([48.5, 33.5], 6);

  const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19,
  }).addTo(map);

  const carto = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 20,
  });

  const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  });

  L.control.layers(
    {
      'OpenStreetMap': osm,
      'CARTO Light': carto,
      'Műholdkép (Esri)': esriSat,
    },
    {},
    { collapsed: false }
  ).addTo(map);

  return map;
}
