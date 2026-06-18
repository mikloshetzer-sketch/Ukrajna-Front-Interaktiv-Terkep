const ANNOTATION_STORAGE_KEY = 'ukraine_front_map_annotations_v1';

function loadAnnotations() {
  try {
    const raw = localStorage.getItem(ANNOTATION_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAnnotations(items) {
  localStorage.setItem(ANNOTATION_STORAGE_KEY, JSON.stringify(items));
}

function getTypeStyle(type) {
  if (type === 'operation') return { icon: '⚔️', color: '#b91c1c', title: 'Műveleti' };
  if (type === 'logistics') return { icon: '🚚', color: '#ea580c', title: 'Logisztikai' };
  if (type === 'warning') return { icon: '⚠️', color: '#ca8a04', title: 'Figyelmeztetés' };
  if (type === 'note') return { icon: '📝', color: '#374151', title: 'Megjegyzés' };
  return { icon: '📊', color: '#2563eb', title: 'Elemző' };
}

function createAnnotationIcon(item) {
  const style = getTypeStyle(item.type);

  return L.divIcon({
    className: '',
    html: `
      <div style="
        background: rgba(255,255,255,0.96);
        border: 2px solid ${style.color};
        border-radius: 10px;
        padding: 8px 10px;
        min-width: 220px;
        max-width: 280px;
        color: #111827;
        font-size: 12px;
        line-height: 1.35;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        white-space: normal;
      ">
        <div style="font-weight:700; margin-bottom:4px; color:${style.color};">
          ${style.icon} ${style.title}
        </div>
        <div>${String(item.text || '').replace(/\n/g, '<br>')}</div>
        <div style="margin-top:5px; color:#6b7280; font-size:11px;">
          Jobb klikk: törlés · Mozgatható
        </div>
      </div>
    `,
    iconSize: [260, 110],
    iconAnchor: [20, 20],
  });
}

export function initAnnotations({
  map,
  toggle,
  addButton,
  clearButton,
  textInput,
  typeSelect,
  summary,
}) {
  const layer = L.layerGroup().addTo(map);
  let annotations = loadAnnotations();
  let addMode = false;

  function updateSummary() {
    if (!summary) return;

    if (!annotations.length) {
      summary.textContent = 'Nincs még elemző megjegyzés.';
      return;
    }

    summary.innerHTML = `
      Megjegyzések száma: <strong>${annotations.length}</strong><br>
      Új megjegyzéshez nyomd meg a gombot, majd kattints a térképre.
    `;
  }

  function render() {
    layer.clearLayers();

    annotations.forEach((item) => {
      const marker = L.marker([item.lat, item.lng], {
        draggable: true,
        interactive: true,
        icon: createAnnotationIcon(item),
      }).addTo(layer);

      marker.on('dragend', (event) => {
        const pos = event.target.getLatLng();
        annotations = annotations.map(existing =>
          existing.id === item.id
            ? { ...existing, lat: pos.lat, lng: pos.lng }
            : existing
        );
        saveAnnotations(annotations);
      });

      marker.on('contextmenu', () => {
        annotations = annotations.filter(existing => existing.id !== item.id);
        saveAnnotations(annotations);
        render();
        updateSummary();
      });
    });

    updateSummary();
  }

  function addAnnotation(latlng) {
    const text = String(textInput?.value || '').trim();

    if (!text) {
      alert('Előbb írj be egy megjegyzést a bal oldali szövegmezőbe.');
      return;
    }

    const item = {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      lat: latlng.lat,
      lng: latlng.lng,
      text,
      type: typeSelect?.value || 'analysis',
      createdAt: new Date().toISOString(),
    };

    annotations.push(item);
    saveAnnotations(annotations);
    render();

    if (textInput) textInput.value = '';
  }

  addButton?.addEventListener('click', () => {
    addMode = true;
    if (summary) {
      summary.innerHTML = 'Kattints a térképen oda, ahová a megjegyzést szeretnéd tenni.';
    }
  });

  map.on('click', (event) => {
    if (!addMode) return;
    addMode = false;
    addAnnotation(event.latlng);
  });

  clearButton?.addEventListener('click', () => {
    if (!confirm('Biztosan törlöd az összes elemző megjegyzést?')) return;
    annotations = [];
    saveAnnotations(annotations);
    render();
  });

  toggle?.addEventListener('change', () => {
    if (toggle.checked) {
      layer.addTo(map);
    } else {
      map.removeLayer(layer);
    }
  });

  render();

  return {
    layer,
    render,
    clear: () => {
      annotations = [];
      saveAnnotations(annotations);
      render();
    },
  };
}
