export function initMap() {
  const map = L.map('map', { zoomControl: true }).setView([48.5, 33.5], 6);

  const baseLayers = {
    osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap'
    }),

    carto: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 20,
      attribution: '&copy; OpenStreetMap &copy; CARTO'
    }),

    esri: L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 19,
        attribution: 'Tiles &copy; Esri'
      }
    )
  };

  let activeBaseLayerKey = 'osm';
  baseLayers.osm.addTo(map);

  map.baseLayers = baseLayers;

  map.getActiveBaseLayerKey = function () {
    return activeBaseLayerKey;
  };

  map.setBaseLayer = function (layerKey) {
    const nextLayerKey = baseLayers[layerKey] ? layerKey : 'osm';

    Object.values(baseLayers).forEach(layer => {
      if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    });

    baseLayers[nextLayerKey].addTo(map);
    activeBaseLayerKey = nextLayerKey;

    return activeBaseLayerKey;
  };

  return map;
}
