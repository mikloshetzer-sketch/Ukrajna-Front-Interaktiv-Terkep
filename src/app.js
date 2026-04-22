import { initMap } from './map/initMap.js';
import {
  createLayers,
  replaceOccupiedLayer,
  replaceBorderLayer,
  renderDeltaLayer,
  renderFirmsLayer,
  renderOsintLayer,
  renderOsintHighlights,
  renderFirmsHotspotBox,
  renderHeatmapLayer,
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
  sectorBalanceSummary: document.getElementById('sectorBalanceSummary'),
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
  toggleHeatmap: document.getElementById('toggleHeatmap'),

  firmsWindow: document.getElementById('firmsWindow'),
};

const appState = {
  index: [],
  currentIndex: 0,
  cache: new Map(),
  latestDelta: null,
  latestFirmsSummary: null,
  latestFirmsPoints: [],
  latestOsintSummary: null,
  latestHeatmapPoints: [],
};

const map = initMap();
const layerState = createLayers(map);

function setStatus(text) {
  dom.statusText.textContent = text;
}

function getOsintCategoryIcon(category) {
  const normalized = String(category || 'general').toLowerCase();

  if (normalized.includes('drone')) return '🛸';
  if (normalized.includes('missile')) return '🚀';
  if (normalized.includes('air defense')) return '🛡';
  if (normalized.includes('assault')) return '⚔';
  if (normalized.includes('logistics')) return '🚛';
  if (normalized.includes('artillery')) return '💥';
  if (normalized.includes('electronic warfare')) return '📡';
  if (normalized.includes('naval')) return '⚓';
  if (normalized.includes('aviation')) return '✈';
  if (normalized.includes('armor') || normalized.includes('armour') || normalized.includes('tank')) return '🪖';

  return '📍';
}

function getThreatLevel(score) {
  if (score >= 11) return 'CRITICAL';
  if (score >= 7) return 'HIGH';
  if (score >= 4) return 'MEDIUM';
  return 'LOW';
}

function getThreatBadge(level) {
  if (level === 'CRITICAL') return '<span style="color:#7f1d1d;"><b>CRITICAL</b></span>';
  if (level === 'HIGH') return '<span style="color:#b91c1c;"><b>HIGH</b></span>';
  if (level === 'MEDIUM') return '<span style="color:#b45309;"><b>MEDIUM</b></span>';
  return '<span style="color:#166534;"><b>LOW</b></span>';
}

function getClusterSeverity(cluster) {
  let score = 0;

  score += Math.min(Number(cluster.reportCount || 1), 4);

  if (cluster.sourceType === 'Ukrainian official') score += 2;
  else if (cluster.sourceType === 'ISW') score += 1;

  const category = String(cluster.category || '').toLowerCase();
  if (category.includes('assault')) score += 3;
  else if (category.includes('drone')) score += 2;
  else if (category.includes('missile')) score += 3;
  else if (category.includes('air defense')) score += 2;
  else if (category.includes('artillery')) score += 2;
  else if (category.includes('logistics')) score += 1;

  if ((cluster.sectorShortName || cluster.sectorName || '').toLowerCase().includes('outside')) {
    score -= 1;
  }

  return getThreatLevel(score);
}

function addClusterSeverity(summary) {
  if (!summary) return null;

  const clusters = (summary.clusters || []).map(cluster => ({
    ...cluster,
    severity: getClusterSeverity(cluster),
  }));

  const topFive = clusters
    .slice()
    .sort((a, b) => {
      const severityOrder = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
      const sevDiff = (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0);
      if (sevDiff !== 0) return sevDiff;

      const impDiff = (b.importance || 0) - (a.importance || 0);
      if (impDiff !== 0) return impDiff;

      return (b.reportCount || 0) - (a.reportCount || 0);
    })
    .slice(0, 5);

  return {
    ...summary,
    clusters,
    topFive,
  };
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

function buildOsintCategorySummary(summary) {
  const counts = new Map();

  (summary?.clusters || []).forEach(cluster => {
    const category = cluster.category || 'general military update';
    counts.set(category, (counts.get(category) || 0) + 1);
  });

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([category, count]) => {
      const icon = getOsintCategoryIcon(category);
      return `<div>${icon} ${category}: <strong>${count}</strong></div>`;
    })
    .join('');
}

function updateOsintFeedList(summary) {
  if (!dom.osintFeedList) return;

  if (!summary || !summary.topFive.length) {
    dom.osintFeedList.innerHTML = 'No OSINT feed loaded yet.';
    return;
  }

  dom.osintFeedList.innerHTML = `
    <b>Top 5 OSINT clusters</b><br>
    ${summary.topFive.map((item, idx) => {
      const icon = getOsintCategoryIcon(item.category);
      return `
        <div style="margin-bottom:8px;">
          <b>${idx + 1}. ${icon} ${item.title || 'Untitled'}</b><br>
          ${item.sourceType || 'OSINT'} · ${item.date || 'Unknown date'}<br>
          ${item.sectorShortName || item.sectorName || 'Unknown sector'} · ${item.nearestPlace || 'Unknown place'}<br>
          Reports: ${item.reportCount || 1} · Category: ${icon} ${item.category || 'general military update'}<br>
          Severity: ${getThreatBadge(item.severity || 'LOW')}<br>
          <span style="color:#444;">Latest: ${item.latestTitle || item.title || 'Untitled'}</span>
          ${item.urls?.length ? item.urls.map((url, i) => `<div><a href="${url}" target="_blank" rel="noopener noreferrer">Open source ${i + 1}</a></div>`).join('') : ''}
        </div>
      `;
    }).join('')}
    <hr style="margin:6px 0;">
    <b>OSINT categories</b><br>
    ${buildOsintCategorySummary(summary)}
    <hr style="margin:6px 0;">
    Total raw items: <strong>${summary.total}</strong><br>
    Clusters: <strong>${summary.clusters?.length || 0}</strong><br>
    ISW: <strong>${summary.isw}</strong><br>
    Ukrainian official: <strong>${summary.official}</strong><br>
    Other: <strong>${summary.other}</strong>
  `;
}

function buildSectorBalance(delta, osintSummary, firmsPoints) {
  const sectors = new Map();

  function ensureSector(name) {
    if (!sectors.has(name)) {
      sectors.set(name, {
        name,
        ruGainKm2: 0,
        uaRecaptureKm2: 0,
        osintClusters: 0,
        firmsPoints: 0,
        threatScore: 0,
        threatLevel: 'LOW',
      });
    }
    return sectors.get(name);
  }

  (delta?.gained || []).forEach(item => {
    const name = item.sectorShortName || item.sectorName || 'Unknown sector';
    const sector = ensureSector(name);
    sector.ruGainKm2 += Number(item.areaKm2 || 0);
  });

  (delta?.lost || []).forEach(item => {
    const name = item.sectorShortName || item.sectorName || 'Unknown sector';
    const sector = ensureSector(name);
    sector.uaRecaptureKm2 += Number(item.areaKm2 || 0);
  });

  (osintSummary?.clusters || []).forEach(cluster => {
    const name = cluster.sectorShortName || cluster.sectorName || 'Unknown sector';
    const sector = ensureSector(name);
    sector.osintClusters += 1;

    if (cluster.severity === 'CRITICAL') sector.threatScore += 4;
    else if (cluster.severity === 'HIGH') sector.threatScore += 3;
    else if (cluster.severity === 'MEDIUM') sector.threatScore += 2;
    else sector.threatScore += 1;
  });

  (firmsPoints || []).forEach(point => {
    const name = point.sectorShortName || point.sectorName || 'Unknown sector';
    const sector = ensureSector(name);
    sector.firmsPoints += 1;
  });

  [...sectors.values()].forEach(sector => {
    sector.threatScore += Math.min(sector.ruGainKm2 / 2, 4);
    sector.threatScore += Math.min(sector.uaRecaptureKm2 / 2, 3);
    sector.threatScore += Math.min(sector.firmsPoints / 8, 4);
    sector.threatLevel = getThreatLevel(sector.threatScore);
  });

  return [...sectors.values()]
    .filter(item =>
      item.ruGainKm2 > 0 ||
      item.uaRecaptureKm2 > 0 ||
      item.osintClusters > 0 ||
      item.firmsPoints > 0
    )
    .sort((a, b) => b.threatScore - a.threatScore);
}

function updateSectorBalanceSummary() {
  if (!dom.sectorBalanceSummary) return;

  const rows = buildSectorBalance(
    appState.latestDelta,
    appState.latestOsintSummary,
    appState.latestFirmsPoints
  );

  if (!rows.length) {
    dom.sectorBalanceSummary.innerHTML = 'Nincs még napi szektormérleg.';
    return;
  }

  dom.sectorBalanceSummary.innerHTML = rows
    .map(row => {
      const ru = row.ruGainKm2 > 0
        ? `<div><span style="color:#b91c1c;"><b>RU gain:</b> ${row.ruGainKm2.toFixed(2)} km²</span></div>`
        : '';

      const ua = row.uaRecaptureKm2 > 0
        ? `<div><span style="color:#1d4ed8;"><b>UA recapture:</b> ${row.uaRecaptureKm2.toFixed(2)} km²</span></div>`
        : '';

      const osint = row.osintClusters > 0
        ? `<div><span style="color:#444;"><b>OSINT clusters:</b> ${row.osintClusters}</span></div>`
        : '';

      const firms = row.firmsPoints > 0
        ? `<div><span style="color:#444;"><b>FIRMS points:</b> ${row.firmsPoints}</span></div>`
        : '';

      return `
        <div style="margin-bottom:10px;">
          <div><b>${row.name}</b></div>
          <div><b>Threat:</b> ${getThreatBadge(row.threatLevel)}</div>
          ${ru}
          ${ua}
          ${osint}
          ${firms}
        </div>
      `;
    })
    .join('<hr style="margin:6px 0;">');
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
  const topOsint = summary.topOsint;
  const osint = summary.osintSummary;

  const sectorRows = buildSectorBalance(
    appState.latestDelta,
    appState.latestOsintSummary,
    appState.latestFirmsPoints
  );
  const topThreatSector = sectorRows[0] || null;

  dom.dailyDashboard.innerHTML = `
    <b>Operational picture</b><br>
    Date: <strong>${summary.currentDate || 'n/a'}</strong>
    <hr style="margin:6px 0;">
    <b>Top threat sector</b><br>
    ${topThreatSector ? `${topThreatSector.name} · ${getThreatBadge(topThreatSector.threatLevel)}` : 'No threat sector'}
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
    <b>Top OSINT cluster</b><br>
    ${topOsint ? `${getOsintCategoryIcon(topOsint.category)} ${topOsint.sourceType} · ${topOsint.sectorShortName || topOsint.sectorName} · ${topOsint.nearestPlace} · ${topOsint.reportCount} reports · ${getThreatBadge(topOsint.severity || 'LOW')}` : 'No OSINT cluster'}
    <hr style="margin:6px 0;">
    <b>OSINT categories</b><br>
    ${osint ? buildOsintCategorySummary(osint) : 'No category summary'}
    <hr style="margin:6px 0;">
    <b>OSINT feed</b><br>
    ${osint ? `Raw ${osint.total} items · Clusters ${osint.clusters?.length || 0} · ISW ${osint.isw} · Official ${osint.official}` : 'No OSINT summary'}
  `;
}

function buildHeatmapPoints() {
  const points = [];

  (appState.latestDelta?.gained || []).forEach(item => {
    points.push({
      lat: Number(item.lat),
      lng: Number(item.lng),
      weight: Math.min(1, 0.35 + Number(item.areaKm2 || 0) / 12)
    });
  });

  (appState.latestDelta?.lost || []).forEach(item => {
    points.push({
      lat: Number(item.lat),
      lng: Number(item.lng),
      weight: Math.min(1, 0.30 + Number(item.areaKm2 || 0) / 14)
    });
  });

  (appState.latestFirmsPoints || []).forEach(point => {
    points.push({
      lat: Number(point.lat),
      lng: Number(point.lng),
      weight: 0.12
    });
  });

  (appState.latestOsintSummary?.clusters || []).forEach(cluster => {
    let severityBoost = 0.2;
    if (cluster.severity === 'CRITICAL') severityBoost = 0.5;
    else if (cluster.severity === 'HIGH') severityBoost = 0.4;
    else if (cluster.severity === 'MEDIUM') severityBoost = 0.3;

    points.push({
      lat: Number(cluster.lat),
      lng: Number(cluster.lng),
      weight: Math.min(1, severityBoost + Math.min(Number(cluster.reportCount || 1) * 0.08, 0.35))
    });
  });

  return points.filter(point =>
    Number.isFinite(point.lat) &&
    Number.isFinite(point.lng) &&
    Number.isFinite(point.weight)
  );
}

function refreshHeatmap() {
  appState.latestHeatmapPoints = buildHeatmapPoints();
  renderHeatmapLayer(layerState, appState.latestHeatmapPoints);

  if (!layerState.heatmapLayer) return;

  if (dom.toggleHeatmap.checked) {
    if (!map.hasLayer(layerState.heatmapLayer)) {
      layerState.heatmapLayer.addTo(map);
    }
  } else {
    if (map.hasLayer(layerState.heatmapLayer)) {
      map.removeLayer(layerState.heatmapLayer);
    }
  }
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
  updateSectorBalanceSummary();
  refreshHeatmap();
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
      appState.latestFirmsPoints = [];
      updateFirmsSummary(null);
      updateDailyDashboard();
      updateSectorBalanceSummary();
      refreshHeatmap();
      return;
    }

    const windowDays = Number(dom.firmsWindow.value);
    const firmsRaw = await fetchFirmsLayer(windowDays);
    const firms = categorizeFirmsPoints(firmsRaw);

    appState.latestFirmsPoints = firms;
    renderFirmsLayer(layerState, firms);

    const summary = summarizeFirmsHotspots(firms, windowDays);
    appState.latestFirmsSummary = summary;

    renderFirmsHotspotBox(layerState, summary);
    updateFirmsSummary(summary);
    updateDailyDashboard();
    updateSectorBalanceSummary();
    refreshHeatmap();

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
      layerState.osintHighlightLayer.clearLayers();

      if (map.hasLayer(layerState.osintLayer)) {
        map.removeLayer(layerState.osintLayer);
      }
      if (map.hasLayer(layerState.osintHighlightLayer)) {
        map.removeLayer(layerState.osintHighlightLayer);
      }

      appState.latestOsintSummary = null;
      updateOsintFeedList(null);
      updateDailyDashboard();
      updateSectorBalanceSummary();
      refreshHeatmap();
      return;
    }

    const feed = await fetchOsintFeed();
    const summary = addClusterSeverity(summarizeOsintFeed(feed));
    appState.latestOsintSummary = summary;

    const rawPointsWithSeverity = feed.map(point => {
      const matchingCluster = (summary?.clusters || []).find(cluster =>
        cluster.items?.some(item =>
          Number(item.lat) === Number(point.lat) &&
          Number(item.lng) === Number(point.lng) &&
          item.title === point.title
        )
      );

      return {
        ...point,
        severity: matchingCluster?.severity || 'LOW',
      };
    });

    renderOsintLayer(layerState, rawPointsWithSeverity);
    renderOsintHighlights(layerState, summary);
    updateOsintFeedList(summary);
    updateDailyDashboard();
    updateSectorBalanceSummary();
    refreshHeatmap();

    if (!map.hasLayer(layerState.osintLayer)) {
      layerState.osintLayer.addTo(map);
    }
    if (!map.hasLayer(layerState.osintHighlightLayer)) {
      layerState.osintHighlightLayer.addTo(map);
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
  dom.toggleHeatmap.addEventListener('change', refreshHeatmap);
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
