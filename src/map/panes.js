export const MAP_PANES = {
  BASEMAP: {
    name: 'basemapPane',
    zIndex: 200,
    pointerEvents: 'auto',
  },
  SATELLITE: {
    name: 'satellitePane',
    zIndex: 250,
    pointerEvents: 'none',
  },
  TERRITORIAL_DELTA: {
    name: 'territorialDeltaPane',
    zIndex: 300,
    pointerEvents: 'auto',
  },
  DEEPSTATE: {
    name: 'deepStatePane',
    zIndex: 350,
    pointerEvents: 'auto',
  },
  SURIYAK: {
    name: 'suriyakPane',
    zIndex: 360,
    pointerEvents: 'auto',
  },
  FIRMS: {
    name: 'firmsPane',
    zIndex: 420,
    pointerEvents: 'auto',
  },
  OSINT: {
    name: 'osintPane',
    zIndex: 450,
    pointerEvents: 'auto',
  },
  HEATMAP: {
    name: 'heatmapPane',
    zIndex: 430,
    pointerEvents: 'none',
  },
  MEASURE: {
    name: 'measurePane',
    zIndex: 600,
    pointerEvents: 'auto',
  },
  USER_MARKERS: {
    name: 'userMarkersPane',
    zIndex: 650,
    pointerEvents: 'auto',
  },
  DRAWING: {
    name: 'drawingPane',
    zIndex: 700,
    pointerEvents: 'auto',
  },
};

export function ensureMapPanes(map) {
  Object.values(MAP_PANES).forEach((paneConfig) => {
    let pane = map.getPane(paneConfig.name);

    if (!pane) {
      pane = map.createPane(paneConfig.name);
    }

    pane.style.zIndex = String(paneConfig.zIndex);
    pane.style.pointerEvents = paneConfig.pointerEvents;
  });

  return MAP_PANES;
}

export function getPaneName(paneKey) {
  return MAP_PANES[paneKey]?.name || null;
}
