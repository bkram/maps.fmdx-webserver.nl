// ================ Viewport sizing helpers ================
const viewportVarName = '--viewport-h';
const viewportRoot = typeof document !== 'undefined' ? document.documentElement : null;

function updateViewportHeight() {
  if (!viewportRoot || !viewportRoot.style) return;

  let height = null;
  if (typeof window !== 'undefined') {
    if (window.visualViewport && Number.isFinite(window.visualViewport.height)) {
      height = window.visualViewport.height;
    } else if (Number.isFinite(window.innerHeight)) {
      height = window.innerHeight;
    }
  }

  if (!Number.isFinite(height) || height <= 0) return;
  viewportRoot.style.setProperty(viewportVarName, `${height}px`);
}

updateViewportHeight();

if (typeof window !== 'undefined') {
  window.addEventListener('resize', updateViewportHeight, { passive: true });
  window.addEventListener('orientationchange', updateViewportHeight, { passive: true });
  window.addEventListener('pageshow', updateViewportHeight, { passive: true });

  if (window.visualViewport && typeof window.visualViewport.addEventListener === 'function') {
    window.visualViewport.addEventListener('resize', updateViewportHeight);
  }
}

// ================ Map base ================
const map = L.map('map', {
  preferCanvas: true,
  worldCopyJump: true,
  zoomControl: false
}).setView([20, 0], 2);

L.control.zoom({ position: 'bottomright' }).addTo(map);

const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
});
const noLabels = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd', maxZoom: 20, attribution: '&copy; OSM &copy; CARTO'
});
const dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd', maxZoom: 20, attribution: '&copy; OSM &copy; CARTO'
});
const voyager = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd', maxZoom: 20, attribution: '&copy; OSM &copy; CARTO'
});
const hot = L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
  maxZoom: 20, attribution: '&copy; OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team'
});
const topo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
  maxZoom: 17, attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap'
});
const esriStreet = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  { attribution: 'Tiles &copy; Esri' }
);
const satellite = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  { attribution: 'Tiles © Esri' }
).addTo(map);

L.control.layers(
  {
    'Satellite': satellite,
    'OSM Roads': osm,
    'OSM HOT': hot,
    'Light': noLabels,
    'Dark': dark,
    'Voyager': voyager,
    'Topographic': topo,
    'Esri Streets': esriStreet
  },
  {},
  { collapsed: true, position: 'topright' }
).addTo(map);

addEventListener('load',  () => map.invalidateSize());
addEventListener('resize', () => map.invalidateSize());

// ================ State ================
const markerGroup = L.featureGroup().addTo(map);
const markerById = new Map();
const liById     = new Map();
let all = [];
let selectedId = null;
let selectedMarkerEl = null;
let sidebarHidden = false;
let sidebarToggleButton = null;
const scopedBlacklist = new Map();
let currentBaseList = [];
let currentAdjustedList = [];

const defaultMarkerIcon = L.divIcon({
  className: 'receiver-pin',
  html: '<span class="receiver-pin__body"></span><span class="receiver-pin__shadow"></span>',
  iconSize: [24, 34],
  iconAnchor: [12, 32],
  popupAnchor: [0, -28]
});

const lockedMarkerIcon = L.divIcon({
  className: 'receiver-pin receiver-pin--locked',
  html: '<span class="receiver-pin__body"></span><span class="receiver-pin__shadow"></span>',
  iconSize: [24, 34],
  iconAnchor: [12, 32],
  popupAnchor: [0, -28]
});

const widebandMarkerIcon = L.divIcon({
  className: 'receiver-pin receiver-pin--wideband',
  html: '<span class="receiver-pin__body"></span><span class="receiver-pin__shadow"></span>',
  iconSize: [24, 34],
  iconAnchor: [12, 32],
  popupAnchor: [0, -28]
});

// DOM
const sideListEl  = document.getElementById('side-list');
const sideCountEl = document.getElementById('side-count');
const sidebarEl   = document.getElementById('sidebar');
const sideAvailableEl = document.getElementById('side-available');
const sideLockedEl = document.getElementById('side-locked');
const sideUnreachableEl = document.getElementById('side-unreachable');
const DESKTOP_MEDIA_QUERY = '(min-width: 901px)';
const desktopMediaQuery = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  ? window.matchMedia(DESKTOP_MEDIA_QUERY)
  : null;

const scopeAttr = document.body ? document.body.getAttribute('data-map-scope') : null;
const scopeValue = typeof scopeAttr === 'string' ? scopeAttr.trim().toLowerCase() : '';
const scopeLabelAttr = document.body ? document.body.getAttribute('data-map-scope-label') : null;
const scopeLabelValue = typeof scopeLabelAttr === 'string' ? scopeLabelAttr.trim() : '';
const mapScope = scopeValue ? scopeValue : 'world';
const isWorldScope = mapScope === 'world';
const fallbackScopeLabel = mapScope ? mapScope.toUpperCase() : 'WORLD';
const scopeLabel = scopeLabelValue
  ? scopeLabelValue
  : (isWorldScope ? 'Worldwide' : fallbackScopeLabel);
const sidebarScopeLabel = isWorldScope
  ? 'Worldwide server list'
  : `${scopeLabel} server list`;
const sidebarToggleTarget = isWorldScope
  ? 'worldwide server list'
  : `${scopeLabel} server list`;

if (
  sidebarEl
  && (
    sidebarEl.classList.contains('map-sidebar--hidden')
    || (desktopMediaQuery && !desktopMediaQuery.matches)
  )
) {
  sidebarHidden = true;
}

if (sidebarEl) {
  sidebarEl.setAttribute('aria-label', sidebarScopeLabel);
  sidebarEl.dataset.scope = mapScope;
  if (scopeLabel) sidebarEl.dataset.scopeLabel = scopeLabel;
}

if (sideCountEl) {
  sideCountEl.dataset.scope = mapScope;
  if (scopeLabel) sideCountEl.dataset.scopeLabel = scopeLabel;
  const initialUnit = 'servers';
  let suffix;
  suffix = isWorldScope ? 'worldwide' : `in ${scopeLabel}`;
  const initialLabel = `0 ${initialUnit} ${suffix}`;
  sideCountEl.setAttribute('aria-label', initialLabel);
  sideCountEl.setAttribute('title', initialLabel);
}

// ================ Sidebar toggle ================
function setSidebarVisibility(hidden) {
  const shouldHide = Boolean(hidden);
  const sidebarWasHidden = sidebarEl
    ? sidebarEl.classList.contains('map-sidebar--hidden')
    : sidebarHidden;
  sidebarHidden = shouldHide;

  if (sidebarEl) {
    sidebarEl.classList.toggle('map-sidebar--hidden', shouldHide);
    sidebarEl.setAttribute('aria-hidden', shouldHide ? 'true' : 'false');
    if ('inert' in sidebarEl) {
      sidebarEl.inert = shouldHide;
    }
  }

  if (sidebarToggleButton) {
    sidebarToggleButton.classList.toggle('sidebar-toggle-control__button--hidden', shouldHide);
    sidebarToggleButton.setAttribute('aria-expanded', shouldHide ? 'false' : 'true');
    const showText = `Show ${sidebarToggleTarget}`;
    const hideText = `Hide ${sidebarToggleTarget}`;
    sidebarToggleButton.setAttribute('aria-label', shouldHide ? showText : hideText);
    sidebarToggleButton.setAttribute('title', shouldHide ? showText : hideText);
  }

  if (shouldHide !== sidebarWasHidden && map && typeof map.invalidateSize === 'function') {
    requestAnimationFrame(() => map.invalidateSize());
  }
}

function setupSidebarToggleControl() {
  if (!sidebarEl) return;

  const toggleControl = L.control({ position: 'topright' });
  toggleControl.onAdd = function onAdd() {
    const container = L.DomUtil.create('div', 'leaflet-bar sidebar-toggle-control');
    const link = L.DomUtil.create('a', 'sidebar-toggle-control__button', container);
    link.href = '#';
    const showText = `Show ${sidebarToggleTarget}`;
    const hideText = `Hide ${sidebarToggleTarget}`;
    link.title = sidebarHidden ? showText : hideText;
    link.setAttribute('role', 'button');
    link.setAttribute('aria-label', sidebarHidden ? showText : hideText);
    link.setAttribute('aria-controls', 'sidebar');
    link.setAttribute('aria-expanded', sidebarHidden ? 'false' : 'true');
    link.innerHTML = '<span aria-hidden="true" class="sidebar-toggle-control__icon"></span>';

    L.DomEvent.disableClickPropagation(container);
    L.DomEvent.disableScrollPropagation(container);

    L.DomEvent.on(link, 'click', (event) => {
      L.DomEvent.preventDefault(event);
      L.DomEvent.stopPropagation(event);
      setSidebarVisibility(!sidebarHidden);
    });

    L.DomEvent.on(link, 'keydown', (event) => {
      if (event.key === ' ' || event.key === 'Spacebar') {
        L.DomEvent.preventDefault(event);
        L.DomEvent.stopPropagation(event);
        setSidebarVisibility(!sidebarHidden);
      }
    });

    sidebarToggleButton = link;
    setSidebarVisibility(sidebarHidden);

    return container;
  };

  toggleControl.addTo(map);
}

setupSidebarToggleControl();

function syncSidebarLayout() {
  if (!sidebarEl) return;
  if (!desktopMediaQuery) return;

  setSidebarVisibility(!desktopMediaQuery.matches);
}

if (desktopMediaQuery) {
  if (typeof desktopMediaQuery.addEventListener === 'function') {
    desktopMediaQuery.addEventListener('change', syncSidebarLayout);
  } else if (typeof desktopMediaQuery.addListener === 'function') {
    desktopMediaQuery.addListener(syncSidebarLayout);
  }
}

// ================ Utils ================
const cleanString = (value) =>
  (typeof value === 'string' && value.trim().length) ? value.trim() : null;

const COORD_MATCH_TOLERANCE = 1e-5;

const pickField = (source, keys) => {
  if (!source || typeof source !== 'object' || !Array.isArray(keys)) return null;
  for (let i = 0; i < keys.length; i += 1) {
    const key = keys[i];
    if (!key || typeof key !== 'string') continue;
    const value = cleanString(source[key]);
    if (value) return value;
  }
  return null;
};

const normalizeUrl = (value) => {
  if (value === null || value === undefined) return null;

  const text = String(value).trim();
  if (!text) return null;

  const normalized = text.replace(/\/+$/, '');
  if (!normalized) return null;

  return normalized.toLowerCase();
};

const hasFmtunerSupport = (value) => {
  const normalized = normalizeUrl(value);
  if (!normalized) return false;

  try {
    const parsed = new URL(normalized);
    const hostname = String(parsed.hostname || '').toLowerCase();
    return hostname === 'fmtuner.org' || hostname.endsWith('.fmtuner.org');
  } catch (err) {
    return normalized.includes('fmtuner.org');
  }
};

function setScopedBlacklist(source) {
  scopedBlacklist.clear();

  if (!source || typeof source !== 'object') return;

  const entries = Object.entries(source);
  for (let i = 0; i < entries.length; i += 1) {
    const [scope, list] = entries[i];
    if (typeof scope !== 'string') continue;
    if (!Array.isArray(list) || list.length === 0) continue;

    const scopeKey = scope.trim().toLowerCase();
    if (!scopeKey) continue;

    const parsed = [];
    for (let j = 0; j < list.length; j += 1) {
      const entry = list[j];
      if (!entry || typeof entry !== 'object') continue;

      const url = normalizeUrl(entry.url);
      let lat = null;
      let lng = null;

      const coords = entry.coords;
      if (Array.isArray(coords) && coords.length >= 2) {
        const latCandidate = Number(coords[0]);
        const lngCandidate = Number(coords[1]);
        if (Number.isFinite(latCandidate) && Number.isFinite(lngCandidate)) {
          lat = latCandidate;
          lng = lngCandidate;
        }
      }

      if (!url && lat === null && lng === null) continue;

      const tuner = typeof entry.tuner === 'string' ? entry.tuner.trim().toLowerCase() : null;
      const name = typeof entry.name === 'string' ? entry.name.trim().toLowerCase() : null;

      parsed.push({ url, lat, lng, tuner, name });
    }

    if (parsed.length > 0) {
      scopedBlacklist.set(scopeKey, parsed);
    }
  }
}

function isBlacklistedForScope(scope, candidate) {
  if (!candidate) return false;
  if (!scope) return false;

  const key = String(scope).trim().toLowerCase();
  if (!key) return false;

  const entries = scopedBlacklist.get(key);
  if (!Array.isArray(entries) || entries.length === 0) return false;

  const urlKey = candidate.normalizedUrl || normalizeUrl(candidate.url);
  const latValue = Number.isFinite(candidate.lat) ? candidate.lat : null;
  const lngValue = Number.isFinite(candidate.lng) ? candidate.lng : null;
  const tunerValue = typeof candidate.tuner === 'string' ? candidate.tuner.trim().toLowerCase() : null;
  const nameValue = typeof candidate.name === 'string' ? candidate.name.trim().toLowerCase() : null;

  for (let i = 0; i < entries.length; i += 1) {
    const entry = entries[i];
    if (!entry) continue;

    if (entry.url) {
      if (!urlKey || entry.url !== urlKey) {
        continue;
      }
    }

    if (typeof entry.lat === 'number' && typeof entry.lng === 'number') {
      if (latValue === null || lngValue === null) {
        continue;
      }
      if (Math.abs(latValue - entry.lat) > COORD_MATCH_TOLERANCE) {
        continue;
      }
      if (Math.abs(lngValue - entry.lng) > COORD_MATCH_TOLERANCE) {
        continue;
      }
    }

    if (entry.tuner && entry.tuner !== tunerValue) {
      continue;
    }

    if (entry.name && entry.name !== nameValue) {
      continue;
    }

    return true;
  }

  return false;
}

function getBlacklistedScopes(candidate) {
  const matches = [];
  scopedBlacklist.forEach((_, scope) => {
    if (isBlacklistedForScope(scope, candidate)) {
      matches.push(scope);
    }
  });
  return matches;
}

const SUB_BAND_MIN = 83;
const SUB_BAND_MAX = 87.5;
const SUB_BAND_EPSILON = 0.01;

const DEG_TO_RAD = Math.PI / 180;
const METERS_PER_DEGREE_LAT = 111_320;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function approxDistanceMeters(lat1, lng1, lat2, lng2) {
  if (!Number.isFinite(lat1) || !Number.isFinite(lng1) || !Number.isFinite(lat2) || !Number.isFinite(lng2)) {
    return Infinity;
  }
  const latMeters = (lat2 - lat1) * METERS_PER_DEGREE_LAT;
  const avgLat = (lat1 + lat2) / 2;
  const metersPerDegreeLng = METERS_PER_DEGREE_LAT * Math.max(Math.cos(avgLat * DEG_TO_RAD), 0.0001);
  const lngMeters = (lng2 - lng1) * metersPerDegreeLng;
  return Math.hypot(latMeters, lngMeters);
}

function metersToLatDelta(meters) {
  if (!Number.isFinite(meters)) return 0;
  return meters / METERS_PER_DEGREE_LAT;
}

function metersToLngDelta(meters, referenceLat) {
  if (!Number.isFinite(meters)) return 0;
  const lat = Number.isFinite(referenceLat) ? referenceLat : 0;
  const cosLat = Math.max(Math.cos(lat * DEG_TO_RAD), 0.0001);
  return meters / (METERS_PER_DEGREE_LAT * cosLat);
}

function pixelsToMeters(lat, lng, pixels, zoom) {
  if (!Number.isFinite(pixels) || pixels <= 0) return 0;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return 0;
  if (!map || typeof map.project !== 'function' || typeof map.unproject !== 'function') return 0;
  if (typeof L !== 'object' || typeof L.latLng !== 'function' || typeof L.point !== 'function') return 0;

  const resolvedZoom = Number.isFinite(zoom)
    ? zoom
    : (typeof map.getZoom === 'function' ? map.getZoom() : null);
  if (!Number.isFinite(resolvedZoom)) return 0;

  try {
    const origin = L.latLng(lat, lng);
    const originPoint = map.project(origin, resolvedZoom);
    const offsetPoint = L.point(originPoint.x + pixels, originPoint.y);
    const offsetLatLng = map.unproject(offsetPoint, resolvedZoom);
    return approxDistanceMeters(lat, lng, offsetLatLng.lat, offsetLatLng.lng);
  } catch (err) {
    return 0;
  }
}

const convertToMHz = (value, hint = '') => {
  if (!Number.isFinite(value)) return null;
  const h = String(hint || '').toLowerCase();
  if (h.includes('ghz')) return value * 1000;
  if (h.includes('mhz')) return value;
  if (h.includes('khz')) return value / 1000;
  if (h.includes('hz')) return value / 1_000_000;
  if (!h && value >= 1e6) return value / 1_000_000;
  if (!h && value >= 1e3 && value <= 500_000) return value / 1_000;
  return value;
};

const frequencyValueToMHz = (value) => {
  if (value == null) return null;
  if (typeof value === 'number') return convertToMHz(value);
  if (typeof value === 'string') {
    const normalized = value.trim().replace(/,/g, '.');
    if (!normalized) return null;
    const match = /(-?\d+(?:\.\d+)?)(?:\s*(ghz|mhz|khz|hz))?/i.exec(normalized);
    if (!match) return null;
    const raw = Number.parseFloat(match[1]);
    if (!Number.isFinite(raw)) return null;
    const unit = (match[2] || '').toLowerCase();
    return convertToMHz(raw, unit || normalized);
  }
  return null;
};

const parseFrequencyRangesFromString = (text) => {
  if (!text) return [];
  const normalized = String(text).trim().replace(/,/g, '.');
  if (!normalized) return [];
  const ranges = [];
  const rangeRegex = /(-?\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)?\s*(?:-|–|—|to)\s*(-?\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)?/gi;
  let match;
  while ((match = rangeRegex.exec(normalized)) !== null) {
    const startRaw = Number.parseFloat(match[1]);
    const endRaw = Number.parseFloat(match[3]);
    if (!Number.isFinite(startRaw) || !Number.isFinite(endRaw)) continue;
    const unitStart = (match[2] || match[4] || '').toLowerCase();
    const unitEnd = (match[4] || match[2] || '').toLowerCase();
    const startMHz = convertToMHz(startRaw, unitStart || normalized);
    const endMHz = convertToMHz(endRaw, unitEnd || normalized);
    if (!Number.isFinite(startMHz) || !Number.isFinite(endMHz)) continue;
    const min = Math.min(startMHz, endMHz);
    const max = Math.max(startMHz, endMHz);
    ranges.push({ min, max });
  }
  if (!ranges.length) {
    const tokenRegex = /(-?\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)?/gi;
    const values = [];
    while ((match = tokenRegex.exec(normalized)) !== null) {
      const raw = Number.parseFloat(match[1]);
      if (!Number.isFinite(raw)) continue;
      const unit = (match[2] || '').toLowerCase();
      const mhz = convertToMHz(raw, unit || normalized);
      if (!Number.isFinite(mhz)) continue;
      if (mhz < 20 || mhz > 500) continue;
      values.push(mhz);
    }
    if (values.length >= 2) {
      const min = Math.min(...values);
      const max = Math.max(...values);
      ranges.push({ min, max });
    }
  }
  return ranges;
};

const rangeCoversSubBand = ({ min, max }) =>
  Number.isFinite(min) && Number.isFinite(max) &&
  min <= SUB_BAND_MIN + SUB_BAND_EPSILON &&
  max >= SUB_BAND_MAX - SUB_BAND_EPSILON;

const detectExtendedRange = (item) => {
  if (!item) return false;
  const rawLimit = typeof item.bwLimit === 'string'
    ? item.bwLimit
    : (typeof item.bwlimit === 'string'
      ? item.bwlimit
      : (typeof item.bw_limit === 'string' ? item.bw_limit : null));

  if (typeof rawLimit === 'string' && rawLimit.trim() === '') return true;

  const limit = cleanString(rawLimit);
  if (limit && parseFrequencyRangesFromString(limit).some(rangeCoversSubBand)) {
    return true;
  }

  const minCandidates = [
    item.minFreq, item.minfreq, item.min_frequency,
    item.freqMin, item.frequencyMin, item.freq_min,
    item.bwMin, item.bw_min, item.lowerFreq, item.lowerFrequency,
    item.frequencyLower, item.lower_limit, item.lowerLimit
  ];
  const maxCandidates = [
    item.maxFreq, item.maxfreq, item.max_frequency,
    item.freqMax, item.frequencyMax, item.freq_max,
    item.bwMax, item.bw_max, item.upperFreq, item.upperFrequency,
    item.frequencyUpper, item.upper_limit, item.upperLimit
  ];

  const minMHz = minCandidates
    .map(frequencyValueToMHz)
    .find(v => Number.isFinite(v));
  const maxMHz = maxCandidates
    .map(frequencyValueToMHz)
    .find(v => Number.isFinite(v));

  if (Number.isFinite(minMHz) && Number.isFinite(maxMHz)) {
    return rangeCoversSubBand({ min: minMHz, max: maxMHz });
  }
  if (Number.isFinite(minMHz)) {
    return minMHz <= SUB_BAND_MIN + SUB_BAND_EPSILON && (!Number.isFinite(maxMHz) || maxMHz >= SUB_BAND_MAX - SUB_BAND_EPSILON);
  }
  if (Number.isFinite(maxMHz)) {
    return maxMHz >= SUB_BAND_MAX - SUB_BAND_EPSILON && (!Number.isFinite(minMHz) || minMHz <= SUB_BAND_MIN + SUB_BAND_EPSILON);
  }
  return false;
};

function esc(value) {
  const source = String(value);
  return source
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

const COUNTRY_ALIASES = {
  NETHERLANDS: 'NL',
  'THE NETHERLANDS': 'NL',
  'NETHERLANDS (THE)': 'NL',
  HOLLAND: 'NL',
  NEDERLAND: 'NL',
  USA: 'US',
  'UNITED STATES': 'US',
  'UNITED STATES OF AMERICA': 'US',
  'UNITED STATES (THE)': 'US',
  UK: 'GB',
  'UNITED KINGDOM': 'GB',
  'UNITED KINGDOM (THE)': 'GB',
  'GREAT BRITAIN': 'GB',
  ENGLAND: 'GB',
  SCOTLAND: 'GB',
  WALES: 'GB',
  JAPAN: 'JP',
  'JAPAN (THE)': 'JP'
};

const ISO3_TO_ISO2 = {
  NLD: 'NL',
  USA: 'US',
  GBR: 'GB',
  JPN: 'JP'
};

const normalizeCountryCode = (country) => {
  if (!country) return null;
  const s = String(country).trim();
  if (!s) return null;
  const upper = s.toUpperCase();
  if (/^[A-Z]{2}$/.test(upper)) return upper;
  if (ISO3_TO_ISO2[upper]) return ISO3_TO_ISO2[upper];
  if (COUNTRY_ALIASES[upper]) return COUNTRY_ALIASES[upper];
  return null;
};
const iso2ToFlag = (cc) => {
  if (!cc || cc.length !== 2) return '🌐';
  const A = 0x1F1E6;
  const a = cc.toUpperCase().charCodeAt(0) - 65;
  const b = cc.toUpperCase().charCodeAt(1) - 65;
  if (a < 0 || a > 25 || b < 0 || b > 25) return '🌐';
  return String.fromCodePoint(A + a) + String.fromCodePoint(A + b);
};

function matchesScope(p) {
  if (!p) return false;

  if (isWorldScope) return true;

  if (Array.isArray(p.blacklistedScopes) && p.blacklistedScopes.includes(mapScope)) {
    return false;
  }

  const target = mapScope.toUpperCase();
  if (!target || target.length !== 2) return false;

  const candidates = [];

  if (p.countryISO2) candidates.push(p.countryISO2);
  if (p.displayISO2) candidates.push(p.displayISO2);
  if (p.geocode && typeof p.geocode === 'object') {
    if (p.geocode.countryCode) candidates.push(p.geocode.countryCode);
    if (p.geocode.cc) candidates.push(p.geocode.cc);
  }
  if (p.countryText) candidates.push(p.countryText);

  for (let i = 0; i < candidates.length; i += 1) {
    const iso = normalizeCountryCode(candidates[i]);
    if (iso && iso === target) {
      return true;
    }
  }

  return false;
}

function fitToBounds(list, { fallbackBounds = null } = {}) {
  const fitOptions = getMapViewportFitOptions();
  if (!Array.isArray(list) || !list.length) {
    if (fallbackBounds) {
      map.fitBounds(fallbackBounds, fitOptions);
      requestAnimationFrame(() => map.invalidateSize());
    }
    return;
  }
  const latlngs = list
    .map(p => {
      if (!p) return null;
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lng)) return null;
      return [p.lat, p.lng];
    })
    .filter(Boolean);
  if (!latlngs.length) {
    if (fallbackBounds) {
      map.fitBounds(fallbackBounds, fitOptions);
      requestAnimationFrame(() => map.invalidateSize());
    }
    return;
  }
  const bounds = L.latLngBounds(latlngs);
  map.fitBounds(bounds, fitOptions);
  requestAnimationFrame(() => map.invalidateSize());
}

function getSidebarCompensationWidth() {
  if (sidebarHidden || !sidebarEl || typeof window === 'undefined') return 0;
  if (typeof window.matchMedia === 'function' && !window.matchMedia(DESKTOP_MEDIA_QUERY).matches) {
    return 0;
  }
  const rect = sidebarEl.getBoundingClientRect();
  if (!rect || !Number.isFinite(rect.width) || rect.width <= 0) return 0;
  return rect.width;
}

function getMapViewportFitOptions() {
  const sidebarWidth = getSidebarCompensationWidth();
  const leftPadding = Math.max(16, Math.round(sidebarWidth + 24));
  return {
    paddingTopLeft: [leftPadding, 16],
    paddingBottomRight: [16, 16],
    maxZoom: 9
  };
}

function resolveEntryCountryCode(entry) {
  if (!entry) return null;

  const candidates = [
    entry.countryISO2,
    entry.displayISO2,
    entry.countryText,
    entry.geocode && typeof entry.geocode === 'object' ? entry.geocode.countryCode : null
  ];

  for (let i = 0; i < candidates.length; i += 1) {
    const iso = normalizeCountryCode(candidates[i]);
    if (iso) return iso;
  }

  return null;
}

function getCountryEntries(entry) {
  const countryCode = resolveEntryCountryCode(entry);
  if (!countryCode) return [];

  const source = Array.isArray(all) ? all : [];
  return source.filter(candidate => resolveEntryCountryCode(candidate) === countryCode);
}

function clearSelectedMarker() {
  if (selectedMarkerEl) {
    selectedMarkerEl.classList.remove('receiver-pin--active');
    selectedMarkerEl = null;
  }
}

function setActive(id, { focus = false, zoomToCountry = false } = {}) {
  if (selectedId != null) {
    const previousItem = liById.get(selectedId);
    if (previousItem) previousItem.classList.remove('active');

    const previousMarker = markerById.get(selectedId);
    if (previousMarker && typeof previousMarker.closeTooltip === 'function') {
      previousMarker.closeTooltip();
    }
    clearSelectedMarker();
  }
  selectedId = id;
  if (id == null) return;
  const listItem = liById.get(id);
  if (listItem) listItem.classList.add('active');
  const marker = markerById.get(id);
  if (marker && typeof marker.openTooltip === 'function') {
    marker.openTooltip();
  }
  const markerEl = (marker && typeof marker.getElement === 'function')
    ? marker.getElement()
    : null;
  if (markerEl) {
    markerEl.classList.add('receiver-pin--active');
    selectedMarkerEl = markerEl;
  }
  if (focus) {
    const selectedEntry = Array.isArray(currentAdjustedList)
      ? currentAdjustedList.find(entry => entry && entry.id === id)
      : null;

    if (zoomToCountry && selectedEntry) {
      const countryEntries = getCountryEntries(selectedEntry)
        .map(entry => {
          if (!entry) return null;
          const lat = Number.isFinite(entry.originalLat) ? entry.originalLat : entry.lat;
          const lng = Number.isFinite(entry.originalLng) ? entry.originalLng : entry.lng;
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
          return Object.assign({}, entry, { lat, lng });
        })
        .filter(Boolean);

      if (countryEntries.length > 1) {
        fitToBounds(countryEntries);
        return;
      }
    }
  }
  if (focus && marker && typeof marker.getLatLng === 'function') {
    const latlng = marker.getLatLng();
    if (latlng) {
      const sidebarWidth = getSidebarCompensationWidth();
      if (sidebarWidth > 0 && typeof map.project === 'function' && typeof map.unproject === 'function') {
        const point = map.project(latlng, map.getZoom());
        const adjusted = L.point(point.x - sidebarWidth * 0.22, point.y);
        map.panTo(map.unproject(adjusted, map.getZoom()));
      } else {
        map.panTo(latlng);
      }
    }
  }
}

// ================ UI builders ================
function addPin({ id, name, url, lat, lng, locked, wideband }) {
  const icon = locked
    ? lockedMarkerIcon
    : (wideband ? widebandMarkerIcon : defaultMarkerIcon);
  const m = L.marker([lat, lng], { icon }).addTo(markerGroup);
  markerById.set(id, m);
  m.bindTooltip(esc(name), { direction:'top', offset:[0,-22], className:'place-label' });
  m.on('click', () => {
    setActive(id);
    if (url) window.open(url, '_blank', 'noopener');
  });
}

function makeListItem(p) {
  const latForIso = Number.isFinite(p.originalLat) ? p.originalLat : p.lat;
  const lngForIso = Number.isFinite(p.originalLng) ? p.originalLng : p.lng;
  const isoCandidate = p.displayISO2 || p.countryISO2 || p.countryText;
  const iso2 = normalizeCountryCode(isoCandidate);
  const flag  = iso2ToFlag(iso2);

  const li = document.createElement('li');
  li.className = 'side-item';
  li.tabIndex = 0;
  li.dataset.id = String(p.id);
  if (p.locked) li.classList.add('locked');
  if (p.wideband) li.classList.add('wideband');
  if (!p.locked && !p.wideband) li.classList.add('default');

  const flagEl = document.createElement('div');
  flagEl.className = 'flag';
  flagEl.textContent = flag;

  const title = document.createElement('div');
  title.className = 'side-title';
  title.textContent = p.name || 'Unknown';

  const locationText = cleanString(p.locationLabel);
  const location = locationText ? document.createElement('div') : null;
  if (location) {
    location.className = 'side-location';
    location.textContent = locationText;
  }

  const meta = document.createElement('div');
  meta.className = 'side-meta';

  const statusBadge = document.createElement('span');
  statusBadge.className = `side-badge side-badge--${p.statusKind}`;
  statusBadge.textContent = p.statusLabel;
  meta.append(statusBadge);

  if (p.wideband) {
    const rangeBadge = document.createElement('span');
    rangeBadge.className = 'side-badge side-badge--wideband';
    rangeBadge.textContent = 'Wideband';
    meta.append(rangeBadge);
  }

  if (p.supporter) {
    const supporterBadge = document.createElement('span');
    supporterBadge.className = 'side-badge side-badge--supporter';
    supporterBadge.innerHTML = '<span aria-hidden="true">★</span><span>Supporter</span>';
    meta.append(supporterBadge);
  }

  let url = null;
  if (p.url) {
    url = document.createElement('a');
    url.className = 'side-url';
    url.textContent = p.url;
    url.href = p.url;
    url.target = '_blank';
    url.rel = 'noopener';
    url.addEventListener('click', e => e.stopPropagation());
  } else {
    url = document.createElement('div');
    url.className = 'side-url';
    url.textContent = '';
  }

  li.append(flagEl, title);
  if (location) li.append(location);
  li.append(meta);
  li.append(url);

  li.addEventListener('click', () => setActive(p.id, { focus: true, zoomToCountry: true }));
  li.addEventListener('keypress', e => {
    const key = e.key || e.code;
    if (key === 'Enter' || key === 'Space' || key === ' ' || key === 'Spacebar') {
      e.preventDefault();
      setActive(p.id, { focus: true, zoomToCountry: true });
    }
  });
  return li;
}

function applyMarkerOffsets(list, {
  clusterDistanceMeters = 1000,
  minSeparationMeters = 450,
  offsetStepMeters = 400,
  maxOffsetMeters = 15000,
  maxAttempts = 120,
  minPixelSeparation = 18,
  pixelSeparationZoom = 12
} = {}) {
  if (!Array.isArray(list) || list.length === 0) return [];

  const clusterDistanceBase = Number.isFinite(clusterDistanceMeters) && clusterDistanceMeters > 0
    ? clusterDistanceMeters
    : 1000;
  const minSeparationBase = Number.isFinite(minSeparationMeters) && minSeparationMeters >= 0
    ? minSeparationMeters
    : 450;
  const offsetStepBase = Number.isFinite(offsetStepMeters) && offsetStepMeters > 0
    ? offsetStepMeters
    : 400;
  const maxOffsetBase = Number.isFinite(maxOffsetMeters) && maxOffsetMeters > 0
    ? Math.max(maxOffsetMeters, minSeparationBase)
    : Math.max(15000, minSeparationBase);
  const attemptLimit = Number.isFinite(maxAttempts) ? Math.max(0, Math.floor(maxAttempts)) : 120;
  const pixelSeparationBase = Number.isFinite(minPixelSeparation) && minPixelSeparation > 0
    ? minPixelSeparation
    : 0;
  const spacingTolerance = 1;

  const mapZoom = (map && typeof map.getZoom === 'function') ? map.getZoom() : null;
  const fallbackPixelZoom = Number.isFinite(pixelSeparationZoom) ? pixelSeparationZoom : null;
  const effectivePixelZoom = Number.isFinite(mapZoom)
    ? mapZoom
    : (fallbackPixelZoom != null ? fallbackPixelZoom : 12);

  const clones = list
    .map(item => {
      if (!item) return null;
      const baseLat = Number.isFinite(item.originalLat)
        ? item.originalLat
        : (Number.isFinite(item.lat) ? item.lat : null);
      const baseLng = Number.isFinite(item.originalLng)
        ? item.originalLng
        : (Number.isFinite(item.lng) ? item.lng : null);
      if (!Number.isFinite(baseLat) || !Number.isFinite(baseLng)) return null;
      return Object.assign({}, item, {
        lat: baseLat,
        lng: baseLng,
        originalLat: baseLat,
        originalLng: baseLng
      });
    })
    .filter(Boolean);

  if (clones.length <= 1) return clones;

  const visited = new Set();
  const globalOccupied = [];

  const computeSpacingForCoords = (lat, lng) => {
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return minSeparationBase;
    if (pixelSeparationBase <= 0) return minSeparationBase;
    const pixelMeters = pixelsToMeters(lat, lng, pixelSeparationBase, effectivePixelZoom);
    if (!Number.isFinite(pixelMeters) || pixelMeters <= 0) return minSeparationBase;
    const desired = Math.max(minSeparationBase, pixelMeters);
    return Math.min(desired, maxOffsetBase);
  };

  for (let i = 0; i < clones.length; i += 1) {
    if (visited.has(i)) continue;

    const base = clones[i];
    const baseLat = base.originalLat;
    const baseLng = base.originalLng;
    if (!Number.isFinite(baseLat) || !Number.isFinite(baseLng)) {
      visited.add(i);
      continue;
    }

    const clusterSpacingHint = computeSpacingForCoords(baseLat, baseLng);
    const clusterDistanceThreshold = Math.max(
      clusterDistanceBase,
      clusterSpacingHint,
      minSeparationBase
    );

    const cluster = [];
    const queue = [i];
    const enqueued = new Set([i]);

    while (queue.length) {
      const idx = queue.pop();
      if (visited.has(idx)) continue;

      const current = clones[idx];
      const currentLat = current.originalLat;
      const currentLng = current.originalLng;
      if (!Number.isFinite(currentLat) || !Number.isFinite(currentLng)) {
        visited.add(idx);
        continue;
      }

      visited.add(idx);
      cluster.push(idx);

      for (let j = 0; j < clones.length; j += 1) {
        if (visited.has(j) || enqueued.has(j) || j === idx) continue;
        const candidate = clones[j];
        const candidateLat = candidate.originalLat;
        const candidateLng = candidate.originalLng;
        if (!Number.isFinite(candidateLat) || !Number.isFinite(candidateLng)) continue;
        const distance = approxDistanceMeters(currentLat, currentLng, candidateLat, candidateLng);
        if (!Number.isFinite(distance)) continue;
        if (distance <= clusterDistanceThreshold) {
          queue.push(j);
          enqueued.add(j);
        }
      }
    }

    if (!cluster.length) continue;

    if (cluster.length === 1) {
      const soloEntry = clones[cluster[0]];
      if (soloEntry && Number.isFinite(soloEntry.lat) && Number.isFinite(soloEntry.lng)) {
        globalOccupied.push({ lat: soloEntry.lat, lng: soloEntry.lng });
      }
      continue;
    }

    cluster.sort((a, b) => {
      const entryA = clones[a];
      const entryB = clones[b];
      const idA = entryA ? entryA.id : undefined;
      const idB = entryB ? entryB.id : undefined;
      if (Number.isFinite(idA) && Number.isFinite(idB)) return idA - idB;
      if (Number.isFinite(idA)) return -1;
      if (Number.isFinite(idB)) return 1;
      return a - b;
    });

    const assigned = [];

    for (const idx of cluster) {
      const entry = clones[idx];
      const originLat = entry.originalLat;
      const originLng = entry.originalLng;

      if (!Number.isFinite(originLat) || !Number.isFinite(originLng)) {
        entry.lat = originLat;
        entry.lng = originLng;
        continue;
      }

      const clusterSpacingMeters = computeSpacingForCoords(originLat, originLng);
      const clusterStep = Math.min(
        Math.max(offsetStepBase, clusterSpacingMeters * 0.6),
        maxOffsetBase
      );
      const clusterMaxOffset = Math.max(clusterSpacingMeters, minSeparationBase, clusterStep);

      let selectedLat = originLat;
      let selectedLng = originLng;
      let placed = false;
      let moved = false;
      let bestCandidate = null;
      let bestScore = -Infinity;

      for (let attempt = 0; attempt <= attemptLimit; attempt += 1) {
        let candidateLat = originLat;
        let candidateLng = originLng;

        if (attempt > 0 && clusterMaxOffset > 0) {
          const baseRadius = clusterStep > 0 ? clusterStep * Math.sqrt(attempt) : 0;
          let radius = baseRadius;
          if (clusterSpacingMeters > 0) radius = Math.max(radius, clusterSpacingMeters);
          if (radius > clusterMaxOffset) radius = clusterMaxOffset;
          if (radius > 0) {
            const angle = GOLDEN_ANGLE * attempt;
            const deltaNorth = radius * Math.cos(angle);
            const deltaEast = radius * Math.sin(angle);
            candidateLat = originLat + metersToLatDelta(deltaNorth);
            candidateLng = originLng + metersToLngDelta(deltaEast, originLat);
          }
        }

        if (!Number.isFinite(candidateLat) || !Number.isFinite(candidateLng)) continue;
        if (candidateLat < -90 || candidateLat > 90 || candidateLng < -180 || candidateLng > 180) continue;

        let nearestClusterSpacing = Infinity;
        if (clusterSpacingMeters > 0 && assigned.length) {
          for (let k = 0; k < assigned.length; k += 1) {
            const pos = assigned[k];
            if (!pos) continue;
            const dist = approxDistanceMeters(candidateLat, candidateLng, pos.lat, pos.lng);
            if (!Number.isFinite(dist)) continue;
            if (dist < nearestClusterSpacing) nearestClusterSpacing = dist;
          }
        }

        let nearestGlobalSpacing = Infinity;
        if (minSeparationBase > 0 && globalOccupied.length) {
          for (let k = 0; k < globalOccupied.length; k += 1) {
            const pos = globalOccupied[k];
            if (!pos) continue;
            const dist = approxDistanceMeters(candidateLat, candidateLng, pos.lat, pos.lng);
            if (!Number.isFinite(dist)) continue;
            if (dist < nearestGlobalSpacing) nearestGlobalSpacing = dist;
          }
        }

        const meetsClusterSpacing = clusterSpacingMeters > 0
          ? nearestClusterSpacing >= (clusterSpacingMeters - spacingTolerance)
          : true;
        const meetsGlobalSpacing = minSeparationBase > 0
          ? nearestGlobalSpacing >= (minSeparationBase - spacingTolerance)
          : true;

        const spacingScore = Math.min(
          Number.isFinite(nearestClusterSpacing) ? nearestClusterSpacing : Infinity,
          Number.isFinite(nearestGlobalSpacing) ? nearestGlobalSpacing : Infinity
        );
        const displacement = approxDistanceMeters(originLat, originLng, candidateLat, candidateLng);

        if (meetsClusterSpacing && meetsGlobalSpacing) {
          selectedLat = candidateLat;
          selectedLng = candidateLng;
          moved = displacement > spacingTolerance;
          placed = true;
          break;
        }

        if (spacingScore > bestScore + spacingTolerance ||
          (Math.abs(spacingScore - bestScore) <= spacingTolerance &&
            displacement < (bestCandidate ? bestCandidate.displacement : Infinity))) {
          bestScore = spacingScore;
          bestCandidate = {
            lat: candidateLat,
            lng: candidateLng,
            displacement
          };
        }
      }

      if (!placed && bestCandidate) {
        selectedLat = bestCandidate.lat;
        selectedLng = bestCandidate.lng;
        const displacement = bestCandidate.displacement;
        moved = Number.isFinite(displacement) ? displacement > spacingTolerance : true;
        placed = true;
      }

      if (!placed) {
        selectedLat = originLat;
        selectedLng = originLng;
        moved = false;
      }

      entry.lat = selectedLat;
      entry.lng = selectedLng;
      if (moved) entry.offsetApplied = true;
      if (Number.isFinite(selectedLat) && Number.isFinite(selectedLng)) {
        const point = { lat: selectedLat, lng: selectedLng };
        assigned.push(point);
        globalOccupied.push(point);
      }
    }
  }

  return clones;
}

function refreshMarkerOffsets() {
  if (!Array.isArray(currentBaseList) || currentBaseList.length === 0) return;

  const updated = applyMarkerOffsets(currentBaseList);
  currentAdjustedList = updated;

  for (const entry of updated) {
    if (!entry) continue;
    if (!Number.isFinite(entry.lat) || !Number.isFinite(entry.lng)) continue;
    const marker = markerById.get(entry.id);
    if (marker && typeof marker.setLatLng === 'function') {
      marker.setLatLng([entry.lat, entry.lng]);
    }
  }

  if (selectedId != null) {
    const marker = markerById.get(selectedId);
    if (marker && typeof marker.getElement === 'function') {
      const el = marker.getElement();
      if (el && selectedMarkerEl !== el) {
        if (selectedMarkerEl) selectedMarkerEl.classList.remove('receiver-pin--active');
        el.classList.add('receiver-pin--active');
        selectedMarkerEl = el;
      }
    }
  }
}

function updateSidebarCount(count) {
  if (!sideCountEl) return;
  const safeCount = Number.isFinite(count) ? count : 0;
  const unit = safeCount === 1 ? 'server' : 'servers';
  const suffix = isWorldScope ? 'worldwide' : `in ${scopeLabel}`;
  const label = `${safeCount} ${unit} ${suffix}`;
  sideCountEl.textContent = String(safeCount);
  sideCountEl.setAttribute('aria-label', label);
  sideCountEl.setAttribute('title', label);
}

function updateSidebarStatusCounts(list) {
  if (!sideAvailableEl || !sideLockedEl || !sideUnreachableEl) return;
  const items = Array.isArray(list) ? list : [];
  let available = 0;
  let locked = 0;
  let unreachable = 0;

  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    if (!item) continue;
    if (item.statusKind === 'locked') {
      locked += 1;
    } else if (item.statusKind === 'available') {
      available += 1;
    } else {
      unreachable += 1;
    }
  }

  sideAvailableEl.textContent = String(available);
  sideLockedEl.textContent = String(locked);
  sideUnreachableEl.textContent = String(unreachable);
}

// ================ Render ================
function render() {
  markerGroup.clearLayers();
  markerById.clear(); liById.clear();
  if (sideListEl) sideListEl.innerHTML = '';
  updateSidebarCount(0);
  updateSidebarStatusCounts([]);
  setActive(null);

  currentBaseList = [];
  currentAdjustedList = [];

  const filterToScope = !isWorldScope;
  const rawBaseList = filterToScope ? all.filter(matchesScope) : all.slice();
  const baseList = rawBaseList
    .map(item => {
      if (!item) return null;
      const originalLat = Number.isFinite(item.originalLat)
        ? item.originalLat
        : (Number.isFinite(item.lat) ? item.lat : null);
      const originalLng = Number.isFinite(item.originalLng)
        ? item.originalLng
        : (Number.isFinite(item.lng) ? item.lng : null);
      if (!Number.isFinite(originalLat) || !Number.isFinite(originalLng)) return null;
      return Object.assign({}, item, {
        lat: originalLat,
        lng: originalLng,
        originalLat,
        originalLng
      });
    })
    .filter(Boolean);

  currentBaseList = baseList;
  const list = applyMarkerOffsets(baseList);
  currentAdjustedList = list;

  for (const p of list) {
    addPin(p);
    const el = makeListItem(p);
    liById.set(p.id, el);
    if (sideListEl) sideListEl.appendChild(el);
  }
  updateSidebarCount(list.length);
  updateSidebarStatusCounts(list);

  if (!list.length) {
    map.setView([20, 0], 2);
    return;
  }

  fitToBounds(list);
}

// ================ Data ================
function fetchServersPayload() {
  const url = `/api/servers?nocache=${Date.now()}`;
  const headers = { 'Pragma': 'no-cache', 'Cache-Control': 'no-store' };

  if (typeof window.fetch === 'function') {
    return window.fetch(url, { cache: 'no-store', headers })
      .then(resp => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
      });
  }

  return new Promise((resolve, reject) => {
    try {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);
      xhr.setRequestHeader('Pragma', headers['Pragma']);
      xhr.setRequestHeader('Cache-Control', headers['Cache-Control']);
      xhr.onreadystatechange = function() {
        if (xhr.readyState !== 4) return;
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch (err) {
            reject(err);
          }
        } else {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(null);
    } catch (err) {
      reject(err);
    }
  });
}

async function load() {
  const payload = await fetchServersPayload();
  const items = (payload && Array.isArray(payload.dataset)) ? payload.dataset : [];

  setScopedBlacklist(payload ? payload.blacklist : null);

  all = [];
  let id = 1;
  for (const s of items) {
    const coordsField = s ? s.coords : null;
    const c = Array.isArray(coordsField) ? coordsField : null;
    if (!c || c.length < 2) continue;
    const lat = Number(c[0]), lng = Number(c[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;

    const rawUrlValue = (s && typeof s.url === 'string') ? s.url : null;

    const geocodeSource = s && typeof s.geocode === 'object' ? s.geocode : null;
    let geocode = null;
    if (geocodeSource) {
      const geocodeCity = cleanString(geocodeSource.city || geocodeSource.name);
      const geocodeAdmin1 = cleanString(geocodeSource.admin1 || geocodeSource.state);
      const geocodeAdmin2 = cleanString(geocodeSource.admin2 || geocodeSource.county);
      const geocodeCountryCodeRaw = cleanString(geocodeSource.countryCode || geocodeSource.cc);
      const geocodeCountryCode = geocodeCountryCodeRaw
        ? geocodeCountryCodeRaw.toUpperCase()
        : null;

      const payload = {};
      if (geocodeCity) payload.city = geocodeCity;
      if (geocodeAdmin1) payload.admin1 = geocodeAdmin1;
      if (geocodeAdmin2) payload.admin2 = geocodeAdmin2;
      if (geocodeCountryCode) payload.countryCode = geocodeCountryCode;

      if (Object.keys(payload).length) {
        geocode = payload;
      }
    }

    const statusField = s ? s.status : null;
    const statusRaw = cleanString(statusField);
    const statusValue = typeof statusField === 'number'
      ? statusField
      : (statusRaw != null ? Number.parseInt(statusRaw, 10) : NaN);
    const status = Number.isFinite(statusValue) ? statusValue : null;
    const locked = status === 2;
    const statusKind = locked ? 'locked' : (status === 1 ? 'available' : 'unreachable');
    const statusLabel = locked ? 'Locked' : (status === 1 ? 'Available' : 'Unreachable');

    const countryCodeField = cleanString(s ? s.countryCode : null) ||
      cleanString(s ? s.country_code : null) ||
      cleanString(s ? s.cc : null);
    const rawCountry = cleanString(s ? s.country : null) || null;
    const countryName = cleanString(s ? s.countryName : null) || null;

    const countryCandidates = [
      geocode ? geocode.countryCode : null,
      countryCodeField,
      rawCountry,
      countryName
    ];
    let countryISO2 = null;
    for (let i = 0; i < countryCandidates.length; i += 1) {
      const iso = normalizeCountryCode(countryCandidates[i]);
      if (iso) {
        countryISO2 = iso;
        break;
      }
    }

    const countryText = countryName || rawCountry || countryCodeField || null;
    const trimmedUrl = (rawUrlValue && rawUrlValue.trim()) ? rawUrlValue.trim() : null;
    const normalizedUrl = normalizeUrl(trimmedUrl);
    const supporter = hasFmtunerSupport(trimmedUrl);
    const blacklistedScopes = getBlacklistedScopes({
      normalizedUrl,
      url: trimmedUrl,
      lat,
      lng,
      tuner: s ? s.tuner : null,
      name: s ? s.name : null
    });

    const displayISO2 = countryISO2 || normalizeCountryCode(countryText);

    const rawBwLimit = typeof (s && s.bwLimit) === 'string'
      ? s.bwLimit
      : (typeof (s && s.bwlimit) === 'string'
        ? s.bwlimit
        : (typeof (s && s.bw_limit) === 'string' ? s.bw_limit : null));
    const bwLimit = cleanString(rawBwLimit);
    const wideband = detectExtendedRange(s);

    const cityField = pickField(s, ['city', 'town', 'locality', 'nlCity']);
    const regionField = pickField(s, [
      'region',
      'state',
      'province',
      'prefecture',
      'stateName',
      'countrySubdivision',
      'usState',
      'jpPrefecture',
      'nlProvince'
    ]);
    const admin2Field = pickField(s, ['municipality', 'county', 'district', 'admin2', 'nlMunicipality']);

    const geocodeCity = geocode && geocode.city ? geocode.city : null;
    const geocodeAdmin1 = geocode && geocode.admin1 ? geocode.admin1 : null;
    const geocodeAdmin2 = geocode && geocode.admin2 ? geocode.admin2 : null;

    const resolvedCity = cityField || geocodeCity;
    const resolvedAdmin2 = admin2Field || geocodeAdmin2;
    const resolvedRegion = regionField || geocodeAdmin1;

    let locationLabel = null;
    if (resolvedCity && resolvedRegion) {
      locationLabel = `${resolvedCity}, ${resolvedRegion}`;
    } else if (resolvedCity && resolvedAdmin2) {
      locationLabel = `${resolvedCity}, ${resolvedAdmin2}`;
    } else if (resolvedCity) {
      locationLabel = resolvedCity;
    } else if (resolvedAdmin2 && resolvedRegion) {
      locationLabel = `${resolvedAdmin2}, ${resolvedRegion}`;
    } else if (resolvedRegion) {
      locationLabel = resolvedRegion;
    } else if (resolvedAdmin2) {
      locationLabel = resolvedAdmin2;
    }

    all.push({
      id: id++,
      name: s && s.name ? s.name : 'Unknown',
      url: trimmedUrl,
      blacklistedScopes,
      originalLat: lat,
      originalLng: lng,
      lat,
      lng,
      status,
      statusKind,
      statusLabel,
      locked,
      countryISO2: countryISO2 || null,
      countryText,
      displayISO2,
      wideband,
      supporter,
      bwLimit,
      locationLabel,
      geocode
    });
  }
  render();
}

// ================ Boot ================
document.addEventListener('DOMContentLoaded', () => {
  syncSidebarLayout();
  map.on('click', () => setActive(null));
  map.on('zoomend', refreshMarkerOffsets);
  document.addEventListener('keydown', e => e.key==='Escape' && setActive(null));
  load().catch(err => console.error('Failed to load servers:', err));
});
