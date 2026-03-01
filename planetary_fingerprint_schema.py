"""
=============================================================================
PLANETARY DAILY FINGERPRINT SCHEMA
=============================================================================
IDS Project — Mare Nostra Subproject
Physical State Diary of the Planet

Storage: MongoDB (structured data) + ChromaDB (vector similarity search)
Update mode: Manual daily (with future automation path)
Purpose: Enable agent pattern search across environmental/maritime conditions

Schema version: 1.0
=============================================================================
"""

from datetime import datetime, date
from typing import Optional, List
import numpy as np

# =============================================================================
# MONGODB COLLECTION: planetary_fingerprints
# =============================================================================
# One document per day. Global physical state + route-specific overlays.
# Index on: date (unique), lunar_phase_category, solar_cycle_position
# Compound index on: date + route_corridors.corridor_id

DAILY_FINGERPRINT_DOCUMENT = {
    # -------------------------------------------------------------------------
    # IDENTITY
    # -------------------------------------------------------------------------
    "date": "2026-03-01",                    # ISO date, unique key
    "julian_day": 2461000.5,                 # For astronomical calculations
    "day_of_year": 60,
    "updated_at": "2026-03-01T18:30:00Z",   # Last manual/auto update timestamp
    "version": "1.0",
    "source": "manual",                       # "manual" | "automated" | "backfill"

    # -------------------------------------------------------------------------
    # SOLAR UPDATES (Sun → Earth energy/particle transfer)
    # -------------------------------------------------------------------------
    "solar": {
        # Real-time solar wind (NOAA DSCOVR / ACE / xras.ru)
        "solar_wind_speed_km_s": 420.0,      # Typical 300-800
        "solar_wind_density_cm3": 5.2,        # Protons per cm³
        "solar_wind_temperature_k": 120000,   # Kelvin, typical 10000-500000
        "imf_bt_nt": 6.5,                    # Total IMF magnitude (nT)
        "imf_bz_nt": -3.5,                   # Interplanetary magnetic field Bz component
                                              # Negative = geomagnetically active

        # Geomagnetic indices
        "kp_index": 3,                        # 0-9, planetary geomagnetic disturbance
        "ap_index": 15,                       # 0-400, daily geomagnetic index
        "dst_index_nt": -25,                  # Disturbance storm time (nT)

        # Solar surface activity
        "sunspot_number": 125,
        "solar_flux_f107": 150.0,             # 10.7cm radio flux (solar UV proxy)
        "solar_cycle_position": 0.65,         # 0.0-1.0 within ~11yr cycle
        "active_region_count": 8,

        # Flare activity (last 24h)
        "flare_max_class": "M2.1",           # None | B | C | M | X class
        "cme_earth_directed": False,          # Coronal mass ejection toward Earth

        # Solar irradiance
        "tsi_w_m2": 1361.2,                  # Total solar irradiance

        # Source references
        "_sources": ["NOAA SWPC", "DSCOVR", "SILSO", "xras.ru"]
    },

    # -------------------------------------------------------------------------
    # SPACE WEATHER FORECAST (3-day outlook)
    # -------------------------------------------------------------------------
    "forecast": {
        "kp_forecast_3day": [3, 4, 2],       # Max Kp expected per day
        "f107_forecast": 148.0,               # Predicted F10.7
        "storm_probability_3day": {
            "quiet": 0.60,                    # Kp < 4
            "moderate": 0.30,                 # Kp 4-6
            "strong": 0.10,                   # Kp > 6
        },
        "_sources": ["NOAA SWPC", "xras.ru"]
    },

    # -------------------------------------------------------------------------
    # COSMIC RAYS (Galactic cosmic ray flux — heliospheric boundary state)
    # -------------------------------------------------------------------------
    "cosmic_rays": {
        # Neutron monitor count rates (NMDB network)
        "neutron_counts": {
            "oulu": {
                "count_rate_per_hour": 6420,  # Typical ~6000-7000 in solar max
                "baseline_rate": 6800,         # Long-term average
                "deviation_pct": -5.6,         # % deviation from baseline (negative = suppressed)
            },
            "kiel": {
                "count_rate_per_hour": 3850,
                "baseline_rate": 4100,
                "deviation_pct": -6.1,
            },
            "mcmurdo": {
                "count_rate_per_hour": 2180,
                "baseline_rate": 2300,
                "deviation_pct": -5.2,
            },
        },

        # Derived indices
        "gcr_intensity_normalized": 0.35,     # 0.0=suppressed (solar max), 1.0=high flux (solar min)
        "phi_modulation_mv": 650.0,           # Solar modulation potential 300-1200 MV

        # Event flags
        "gle_active": False,                  # Ground Level Enhancement in progress
        "gle_last_event_date": "2025-01-14",  # Date of most recent GLE
        "forbush_decrease_active": False,     # Forbush decrease in progress
        "forbush_decrease_magnitude_pct": 0,  # 0-20% suppression

        # Anisotropy (Bartol Spaceship Earth)
        "loss_cone_anisotropy": 0.05,         # 0.0=isotropic, 1.0=strong anisotropy
        "bidirectional_streaming": False,     # Bidirectional particle streaming

        "_sources": ["NMDB", "Oulu Cosmic Ray Station", "Bartol"]
    },

    # -------------------------------------------------------------------------
    # LUNAR UPDATES (Moon → Earth gravitational/tidal forcing)
    # -------------------------------------------------------------------------
    "lunar": {
        "phase_angle_deg": 145.0,             # 0=new, 90=first quarter, 180=full
        "phase_name": "waxing_gibbous",       # new|waxing_crescent|first_quarter|
                                              # waxing_gibbous|full|waning_gibbous|
                                              # third_quarter|waning_crescent
        "illumination_pct": 78.5,
        "age_days": 11.2,                     # Days since last new moon

        # Orbital parameters
        "distance_km": 375420.0,              # Earth-Moon distance (perigee ~356k, apogee ~406k)
        "distance_normalized": 0.62,          # 0.0=perigee, 1.0=apogee
        "declination_deg": 18.5,              # Lunar declination (affects tidal asymmetry)
        "ecliptic_longitude_deg": 210.0,

        # Tidal forcing
        "tidal_force_normalized": 0.75,       # 0.0-1.0 composite tidal strength
                                              # Accounts for distance + phase + declination
        "lunar_node_longitude_deg": 15.3,     # 18.6-year nodal cycle position
        "perigee_proximity_days": 5,          # Days to/from nearest perigee (signed)

        "_sources": ["JPL Horizons", "USNO"]
    },

    # -------------------------------------------------------------------------
    # PLANETARY CONFIGURATION (CM hierarchy — outer body influences)
    # -------------------------------------------------------------------------
    "planetary": {
        # Key planetary positions (ecliptic longitude, geocentric)
        "positions_ecliptic_lon": {
            "mercury": 320.5,
            "venus": 45.2,
            "mars": 180.3,
            "jupiter": 92.7,
            "saturn": 5.8
        },

        # Significant alignments (angular separations < 15°)
        "alignments": [
            {
                "bodies": ["venus", "jupiter"],
                "separation_deg": 12.5,
                "type": "conjunction"          # conjunction | opposition | square | trine
            }
        ],

        # Composite gravitational perturbation on Earth
        # (planetary tidal contribution, normalized)
        "planetary_tidal_composite": 0.15,     # 0.0-1.0, typically small
                                               # Peaks during multi-body alignments

        # Earth-Sun-Jupiter angle (dominant planetary perturber)
        "jupiter_earth_sun_angle_deg": 87.3,

        # Barycentric offset
        "solar_system_barycenter_offset_solar_radii": 1.2,  # How far Sun is from SSB

        "_sources": ["JPL Horizons", "astropy"]
    },

    # -------------------------------------------------------------------------
    # EARTH MAGNETIC FIELD (Internal dynamo update)
    # -------------------------------------------------------------------------
    "geomagnetic": {
        "magnetic_north_lat": 86.5,           # Current magnetic pole position
        "magnetic_north_lon": 162.3,
        "dipole_tilt_deg": 9.4,               # Angle between geographic and magnetic axis

        # Regional field measurements (relevant waypoints)
        "declination_at_waypoints": {
            "sulina": {"declination_deg": 6.2, "annual_change_arcmin": 7.5},
            "istanbul": {"declination_deg": 5.8, "annual_change_arcmin": 7.1},
            "gibraltar": {"declination_deg": -1.2, "annual_change_arcmin": 8.0}
        },

        "_sources": ["NOAA NCEI", "WMM", "IGRF"]
    },

    # -------------------------------------------------------------------------
    # ATMOSPHERIC STATE (Solar-driven weather system)
    # -------------------------------------------------------------------------
    "atmospheric": {
        # Large-scale indices
        "nao_index": 1.2,                     # North Atlantic Oscillation
        "ao_index": 0.8,                      # Arctic Oscillation
        "enso_oni": -0.5,                     # ENSO Oceanic Niño Index
        "qbo_phase": "westerly",              # Quasi-biennial oscillation

        # Mediterranean-specific (Mare Nostra focus)
        "med_mslp_hpa": 1018.5,              # Mean sea level pressure, Med basin
        "med_dominant_wind": "NW",            # Dominant wind direction
        "med_wind_speed_avg_kts": 15,
        "med_sea_state_douglas": 3,           # Douglas sea state 0-9
        "med_sst_avg_c": 18.5,               # Sea surface temperature

        "_sources": ["ECMWF ERA5", "NOAA CPC"]
    },

    # -------------------------------------------------------------------------
    # TIDAL STATE AT KEY WAYPOINTS (Lunar + solar + planetary combined)
    # -------------------------------------------------------------------------
    "tides": {
        "waypoints": {
            "sulina": {
                "high_tide_times_utc": ["03:45", "16:10"],
                "low_tide_times_utc": ["09:55", "22:20"],
                "tidal_range_m": 0.3,          # Danube delta — small range
                "tidal_coefficient": 65,        # 20-120 scale
                "current_max_kts": 0.5
            },
            "bosphorus": {
                "high_tide_times_utc": ["04:20", "16:45"],
                "low_tide_times_utc": ["10:30", "22:55"],
                "tidal_range_m": 0.15,
                "tidal_coefficient": 55,
                "current_max_kts": 3.5,        # Bosphorus currents are significant
                "surface_current_direction": "S"  # Black Sea → Mediterranean dominant
            },
            "gibraltar": {
                "high_tide_times_utc": ["02:15", "14:40"],
                "low_tide_times_utc": ["08:25", "20:50"],
                "tidal_range_m": 1.2,
                "tidal_coefficient": 75,
                "current_max_kts": 4.0,
                "surface_current_direction": "E"  # Atlantic inflow
            }
        },
        "spring_neap_position": "neap_to_spring",  # spring | neap | spring_to_neap | neap_to_spring

        "_sources": ["SHOM", "local tide gauges", "UKHO"]
    },

    # -------------------------------------------------------------------------
    # SEISMIC STATE (Earth internal dynamics)
    # -------------------------------------------------------------------------
    "seismic": {
        "significant_events_24h": [
            {
                "magnitude": 4.5,
                "depth_km": 35,
                "lat": 38.2,
                "lon": 26.1,
                "region": "Aegean Sea",
                "timestamp_utc": "2026-03-01T06:22:00Z"
            }
        ],
        "med_seismic_activity_level": "low",   # low | moderate | elevated | high
        "total_events_med_24h": 12,            # M2.5+ in Mediterranean basin

        "_sources": ["USGS", "EMSC"]
    },

    # -------------------------------------------------------------------------
    # ROUTE CORRIDOR OVERLAYS (Mare Nostra specific)
    # -------------------------------------------------------------------------
    "route_corridors": [
        {
            "corridor_id": "danube_bosphorus",
            "name": "Danube Delta → Bosphorus",
            "conditions_summary": "moderate",   # favorable | moderate | challenging | hazardous
            "dominant_factors": ["wind_NW_15kts", "current_southward"],
            "estimated_delay_hours": 2.0,       # vs ideal conditions
            "warnings": []
        },
        {
            "corridor_id": "bosphorus_med_east",
            "name": "Bosphorus → Eastern Mediterranean",
            "conditions_summary": "favorable",
            "dominant_factors": ["following_current", "low_sea_state"],
            "estimated_delay_hours": 0.0,
            "warnings": []
        },
        {
            "corridor_id": "med_full_transit",
            "name": "Eastern Med → Gibraltar",
            "conditions_summary": "moderate",
            "dominant_factors": ["headwind_component", "moderate_swell"],
            "estimated_delay_hours": 4.5,
            "warnings": ["gale_warning_balearic"]
        }
    ],

    # -------------------------------------------------------------------------
    # COMPOSITE FINGERPRINT (for ChromaDB embedding) — 22 dimensions
    # -------------------------------------------------------------------------
    "fingerprint_components": {
        # Normalized 0.0-1.0 values used to build the vector
        # These are the dimensions of your "physical day" space
        # === Original 16 ===
        "solar_activity": 0.45,               # (kp/9 * 0.5) + (sunspot/250 * 0.3) + (flux/300 * 0.2)
        "lunar_tidal_force": 0.75,            # From lunar.tidal_force_normalized
        "lunar_phase": 0.40,                  # phase_angle_deg / 360
        "lunar_distance": 0.62,               # distance_normalized (0=perigee, 1=apogee)
        "planetary_perturbation": 0.15,       # planetary_tidal_composite
        "geomagnetic_disturbance": 0.35,      # (kp/9 + abs(dst)/300) / 2
        "med_wind_strength": 0.38,            # wind_kts / 40
        "med_sea_state": 0.33,                # douglas / 9
        "med_pressure_anomaly": 0.52,         # (mslp - 990) / 50
        "nao_state": 0.65,                    # (nao + 3) / 6
        "enso_state": 0.45,                   # (oni + 2.5) / 5
        "tidal_range_composite": 0.55,        # avg(tidal_coefficients - 20) / 100
        "seismic_activity": 0.15,             # event_count / 50
        "solar_cycle_position": 0.65,         # direct from solar.solar_cycle_position
        "lunar_node_cycle": 0.04,             # node_longitude / 360
        "season_position": 0.16,              # day_of_year / 365
        # === Cosmic ray dimensions (v1.1+) ===
        "gcr_intensity": 0.35,                # 0=suppressed (solar max), 1=high flux (solar min)
        "phi_modulation": 0.39,               # (phi_mv - 300) / 900
        "solar_wind_dynamic_pressure": 0.22,  # density * (speed/100)^2 * 0.1 / 20
        "imf_magnitude": 0.22,                # imf_bt_nt / 30
        "forbush_decrease": 0.00,             # forbush_magnitude_pct / 20
        "loss_cone_state": 0.05,              # loss_cone_anisotropy (already 0-1)
    }
}


# =============================================================================
# CHROMADB COLLECTION: planetary_fingerprints
# =============================================================================

CHROMADB_DOCUMENT = {
    "collection_name": "planetary_fingerprints",

    # The embedding vector — built from fingerprint_components above
    # 16 dimensions, each 0.0-1.0 normalized
    "embedding_example": [
        0.45, 0.75, 0.40, 0.62, 0.15, 0.35, 0.38, 0.33,
        0.52, 0.65, 0.45, 0.55, 0.15, 0.65, 0.04, 0.16
    ],

    # Document content — lightweight summary for context retrieval
    "document": "2026-03-01 | solar:moderate kp:3 | moon:waxing_gibbous 78% d:375420km | "
                "med:NW15kts ss:3 | tidal:neap_to_spring | seismic:low | nao:+1.2",

    # Metadata — filterable in ChromaDB queries
    "metadata": {
        "date": "2026-03-01",
        "season": "winter",                    # winter | spring | summer | autumn
        "lunar_phase": "waxing_gibbous",
        "solar_activity_level": "moderate",    # quiet | moderate | active | storm
        "med_conditions": "moderate",
        "spring_neap": "neap_to_spring",
        "enso_phase": "neutral",               # nino | nina | neutral
        "gcr_level": "low",                    # high | moderate | low | suppressed
        "gle_active": False,
        "forbush_active": False,
        "year": 2026,
        "month": 3,
        "day_of_week": "sunday"
    }
}


# =============================================================================
# MONGODB INDEXES
# =============================================================================

MONGODB_INDEXES = [
    # Primary lookup
    {"keys": {"date": 1}, "unique": True},

    # Pattern search filters
    {"keys": {"lunar.phase_name": 1, "date": 1}},
    {"keys": {"solar.kp_index": 1, "date": 1}},
    {"keys": {"solar.solar_cycle_position": 1}},
    {"keys": {"tides.spring_neap_position": 1, "date": 1}},
    {"keys": {"atmospheric.enso_oni": 1}},

    # Cosmic ray queries
    {"keys": {"cosmic_rays.gcr_intensity_normalized": 1, "date": 1}},
    {"keys": {"cosmic_rays.gle_active": 1, "date": 1}},
    {"keys": {"cosmic_rays.forbush_decrease_active": 1, "date": 1}},

    # Route corridor queries
    {"keys": {"route_corridors.corridor_id": 1, "date": 1}},
    {"keys": {"route_corridors.conditions_summary": 1}},

    # Time range + condition queries
    {"keys": {"date": 1, "atmospheric.med_sea_state_douglas": 1}},
    {"keys": {"date": 1, "seismic.med_seismic_activity_level": 1}},
]


# =============================================================================
# HELPER: Build fingerprint vector from raw daily data
# =============================================================================

def build_fingerprint_vector(doc: dict) -> List[float]:
    """
    Extract normalized components from a daily document
    and return as a 22-dimensional vector for ChromaDB.

    All values normalized to 0.0-1.0 range.
    Matches the normalization rules in planetary_fingerprint_agent_prompt.py.
    """
    solar = doc.get("solar", {})
    lunar = doc.get("lunar", {})
    planetary = doc.get("planetary", {})
    atmo = doc.get("atmospheric", {})
    tides = doc.get("tides", {})
    seismic = doc.get("seismic", {})
    cr = doc.get("cosmic_rays", {})

    def clamp(val, min_v=0.0, max_v=1.0):
        return max(min_v, min(max_v, float(val)))

    vector = [
        # 1. Solar activity composite
        clamp(solar.get("kp_index", 0) / 9.0 * 0.5 +
              solar.get("sunspot_number", 0) / 250.0 * 0.3 +
              solar.get("solar_flux_f107", 70) / 300.0 * 0.2),

        # 2. Lunar tidal force
        clamp(lunar.get("tidal_force_normalized", 0.5)),

        # 3. Lunar phase (circular → linear)
        clamp(lunar.get("phase_angle_deg", 0) / 360.0),

        # 4. Lunar distance (0=perigee 356500km, 1=apogee 406700km)
        clamp(lunar.get("distance_normalized", 0.5)),

        # 5. Planetary perturbation
        clamp(planetary.get("planetary_tidal_composite", 0.0)),

        # 6. Geomagnetic disturbance
        clamp((solar.get("kp_index", 0) / 9.0 +
               abs(solar.get("dst_index_nt", 0)) / 300.0) / 2.0),

        # 7. Mediterranean wind strength
        clamp(atmo.get("med_wind_speed_avg_kts", 0) / 40.0),

        # 8. Sea state
        clamp(atmo.get("med_sea_state_douglas", 0) / 9.0),

        # 9. Pressure anomaly
        clamp((atmo.get("med_mslp_hpa", 1013.25) - 990.0) / 50.0),

        # 10. NAO state
        clamp((atmo.get("nao_index", 0) + 3.0) / 6.0),

        # 11. ENSO state
        clamp((atmo.get("enso_oni", 0) + 2.5) / 5.0),

        # 12. Tidal range composite (average across waypoints)
        _compute_tidal_range_composite(tides),

        # 13. Seismic activity
        clamp(seismic.get("total_events_med_24h", 0) / 50.0),

        # 14. Solar cycle position
        clamp(solar.get("solar_cycle_position", 0.5)),

        # 15. Lunar node cycle
        clamp(lunar.get("lunar_node_longitude_deg", 0) / 360.0),

        # 16. Season position
        clamp(doc.get("day_of_year", 1) / 365.0),

        # 17. GCR intensity (0=suppressed solar max, 1=high flux solar min)
        clamp(cr.get("gcr_intensity_normalized", 0.5)),

        # 18. Solar modulation potential phi (300-1200 MV → 0-1)
        clamp((cr.get("phi_modulation_mv", 750) - 300.0) / 900.0),

        # 19. Solar wind dynamic pressure: density * (speed/100)^2 * 0.1 / 20
        clamp(solar.get("solar_wind_density_cm3", 5) *
              (solar.get("solar_wind_speed_km_s", 400) / 100.0) ** 2 * 0.1 / 20.0),

        # 20. IMF total magnitude
        clamp(solar.get("imf_bt_nt", 5) / 30.0),

        # 21. Forbush decrease magnitude
        clamp(cr.get("forbush_decrease_magnitude_pct", 0) / 20.0),

        # 22. Loss cone anisotropy (already 0-1)
        clamp(cr.get("loss_cone_anisotropy", 0.0)),
    ]

    return vector


def _compute_tidal_range_composite(tides: dict) -> float:
    """Average tidal coefficient across waypoints, normalized."""
    waypoints = tides.get("waypoints", {})
    if not waypoints:
        return 0.5
    coefficients = [wp.get("tidal_coefficient", 70) for wp in waypoints.values()]
    avg = sum(coefficients) / len(coefficients)
    return max(0.0, min(1.0, (avg - 20.0) / 100.0))  # Scale 20-120 → 0-1


# =============================================================================
# HELPER: Build ChromaDB metadata from daily document
# =============================================================================

def build_chromadb_metadata(doc: dict) -> dict:
    """Extract filterable metadata for ChromaDB from daily document."""

    kp = doc.get("solar", {}).get("kp_index", 0)
    if kp <= 2:
        solar_level = "quiet"
    elif kp <= 4:
        solar_level = "moderate"
    elif kp <= 6:
        solar_level = "active"
    else:
        solar_level = "storm"

    oni = doc.get("atmospheric", {}).get("enso_oni", 0)
    if oni >= 0.5:
        enso = "nino"
    elif oni <= -0.5:
        enso = "nina"
    else:
        enso = "neutral"

    d = doc.get("date", "")
    month = int(d.split("-")[1]) if d else 1
    if month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    else:
        season = "autumn"

    day_names = ["monday", "tuesday", "wednesday", "thursday",
                 "friday", "saturday", "sunday"]
    try:
        d_obj = date.fromisoformat(d)
        dow = day_names[d_obj.weekday()]
    except (ValueError, IndexError):
        dow = "unknown"

    cr = doc.get("cosmic_rays", {})
    gcr = cr.get("gcr_intensity_normalized", 0.5)
    if gcr >= 0.75:
        gcr_level = "high"
    elif gcr >= 0.50:
        gcr_level = "moderate"
    elif gcr >= 0.25:
        gcr_level = "low"
    else:
        gcr_level = "suppressed"

    return {
        "date": d,
        "season": season,
        "lunar_phase": doc.get("lunar", {}).get("phase_name", "unknown"),
        "solar_activity_level": solar_level,
        "med_conditions": _overall_med_conditions(doc),
        "spring_neap": doc.get("tides", {}).get("spring_neap_position", "unknown"),
        "enso_phase": enso,
        "gcr_level": gcr_level,
        "gle_active": bool(cr.get("gle_active", False)),
        "forbush_active": bool(cr.get("forbush_decrease_active", False)),
        "year": int(d.split("-")[0]) if d else 0,
        "month": month,
        "day_of_week": dow,
    }


def _overall_med_conditions(doc: dict) -> str:
    """Derive overall Mediterranean conditions from atmospheric data."""
    ss = doc.get("atmospheric", {}).get("med_sea_state_douglas", 0)
    wind = doc.get("atmospheric", {}).get("med_wind_speed_avg_kts", 0)
    if ss <= 2 and wind <= 10:
        return "favorable"
    elif ss <= 4 and wind <= 25:
        return "moderate"
    elif ss <= 6 and wind <= 40:
        return "challenging"
    return "hazardous"


# =============================================================================
# HELPER: Build ChromaDB document string (compact human-readable summary)
# =============================================================================

def build_chromadb_document(doc: dict) -> str:
    """Compact text summary for ChromaDB document field (matches agent chromadb_ready.document format)."""
    s = doc.get("solar", {})
    l = doc.get("lunar", {})
    a = doc.get("atmospheric", {})
    t = doc.get("tides", {})
    seis = doc.get("seismic", {})
    cr = doc.get("cosmic_rays", {})

    kp = s.get("kp_index", 0)
    solar_level = "quiet" if kp <= 2 else "moderate" if kp <= 4 else "active" if kp <= 6 else "storm"
    gcr = cr.get("gcr_intensity_normalized")
    phi = cr.get("phi_modulation_mv")

    parts = [
        doc.get("date", "unknown"),
        f"solar:{solar_level} kp:{kp}",
        (f"moon:{l.get('phase_name', '?')} {l.get('illumination_pct', '?')}%"
         f" d:{l.get('distance_km', '?'):.0f}km") if isinstance(l.get("distance_km"), (int, float))
        else f"moon:{l.get('phase_name', '?')}",
        f"gcr:{gcr:.2f} phi:{phi:.0f}MV" if isinstance(gcr, (int, float)) and isinstance(phi, (int, float)) else "",
        f"med:{a.get('med_dominant_wind', '?')}{a.get('med_wind_speed_avg_kts', '?')}kts"
        f" ss:{a.get('med_sea_state_douglas', '?')}",
        f"tidal:{t.get('spring_neap_position', '?')}",
        f"seismic:{seis.get('med_seismic_activity_level', '?')}",
        f"nao:{a.get('nao_index', '?'):+.1f}" if isinstance(a.get("nao_index"), (int, float)) else "",
    ]

    return " | ".join(p for p in parts if p)


# =============================================================================
# MANUAL UPDATE TEMPLATE
# =============================================================================
# Copy this template for daily manual entries.
# Fill in what you have, leave defaults for what you don't.

MANUAL_ENTRY_TEMPLATE = {
    "date": "YYYY-MM-DD",  # ← FILL THIS

    "solar": {
        "kp_index": 0,                # Check: https://www.swpc.noaa.gov/products/planetary-k-index
        "sunspot_number": 0,           # Check: https://www.sidc.be/silso/
        "solar_flux_f107": 70.0,       # Check: https://www.spaceweather.gc.ca/forecast-prevision/solar-solaire/solarflux/sx-5-en.php
        "solar_wind_speed_km_s": 400,  # Check: https://www.swpc.noaa.gov/products/real-time-solar-wind
        "flare_max_class": "None",
        "solar_cycle_position": 0.65,  # Update monthly, currently near solar max
    },

    "lunar": {
        "phase_name": "",              # Check: any lunar phase calendar
        "phase_angle_deg": 0,
        "illumination_pct": 0,
        "distance_km": 384400,         # Check: https://www.timeanddate.com/moon/distance/
        "declination_deg": 0,
    },

    "planetary": {
        "positions_ecliptic_lon": {},   # Check: https://theskylive.com/planets
        "alignments": [],
    },

    "atmospheric": {
        "nao_index": 0.0,              # Check: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.shtml
        "med_dominant_wind": "",
        "med_wind_speed_avg_kts": 0,
        "med_sea_state_douglas": 0,
        "med_mslp_hpa": 1013.25,
    },

    "tides": {
        "waypoints": {
            "sulina": {"tidal_coefficient": 70, "tidal_range_m": 0.0},
            "bosphorus": {"tidal_coefficient": 70, "current_max_kts": 0.0},
        },
        "spring_neap_position": "",
    },

    "seismic": {
        "total_events_med_24h": 0,      # Check: https://www.emsc-csem.org/
        "med_seismic_activity_level": "low",
    },
}


# =============================================================================
# AGENT QUERY PATTERNS
# =============================================================================
# Examples of how Parliament agents would query this data

AGENT_QUERY_EXAMPLES = {
    "find_similar_days": """
        # Agent asks: "What historical days had similar physical conditions?"
        # 1. Build today's fingerprint vector
        # 2. Query ChromaDB for nearest neighbors

        import chromadb
        client = chromadb.PersistentClient(path="./chromadb_data")
        collection = client.get_collection("planetary_fingerprints")

        today_vector = build_fingerprint_vector(today_document)

        results = collection.query(
            query_embeddings=[today_vector],
            n_results=10,
            where={"season": "winter"},  # Optional filter
            include=["documents", "metadatas", "distances"]
        )
        # Returns 10 most physically similar days
    """,

    "voyage_condition_lookup": """
        # Agent asks: "What were conditions on this route last time 
        # we had spring tides + active solar + NW wind?"

        from pymongo import MongoClient
        db = MongoClient()["ids_mare_nostra"]

        cursor = db.planetary_fingerprints.find({
            "tides.spring_neap_position": {"$in": ["spring", "neap_to_spring"]},
            "solar.kp_index": {"$gte": 4},
            "atmospheric.med_dominant_wind": "NW",
            "route_corridors": {
                "$elemMatch": {
                    "corridor_id": "danube_bosphorus"
                }
            }
        }).sort("date", -1).limit(20)
    """,

    "correlation_discovery": """
        # Agent asks: "Is there a pattern between lunar distance 
        # and Bosphorus current strength?"

        import pandas as pd

        cursor = db.planetary_fingerprints.find(
            {},
            {"lunar.distance_km": 1, 
             "tides.waypoints.bosphorus.current_max_kts": 1,
             "date": 1}
        )

        df = pd.DataFrame(list(cursor))
        # Flatten and compute correlation
        # Feed back into agent learning loop
    """,

    "daily_briefing": """
        # Agent generates morning briefing:
        # "Today's physical fingerprint is 87% similar to 2024-11-15,
        #  when we experienced 3-hour delays through Bosphorus due to
        #  strong southward currents during spring tide + perigee."

        similar_days = query_chromadb(today_vector, n=5)
        historical_outcomes = fetch_voyage_logs(similar_days)
        generate_briefing(today_document, similar_days, historical_outcomes)
    """
}


# =============================================================================
# DATA SOURCES REFERENCE
# =============================================================================

DATA_SOURCES = {
    "solar_wind":        "https://www.swpc.noaa.gov/products/real-time-solar-wind",
    "kp_index":          "https://www.swpc.noaa.gov/products/planetary-k-index",
    "sunspot_number":    "https://www.sidc.be/silso/home",
    "solar_flux":        "https://www.spaceweather.gc.ca/forecast-prevision/solar-solaire/solarflux/sx-5-en.php",
    "lunar_ephemeris":   "https://ssd.jpl.nasa.gov/horizons/",
    "lunar_distance":    "https://www.timeanddate.com/moon/distance/",
    "planetary_pos":     "https://theskylive.com/planets",
    "nao_index":         "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.shtml",
    "enso_oni":          "https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php",
    "med_weather":       "https://www.ecmwf.int/",
    "tides":             "https://www.tide-forecast.com/",
    "seismic":           "https://www.emsc-csem.org/",
    "geomagnetic_model": "https://www.ncei.noaa.gov/products/world-magnetic-model",
}


if __name__ == "__main__":
    # Quick validation: build vector from example document
    vec = build_fingerprint_vector(DAILY_FINGERPRINT_DOCUMENT)
    print(f"Fingerprint vector ({len(vec)} dimensions):")
    print([f"{v:.3f}" for v in vec])
    print()

    meta = build_chromadb_metadata(DAILY_FINGERPRINT_DOCUMENT)
    print("ChromaDB metadata:")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    print()

    doc_str = build_chromadb_document(DAILY_FINGERPRINT_DOCUMENT)
    print(f"ChromaDB document: {doc_str}")
