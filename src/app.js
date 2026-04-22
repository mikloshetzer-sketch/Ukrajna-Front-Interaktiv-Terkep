import { initMap } from './map/initMap.js';
import {
  createLayers,
  replaceOccupiedLayer,
  replaceBorderLayer,
  renderDeltaLayer,
  renderFirmsLayer,
  renderOsintLayer,
  renderFirmsHotspotBox,
  resetAllSavedDeltaLabels
} from './map/layers.js';
import { fetchDeepStateIndex, fetchDeepStateByFilename } from './data/deepstate.js';
import { computeNaiveDailyDelta } from './data/deepstateDelta.js';
import { enrichDeltaItemsWithPlaceNames } from './data/placeLookup.js';
import { fetchFirmsLayer } from './data/firms.js';
import { categorizeFirmsPoints, summarizeFirmsHotspots } from './data/firmsSummary.js';
import { fetchOsintFeed, summarizeOsintFeed, buildDashboardSummary } from './data/osintFeeds.js';
import { bindTimeline, setTimelineBounds, setTimelineValue } from './ui/timeline.js';
import { createPlayer } from './ui/player.js';
import { clamp } from './utils/date.js';

const bordersUrl = 'https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson';
const borderCountries = new Set([
  'Ukraine',
  'Russia',
  'Belarus',
  'Poland',
  'Slovakia',
  'Hungary',
  'Romania',
  'Moldova'
]);

const dom = {
  statusText: document.getElementById('statusText'),
  currentDate: document.getElementById('currentDate'),
  timeline: document.getElementById('timeline'),
  deltaSummary: document.getElementById('deltaSummary'),
  firmsSummary: document.getElementById('firmsSummary'),
  dailyDashboard: document.getElementById('dailyDashboard'),
  osintFeedList: document.getElementById('osintFeedList'),

  btnLatest: document.getElementById('btnLatest'),
  btnFit: document.getElementById('btnFit'),
  btnMinus7: document.getElementById('btnMinus7'),
  btnMinus30: document.getElementById('btnMinus30'),
  btnToday: document.getElementById('btnToday'),
  btnResetLabels: document.getElementById('btnResetLabels'),

  btnPlay: document.getElementById('btnPlay'),
  btnPause: document.getElementById('btnPause'),
  speedSelect: document.getElementById('speedSelect'),

  toggleOccupied: document.getElementById('toggleOccupied'),
  toggleDelta: document.getElementById('toggleDelta'),
  toggleBorders: document.getElementById('toggleBorders'),
  toggleFirms: document.getElementById('toggleFirms'),
  toggleOsint: document.getElementById('toggleOsint'),

  firmsWindow: document.getElementById('firmsWindow'),
};

const appState = {
  index: [],
  currentIndex: 0,
  cache: new Map(),
  latestDelta: null,
  latestFirmsSummary: null,
  latestOsintSummary: null,
};

const map = initMap();
const layerState = createLayers(map);

function setStatus(text) {
  dom.statusText.textContent = text;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} – ${url}`);
  }
  return response.json();
}

async function loadBorders() {
  const countries = await fetchJson(bordersUrl);

  const filtered = {
    type: 'FeatureCollection',
    features: (countries.features || []).filter(feature => {
      const name =
        feature?.properties?.ADMIN ||
        feature?.properties?.name ||
        feature?.properties?.NAME;

      return borderCountries.has(name);
    }),
  };

  replaceBorderLayer(map, layerState, filtered);
}

async function getGeoJsonAt(index) {
  const item = appState.index[index];
  if (!item) return null;

  if (!appState.cache.has(item.filename)) {
    const data = await fetchDeepStateByFilename(item.filename);
    appState.cache.set(item.filename, data);
  }

  return appState.cache.get(item.filename);
}

function updateDeltaSummary(delta) {
  const gainArea = delta?.totals?.gainedKm2 || 0;
  const lossArea = delta?.totals?.lostKm2 || 0;
  const shown = delta?.all?.length || 0;

  const gainText = (delta.gained || [])
    .map((item, i) => `#${i + 1}: ${item.sectorShortName || item.sectorName || 'Unknown'} / ${item.nearestPlace || 'Unknown place'}`)
    .join('<br>');

  const lossText = (delta.lost || [])
    .map((item, i) => `#${i + 1}: ${item.sectorShortName || item.sectorName || 'Unknown'} / ${item.nearestPlace || 'Unknown place'}`)
    .join('<br>');

  dom.deltaSummary.innerHTML = `
    Shown changes: <strong>${shown}</strong> / max. 5<br>
    Russian territorial gain total: <strong>${gainArea.toFixed(2)} km²</strong><br>
    Ukrainian recapture total: <strong>${lossArea.toFixed(2)} km²</strong>
    ${gainText ? `<hr style="margin:6px 0;"><div><b>Gain list</b><br>${gainText}</div>` : ''}
    ${lossText ? `<hr style="margin:6px 0;"><div><b>Recapture list</b><br>${lossText}</div>` : ''}
  `;
}

function zoneLine(zone, idx) {
  if (!zone) return `#${idx}: n/a`;
  return `#${idx}: ${zone.categoryLabel} / ${zone.sectorShortName || zone.sectorName || 'Unknown'} / ${zone.nearestPlace || 'Unknown'} / ${zone.count}`;
}

function updateFirmsSummary(summary) {
  if (!dom.firmsSummary) return;

  if (!summary?.topZone) {
    dom.firmsSummary.innerHTML = 'No FIRMS hotspot summary available.';
    return;
  }

  dom.firmsSummary.innerHTML = `
    <b>Top 3 FIRMS zones</b><br>
    ${summary.topThreeZones.map((zone, idx) => `${zoneLine(zone, idx + 1)}`).join('<br>')}
    <hr style="margin:6px 0;">
    <b>Category counts</b><br>
    Front-adjacent: <strong>${summary.countsByCategory.front}</strong><br>
    Ukrainian rear-area: <strong>${summary.countsByCategory.ukrainianRear}</strong><br>
    Russian rear-area: <strong>${summary.countsByCategory.russianRear}</strong><br>
    Other / grey: <strong>${summary.countsByCategory.other}</strong><br>
    Window: <strong>${summary.windowDays} days</strong><br>
    Total loaded: <strong>${summary.totalPoints}</strong>
  `;
}

function updateOsintFeedList(summary) {
  if (!dom.osintFeedList) return;

  if (!summary || !summary.latest.length) {
    dom.osintFeedList.innerHTML = 'No OSINT feed loaded yet.';
    return;
  }

  dom.osintFeedList.innerHTML = `
    <b>Latest OSINT items</b><br>
    ${summary.latest.map((item, idx) => `
      <div style="margin-bottom:8px;">
        <b>${idx + 1}. ${item.title || 'Untitled'}</b><br>
        ${item.sourceType || 'OSINT'} · ${item.date || 'Unknown date'}<br>
        ${item.sectorShortName || item.sectorName || 'Unknown sector'} · ${item.nearestPlace || 'Unknown place'}
        ${item.url ? `<div><a href="${item.url}" target="_blank" rel="noopener noreferrer">Open source</a></div>` : ''}
      </div>
    `).join('')}
    <hr style="margin:6px 0;">
    Total: <strong>${summary.total}</strong><br>
    ISW: <strong>${summary.isw}</strong><br>
    Ukrainian official: <strong>${summary.official}</strong><br>
    Other: <strong>${summary.other}</strong>
  `;
}

function updateDailyDashboard() {
  if (!dom.dailyDashboard) return;

  const summary = buildDashboardSummary({
    currentDate: dom.currentDate.textContent,
    delta: appState.latestDelta,
    firmsSummary: appState.latestFirmsSummary,
    osintSummary: appState.latestOsintSummary,
  });

  const topGain = summary.topGain;
  const topLoss = summary.topLoss;
  const topFirms = summary.topFirms;
  const osint = summary.osintSummary;

  dom.dailyDashboard.innerHTML = `
    <b>Operational picture</b><br>
    Date: <strong>${summary.currentDate || 'n/a'}</strong>
    <hr style="margin:6px 0;">
    <b>Top Russian gain</b><br>
    ${topGain ? `${topGain.sectorShortName || topGain.sectorName} · ${topGain.nearestPlace} · ${topGain.areaKm2.toFixed(2)} km²` : 'No major gain'}
    <hr style="margin:6px 0;">
    <b>Top Ukrainian recapture</b><br>
    ${topLoss ? `${topLoss.sectorShortName || topLoss.sectorName} · ${topLoss.nearestPlace} · ${topLoss.areaKm2.toFixed(2)} km²` : 'No major recapture'}
    <hr style="margin:6px 0;">
    <b>Top FIRMS zone</b><br>
    ${topFirms ? `${topFirms.categoryLabel} · ${topFirms.sectorShortName || topFirms.sectorName} · ${topFirms.nearestPlace} · ${topFirms.count} hotspots` : 'No FIRMS zone'}
    <hr style="margin:6px 0;">
    <b>OSINT feed</b><br>
    ${osint ? `Total ${osint.total} items · ISW ${osint.isw} · Official ${osint.official}` : 'No OSINT summary'}
  `;
}

async function renderAtIndex(index) {
  const item = appState.index[index];
  if (!item) return;

  appState.currentIndex = index;
  dom.currentDate.textContent = item.date;
  setTimelineValue(dom.timeline, index);
  setStatus(`Betöltés: ${item.date}`);

  const currentGeoJson = await getGeoJsonAt(index);
  if (!currentGeoJson) {
    setStatus(`Nincs adat: ${item.date}`);
    return;
  }

  replaceOccupiedLayer(map, layerState, currentGeoJson);

  if (index > 0) {
    const previousItem = appState.index[index - 1];
    const previousGeoJson = await getGeoJsonAt(index - 1);

    if (previousGeoJson) {
      const rawDelta = computeNaiveDailyDelta(previousGeoJson, currentGeoJson);
      const delta = enrichDeltaItemsWithPlaceNames(rawDelta);

      appState.latestDelta = delta;
      renderDeltaLayer(layerState, delta, item.date, previousItem.date);
      updateDeltaSummary(delta);
    } else {
      layerState.deltaLayer.clearLayers();
      dom.deltaSummary.textContent = 'Az előző napi adat nem érhető el.';
      appState.latestDelta = null;
    }
  } else {
    layerState.deltaLayer.clearLayers();
    dom.deltaSummary.textContent = 'A legelső betöltött naphoz nincs előző napi összehasonlítás.';
    appState.latestDelta = null;
  }

  if (dom.toggleFirms.checked) {
    await refreshFirms();
  }

  if (dom.toggleOsint.checked) {
    await refreshOsint();
  }

  updateDailyDashboard();
  setStatus(`Betöltve: ${item.date}`);
}

async function refreshFirms() {
  try {
    if (!dom.toggleFirms.checked) {
      layerState.firmsLayer.clearLayers();
      layerState.firmsHotspotLayer.clearLayers();
      if (map.hasLayer(layerState.firmsLayer)) {
        map.removeLayer(layerState.firmsLayer);
      }
      if (map.hasLayer(layerState.firmsHotspotLayer)) {
        map.removeLayer(layerState.firmsHotspotLayer);
      }
      appState.latestFirmsSummary = null;
      updateFirmsSummary(null);
      updateDailyDashboard();
      return;
    }

    const windowDays = Number(dom.firmsWindow.value);
    const firmsRaw = await fetchFirmsLayer(windowDays);
    const firms = categorizeFirmsPoints(firmsRaw);

    renderFirmsLayer(layerState, firms);

    const summary = summarizeFirmsHotspots(firms, windowDays);
    appState.latestFirmsSummary = summary;

    renderFirmsHotspotBox(layerState, summary);
    updateFirmsSummary(summary);
    updateDailyDashboard();

    if (!map.hasLayer(layerState.firmsLayer)) {
      layerState.firmsLayer.addTo(map);
    }
    if (!map.hasLayer(layerState.firmsHotspotLayer)) {
      layerState.firmsHotspotLayer.addTo(map);
    }
  } catch (error) {
    console.error('FIRMS hiba:', error);
    setStatus(`FIRMS hiba: ${error.message}`);
  }
}

async function refreshOsint() {
  try {
    if (!dom.toggleOsint.checked) {
      layerState.osintLayer.clearLayers();
      if (map.hasLayer(layerState.osintLayer)) {
        map.removeLayer(layerState.osintLayer);
      }
      appState.latestOsintSummary = null;
      updateOsintFeedList(null);
      updateDailyDashboard();
      return;
    }

    const feed = await fetchOsintFeed();
    renderOsintLayer(layerState, feed);

    const summary = summarizeOsintFeed(feed);
    appState.latestOsintSummary = summary;

    updateOsintFeedList(summary);
    updateDailyDashboard();

    if (!map.hasLayer(layerState.osintLayer)) {
      layerState.osintLayer.addTo(map);
    }
  } catch (error) {
    console.error('OSINT hiba:', error);
    setStatus(`OSINT hiba: ${error.message}`);
  }
}

function bindLayerToggles() {
  dom.toggleOccupied.addEventListener('change', () => {
    if (dom.toggleOccupied.checked) {
      layerState.occupiedLayer.addTo(map);
    } else {
      map.removeLayer(layerState.occupiedLayer);
    }
  });

  dom.toggleDelta.addEventListener('change', () => {
    if (dom.toggleDelta.checked) {
      layerState.deltaLayer.addTo(map);
    } else {
      map.removeLayer(layerState.deltaLayer);
    }
  });

  dom.toggleBorders.addEventListener('change', () => {
    if (dom.toggleBorders.checked) {
      layerState.borderLayer.addTo(map);
    } else {
      map.removeLayer(layerState.borderLayer);
    }
  });

  dom.toggleFirms.addEventListener('change', refreshFirms);
  dom.toggleOsint.addEventListener('change', refreshOsint);
  dom.firmsWindow.addEventListener('change', refreshFirms);
}

function bindControls(player) {
  dom.btnFit.addEventListener('click', () => {
    map.setView([48.5, 33.5], 6);
  });

  dom.btnLatest.addEventListener('click', async () => {
    if (!appState.index.length) return;
    await renderAtIndex(appState.index.length - 1);
  });

  dom.btnToday.addEventListener('click', async () => {
    if (!appState.index.length) return;
    await renderAtIndex(appState.index.length - 1);
  });

  dom.btnMinus7.addEventListener('click', async () => {
    if (!appState.index.length) return;
    const target = clamp(appState.currentIndex - 7, 0, appState.index.length - 1);
    await renderAtIndex(target);
  });

  dom.btnMinus30.addEventListener('click', async () => {
    if (!appState.index.length) return;
    const target = clamp(appState.currentIndex - 30, 0, appState.index.length - 1);
    await renderAtIndex(target);
  });

  dom.btnPlay.addEventListener('click', () => {
    player.play(Number(dom.speedSelect.value));
  });

  dom.btnPause.addEventListener('click', () => {
    player.stop();
  });

  dom.btnResetLabels?.addEventListener('click', () => {
    resetAllSavedDeltaLabels(layerState);
  });
}

bindTimeline({
  input: dom.timeline,
  onChange: async (value) => {
    await renderAtIndex(Number(value));
  },
});

const player = createPlayer({
  onTick: async (value) => {
    await renderAtIndex(value);
  },
  getMaxIndex: () => appState.index.length - 1,
  getCurrentIndex: () => appState.currentIndex,
  setCurrentIndex: (value) => {
    appState.currentIndex = value;
  },
});

async function init() {
  try {
    setStatus('DeepState index betöltése…');

    const files = await fetchDeepStateIndex();
    appState.index = files.map(item => ({
      filename: item.name,
      date: item.date,
    }));

    if (!appState.index.length) {
      throw new Error('Nem található 2024-01-01 utáni DeepState napi adat.');
    }

    setTimelineBounds(dom.timeline, appState.index.length - 1);

    await loadBorders();
    await renderAtIndex(appState.index.length - 1);

    bindLayerToggles();
    bindControls(player);

    setStatus('Kész');
  } catch (error) {
    console.error('Init hiba:', error);
    setStatus(`Hiba: ${error.message}`);
  }
}

init();
