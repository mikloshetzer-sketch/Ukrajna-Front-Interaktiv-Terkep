import { SatelliteArchive, formatSatelliteRecordLabel } from './satelliteArchive.js';

function setText(element, text) {
  if (element) {
    element.textContent = text;
  }
}

function setHtml(element, html) {
  if (element) {
    element.innerHTML = html;
  }
}

function clearSelect(selectElement) {
  if (!selectElement) return;

  while (selectElement.firstChild) {
    selectElement.removeChild(selectElement.firstChild);
  }
}

function addOption(selectElement, value, label, selected = false) {
  if (!selectElement) return;

  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  option.selected = selected;

  selectElement.appendChild(option);
}

function formatDateForUi(record) {
  if (!record) return 'n/a';

  return (
    record.timestamp ||
    record.generated_at ||
    record.imagery?.requested_time_range?.to ||
    'n/a'
  );
}

function buildSummary(record) {
  if (!record) {
    return 'Nincs kiválasztott Sentinel-2 kép.';
  }

  const bbox = record.target_area?.bbox || record.bbox || null;
  const radius = record.target_area?.radius_km ?? 'n/a';
  const lat = record.target_area?.lat ?? 'n/a';
  const lon = record.target_area?.lon ?? 'n/a';

  return `
    <b>${record.location_name}</b><br>
    Dátum: <strong>${formatDateForUi(record)}</strong><br>
    Középpont: <strong>${lat}, ${lon}</strong><br>
    Sugár: <strong>${radius} km</strong><br>
    ${bbox ? `BBox: <strong>${bbox.join(', ')}</strong><br>` : ''}
    Forrás: Sentinel-2 L2A True Color / Copernicus / Sentinel Hub
  `;
}

export async function initSatelliteControls({
  map,
  satelliteLayer,
  dom,
  onStatus,
} = {}) {
  const archive = new SatelliteArchive();

  const state = {
    archive,
    selectedLocationSlug: null,
    selectedRecordId: null,
    currentRecord: null,
    ready: false,
  };

  function status(text) {
    if (typeof onStatus === 'function') {
      onStatus(text);
    }
  }

  function getSelectedRecord() {
    if (state.selectedRecordId) {
      const record = archive.getRecordById(state.selectedRecordId);
      if (record) return record;
    }

    if (state.selectedLocationSlug) {
      const records = archive.getRecordsByLocation(state.selectedLocationSlug);
      if (records.length) return records[0];
    }

    return archive.getDefaultRecord();
  }

  function refreshImageSelect() {
    if (!dom.satelliteImageSelect) return;

    clearSelect(dom.satelliteImageSelect);

    const records = state.selectedLocationSlug
      ? archive.getRecordsByLocation(state.selectedLocationSlug)
      : archive.getRecords();

    if (!records.length) {
      addOption(dom.satelliteImageSelect, '', 'Nincs elérhető kép', true);
      return;
    }

    records.forEach((record, index) => {
      addOption(
        dom.satelliteImageSelect,
        record.id,
        formatSatelliteRecordLabel(record),
        index === 0
      );
    });

    state.selectedRecordId = records[0].id;
  }

  function refreshLocationSelect() {
    if (!dom.satelliteLocationSelect) return;

    clearSelect(dom.satelliteLocationSelect);

    const locations = archive.getLocations();

    if (!locations.length) {
      addOption(dom.satelliteLocationSelect, '', 'Nincs elérhető helyszín', true);
      return;
    }

    locations.forEach((location, index) => {
      addOption(
        dom.satelliteLocationSelect,
        location.slug,
        `${location.name} (${location.count})`,
        index === 0
      );
    });

    state.selectedLocationSlug = locations[0].slug;
  }

  function applySelectedRecord(options = {}) {
    const record = getSelectedRecord();
    state.currentRecord = record;

    setHtml(dom.satelliteSummary, buildSummary(record));

    if (!record) {
      satelliteLayer.clear();
      return null;
    }

    if (dom.toggleSatellite?.checked) {
      satelliteLayer.show(record, {
        fitBounds: Boolean(options.fitBounds),
      });
    }

    return record;
  }

  function updateAvailabilityUi() {
    if (!archive.isAvailable()) {
      if (dom.toggleSatellite) {
        dom.toggleSatellite.checked = false;
        dom.toggleSatellite.disabled = true;
      }

      if (dom.satelliteLocationSelect) {
        dom.satelliteLocationSelect.disabled = true;
      }

      if (dom.satelliteImageSelect) {
        dom.satelliteImageSelect.disabled = true;
      }

      if (dom.satelliteOpacity) {
        dom.satelliteOpacity.disabled = true;
      }

      setHtml(dom.satelliteSummary, 'Nincs elérhető Sentinel-2 archívum.');
      return;
    }

    if (dom.toggleSatellite) dom.toggleSatellite.disabled = false;
    if (dom.satelliteLocationSelect) dom.satelliteLocationSelect.disabled = false;
    if (dom.satelliteImageSelect) dom.satelliteImageSelect.disabled = false;
    if (dom.satelliteOpacity) dom.satelliteOpacity.disabled = false;
  }

  try {
    await archive.load();
    state.ready = true;

    updateAvailabilityUi();
    refreshLocationSelect();
    refreshImageSelect();
    applySelectedRecord({ fitBounds: false });

    status(`Sentinel-2 archívum betöltve: ${archive.getRecords().length} kép`);
  } catch (error) {
    console.error('Sentinel-2 archívum hiba:', error);

    updateAvailabilityUi();
    setHtml(dom.satelliteSummary, `Sentinel-2 archívum hiba: ${error.message}`);
    status(`Sentinel-2 hiba: ${error.message}`);
  }

  dom.toggleSatellite?.addEventListener('change', () => {
    const record = getSelectedRecord();

    if (dom.toggleSatellite.checked) {
      if (record) {
        satelliteLayer.show(record, { fitBounds: true });
        status(`Sentinel-2 réteg bekapcsolva: ${record.location_name}`);
      }
    } else {
      satelliteLayer.hide();
      status('Sentinel-2 réteg kikapcsolva');
    }
  });

  dom.satelliteLocationSelect?.addEventListener('change', () => {
    state.selectedLocationSlug = dom.satelliteLocationSelect.value || null;
    state.selectedRecordId = null;

    refreshImageSelect();
    applySelectedRecord({ fitBounds: true });

    const record = getSelectedRecord();
    if (record) {
      status(`Sentinel-2 helyszín: ${record.location_name}`);
    }
  });

  dom.satelliteImageSelect?.addEventListener('change', () => {
    state.selectedRecordId = dom.satelliteImageSelect.value || null;
    const record = applySelectedRecord({ fitBounds: true });

    if (record) {
      status(`Sentinel-2 kép kiválasztva: ${record.location_name}`);
    }
  });

  dom.satelliteOpacity?.addEventListener('input', () => {
    const value = Number(dom.satelliteOpacity.value || 72) / 100;
    satelliteLayer.setOpacity(value);

    setText(dom.satelliteOpacityValue, `${Math.round(value * 100)}%`);
  });

  dom.btnSatelliteFit?.addEventListener('click', () => {
    const record = getSelectedRecord();

    if (record) {
      satelliteLayer.show(record, { fitBounds: true });
      if (dom.toggleSatellite) dom.toggleSatellite.checked = true;
      status(`Sentinel-2 nézetre igazítva: ${record.location_name}`);
    }
  });

  dom.btnSatelliteRefresh?.addEventListener('click', async () => {
    try {
      await archive.load();

      updateAvailabilityUi();
      refreshLocationSelect();
      refreshImageSelect();
      applySelectedRecord({ fitBounds: false });

      status(`Sentinel-2 archívum frissítve: ${archive.getRecords().length} kép`);
    } catch (error) {
      console.error('Sentinel-2 frissítési hiba:', error);
      setHtml(dom.satelliteSummary, `Sentinel-2 frissítési hiba: ${error.message}`);
      status(`Sentinel-2 frissítési hiba: ${error.message}`);
    }
  });

  return {
    archive,
    state,
    getSelectedRecord,
    applySelectedRecord,
  };
}
