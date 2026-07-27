import { initMap } from './map/initMap.js';
import { ensureMapPanes } from './map/panes.js';
import { SatelliteImageLayer } from './satellite/satelliteLayer.js';
import { initSatelliteControls } from './satellite/satelliteControls.js';
import {
  createLayers,
  replaceOccupiedLayer,
  replaceBorderLayer,
  replaceFrontlineLayer,
  renderDeltaLayer,
  renderHistoricalDeltaLayer,
  renderFirmsLayer,
  renderOsintLayer,
  renderOsintHighlights,
  renderFirmsHotspotBox,
  renderHeatmapLayer,
  renderAttackAxes,
  renderBattleNodes,
  renderSuriyakLayer,
  setSatelliteContrastMode,
  resetAllSavedDeltaLabels,
  renderDeepStrikesLayer,
  resetAllSavedDeepStrikeLabels
} from './map/layers.js';
import { initAnnotations } from './map/annotations.js';
import { initCoordinateMarkers } from './map/coordinateMarkers.js';
import { initMeasureTool } from './map/measureTool.js';
import { initObjectIdentificationTool } from './map/objectIdentificationTool.js';
import { fetchDeepStateIndex, fetchDeepStateByFilename } from './data/deepstate.js';
import { computeNaiveDailyDelta } from './data/deepstateDelta.js';
import { enrichDeltaItemsWithPlaceNames } from './data/placeLookup.js';
import { fetchFirmsLayer } from './data/firms.js';
import { categorizeFirmsPoints, summarizeFirmsHotspots } from './data/firmsSummary.js';
import { fetchOsintFeed, summarizeOsintFeed, buildDashboardSummary } from './data/osintFeeds.js';
import { fetchDeepStrikes } from './data/deepStrikes.js';
import { bindTimeline, setTimelineBounds, setTimelineValue } from './ui/timeline.js';
import { createPlayer } from './ui/player.js';
import { clamp } from './utils/date.js';

const OSINT_FEED_LIMIT = 8;

const bordersUrl = 'https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson';
const historicalDeltaUrl = './data/territorial_delta_30days.geojson';
const suriyakOverlayUrl = './data/suriyak_overlay.geojson';
const suriyakLegendUrl = './data/suriyak_legend.json';
const SURIYAK_CATEGORY_STORAGE_KEY = 'ukraine_front_suriyak_category_selection_v1';

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
  historicalDeltaSummary: document.getElementById('historicalDeltaSummary'),
  historicalDeltaLegend: document.getElementById('historicalDeltaLegend'),
  firmsSummary: document.getElementById('firmsSummary'),
  dailyDashboard: document.getElementById('dailyDashboard'),
  autoOpsSummary: document.getElementById('autoOpsSummary'),
  topThreatSectors: document.getElementById('topThreatSectors'),
  sectorBalanceSummary: document.getElementById('sectorBalanceSummary'),
  osintFeedList: document.getElementById('osintFeedList'),

  toolboxMode: document.getElementById('toolboxMode'),
  toolboxObjectType: document.getElementById('toolboxObjectType'),
  toolboxDrawShape: document.getElementById('toolboxDrawShape'),
  toolboxDrawColor: document.getElementById('toolboxDrawColor'),
  btnToolboxUndoDrawing: document.getElementById('btnToolboxUndoDrawing'),
  btnToolboxClearDrawings: document.getElementById('btnToolboxClearDrawings'),
  btnToolboxClearMarkers: document.getElementById('btnToolboxClearMarkers'),
  btnToolboxExportGeoJson: document.getElementById('btnToolboxExportGeoJson'),
  toolboxStatus: document.getElementById('toolboxStatus'),

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
  toggleFrontline: document.getElementById('toggleFrontline'),
  toggleSuriyak: document.getElementById('toggleSuriyak'),
  toggleSatelliteContrast: document.getElementById('toggleSatelliteContrast'),
  toggleSatellite: document.getElementById('toggleSatellite'),
  satelliteLocationSelect: document.getElementById('satelliteLocationSelect'),
  satelliteImageSelect: document.getElementById('satelliteImageSelect'),
  satelliteOpacity: document.getElementById('satelliteOpacity'),
  satelliteOpacityValue: document.getElementById('satelliteOpacityValue'),
  satelliteSummary: document.getElementById('satelliteSummary'),
  btnSatelliteFit: document.getElementById('btnSatelliteFit'),
  btnSatelliteRefresh: document.getElementById('btnSatelliteRefresh'),
  toggleAxes: document.getElementById('toggleAxes'),
  toggleBattleNodes: document.getElementById('toggleBattleNodes'),
  toggleDelta: document.getElementById('toggleDelta'),
  toggleHistoricalDelta: document.getElementById('toggleHistoricalDelta'),
  toggleAnnotations: document.getElementById('toggleAnnotations'),
  toggleBorders: document.getElementById('toggleBorders'),
  toggleFirms: document.getElementById('toggleFirms'),
  toggleOsint: document.getElementById('toggleOsint'),
  toggleHeatmap: document.getElementById('toggleHeatmap'),

  // Deep strike controls are optional until index.html is extended.
  toggleDeepStrikes: document.getElementById('toggleDeepStrikes'),
  deepStrikesDate: document.getElementById('deepStrikesDate'),
  deepStrikesWindow: document.getElementById('deepStrikesWindow'),
  toggleDeepStrikesUaRu: document.getElementById('toggleDeepStrikesUaRu'),
  toggleDeepStrikesRuUa: document.getElementById('toggleDeepStrikesRuUa'),
  toggleDeepStrikeLabels: document.getElementById('toggleDeepStrikeLabels'),
  btnResetDeepStrikeLabels: document.getElementById('btnResetDeepStrikeLabels'),
  deepStrikesSummary: document.getElementById('deepStrikesSummary'),

  suriyakSubpanel: document.getElementById('suriyakSubpanel'),
  suriyakLayerMeta: document.getElementById('suriyakLayerMeta'),
  suriyakCategoryList: document.getElementById('suriyakCategoryList'),
  suriyakLegendNote: document.getElementById('suriyakLegendNote'),
  satelliteContrastNote: document.getElementById('satelliteContrastNote'),

  historicalDeltaWindow: document.getElementById('historicalDeltaWindow'),
  firmsWindow: document.getElementById('firmsWindow'),

  btnAddAnnotation: document.getElementById('btnAddAnnotation'),
  btnClearAnnotations: document.getElementById('btnClearAnnotations'),
  annotationText: document.getElementById('annotationText'),
  annotationType: document.getElementById('annotationType'),
  annotationsSummary: document.getElementById('annotationsSummary'),
};

const appState = {
  index: [],
  currentIndex: 0,
  cache: new Map(),
  latestDelta: null,
  historicalDelta: null,
  suriyakOverlay: null,
  suriyakLegend: null,
  suriyakSelectedCategories: null,
  annotationsController: null,
  latestFirmsSummary: null,
  latestFirmsPoints: [],
  latestOsintSummary: null,
  latestHeatmapPoints: [],
  latestAttackAxes: [],
  latestBattleNodes: [],
  deepStrikes: [],
  deepStrikesLoaded: false,
  deepStrikesSummary: null,
  coordinateMarkersController: null,
  measureToolController: null,
  objectIdentificationController: null,
  satelliteController: null,

  analysisDrawings: [],
  analysisDraftPoints: [],
  analysisDrawClickBound: false,
  analysisDrawNativeHandler: null,
};

const map = initMap();
ensureMapPanes(map);
const layerState = createLayers(map);
const satelliteImageLayer = new SatelliteImageLayer(map, {
  opacity: 0.72,
  fitOnLoad: false,
});
const coordinateMarkerLayer = L.layerGroup().addTo(map);
const measureLayer = L.layerGroup().addTo(map);
const objectIdentificationLayer = L.layerGroup().addTo(map);

// Elemző rajzolás: teljesen külön rétegek, hogy a meglévő Toolbox eszközöket ne érintse.
const analysisDrawingLayer = L.layerGroup().addTo(map);
const analysisDraftLayer = L.layerGroup().addTo(map);

function setStatus(text) {
  dom.statusText.textContent = text;
}

function getHistoricalColor(dayIndexFromLatest) {
  const day = Number(dayIndexFromLatest || 0);

  if (day === 0) return '#7f1d1d';
  if (day <= 2) return '#b91c1c';
  if (day <= 5) return '#dc2626';
  if (day <= 10) return '#ea580c';
  if (day <= 15) return '#ca8a04';

  return '#facc15';
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
  else if (cluster.sourceType === 'GeoConfirmed') score += 2;
  else if (cluster.sourceType === 'Critical Threats') score += 1;
  else if (cluster.sourceType === 'Hungarian media') score += 1;

  const category = String(cluster.category || '').toLowerCase();
  if (category.includes('assault')) score += 3;
  else if (category.includes('drone')) score += 2;
  else if (category.includes('missile')) score += 3;
  else if (category.includes('air defense')) score += 2;
  else if (category.includes('artillery')) score += 2;
  else if (category.includes('logistics')) score += 1;
  else if (category.includes('rear area')) score += 2;

  const freshnessHours = Number(cluster.freshnessHours || 999);
  if (freshnessHours <= 12) score += 2;
  else if (freshnessHours <= 24) score += 1;
  else if (freshnessHours <= 36) score += 0.5;

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

      const freshDiff = Number(a.freshnessHours || 999) - Number(b.freshnessHours || 999);
      if (freshDiff !== 0) return freshDiff;

      return (b.reportCount || 0) - (a.reportCount || 0);
    })
    .slice(0, OSINT_FEED_LIMIT);

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

async function loadHistoricalDelta() {
  if (appState.historicalDelta) {
    return appState.historicalDelta;
  }

  appState.historicalDelta = await fetchJson(historicalDeltaUrl);
  return appState.historicalDelta;
}


function loadSavedSuriyakCategorySelection() {
  try {
    const raw = localStorage.getItem(SURIYAK_CATEGORY_STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;

    return new Set(parsed.map(item => String(item)));
  } catch (error) {
    console.warn('Could not load saved Suriyak category selection:', error);
    return null;
  }
}

function saveSuriyakCategorySelection() {
  try {
    const values = [...(appState.suriyakSelectedCategories || new Set())];
    localStorage.setItem(SURIYAK_CATEGORY_STORAGE_KEY, JSON.stringify(values));
  } catch (error) {
    console.warn('Could not save Suriyak category selection:', error);
  }
}

function getSuriyakCategoriesFromLegend(legend) {
  return Array.isArray(legend?.categories) ? legend.categories : [];
}


const suriyakHungarianLabels = {
  current_frontline: 'Jelenlegi fő frontvonal',
  historical_frontline: 'Történelmi frontvonalak',
  russian_control: 'Orosz ellenőrzésű területek',
  ukrainian_control: 'Ukrán ellenőrzés / AFU állások',
  russian_defense_line: 'Orosz védelmi vonalak',
  historical_border_2014: '2014-es határvonalak és korábbi érintkezési vonalak',
  operational_sector: 'Műveleti szektorok / regionális területek',
  other_suriyak: 'Egyéb Suriyak rétegek'
};

const suriyakHungarianDescriptions = {
  current_frontline: 'A Suriyak által jelölt jelenlegi vagy fő érintkezési vonal. DeepState mellé kapcsolva összehasonlító rétegként érdemes használni.',
  historical_frontline: 'Korábbi, dátummal jelölt frontvonalak és történeti érintkezési vonalak. Nem aktuális frontként, hanem összehasonlítási háttérként kezelendők.',
  russian_control: 'Orosz vagy oroszbarát erőkhöz kötött ellenőrzési területek, illetve ezek határvonalai.',
  ukrainian_control: 'Ukrán fegyveres erőkhöz vagy ukrán ellenőrzésű állásokhoz kötött területek és pozíciók.',
  russian_defense_line: 'Orosz védelmi övek, előkészített védelmi vonalak és erődítési jellegű vonalas elemek.',
  historical_border_2014: '2014-es határvonalak, korábbi érintkezési vonalak és régebbi pozíciós hivatkozások.',
  operational_sector: 'Térségi vagy műveleti szektorokat jelölő Suriyak elemek, például Szumi, Harkiv, Donyeck, Zaporizzsja vagy Herszon térségében.',
  other_suriyak: 'Automatikusan nem besorolt Suriyak elemek. Elemzési következtetés előtt külön ellenőrzést igényelnek.'
};

function getSuriyakHungarianLabel(category) {
  const id = category?.id || 'other_suriyak';
  return suriyakHungarianLabels[id] || category?.label || id;
}

function getSuriyakHungarianDescription(category) {
  const id = category?.id || 'other_suriyak';
  return suriyakHungarianDescriptions[id] || category?.description || '';
}

function formatSuriyakNumber(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat('hu-HU', { maximumFractionDigits: 0 }).format(number);
}

function getSuriyakCategoryColor(category) {
  return (
    category?.display?.fillColor ||
    category?.display?.color ||
    category?.style_colors?.[0]?.color ||
    '#757575'
  );
}

function ensureSuriyakCategorySelection(legend) {
  const categories = getSuriyakCategoriesFromLegend(legend);
  const ids = categories.map(category => category.id).filter(Boolean);

  if (!appState.suriyakSelectedCategories) {
    const saved = loadSavedSuriyakCategorySelection();
    appState.suriyakSelectedCategories = saved || new Set(ids);
  }

  ids.forEach(id => {
    if (!appState.suriyakSelectedCategories.has(id) && appState.suriyakSelectedCategories.size === 0) {
      appState.suriyakSelectedCategories.add(id);
    }
  });

  return appState.suriyakSelectedCategories;
}

async function loadSuriyakLegend() {
  if (appState.suriyakLegend) {
    return appState.suriyakLegend;
  }

  appState.suriyakLegend = await fetchJson(suriyakLegendUrl);
  return appState.suriyakLegend;
}

function updateSuriyakSubpanelVisibility(isVisible) {
  if (!dom.suriyakSubpanel) return;
  dom.suriyakSubpanel.classList.toggle('is-open', Boolean(isVisible));
}

function buildSuriyakCategoryList(legend) {
  if (!dom.suriyakCategoryList) return;

  const categories = getSuriyakCategoriesFromLegend(legend);
  if (!categories.length) {
    dom.suriyakCategoryList.innerHTML = `
      <div class="suriyak-legend-empty">
        Nincs elérhető Suriyak kategória a legend fájlban.
      </div>
    `;
    return;
  }

  const selected = ensureSuriyakCategorySelection(legend);

  dom.suriyakCategoryList.innerHTML = categories.map(category => {
    const id = category.id;
    const checked = selected.has(id) ? 'checked' : '';
    const color = getSuriyakCategoryColor(category);
    const count = Number(category.feature_count || 0);
    const lengthKm = Number(category.total_length_km || 0);
    const areaKm2 = Number(category.total_area_km2 || 0);
    const metricParts = [];

    if (lengthKm > 0) metricParts.push(`${formatSuriyakNumber(lengthKm)} km`);
    if (areaKm2 > 0) metricParts.push(`${formatSuriyakNumber(areaKm2)} km²`);

    const metricText = metricParts.length ? ` • ${metricParts.join(' • ')}` : '';

    return `
      <label class="suriyak-category-row" title="${getSuriyakHungarianDescription(category)}">
        <input
          type="checkbox"
          class="suriyak-category-toggle"
          data-category-id="${id}"
          ${checked}
        />
        <span class="suriyak-swatch" style="background:${color};"></span>
        <span>${getSuriyakHungarianLabel(category)}</span>
        <span class="suriyak-category-count">${formatSuriyakNumber(count)} objektum${metricText}</span>
      </label>
    `;
  }).join('');
}

function updateSuriyakLegendPanel(legend) {
  const categories = getSuriyakCategoriesFromLegend(legend);
  const total = Number(legend?.total_overlay_features || 0);
  const generatedAt = legend?.generated_at ? String(legend.generated_at).slice(0, 10) : 'n/a';

  if (dom.suriyakLayerMeta) {
    dom.suriyakLayerMeta.textContent = `${formatSuriyakNumber(total)} objektum • Frissítve: ${generatedAt}`;
  }

  buildSuriyakCategoryList(legend);

  if (dom.suriyakLegendNote) {
    dom.suriyakLegendNote.innerHTML = `
      A kategóriák automatikusan kerülnek besorolásra a <code>suriyak_style_rules.json</code> alapján.
      Az elnevezések elemzési célokat szolgálnak, és nem a Suriyak hivatalos kategóriái.
    `;
  }
}

async function syncSuriyakLegendPanel() {
  try {
    const legend = await loadSuriyakLegend();
    ensureSuriyakCategorySelection(legend);
    updateSuriyakLegendPanel(legend);
    return legend;
  } catch (error) {
    console.error('Suriyak legend hiba:', error);

    if (dom.suriyakLayerMeta) {
      dom.suriyakLayerMeta.textContent = 'Legend hiba';
    }

    if (dom.suriyakCategoryList) {
      dom.suriyakCategoryList.innerHTML = `
        <div class="suriyak-legend-empty">
          A Suriyak legend nem tölthető be: ${error.message}
        </div>
      `;
    }

    return null;
  }
}

function getActiveSuriyakCategoryIds() {
  return new Set([...(appState.suriyakSelectedCategories || new Set())]);
}

function filterSuriyakOverlayByCategories(data) {
  const selected = getActiveSuriyakCategoryIds();

  if (!selected.size) {
    return {
      ...(data || {}),
      features: [],
    };
  }

  return {
    ...(data || {}),
    features: (data?.features || []).filter(feature => {
      const category = feature?.properties?.suriyak_category || 'other_suriyak';
      return selected.has(category);
    }),
  };
}

async function loadSuriyakOverlay() {
  if (appState.suriyakOverlay) {
    return appState.suriyakOverlay;
  }

  appState.suriyakOverlay = await fetchJson(suriyakOverlayUrl);
  return appState.suriyakOverlay;
}

async function refreshSuriyak() {
  try {
    if (!layerState.suriyakLayer) return;

    if (!dom.toggleSuriyak?.checked) {
      updateSuriyakSubpanelVisibility(false);
      layerState.suriyakLayer.clearLayers();

      if (map.hasLayer(layerState.suriyakLayer)) {
        map.removeLayer(layerState.suriyakLayer);
      }

      return;
    }

    updateSuriyakSubpanelVisibility(true);
    await syncSuriyakLegendPanel();

    const data = await loadSuriyakOverlay();
    const filteredData = filterSuriyakOverlayByCategories(data);
    renderSuriyakLayer(layerState, filteredData);

    if (!map.hasLayer(layerState.suriyakLayer)) {
      layerState.suriyakLayer.addTo(map);
    }

    const shown = filteredData.features?.length || 0;
    setStatus(`Suriyak betöltve: ${formatSuriyakNumber(shown)} objektum`);
  } catch (error) {
    console.error('Suriyak overlay hiba:', error);

    if (layerState.suriyakLayer) {
      layerState.suriyakLayer.clearLayers();

      if (map.hasLayer(layerState.suriyakLayer)) {
        map.removeLayer(layerState.suriyakLayer);
      }
    }

    if (dom.toggleSuriyak) {
      dom.toggleSuriyak.checked = false;
    }

    updateSuriyakSubpanelVisibility(false);
    setStatus(`Suriyak hiba: ${error.message}`);
  }
}
function renderHistoricalLegend(days, data) {
  if (!dom.historicalDeltaLegend) return;

  const summaries = data?.metadata?.daily_summaries || [];

  const html = Array.from({ length: days }, (_, dayIndex) => {
    const matchingSummary = summaries.find(
      item => Number(item.day_index_from_latest) === dayIndex
    );

    const label = matchingSummary
      ? `${matchingSummary.current_date}`
      : dayIndex === 0
        ? 'Legfrissebb nap'
        : `${dayIndex} nappal ezelőtt`;

    return `
      <div class="historical-legend-item">
        <span
          class="historical-legend-swatch"
          style="background:${getHistoricalColor(dayIndex)};"
        ></span>
        <span>${label}</span>
      </div>
    `;
  }).join('');

  dom.historicalDeltaLegend.innerHTML = `
    <div><b>Napi színskála</b></div>
    ${html}
  `;
}

function updateHistoricalDeltaSummary(features, selectedDays, data) {
  if (!dom.historicalDeltaSummary) return;

  const gainTotal = features
    .filter(feature => feature?.properties?.change_type === 'russian_gain')
    .reduce((sum, feature) => sum + Number(feature?.properties?.area_km2 || 0), 0);

  const recaptureTotal = features
    .filter(feature => feature?.properties?.change_type === 'ukrainian_recapture')
    .reduce((sum, feature) => sum + Number(feature?.properties?.area_km2 || 0), 0);

  const latestDate = data?.metadata?.latest_date || 'n/a';

  dom.historicalDeltaSummary.innerHTML = `
    Nézet: <strong>${selectedDays} nap</strong><br>
    Legfrissebb dátum: <strong>${latestDate}</strong><br>
    Megjelenített változások: <strong>${features.length}</strong><br>
    Orosz területszerzés: <strong>${gainTotal.toFixed(2)} km²</strong><br>
    Ukrán visszaszerzés: <strong>${recaptureTotal.toFixed(2)} km²</strong><br>
    Nettó változás: <strong>${(gainTotal - recaptureTotal).toFixed(2)} km²</strong>
  `;
}

async function renderHistoricalDelta() {
  try {
    if (!layerState.historicalDeltaLayer) return;

    if (!dom.toggleHistoricalDelta?.checked) {
      layerState.historicalDeltaLayer.clearLayers();

      if (map.hasLayer(layerState.historicalDeltaLayer)) {
        map.removeLayer(layerState.historicalDeltaLayer);
      }

      if (dom.historicalDeltaSummary) {
        dom.historicalDeltaSummary.innerHTML = 'A történeti területi delta réteg ki van kapcsolva.';
      }

      return;
    }

    const selectedDays = Number(dom.historicalDeltaWindow?.value || 10);
    const data = await loadHistoricalDelta();

    const features = (data.features || []).filter(feature =>
      Number(feature?.properties?.day_index_from_latest) <= selectedDays - 1
    );

    renderHistoricalDeltaLayer(layerState, features, selectedDays);

    if (!map.hasLayer(layerState.historicalDeltaLayer)) {
      layerState.historicalDeltaLayer.addTo(map);
    }

    updateHistoricalDeltaSummary(features, selectedDays, data);
    renderHistoricalLegend(selectedDays, data);
  } catch (error) {
    console.error('Historical delta hiba:', error);

    if (dom.historicalDeltaSummary) {
      dom.historicalDeltaSummary.innerHTML = `Történeti delta hiba: ${error.message}`;
    }

    if (layerState.historicalDeltaLayer) {
      layerState.historicalDeltaLayer.clearLayers();
    }
  }
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
    dom.osintFeedList.innerHTML = 'No OSINT feed available.';
    return;
  }

  const modeText =
    summary.mode === 'fresh'
      ? `Fresh window: last <strong>${summary.freshnessWindowHours}h</strong>`
      : summary.mode === 'fallback'
        ? `Fallback mode: latest available date <strong>${summary.referenceDate || 'n/a'}</strong>`
        : 'No fresh data';

  const visibleItems = summary.topFive.slice(0, OSINT_FEED_LIMIT);

  dom.osintFeedList.innerHTML = `
    <b>Top ${OSINT_FEED_LIMIT} OSINT clusters</b><br>
    <div style="margin-bottom:8px;">${modeText}</div>
    ${visibleItems.map((item, idx) => {
      const icon = getOsintCategoryIcon(item.category);
      return `
        <div style="margin-bottom:8px;">
          <b>${idx + 1}. ${icon} ${item.title || 'Untitled'}</b><br>
          ${item.sourceType || 'OSINT'} · ${item.date || 'Unknown date'} · ${item.freshnessLabel || 'UNKNOWN'}<br>
          ${item.sectorShortName || item.sectorName || 'Unknown sector'} · ${item.nearestPlace || 'Unknown place'}<br>
          Reports: ${item.reportCount || 1} · Category: ${icon} ${item.category || 'general military update'}<br>
          Severity: ${getThreatBadge(item.severity || 'LOW')}<br>
          Freshness: <strong>${Number(item.freshnessHours || 0).toFixed(1)}h</strong><br>
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

function updateTopThreatSectors() {
  if (!dom.topThreatSectors) return;

  const rows = buildSectorBalance(
    appState.latestDelta,
    appState.latestOsintSummary,
    appState.latestFirmsPoints
  ).slice(0, 5);

  if (!rows.length) {
    dom.topThreatSectors.innerHTML = 'Nincs még threat ranking.';
    return;
  }

  dom.topThreatSectors.innerHTML = rows.map((row, idx) => `
    <div style="margin-bottom:8px;">
      <b>#${idx + 1} ${row.name}</b><br>
      Threat: ${getThreatBadge(row.threatLevel)}<br>
      Score: <strong>${row.threatScore.toFixed(1)}</strong><br>
      RU gain: ${row.ruGainKm2.toFixed(2)} km² · UA recapture: ${row.uaRecaptureKm2.toFixed(2)} km²<br>
      OSINT: ${row.osintClusters} · FIRMS: ${row.firmsPoints}
    </div>
  `).join('<hr style="margin:6px 0;">');
}

function updateAutoOpsSummary() {
  if (!dom.autoOpsSummary) return;

  const sectors = buildSectorBalance(
    appState.latestDelta,
    appState.latestOsintSummary,
    appState.latestFirmsPoints
  );

  const topThreat = sectors[0] || null;
  const secondThreat = sectors[1] || null;
  const topGain = (appState.latestDelta?.gained || [])[0] || null;
  const topLoss = (appState.latestDelta?.lost || [])[0] || null;
  const topFirms = appState.latestFirmsSummary?.topZone || null;
  const topOsint = (appState.latestOsintSummary?.topFive || [])[0] || null;

  if (!topThreat && !topGain && !topLoss && !topFirms && !topOsint) {
    dom.autoOpsSummary.innerHTML = 'Nincs még automatikus összefoglaló.';
    return;
  }

  const sentences = [];

  if (topThreat) {
    sentences.push(
      `A napi összkép alapján a legmagasabb fenyegetési szint jelenleg a(z) <b>${topThreat.name}</b> szektorban látszik, ${getThreatBadge(topThreat.threatLevel)} besorolással.`
    );
  }

  if (topGain) {
    sentences.push(
      `A legnagyobb orosz területszerzés a(z) <b>${topGain.sectorShortName || topGain.sectorName}</b> szektorban történt, ${topGain.nearestPlace} térségében, <b>${topGain.areaKm2.toFixed(2)} km²</b> nagyságrendben.`
    );
  }

  if (topLoss) {
    sentences.push(
      `A legjelentősebb ukrán visszaszerzés a(z) <b>${topLoss.sectorShortName || topLoss.sectorName}</b> szektorban jelent meg, ${topLoss.nearestPlace} közelében, <b>${topLoss.areaKm2.toFixed(2)} km²</b> mértékben.`
    );
  }

  if (topFirms) {
    sentences.push(
      `A FIRMS adatok alapján a legintenzívebb hőaktivitás a(z) <b>${topFirms.sectorShortName || topFirms.sectorName}</b> térségben koncentrálódott, ${topFirms.nearestPlace} közelében, <b>${topFirms.count}</b> hotspot értékkel.`
    );
  }

  if (topOsint) {
    sentences.push(
      `Az OSINT feedben a legerősebb, friss cluster a(z) <b>${topOsint.sectorShortName || topOsint.sectorName}</b> szektorhoz kapcsolódik ${topOsint.nearestPlace} környezetében, <b>${topOsint.reportCount}</b> jelentéssel, ${topOsint.freshnessLabel || 'UNKNOWN'} státusszal és ${getThreatBadge(topOsint.severity || 'LOW')} severity szinttel.`
    );
  }

  if (secondThreat) {
    sentences.push(
      `Másodlagos kiemelt aktivitás még a(z) <b>${secondThreat.name}</b> szektorban látható, ahol a kombinált delta, OSINT és FIRMS terhelés továbbra is emelkedett.`
    );
  }

  dom.autoOpsSummary.innerHTML = sentences.map(sentence => `<div style="margin-bottom:8px;">${sentence}</div>`).join('');
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

  const osintModeText =
    osint?.mode === 'fresh'
      ? `Fresh < ${osint.freshnessWindowHours}h`
      : osint?.mode === 'fallback'
        ? `Fallback ${osint.referenceDate || 'n/a'}`
        : 'No OSINT';

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
    ${topOsint ? `${getOsintCategoryIcon(topOsint.category)} ${topOsint.sourceType} · ${topOsint.sectorShortName || topOsint.sectorName} · ${topOsint.nearestPlace} · ${topOsint.reportCount} reports · ${topOsint.freshnessLabel || 'UNKNOWN'} · ${getThreatBadge(topOsint.severity || 'LOW')}` : 'No OSINT cluster'}
    <hr style="margin:6px 0;">
    <b>OSINT status</b><br>
    ${osintModeText}
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

function buildAttackAxes() {
  const axes = [];

  const gains = (appState.latestDelta?.gained || []).slice(0, 3);
  const losses = (appState.latestDelta?.lost || []).slice(0, 2);

  gains.forEach((item) => {
    axes.push({
      side: 'ru',
      startLat: Number(item.lat) + 0.05,
      startLng: Number(item.lng) + 0.55,
      endLat: Number(item.lat),
      endLng: Number(item.lng),
      sectorName: item.sectorName,
      nearestPlace: item.nearestPlace,
      label: `Russian push near ${item.nearestPlace || 'front sector'}`,
      note: `${item.areaKm2.toFixed(2)} km² daily gain`,
      weight: Math.min(7, 4 + item.areaKm2 / 2)
    });
  });

  losses.forEach((item) => {
    axes.push({
      side: 'ua',
      startLat: Number(item.lat) - 0.03,
      startLng: Number(item.lng) - 0.45,
      endLat: Number(item.lat),
      endLng: Number(item.lng),
      sectorName: item.sectorName,
      nearestPlace: item.nearestPlace,
      label: `Ukrainian counter-axis near ${item.nearestPlace || 'front sector'}`,
      note: `${item.areaKm2.toFixed(2)} km² recapture`,
      weight: Math.min(6, 3 + item.areaKm2 / 2)
    });
  });

  const topOsintAssaults = (appState.latestOsintSummary?.clusters || [])
    .filter(cluster => String(cluster.category || '').toLowerCase().includes('assault'))
    .slice(0, 2);

  topOsintAssaults.forEach((cluster) => {
    axes.push({
      side: cluster.sourceType === 'Ukrainian official' ? 'ua' : 'ru',
      startLat: Number(cluster.lat) + 0.12,
      startLng: Number(cluster.lng) + (cluster.sourceType === 'Ukrainian official' ? -0.4 : 0.45),
      endLat: Number(cluster.lat),
      endLng: Number(cluster.lng),
      sectorName: cluster.sectorName,
      nearestPlace: cluster.nearestPlace,
      label:
        cluster.sourceType === 'Ukrainian official'
          ? `Ukrainian pressure near ${cluster.nearestPlace || 'front sector'}`
          : `Russian pressure near ${cluster.nearestPlace || 'front sector'}`,
      note: `${cluster.reportCount} assault reports`,
      weight: cluster.severity === 'CRITICAL' ? 7 : cluster.severity === 'HIGH' ? 6 : 5
    });
  });

  appState.latestAttackAxes = axes.slice(0, 5);
  renderAttackAxes(layerState, appState.latestAttackAxes);

  if (dom.toggleAxes.checked) {
    if (!map.hasLayer(layerState.attackAxesLayer)) {
      layerState.attackAxesLayer.addTo(map);
    }
  } else {
    if (map.hasLayer(layerState.attackAxesLayer)) {
      map.removeLayer(layerState.attackAxesLayer);
    }
  }
}

function buildBattleNodes() {
  const nodes = [];

  const sectorRows = buildSectorBalance(
    appState.latestDelta,
    appState.latestOsintSummary,
    appState.latestFirmsPoints
  ).slice(0, 5);

  sectorRows.forEach((sectorRow) => {
    const matchingDelta =
      (appState.latestDelta?.gained || []).find(item => (item.sectorShortName || item.sectorName) === sectorRow.name) ||
      (appState.latestDelta?.lost || []).find(item => (item.sectorShortName || item.sectorName) === sectorRow.name);

    const matchingCluster =
      (appState.latestOsintSummary?.clusters || []).find(cluster => (cluster.sectorShortName || cluster.sectorName) === sectorRow.name);

    const matchingFirm =
      (appState.latestFirmsSummary?.topThreeZones || []).find(zone => (zone.sectorShortName || zone.sectorName) === sectorRow.name);

    let lat = 48.5;
    let lng = 36.0;
    let reason = 'Combined multi-source activity';

    if (matchingCluster) {
      lat = Number(matchingCluster.lat);
      lng = Number(matchingCluster.lng);
      reason = `OSINT cluster concentration`;
    } else if (matchingDelta) {
      lat = Number(matchingDelta.lat);
      lng = Number(matchingDelta.lng);
      reason = `Territorial delta activity`;
    } else if (matchingFirm) {
      lat = Number(matchingFirm.lat || ((matchingFirm.bounds?.[0]?.[0] + matchingFirm.bounds?.[1]?.[0]) / 2));
      lng = Number(matchingFirm.lng || ((matchingFirm.bounds?.[0]?.[1] + matchingFirm.bounds?.[1]?.[1]) / 2));
      reason = `FIRMS hotspot concentration`;
    }

    nodes.push({
      lat,
      lng,
      sectorName: sectorRow.name,
      nearestPlace:
        matchingCluster?.nearestPlace ||
        matchingDelta?.nearestPlace ||
        matchingFirm?.nearestPlace ||
        'Unknown place',
      level: sectorRow.threatLevel,
      score: sectorRow.threatScore,
      reason,
      radiusMeters:
        sectorRow.threatLevel === 'CRITICAL' ? 26000 :
        sectorRow.threatLevel === 'HIGH' ? 22000 :
        sectorRow.threatLevel === 'MEDIUM' ? 18000 :
        14000
    });
  });

  appState.latestBattleNodes = nodes;
  renderBattleNodes(layerState, appState.latestBattleNodes);

  if (dom.toggleBattleNodes.checked) {
    if (!map.hasLayer(layerState.battleNodesLayer)) {
      layerState.battleNodesLayer.addTo(map);
    }
  } else {
    if (map.hasLayer(layerState.battleNodesLayer)) {
      map.removeLayer(layerState.battleNodesLayer);
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
  replaceFrontlineLayer(layerState, currentGeoJson);

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

  await renderHistoricalDelta();

  if (dom.toggleSuriyak?.checked) {
    await refreshSuriyak();
  }

  if (dom.toggleFirms.checked) {
    await refreshFirms();
  }

  if (dom.toggleOsint.checked) {
    await refreshOsint();
  }

  updateDailyDashboard();
  updateAutoOpsSummary();
  updateTopThreatSectors();
  updateSectorBalanceSummary();
  buildAttackAxes();
  buildBattleNodes();
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
      updateAutoOpsSummary();
      updateTopThreatSectors();
      updateSectorBalanceSummary();
      buildAttackAxes();
      buildBattleNodes();
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
    updateAutoOpsSummary();
    updateTopThreatSectors();
    updateSectorBalanceSummary();
    buildAttackAxes();
    buildBattleNodes();
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
      updateAutoOpsSummary();
      updateTopThreatSectors();
      updateSectorBalanceSummary();
      buildAttackAxes();
      buildBattleNodes();
      refreshHeatmap();
      return;
    }

    const feed = await fetchOsintFeed({
      maxAgeHours: 36,
      fallbackAgeHours: 96,
    });

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
    updateAutoOpsSummary();
    updateTopThreatSectors();
    updateSectorBalanceSummary();
    buildAttackAxes();
    buildBattleNodes();
    refreshHeatmap();

    if (!map.hasLayer(layerState.osintLayer)) {
      layerState.osintLayer.addTo(map);
    }
    if (!map.hasLayer(layerState.osintHighlightLayer)) {
      layerState.osintHighlightLayer.addTo(map);
    }
  } catch (error) {
    console.error('OSINT hiba:', error);

    appState.latestOsintSummary = null;
    layerState.osintLayer.clearLayers();
    layerState.osintHighlightLayer.clearLayers();

    if (map.hasLayer(layerState.osintLayer)) {
      map.removeLayer(layerState.osintLayer);
    }
    if (map.hasLayer(layerState.osintHighlightLayer)) {
      map.removeLayer(layerState.osintHighlightLayer);
    }

    updateOsintFeedList(null);
    updateDailyDashboard();
    updateAutoOpsSummary();
    updateTopThreatSectors();
    updateSectorBalanceSummary();
    buildAttackAxes();
    buildBattleNodes();
    refreshHeatmap();
  }
}



function getDeepStrikeDateList(events) {
  return [...new Set(
    (Array.isArray(events) ? events : [])
      .map(item => String(item?.date || '').trim())
      .filter(Boolean)
  )].sort();
}

function addDaysToIsoDate(isoDate, days) {
  const raw = String(isoDate || '').trim();
  if (!raw) return null;

  const parsed = new Date(`${raw}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;

  parsed.setUTCDate(parsed.getUTCDate() + Number(days || 0));
  return parsed.toISOString().slice(0, 10);
}

function prepareDeepStrikeDateControl(events) {
  const control = dom.deepStrikesDate;
  if (!control) return;

  const dates = getDeepStrikeDateList(events);
  if (!dates.length) return;

  const latestDate = dates[dates.length - 1];

  if (control.tagName === 'SELECT') {
    const currentValue = control.value;

    control.innerHTML = dates
      .slice()
      .reverse()
      .map(date => `<option value="${date}">${date}</option>`)
      .join('');

    control.value = dates.includes(currentValue)
      ? currentValue
      : latestDate;

    return;
  }

  if (control.type === 'date') {
    control.min = dates[0];
    control.max = latestDate;

    if (!control.value) {
      control.value = latestDate;
    }
  }
}

function getDeepStrikeDateRange(events) {
  const dates = getDeepStrikeDateList(events);
  if (!dates.length) {
    return { startDate: null, endDate: null };
  }

  const latestDate = dates[dates.length - 1];

  const selectedDate =
    String(dom.deepStrikesDate?.value || '').trim() ||
    latestDate;

  const mode =
    String(dom.deepStrikesWindow?.value || 'all').trim().toLowerCase();

  if (mode === 'day' || mode === '1') {
    return {
      startDate: selectedDate,
      endDate: selectedDate,
    };
  }

  if (mode === '7') {
    return {
      startDate: addDaysToIsoDate(selectedDate, -6),
      endDate: selectedDate,
    };
  }

  if (mode === '30') {
    return {
      startDate: addDaysToIsoDate(selectedDate, -29),
      endDate: selectedDate,
    };
  }

  if (mode === '90') {
    return {
      startDate: addDaysToIsoDate(selectedDate, -89),
      endDate: selectedDate,
    };
  }

  return {
    startDate: null,
    endDate: null,
  };
}

function filterDeepStrikeEventsForUi(events) {
  const { startDate, endDate } = getDeepStrikeDateRange(events);

  const showUaRu =
    dom.toggleDeepStrikesUaRu
      ? dom.toggleDeepStrikesUaRu.checked
      : true;

  const showRuUa =
    dom.toggleDeepStrikesRuUa
      ? dom.toggleDeepStrikesRuUa.checked
      : true;

  return (Array.isArray(events) ? events : []).filter(item => {
    const direction = String(item?.direction || '').toUpperCase();
    const date = String(item?.date || '').trim();

    if (direction === 'UA_RU' && !showUaRu) return false;
    if (direction === 'RU_UA' && !showRuUa) return false;

    if (startDate && date < startDate) return false;
    if (endDate && date > endDate) return false;

    return true;
  });
}

function updateDeepStrikesSummary(visibleEvents) {
  if (!dom.deepStrikesSummary) return;

  const events = Array.isArray(visibleEvents) ? visibleEvents : [];

  const uaRu = events.filter(
    item => String(item?.direction || '').toUpperCase() === 'UA_RU'
  ).length;

  const ruUa = events.filter(
    item => String(item?.direction || '').toUpperCase() === 'RU_UA'
  ).length;

  const { startDate, endDate } = getDeepStrikeDateRange(appState.deepStrikes);

  const periodText =
    startDate && endDate
      ? startDate === endDate
        ? startDate
        : `${startDate} – ${endDate}`
      : 'összes elérhető dátum';

  dom.deepStrikesSummary.innerHTML = `
    Megjelenített események: <strong>${events.length}</strong><br>
    <span style="color:#1565c0;"><b>UA → RU:</b> ${uaRu}</span><br>
    <span style="color:#c1121f;"><b>RU → UA:</b> ${ruUa}</span><br>
    Időszak: <strong>${periodText}</strong>
  `;
}

function removeDeepStrikeLayersFromMap() {
  if (layerState.deepStrikesLayer && map.hasLayer(layerState.deepStrikesLayer)) {
    map.removeLayer(layerState.deepStrikesLayer);
  }

  if (
    layerState.deepStrikeLabelsLayer &&
    map.hasLayer(layerState.deepStrikeLabelsLayer)
  ) {
    map.removeLayer(layerState.deepStrikeLabelsLayer);
  }
}

function isDeepStrikesEnabled() {
  // Until the new checkbox exists in index.html, the layer is enabled.
  // This makes the integration test visible without changing the current UI.
  return dom.toggleDeepStrikes
    ? dom.toggleDeepStrikes.checked
    : true;
}

function shouldShowDeepStrikeLabels() {
  // Until the labels checkbox exists, keep cards OFF to avoid clutter.
  return dom.toggleDeepStrikeLabels
    ? dom.toggleDeepStrikeLabels.checked
    : false;
}

async function loadDeepStrikesOnce() {
  if (appState.deepStrikesLoaded) {
    return appState.deepStrikes;
  }

  const events = await fetchDeepStrikes();

  appState.deepStrikes = Array.isArray(events) ? events : [];
  appState.deepStrikesLoaded = true;

  prepareDeepStrikeDateControl(appState.deepStrikes);

  return appState.deepStrikes;
}

async function refreshDeepStrikes() {
  try {
    const events = await loadDeepStrikesOnce();

    if (!isDeepStrikesEnabled()) {
      removeDeepStrikeLayersFromMap();
      updateDeepStrikesSummary([]);
      return;
    }

    const visibleEvents = filterDeepStrikeEventsForUi(events);
    const { startDate, endDate } = getDeepStrikeDateRange(events);

    renderDeepStrikesLayer(
      layerState,
      visibleEvents,
      {
        startDate,
        endDate,
        showUaRu: true,
        showRuUa: true,
        showLabels: shouldShowDeepStrikeLabels(),
        defaultLanguage: 'hu',
      }
    );

    if (
      layerState.deepStrikesLayer &&
      !map.hasLayer(layerState.deepStrikesLayer)
    ) {
      layerState.deepStrikesLayer.addTo(map);
    }

    if (shouldShowDeepStrikeLabels()) {
      if (
        layerState.deepStrikeLabelsLayer &&
        !map.hasLayer(layerState.deepStrikeLabelsLayer)
      ) {
        layerState.deepStrikeLabelsLayer.addTo(map);
      }
    } else if (
      layerState.deepStrikeLabelsLayer &&
      map.hasLayer(layerState.deepStrikeLabelsLayer)
    ) {
      map.removeLayer(layerState.deepStrikeLabelsLayer);
    }

    appState.deepStrikesSummary = {
      total: visibleEvents.length,
      uaToRussia: visibleEvents.filter(
        item => String(item?.direction || '').toUpperCase() === 'UA_RU'
      ).length,
      russiaToUkraine: visibleEvents.filter(
        item => String(item?.direction || '').toUpperCase() === 'RU_UA'
      ).length,
    };

    updateDeepStrikesSummary(visibleEvents);
  } catch (error) {
    // Deep-strike failure must never stop the existing front map.
    console.error('Deep strike layer hiba:', error);

    appState.deepStrikes = [];
    appState.deepStrikesLoaded = false;
    appState.deepStrikesSummary = null;

    removeDeepStrikeLayersFromMap();

    if (dom.deepStrikesSummary) {
      dom.deepStrikesSummary.textContent =
        `Mélységi csapás adat hiba: ${error.message}`;
    }
  }
}

function bindDeepStrikeControls() {
  const controls = [
    dom.toggleDeepStrikes,
    dom.deepStrikesDate,
    dom.deepStrikesWindow,
    dom.toggleDeepStrikesUaRu,
    dom.toggleDeepStrikesRuUa,
    dom.toggleDeepStrikeLabels,
  ].filter(Boolean);

  controls.forEach(control => {
    control.addEventListener('change', refreshDeepStrikes);
  });

  dom.btnResetDeepStrikeLabels?.addEventListener('click', () => {
    resetAllSavedDeepStrikeLabels(layerState);
  });
}


function getToolboxModeLabel(mode) {
  if (mode === 'coordinate') return 'Koordináta jelölés';
  if (mode === 'distance') return 'Távolságmérés';
  if (mode === 'identify') return 'Objektum azonosítás';
  if (mode === 'draw') return 'Elemző rajzolás';
  return 'Kikapcsolva';
}

function getToolboxObjectTypeLabel(value) {
  const select = dom.toolboxObjectType;
  if (!select) return 'Ismeretlen / általános pont';

  const selectedOption = [...select.options].find(option => option.value === value);
  return selectedOption?.textContent || 'Ismeretlen / általános pont';
}


function getAnalysisDrawShape() {
  return dom.toolboxDrawShape?.value || 'line';
}

function getAnalysisDrawColor() {
  return dom.toolboxDrawColor?.value || '#d32f2f';
}

function getAnalysisDrawShapeLabel(shape) {
  const labels = {
    line: 'Vonal',
    'dashed-line': 'Szaggatott vonal',
    circle: 'Kör',
    'dashed-circle': 'Szaggatott kör',
    triangle: 'Háromszög',
    arrow: 'Nyíl',
    'dashed-arrow': 'Szaggatott nyíl',
  };

  return labels[shape] || shape;
}

function getAnalysisRequiredPointCount(shape) {
  if (shape === 'triangle') return 3;
  return 2;
}

function isAnalysisDashedShape(shape) {
  return (
    shape === 'dashed-line' ||
    shape === 'dashed-circle' ||
    shape === 'dashed-arrow'
  );
}

function getAnalysisLineStyle(shape, color) {
  return {
    color,
    weight: 4,
    opacity: 0.95,
    dashArray: isAnalysisDashedShape(shape) ? '10,8' : null,
    lineCap: 'round',
    lineJoin: 'round',
    interactive: true,
  };
}

function clearAnalysisDraft() {
  appState.analysisDraftPoints = [];
  analysisDraftLayer.clearLayers();
}

function drawAnalysisDraftPoints() {
  analysisDraftLayer.clearLayers();

  const color = getAnalysisDrawColor();

  appState.analysisDraftPoints.forEach((latlng, index) => {
    L.circleMarker(latlng, {
      radius: 5,
      color: '#ffffff',
      weight: 2,
      fillColor: color,
      fillOpacity: 1,
      interactive: false,
    })
      .bindTooltip(`${index + 1}. pont`, {
        permanent: false,
        direction: 'top',
      })
      .addTo(analysisDraftLayer);
  });
}

function createAnalysisArrowHead(startLatLng, endLatLng, color, dashed = false) {
  const start = map.latLngToLayerPoint(startLatLng);
  const end = map.latLngToLayerPoint(endLatLng);

  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.sqrt(dx * dx + dy * dy);

  if (!Number.isFinite(length) || length < 1) {
    return null;
  }

  const ux = dx / length;
  const uy = dy / length;

  // A nyílhegy képernyő-pixelben marad stabil méretű zoomolástól függetlenül.
  const headLength = 18;
  const headWidth = 9;

  const baseX = end.x - ux * headLength;
  const baseY = end.y - uy * headLength;

  const perpX = -uy;
  const perpY = ux;

  const left = L.point(
    baseX + perpX * headWidth,
    baseY + perpY * headWidth
  );

  const right = L.point(
    baseX - perpX * headWidth,
    baseY - perpY * headWidth
  );

  const leftLatLng = map.layerPointToLatLng(left);
  const rightLatLng = map.layerPointToLatLng(right);

  return L.polyline(
    [leftLatLng, endLatLng, rightLatLng],
    {
      color,
      weight: 4,
      opacity: 0.95,
      dashArray: dashed ? '8,6' : null,
      lineCap: 'round',
      lineJoin: 'round',
      interactive: false,
    }
  );
}

function addAnalysisDrawingRecord(record) {
  appState.analysisDrawings.push(record);
  updateToolboxStatus();
}

function buildAnalysisGeoJsonFeature(record) {
  const baseProperties = {
    source: 'Törésvonalak OSINT Toolbox',
    drawing_type: record.shape,
    color: record.color,
    dashed: Boolean(record.dashed),
  };

  if (record.shape === 'circle' || record.shape === 'dashed-circle') {
    return {
      type: 'Feature',
      properties: {
        ...baseProperties,
        radius_m: record.radiusMeters,
      },
      geometry: {
        type: 'Point',
        coordinates: [
          record.points[0].lng,
          record.points[0].lat,
        ],
      },
    };
  }

  if (record.shape === 'triangle') {
    const coordinates = record.points.map(point => [point.lng, point.lat]);
    coordinates.push([
      record.points[0].lng,
      record.points[0].lat,
    ]);

    return {
      type: 'Feature',
      properties: baseProperties,
      geometry: {
        type: 'Polygon',
        coordinates: [coordinates],
      },
    };
  }

  return {
    type: 'Feature',
    properties: baseProperties,
    geometry: {
      type: 'LineString',
      coordinates: record.points.map(point => [point.lng, point.lat]),
    },
  };
}

function exportAnalysisDrawingsGeoJson() {
  if (!appState.analysisDrawings.length) {
    updateToolboxStatus('Nincs exportálható elemző rajz.');
    return;
  }

  const geojson = {
    type: 'FeatureCollection',
    features: appState.analysisDrawings.map(buildAnalysisGeoJsonFeature),
  };

  const blob = new Blob(
    [JSON.stringify(geojson, null, 2)],
    { type: 'application/geo+json;charset=utf-8' }
  );

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `ukraine-front-analysis-drawings-${new Date().toISOString().slice(0, 10)}.geojson`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);

  updateToolboxStatus();
}

function finalizeAnalysisDrawing() {
  const shape = getAnalysisDrawShape();
  const color = getAnalysisDrawColor();
  const points = [...appState.analysisDraftPoints];

  if (points.length < getAnalysisRequiredPointCount(shape)) {
    return;
  }

  const group = L.layerGroup();
  const dashed = isAnalysisDashedShape(shape);
  let radiusMeters = null;

  if (shape === 'line' || shape === 'dashed-line') {
    L.polyline(
      [points[0], points[1]],
      getAnalysisLineStyle(shape, color)
    ).addTo(group);
  }

  if (shape === 'circle' || shape === 'dashed-circle') {
    radiusMeters = map.distance(points[0], points[1]);

    L.circle(points[0], {
      radius: radiusMeters,
      color,
      weight: 4,
      opacity: 0.95,
      fillColor: color,
      fillOpacity: 0.06,
      dashArray: dashed ? '10,8' : null,
      interactive: true,
    }).addTo(group);
  }

  if (shape === 'triangle') {
    L.polygon(
      [points[0], points[1], points[2]],
      {
        color,
        weight: 4,
        opacity: 0.95,
        fillColor: color,
        fillOpacity: 0.08,
        lineJoin: 'round',
        interactive: true,
      }
    ).addTo(group);
  }

  if (shape === 'arrow' || shape === 'dashed-arrow') {
    L.polyline(
      [points[0], points[1]],
      getAnalysisLineStyle(shape, color)
    ).addTo(group);

    const arrowHead = createAnalysisArrowHead(
      points[0],
      points[1],
      color,
      dashed
    );

    if (arrowHead) {
      arrowHead.addTo(group);
    }
  }

  group.addTo(analysisDrawingLayer);

  const record = {
    id: `analysis-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    shape,
    color,
    dashed,
    points: points.map(point => ({
      lat: point.lat,
      lng: point.lng,
    })),
    radiusMeters,
    layer: group,
  };

  addAnalysisDrawingRecord(record);
  clearAnalysisDraft();
}

function handleAnalysisDrawClick(event) {
  if ((dom.toolboxMode?.value || '') !== 'draw') {
    return;
  }

  const shape = getAnalysisDrawShape();
  const requiredCount = getAnalysisRequiredPointCount(shape);

  appState.analysisDraftPoints.push(event.latlng);
  drawAnalysisDraftPoints();

  if (appState.analysisDraftPoints.length >= requiredCount) {
    finalizeAnalysisDrawing();
    return;
  }

  updateToolboxStatus();
}

function enableAnalysisDrawing() {
  const mapContainer = map.getContainer();

  if (!appState.analysisDrawClickBound) {
    appState.analysisDrawNativeHandler = (event) => {
      if ((dom.toolboxMode?.value || '') !== 'draw') {
        return;
      }

      // A Leaflet vezérlőkre, popupokra és térképi kártyákra kattintás
      // ne hozzon létre rajzpontot.
      if (
        event.target.closest?.('.leaflet-control') ||
        event.target.closest?.('.leaflet-popup') ||
        event.target.closest?.('.deep-strike-card')
      ) {
        return;
      }

      const latlng = map.mouseEventToLatLng(event);

      if (!latlng) {
        return;
      }

      // Capture fázisban is megbízhatóan megkapjuk a térképkattintást,
      // még akkor is, ha valamely Leaflet overlay leállítja a bubblinget.
      handleAnalysisDrawClick({ latlng });
    };

    mapContainer.addEventListener(
      'click',
      appState.analysisDrawNativeHandler,
      true
    );

    appState.analysisDrawClickBound = true;
  }

  mapContainer.style.cursor = 'crosshair';
}

function disableAnalysisDrawing() {
  const mapContainer = map.getContainer();

  if (
    appState.analysisDrawClickBound &&
    appState.analysisDrawNativeHandler
  ) {
    mapContainer.removeEventListener(
      'click',
      appState.analysisDrawNativeHandler,
      true
    );

    appState.analysisDrawClickBound = false;
    appState.analysisDrawNativeHandler = null;
  }

  clearAnalysisDraft();
  mapContainer.style.cursor = '';
}

function undoAnalysisDrawing() {
  clearAnalysisDraft();

  const record = appState.analysisDrawings.pop();
  if (!record) {
    updateToolboxStatus();
    return;
  }

  if (record.layer) {
    analysisDrawingLayer.removeLayer(record.layer);
  }

  updateToolboxStatus();
}

function clearAnalysisDrawings(confirmDelete = true) {
  const count = appState.analysisDrawings.length;

  if (!count) {
    clearAnalysisDraft();
    updateToolboxStatus();
    return;
  }

  if (confirmDelete) {
    const confirmed = window.confirm(
      `Biztosan törlöd az összes elemző rajzot? (${count} db)`
    );

    if (!confirmed) return;
  }

  analysisDrawingLayer.clearLayers();
  clearAnalysisDraft();
  appState.analysisDrawings = [];
  updateToolboxStatus();
}


function updateToolboxStatus(customText = null) {
  if (!dom.toolboxStatus) return;

  if (customText) {
    dom.toolboxStatus.innerHTML = customText;
    return;
  }

  const mode = dom.toolboxMode?.value || 'coordinate';
  const objectType = dom.toolboxObjectType?.value || 'unknown';
  const markerCount = appState.coordinateMarkersController?.getMarkers?.().length || 0;
  const measurementCount = appState.measureToolController?.getMeasurements?.().length || 0;
  const objectCount = appState.objectIdentificationController?.getObjects?.().length || 0;
  const drawingCount = appState.analysisDrawings.length;
  const draftPointCount = appState.analysisDraftPoints.length;

  if (mode === 'coordinate') {
    dom.toolboxStatus.innerHTML = `
      Aktív mód: <strong>${getToolboxModeLabel(mode)}</strong><br>
      Bal kattintás a térképen: új koordináta marker.<br>
      Mentett markerek: <strong>${markerCount}</strong><br>
      Mentett távolságmérések: <strong>${measurementCount}</strong><br>
      Azonosított objektumok: <strong>${objectCount}</strong>
    `;
    return;
  }

  if (mode === 'distance') {
    dom.toolboxStatus.innerHTML = `
      Aktív mód: <strong>${getToolboxModeLabel(mode)}</strong><br>
      Első kattintás: kezdőpont. Második kattintás: végpont.<br>
      A rendszer vonalat rajzol, és kiszámolja a távolságot, valamint az irányszöget.<br>
      Mentett távolságmérések: <strong>${measurementCount}</strong><br>
      Mentett markerek: <strong>${markerCount}</strong><br>
      Azonosított objektumok: <strong>${objectCount}</strong>
    `;
    return;
  }

  if (mode === 'identify') {
    dom.toolboxStatus.innerHTML = `
      Aktív mód: <strong>${getToolboxModeLabel(mode)}</strong><br>
      Kiválasztott objektumtípus: <strong>${getToolboxObjectTypeLabel(objectType)}</strong><br>
      Bal kattintás a térképen: új azonosított objektum a kiválasztott típussal.<br>
      Mentett markerek: <strong>${markerCount}</strong><br>
      Mentett távolságmérések: <strong>${measurementCount}</strong><br>
      Azonosított objektumok: <strong>${objectCount}</strong><br>
      Azonosított objektumok: <strong>${objectCount}</strong>
    `;
    return;
  }

  if (mode === 'draw') {
    const shape = getAnalysisDrawShape();
    const color = getAnalysisDrawColor();
    const requiredPoints = getAnalysisRequiredPointCount(shape);

    dom.toolboxStatus.innerHTML = `
      Aktív mód: <strong>${getToolboxModeLabel(mode)}</strong><br>
      Rajzeszköz: <strong>${getAnalysisDrawShapeLabel(shape)}</strong><br>
      Szín: <strong style="color:${color};">${color}</strong><br>
      Rajzolás aktív: <strong>${appState.analysisDrawClickBound ? 'IGEN' : 'NEM'}</strong><br>
      Kattints a térképen: <strong>${requiredPoints} pont</strong> szükséges ehhez az alakzathoz.<br>
      Aktuális rajz pontjai: <strong>${draftPointCount}/${requiredPoints}</strong><br>
      Mentett elemző rajzok: <strong>${drawingCount}</strong>
    `;
    return;
  }

  dom.toolboxStatus.innerHTML = `
    Aktív mód: <strong>Kikapcsolva</strong><br>
    A Toolbox nem helyez el új pontot és nem indít távolságmérést a térképen.<br>
    Mentett markerek: <strong>${markerCount}</strong><br>
    Mentett távolságmérések: <strong>${measurementCount}</strong>
  `;
}
function applyToolboxMode() {
  const mode = dom.toolboxMode?.value || 'coordinate';
  const coordinateController = appState.coordinateMarkersController;
  const measureController = appState.measureToolController;
  const objectController = appState.objectIdentificationController;

  if (coordinateController) {
    if (mode === 'coordinate') {
      coordinateController.enable();
    } else {
      coordinateController.disable();
    }
  }

  if (measureController) {
    if (mode === 'distance') {
      measureController.enable();
    } else {
      measureController.disable();
    }
  }

  if (objectController) {
    if (mode === 'identify') {
      objectController.enable();
    } else {
      objectController.disable();
    }
  }

  if (mode === 'draw') {
    enableAnalysisDrawing();
  } else {
    disableAnalysisDrawing();
  }

  updateToolboxStatus();
}
function bindToolboxControls() {
  dom.toolboxMode?.addEventListener('change', applyToolboxMode);
  dom.toolboxObjectType?.addEventListener('change', updateToolboxStatus);

  dom.toolboxDrawShape?.addEventListener('change', () => {
    clearAnalysisDraft();
    updateToolboxStatus();
  });

  // A színválasztó hidden inputját az index.html kezeli.
  // A click esemény után egy tickkel frissítjük a státuszt.
  document.getElementById('toolboxColorGrid')?.addEventListener('click', () => {
    window.setTimeout(updateToolboxStatus, 0);
  });

  dom.btnToolboxUndoDrawing?.addEventListener('click', undoAnalysisDrawing);

  dom.btnToolboxClearDrawings?.addEventListener('click', () => {
    clearAnalysisDrawings(true);
  });

  dom.btnToolboxClearMarkers?.addEventListener('click', () => {
    const mode = dom.toolboxMode?.value || 'coordinate';

    if (mode === 'draw') {
      clearAnalysisDrawings(true);
      return;
    }

    if (mode === 'distance') {
      if (!appState.measureToolController) return;

      const measurementCount = appState.measureToolController.getMeasurements?.().length || 0;
      if (!measurementCount) {
        updateToolboxStatus();
        return;
      }

      const confirmed = window.confirm(`Biztosan törlöd az összes távolságmérést? (${measurementCount} db)`);
      if (!confirmed) return;

      appState.measureToolController.clearMeasurements();
      updateToolboxStatus();
      return;
    }

    if (mode === 'identify') {
      if (!appState.objectIdentificationController) return;

      const objectCount = appState.objectIdentificationController.getObjects?.().length || 0;
      if (!objectCount) {
        updateToolboxStatus();
        return;
      }

      const confirmed = window.confirm(`Biztosan törlöd az összes azonosított objektumot? (${objectCount} db)`);
      if (!confirmed) return;

      appState.objectIdentificationController.clearObjects();
      updateToolboxStatus();
      return;
    }

    if (!appState.coordinateMarkersController) return;

    const markerCount = appState.coordinateMarkersController.getMarkers?.().length || 0;
    if (!markerCount) {
      updateToolboxStatus();
      return;
    }

    const confirmed = window.confirm(`Biztosan törlöd az összes koordináta markert? (${markerCount} db)`);
    if (!confirmed) return;

    appState.coordinateMarkersController.clearMarkers();
    updateToolboxStatus();
  });

  dom.btnToolboxExportGeoJson?.addEventListener('click', () => {
    const mode = dom.toolboxMode?.value || 'coordinate';

    if (mode === 'draw') {
      exportAnalysisDrawingsGeoJson();
      return;
    }

    if (mode === 'identify') {
      if (!appState.objectIdentificationController) return;

      const objectCount = appState.objectIdentificationController.getObjects?.().length || 0;
      if (!objectCount) {
        updateToolboxStatus();
        return;
      }

      appState.objectIdentificationController.exportGeoJson();
      updateToolboxStatus();
      return;
    }

    if (!appState.coordinateMarkersController) return;

    const markerCount = appState.coordinateMarkersController.getMarkers?.().length || 0;
    if (!markerCount) {
      updateToolboxStatus();
      return;
    }

    appState.coordinateMarkersController.exportGeoJson();
    updateToolboxStatus();
  });

  applyToolboxMode();
}

function refreshSatelliteContrastMode() {
  const enabled = Boolean(dom.toggleSatelliteContrast?.checked);

  setSatelliteContrastMode(layerState, enabled);

  if (dom.satelliteContrastNote) {
    dom.satelliteContrastNote.classList.toggle('is-open', enabled);
  }

  if (enabled) {
    setStatus('Műholdas kontraszt mód bekapcsolva');
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

  dom.toggleFrontline.addEventListener('change', () => {
    if (dom.toggleFrontline.checked) {
      layerState.frontlineLayer.addTo(map);
    } else {
      map.removeLayer(layerState.frontlineLayer);
    }
  });

  dom.toggleAxes.addEventListener('change', () => {
    if (dom.toggleAxes.checked) {
      layerState.attackAxesLayer.addTo(map);
    } else {
      map.removeLayer(layerState.attackAxesLayer);
    }
  });

  dom.toggleBattleNodes.addEventListener('change', () => {
    if (dom.toggleBattleNodes.checked) {
      layerState.battleNodesLayer.addTo(map);
    } else {
      map.removeLayer(layerState.battleNodesLayer);
    }
  });

  dom.toggleDelta.addEventListener('change', () => {
    if (dom.toggleDelta.checked) {
      layerState.deltaLayer.addTo(map);
    } else {
      map.removeLayer(layerState.deltaLayer);
    }
  });

  dom.toggleHistoricalDelta?.addEventListener('change', renderHistoricalDelta);
  dom.historicalDeltaWindow?.addEventListener('change', renderHistoricalDelta);

  dom.toggleBorders.addEventListener('change', () => {
    if (dom.toggleBorders.checked) {
      layerState.borderLayer.addTo(map);
    } else {
      map.removeLayer(layerState.borderLayer);
    }
  });

  dom.toggleSuriyak?.addEventListener('change', refreshSuriyak);
  dom.toggleSatelliteContrast?.addEventListener('change', refreshSatelliteContrastMode);

  dom.suriyakCategoryList?.addEventListener('change', async (event) => {
    const target = event.target;
    if (!target?.classList?.contains('suriyak-category-toggle')) return;

    const categoryId = target.dataset.categoryId;
    if (!categoryId) return;

    if (!appState.suriyakSelectedCategories) {
      const legend = await loadSuriyakLegend();
      ensureSuriyakCategorySelection(legend);
    }

    if (target.checked) {
      appState.suriyakSelectedCategories.add(categoryId);
    } else {
      appState.suriyakSelectedCategories.delete(categoryId);
    }

    saveSuriyakCategorySelection();

    if (dom.toggleSuriyak?.checked) {
      await refreshSuriyak();
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

    // Deep strike overlay is isolated from the core front-map startup.
    await refreshDeepStrikes();

    updateSuriyakSubpanelVisibility(Boolean(dom.toggleSuriyak?.checked));
    await syncSuriyakLegendPanel();

    appState.annotationsController = initAnnotations({
      map,
      toggle: dom.toggleAnnotations,
      addButton: dom.btnAddAnnotation,
      clearButton: dom.btnClearAnnotations,
      textInput: dom.annotationText,
      typeSelect: dom.annotationType,
      summary: dom.annotationsSummary,
    });

    appState.coordinateMarkersController = initCoordinateMarkers({
      map,
      layerGroup: coordinateMarkerLayer,
      enabled: true,
    });

    appState.measureToolController = initMeasureTool({
      map,
      layerGroup: measureLayer,
      enabled: false,
      onStatusChange: (text) => {
        if (dom.toolboxStatus) {
          dom.toolboxStatus.innerHTML = text;
        }
      },
    });

    appState.objectIdentificationController = initObjectIdentificationTool({
      map,
      layerGroup: objectIdentificationLayer,
      enabled: false,
      getObjectTypeValue: () => dom.toolboxObjectType?.value || 'unknown',
      onStatusChange: (text) => {
        if (dom.toolboxStatus) {
          dom.toolboxStatus.innerHTML = text;
        }
      },
    });

    appState.satelliteController = await initSatelliteControls({
      map,
      satelliteLayer: satelliteImageLayer,
      dom,
      onStatus: setStatus,
    });

    bindToolboxControls();
    bindLayerToggles();
    bindDeepStrikeControls();
    refreshSatelliteContrastMode();
    bindControls(player);

    setStatus('Kész');
  } catch (error) {
    console.error('Init hiba:', error);
    setStatus(`Hiba: ${error.message}`);
  }
}

init();
