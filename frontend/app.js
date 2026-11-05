// Interfaz de una sola pantalla: dispositivo + día -> resumen, sesiones y mapa.
// Todas las fechas se muestran en America/Santiago, sin importar el navegador.

const TZ = "America/Santiago";
const PALETTE = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#4d7c0f",
];

const statusEl = document.getElementById("status");
const deviceSelect = document.getElementById("device-select");
const dayInput = document.getElementById("day-input");
const prevButton = document.getElementById("prev-day");
const nextButton = document.getElementById("next-day");
const totalReadingsEl = document.getElementById("total-readings");
const avgValueEl = document.getElementById("avg-value");
const totalSessionsEl = document.getElementById("total-sessions");
const sessionListEl = document.getElementById("session-list");

const dateFormatter = new Intl.DateTimeFormat("es-CL", {
  timeZone: TZ,
  dateStyle: "medium",
});
const dateTimeFormatter = new Intl.DateTimeFormat("es-CL", {
  timeZone: TZ,
  dateStyle: "short",
  timeStyle: "medium",
});
const timeFormatter = new Intl.DateTimeFormat("es-CL", {
  timeZone: TZ,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const state = {
  devices: [],
  device: null,
  day: null,
  firstDay: null,
  lastDay: null,
  map: null,
  layerGroup: null,
  layers: [],
  requestId: 0,
};

function setStatus(kind, message) {
  statusEl.dataset.kind = kind;
  statusEl.textContent = message;
}

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body && body.detail) {
        detail = typeof body.detail === "string" ? body.detail : detail;
      }
    } catch (_) {
      /* respuesta sin JSON: se queda el status */
    }
    throw new Error(`${detail} (${path})`);
  }
  return response.json();
}

function shiftDay(isoDay, delta) {
  const [year, month, day] = isoDay.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day));
  shifted.setUTCDate(shifted.getUTCDate() + delta);
  return shifted.toISOString().slice(0, 10);
}

function formatDay(isoDay) {
  const [year, month, day] = isoDay.split("-").map(Number);
  // Mediodía UTC: evita que un cambio de offset mueva la fecha mostrada.
  return dateFormatter.format(new Date(Date.UTC(year, month - 1, day, 12)));
}

function ensureMap() {
  if (state.map) return state.map;
  state.map = L.map("map", { zoomControl: true }).setView([-33.45, -70.66], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; colaboradores de OpenStreetMap",
  }).addTo(state.map);
  state.layerGroup = L.layerGroup().addTo(state.map);
  return state.map;
}

async function loadDevices() {
  setStatus("loading", "Cargando dispositivos…");
  const devices = await api("/devices");
  state.devices = devices;

  if (!devices.length) {
    deviceSelect.innerHTML = "";
    setStatus(
      "empty",
      "La base no tiene lecturas todavía. Carga un lote con `python -m app.load data/lote_1.csv`."
    );
    return;
  }

  deviceSelect.innerHTML = devices
    .map(
      (device) =>
        `<option value="${device.device_id}">${device.device_id}</option>`
    )
    .join("");

  applyDevice(devices[0].device_id);
  await loadDay();
}

function applyDevice(deviceId) {
  const device = state.devices.find((item) => item.device_id === deviceId);
  state.device = deviceId;
  state.firstDay = device ? device.first_day : null;
  state.lastDay = device ? device.last_day : null;
  state.day = state.firstDay;
  deviceSelect.value = deviceId;
  dayInput.value = state.day ?? "";
  updateDayButtons();
}

function updateDayButtons() {
  prevButton.disabled = !state.day || state.day <= state.firstDay;
  nextButton.disabled = !state.day || state.day >= state.lastDay;
}

async function loadDay() {
  if (!state.device || !state.day) return;

  const requestId = ++state.requestId;
  const device = state.device;
  const day = state.day;
  setStatus("loading", `Cargando ${day} de ${device}…`);

  try {
    const [summary, track] = await Promise.all([
      api(`/devices/${encodeURIComponent(device)}/days/${day}`),
      api(`/devices/${encodeURIComponent(device)}/days/${day}/track`),
    ]);
    if (requestId !== state.requestId) return; // respuesta vieja: se descarta

    renderSummary(summary, track);
    renderMap(track);

    if (summary.readings === 0) {
      setStatus("empty", `${device} no tiene lecturas el ${formatDay(day)}.`);
    } else {
      setStatus(
        "ok",
        `${device} · ${formatDay(day)} · ${summary.readings} lecturas · ` +
          `${summary.sessions.length} sesión(es)`
      );
    }
  } catch (error) {
    if (requestId !== state.requestId) return;
    clearView();
    setStatus(
      "error",
      `No se pudo cargar el día: ${error.message}. Revisa que la API y la base estén disponibles.`
    );
  }
}

function clearView() {
  totalReadingsEl.textContent = "–";
  avgValueEl.textContent = "–";
  totalSessionsEl.textContent = "–";
  sessionListEl.innerHTML = "";
  if (state.layerGroup) state.layerGroup.clearLayers();
  state.layers = [];
}

function renderSummary(summary, track) {
  totalReadingsEl.textContent = String(summary.readings);
  avgValueEl.textContent =
    summary.avg_value === null ? "sin datos" : summary.avg_value.toFixed(2);
  totalSessionsEl.textContent = String(summary.sessions.length);

  sessionListEl.innerHTML = "";
  if (!summary.sessions.length) {
    const hint = document.createElement("li");
    hint.className = "empty-hint";
    hint.textContent = "Sin sesiones que comiencen este día.";
    sessionListEl.appendChild(hint);
    return;
  }

  summary.sessions.forEach((session, index) => {
    const feature = track.features[index];
    const positions = feature?.properties?.positions ?? 0;
    const color = PALETTE[index % PALETTE.length];

    const item = document.createElement("li");
    item.className = "session";
    item.tabIndex = 0;
    item.dataset.index = String(index);
    item.innerHTML = `
      <span class="session__dot" style="background:${color}"></span>
      <span>
        <span class="session__times">${timeFormatter.format(new Date(session.start))} → ${timeFormatter.format(new Date(session.end))}</span>
        <br />
        <span class="session__meta">
          ${session.duration_min.toFixed(2)} min · ${session.readings} lecturas · ${positions} punto(s) en el mapa
        </span>
        ${positions === 0 ? '<br /><span class="session__note">Sin posición: no se dibuja en el mapa.</span>' : ""}
      </span>
    `;
    item.addEventListener("click", () => selectSession(index));
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") selectSession(index);
    });
    item.addEventListener("mouseenter", () => highlightLayer(index));
    item.addEventListener("mouseleave", () => highlightLayer(state.activeIndex));
    sessionListEl.appendChild(item);
  });
}

function renderMap(track) {
  const map = ensureMap();
  state.layerGroup.clearLayers();
  state.layers = [];
  state.activeIndex = null;

  const bounds = [];
  track.features.forEach((feature, index) => {
    const color = PALETTE[index % PALETTE.length];
    const geometry = feature.geometry;
    let layer = null;

    if (geometry && geometry.type === "LineString") {
      const latlngs = geometry.coordinates.map(([lon, lat]) => [lat, lon]);
      layer = L.polyline(latlngs, { color, weight: 4, opacity: 0.9 });
      latlngs.forEach((point) => bounds.push(point));
    } else if (geometry && geometry.type === "Point") {
      const [lon, lat] = geometry.coordinates;
      layer = L.circleMarker([lat, lon], {
        radius: 6,
        color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.85,
      });
      bounds.push([lat, lon]);
    }

    if (layer) {
      layer.addTo(state.layerGroup);
      layer.on("click", () => selectSession(index));
    }
    state.layers[index] = layer;
  });

  if (bounds.length) {
    map.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });
  } else {
    map.setView([-33.45, -70.66], 12);
  }
  // El panel pudo cambiar de tamaño al dibujar la lista de sesiones.
  setTimeout(() => map.invalidateSize(), 0);
}

function highlightLayer(index) {
  state.layers.forEach((layer, layerIndex) => {
    if (!layer || !layer.setStyle) return;
    const isActive = layerIndex === index;
    const baseWeight = layer instanceof L.CircleMarker ? 2 : 4;
    layer.setStyle({ weight: isActive ? baseWeight + 3 : baseWeight });
    if (isActive && layer.bringToFront) layer.bringToFront();
  });
}

function selectSession(index) {
  state.activeIndex = index;
  highlightLayer(index);
  sessionListEl.querySelectorAll(".session").forEach((item) => {
    item.setAttribute(
      "aria-current",
      Number(item.dataset.index) === index ? "true" : "false"
    );
  });
}

deviceSelect.addEventListener("change", () => {
  applyDevice(deviceSelect.value);
  loadDay();
});

dayInput.addEventListener("change", () => {
  if (!dayInput.value) return;
  state.day = dayInput.value;
  updateDayButtons();
  loadDay();
});

prevButton.addEventListener("click", () => {
  state.day = shiftDay(state.day, -1);
  dayInput.value = state.day;
  updateDayButtons();
  loadDay();
});

nextButton.addEventListener("click", () => {
  state.day = shiftDay(state.day, 1);
  dayInput.value = state.day;
  updateDayButtons();
  loadDay();
});

ensureMap();
loadDevices().catch((error) => {
  setStatus(
    "error",
    `No se pudieron cargar los dispositivos: ${error.message}. Revisa que la API y la base estén disponibles.`
  );
});


