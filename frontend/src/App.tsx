import { useEffect, useMemo, useRef, useState } from "react";
import L, { type Layer } from "leaflet";

type LayerKey = "power" | "land" | "permits" | "reg" | "broadband" | "transmission";
type MetricLayerKey = Exclude<LayerKey, "transmission">;

type GeoJsonFeature = {
  type: "Feature";
  properties: Record<string, unknown>;
  geometry: {
    type: string;
    coordinates: unknown;
  };
};

type GeoJsonCollection = {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
};

type LoadMetrics = {
  ms: number;
  featureCount: number;
  dataSource: string;
};

type LayerConfig = {
  field: string;
  label: string;
  format: (props: Record<string, unknown>) => string;
};

const METRIC_LAYERS: Record<MetricLayerKey, LayerConfig> = {
  power: {
    field: "s_power",
    label: "Power",
    format: (props) => (props.power_price != null ? `${props.power_price} ¢/kWh` : "n/a")
  },
  land: {
    field: "s_land",
    label: "Land cost",
    format: (props) => (props.home_value != null ? `$${Number(props.home_value).toLocaleString()}` : "n/a")
  },
  permits: {
    field: "s_permits",
    label: "Permits/1k pop",
    format: (props) => (props.permits_pc != null ? String(props.permits_pc) : "n/a")
  },
  reg: {
    field: "s_reg",
    label: "Regulatory freedom",
    format: (props) => (props.reg_freedom != null ? String(props.reg_freedom) : "n/a")
  },
  broadband: {
    field: "s_broadband",
    label: "Broadband tier",
    format: (props) => (props.broadband_tier != null ? `${props.broadband_tier}/5` : "n/a")
  }
};

const defaultActiveLayers: Record<LayerKey, boolean> = {
  power: true,
  land: true,
  permits: true,
  reg: true,
  broadband: true,
  transmission: true
};

type HoverData = {
  title: string;
  subtitle: string;
  score: number;
  detailsHtml: string;
};

function scoreToColor(score: number): string {
  if (score >= 80) return "#1a9641";
  if (score >= 65) return "#a6d96a";
  if (score >= 50) return "#ffffbf";
  if (score >= 35) return "#fdae61";
  if (score >= 20) return "#f46d43";
  return "#d7191c";
}

function scoreToLabel(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 65) return "Good";
  if (score >= 50) return "Moderate";
  if (score >= 35) return "Below Average";
  if (score >= 20) return "Poor";
  return "Very Poor";
}

function scoreToOpacity(score: number): number {
  const dist = Math.abs(score - 50) / 50;
  return 0.4 + dist * 0.35;
}

function numericProp(props: Record<string, unknown>, key: string): number | null {
  const value = props[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function computeScore(props: Record<string, unknown>, activeLayers: Record<LayerKey, boolean>): number {
  let total = 0;
  let count = 0;
  for (const [key, config] of Object.entries(METRIC_LAYERS) as [MetricLayerKey, LayerConfig][]) {
    if (!activeLayers[key]) continue;
    const value = numericProp(props, config.field);
    if (value != null) {
      total += value;
      count += 1;
    }
  }
  return count > 0 ? Math.round((total / count) * 10) / 10 : 50;
}

export function App() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const countiesLayerRef = useRef<L.GeoJSON | null>(null);
  const transmissionLayerRef = useRef<L.GeoJSON | null>(null);
  const activeLayersRef = useRef<Record<LayerKey, boolean>>(defaultActiveLayers);

  const [activeLayers, setActiveLayers] = useState<Record<LayerKey, boolean>>(defaultActiveLayers);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<HoverData | null>(null);
  const [metrics, setMetrics] = useState<LoadMetrics | null>(null);

  activeLayersRef.current = activeLayers;

  const mapStyle = useMemo(() => ({ width: "100vw", height: "100vh" }), []);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [39.0, -96.0],
      zoom: 5,
      zoomControl: false,
      maxBounds: [[24, -130], [50, -65]],
      maxBoundsViscosity: 1.0,
      minZoom: 4,
      preferCanvas: true
    });
    mapRef.current = map;

    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap &copy; CARTO",
      maxZoom: 19
    }).addTo(map);

    const styleFeature = (feature?: GeoJsonFeature) => {
      const props = (feature?.properties ?? {}) as Record<string, unknown>;
      const score = computeScore(props, activeLayersRef.current);
      return {
        fillColor: scoreToColor(score),
        fillOpacity: scoreToOpacity(score),
        color: "#fff",
        weight: 0.5,
        opacity: 0.5
      };
    };

    const loadTransmission = async () => {
      if (!activeLayersRef.current.transmission || !mapRef.current) return;
      const bounds = mapRef.current.getBounds();
      const bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].join(",");
      try {
        const response = await fetch(`/api/transmission?bbox=${encodeURIComponent(bbox)}`);
        if (!response.ok) return;
        const geojson: GeoJsonCollection = await response.json();
        if (transmissionLayerRef.current) {
          transmissionLayerRef.current.remove();
        }
        transmissionLayerRef.current = L.geoJSON(geojson as unknown as GeoJSON.GeoJsonObject, {
          style: { color: "#ff6600", weight: 1.5, opacity: 0.5 },
          onEachFeature: (feature: GeoJsonFeature, layer: Layer) => {
            const props = feature.properties ?? {};
            const voltClass = String(props.volt_class ?? "Unknown");
            const owner = String(props.owner ?? "");
            const suffix = owner && owner !== "NOT AVAILABLE" ? ` — ${owner}` : "";
            (layer as L.Path).bindTooltip(`${voltClass} kV${suffix}`);
          }
        }).addTo(mapRef.current);
      } catch {
        // Non-fatal overlay failure.
      }
    };

    const loadCounties = async () => {
      const startedAt = performance.now();
      try {
        const response = await fetch("/api/counties");
        if (!response.ok) {
          throw new Error(`Counties API failed (${response.status})`);
        }
        const featureCount = Number(response.headers.get("x-feature-count") ?? "0");
        const dataSource = response.headers.get("x-data-source") ?? "unknown";
        const geojson: GeoJsonCollection = await response.json();
        countiesLayerRef.current = L.geoJSON(geojson as unknown as GeoJSON.GeoJsonObject, {
          style: styleFeature,
          onEachFeature: (feature: GeoJsonFeature, layer: Layer) => {
            layer.on("mouseover", () => {
              const props = (feature.properties ?? {}) as Record<string, unknown>;
              const score = computeScore(props, activeLayersRef.current);
              const detailLines = (Object.entries(METRIC_LAYERS) as [MetricLayerKey, LayerConfig][])
                .map(([key, config]) => {
                  const value = `${config.label}: ${config.format(props)}`;
                  return activeLayersRef.current[key] ? value : `<span style="color:#bbb">${value}</span>`;
                })
                .join("<br>");
              setHover({
                title: `${String(props.NAME ?? "Unknown")} County`,
                subtitle: `FIPS: ${String(props.STATE ?? "")}${String(props.COUNTY ?? "")}`,
                score,
                detailsHtml: detailLines
              });
              (layer as L.Path).setStyle({ weight: 2, color: "#333" });
              if ("bringToFront" in layer) {
                (layer as L.Path).bringToFront();
              }
            });
            layer.on("mouseout", () => {
              (layer as L.Path).setStyle({ weight: 0.5, color: "#fff" });
              setHover(null);
            });
          }
        }).addTo(map);

        setMetrics({
          ms: Math.round(performance.now() - startedAt),
          featureCount: Number.isFinite(featureCount) ? featureCount : geojson.features.length,
          dataSource
        });
        setLoading(false);
        void loadTransmission();
      } catch (err) {
        setLoading(false);
        setError(err instanceof Error ? err.message : "Failed to load county map data.");
      }
    };

    const overlayPane = map.getPane("overlayPane");
    map.on("movestart", () => {
      if (overlayPane) overlayPane.style.visibility = "hidden";
    });
    map.on("moveend", () => {
      if (overlayPane) overlayPane.style.visibility = "visible";
      void loadTransmission();
    });

    void loadCounties();

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (countiesLayerRef.current) {
      countiesLayerRef.current.eachLayer((layer) => {
        const feature = (layer as L.Path & { feature?: GeoJsonFeature }).feature;
        if (!feature) return;
        const score = computeScore((feature.properties ?? {}) as Record<string, unknown>, activeLayersRef.current);
        (layer as L.Path).setStyle({
          fillColor: scoreToColor(score),
          fillOpacity: scoreToOpacity(score),
          color: "#fff",
          weight: 0.5,
          opacity: 0.5
        });
      });
    }

    if (!activeLayers.transmission && transmissionLayerRef.current) {
      transmissionLayerRef.current.remove();
      transmissionLayerRef.current = null;
    }
  }, [activeLayers]);

  return (
    <>
      <div ref={mapContainerRef} style={mapStyle} />
      {loading && <div className="loading">Loading map data...</div>}
      {error && (
        <div className="error-panel">
          <h3>Map data failed to load</h3>
          <p>{error}</p>
          <p>Check `/api/counties` and object storage keys.</p>
        </div>
      )}
      <div className="info-panel">
        <h1>Where do I put my data centers?</h1>
        <p>Heatmap of scored regions — hover for details</p>
        {metrics && (
          <p>
            {metrics.featureCount.toLocaleString()} features loaded in {metrics.ms} ms ({metrics.dataSource})
          </p>
        )}
      </div>
      <div className="legend">
        <h3>Suitability Score</h3>
        <div className="legend-item"><div className="legend-color" style={{ background: "#1a9641" }} />Excellent (80-100)</div>
        <div className="legend-item"><div className="legend-color" style={{ background: "#a6d96a" }} />Good (60-80)</div>
        <div className="legend-item"><div className="legend-color" style={{ background: "#ffffbf" }} />Moderate (40-60)</div>
        <div className="legend-item"><div className="legend-color" style={{ background: "#fdae61" }} />Below avg (20-40)</div>
        <div className="legend-item"><div className="legend-color" style={{ background: "#d7191c" }} />Poor (0-20)</div>
      </div>
      {hover && (
        <div className="hover-info">
          <h3>{hover.title}</h3>
          <div className="county-name">{hover.subtitle}</div>
          <div className="score" style={{ color: scoreToColor(hover.score) }}>{hover.score}/100</div>
          <div className="label">{scoreToLabel(hover.score)}</div>
          <div className="details" dangerouslySetInnerHTML={{ __html: hover.detailsHtml }} />
        </div>
      )}
      <div className="toggles">
        {(Object.keys(defaultActiveLayers) as LayerKey[]).map((layerKey) => (
          <button
            key={layerKey}
            className={`toggle-btn ${activeLayers[layerKey] ? "active" : ""}`}
            onClick={() => {
              setActiveLayers((old) => ({ ...old, [layerKey]: !old[layerKey] }));
            }}
          >
            {layerKey === "power" && "Power Price"}
            {layerKey === "land" && "Land Cost"}
            {layerKey === "permits" && "Permits"}
            {layerKey === "reg" && "Regulation"}
            {layerKey === "broadband" && "Broadband"}
            {layerKey === "transmission" && "Transmission Lines"}
          </button>
        ))}
      </div>
    </>
  );
}
