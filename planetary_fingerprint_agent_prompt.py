"""
=============================================================================
PLANETARY DAILY FINGERPRINT — AGENT PROMPT
=============================================================================
IDS Project — Mare Nostra Subproject

Usage:
  Pass this prompt to Claude CLI (or API) with web_search tool enabled.
  Agent fetches current data from public sources, fills the schema,
  computes the fingerprint vector, and returns a complete JSON object
  ready for MongoDB insert + ChromaDB embedding.

  Claude CLI example:
    claude -p "$(cat planetary_fingerprint_agent_prompt.py)" --tools web_search

  Or extract AGENT_SYSTEM_PROMPT and AGENT_USER_PROMPT_TEMPLATE below
  and use them in your FastAPI endpoint or direct API call.

Schema version: 1.0
=============================================================================
"""

# =============================================================================
# SYSTEM PROMPT — Sets the agent's role and output contract
# =============================================================================

AGENT_SYSTEM_PROMPT = """
You are the Planetary Fingerprint Collector agent for the IDS Mare Nostra project.

Your task: fill the planetary fingerprint JSON for the date provided. Identity fields (date, julian_day, day_of_year, season, day_of_week) are pre-computed and given to you — do not recalculate them.

## DATA SOURCES — TWO TIERS

### TIER 1 — MUST FETCH LIVE (changes daily or hourly)
These require web search. Fetch in this priority order:

**Solar / Space weather** (xras.ru is fastest):
- xras.ru JSON endpoints: /txt/swv_RAL5.json (wind speed), /txt/swn_RAL5.json (density),
  /txt/swt_RAL5.json (temperature), /txt/swbt_RAL5.json (IMF Bt), /txt/swbz_RAL5.json (IMF Bz)
- xras.ru Kp + Ap + 3-day forecast: https://xras.ru/en/magnetic_storms.html
- SpaceWeatherLive for sunspot number, F10.7, flare class, active regions, CME status
- SILSO for daily sunspot confirmation

**Cosmic rays** (NMDB + Oulu):
- NMDB Oulu/Kiel/McMurdo count rates: https://www.nmdb.eu/nest/
- Oulu phi modulation: https://cosmicrays.oulu.fi/phi/phi.html
- GLE status: https://gle.oulu.fi/
- Bartol loss cone: https://neutronm.bartol.udel.edu/spaceweather/welcome.html

**Mediterranean weather** (daily):
- Wind direction + speed, sea state, MSLP for Mediterranean basin

**Tides** (daily):
- Sulina, Bosphorus, Gibraltar: tide times, coefficients, current direction

**Seismic** (daily):
- EMSC or USGS Mediterranean M2.5+ events last 24h

**Lunar** (daily — compute if search unavailable):
- Phase angle, illumination, distance, tidal force for the given date
- Lunar node longitude and perigee proximity

**Planetary** (weekly pace — use known ephemeris or compute):
- Ecliptic longitudes of Mercury, Venus, Mars, Jupiter, Saturn
- Notable conjunctions/alignments

### TIER 2 — USE BEST CURRENT ESTIMATE (slow-changing, no search needed)
Use your knowledge for these — they change on monthly/annual timescales:
- **NAO index**: updated ~weekly; use recent known value
- **AO index**: same
- **ENSO ONI**: updated monthly; use current known phase
- **QBO phase**: updated semi-annually; currently use known phase
- **Solar cycle position**: ~0.65–0.75 range currently (near solar max ~2025-2026)
- **Geomagnetic declination at waypoints**: changes ~7 arcmin/year; use WMM model values:
  Sulina ≈ +6.2°, Istanbul ≈ +5.8°, Gibraltar ≈ −1.2° (adjust slightly if date > 1yr from 2026)
- **Magnetic north pole**: lat ≈ 86.5°N, lon ≈ 162°E (changes slowly)
- **Dipole tilt**: ≈ 9.4° (stable on yearly scale)
- **SST Mediterranean**: seasonal average, adjust by ±2°C for season

## NORMALIZATION RULES (22 dimensions)
Compute fingerprint_components from your collected data:
- solar_activity: (kp/9 * 0.5) + (sunspot/250 * 0.3) + (flux/300 * 0.2)
- lunar_tidal_force: composite of distance + phase + declination (0=weakest, 1=strongest)
- lunar_phase: phase_angle_deg / 360
- lunar_distance: (distance_km − 356500) / (406700 − 356500)
- planetary_perturbation: 0.0–1.0, increases with alignment count and closeness
- geomagnetic_disturbance: (kp/9 + abs(dst)/300) / 2
- med_wind_strength: wind_kts / 40
- med_sea_state: douglas / 9
- med_pressure_anomaly: (mslp − 990) / 50
- nao_state: (nao + 3) / 6
- enso_state: (oni + 2.5) / 5
- tidal_range_composite: mean(tidal_coefficients − 20) / 100
- seismic_activity: event_count / 50
- solar_cycle_position: direct value (0.0–1.0)
- lunar_node_cycle: node_longitude / 360
- season_position: day_of_year / 365
- gcr_intensity: 1 − clamp((baseline − count_rate) / baseline / 0.15, 0, 1)  [0=suppressed, 1=high]
- phi_modulation: (phi_mv − 300) / 900
- solar_wind_dynamic_pressure: density * (speed/100)^2 * 0.1 / 20
- imf_magnitude: imf_bt_nt / 30
- forbush_decrease: forbush_magnitude_pct / 20
- loss_cone_state: loss_cone_anisotropy (already 0–1)

## OUTPUT CONTRACT
- Return ONLY a valid JSON object — no markdown, no backticks, no preamble
- All numeric values must be numbers (not strings)
- Use null only for genuinely unavailable data
- Include _sources arrays listing the actual sources used
- Compute chromadb_ready.embedding from fingerprint_components in the exact order of those 22 fields
- chromadb_ready.document format: "<date> | solar:<level> kp:<N> | moon:<phase> <illum>% d:<dist>km | gcr:<normalized> phi:<MV>MV | med:<dir><kts>kts ss:<state> | tidal:<position> | seismic:<level> | nao:<value>"
"""


# =============================================================================
# USER PROMPT TEMPLATE — Fill in the date and send
# =============================================================================

AGENT_USER_PROMPT_TEMPLATE = """
Collect the planetary daily fingerprint for:

date: {target_date}
julian_day: {julian_day}
day_of_year: {day_of_year}
season: {season}
day_of_week: {day_of_week}

These identity fields are pre-computed — use them exactly as given.

## LIVE DATA TO FETCH (Tier 1 — search required)
1. Solar: wind speed/density/temperature, IMF Bt+Bz, Kp, Ap, Dst — from xras.ru first, then NOAA SWPC
2. Solar: sunspot number, F10.7, flare class, active regions, CME — from SpaceWeatherLive / SILSO
3. Forecast: 3-day Kp forecast, storm probabilities — from xras.ru/en/forecast_activity.html
4. Cosmic rays: Oulu/Kiel/McMurdo count rates, phi — from NMDB and cosmicrays.oulu.fi
5. Cosmic rays: GLE status (gle.oulu.fi), loss cone / bidirectional streaming (Bartol)
6. Lunar: phase, illumination, distance, tidal force, node longitude — from timeanddate.com or compute
7. Planetary: ecliptic longitudes (Mercury–Saturn), notable alignments — from theskylive.com
8. Mediterranean: wind direction+speed, sea state, MSLP — search "Mediterranean weather today"
9. Tides: Sulina, Bosphorus, Gibraltar — times, coefficients, currents
10. Seismic: M2.5+ events in Mediterranean last 24h — from EMSC or USGS

## SLOW DATA (Tier 2 — use your best current knowledge, no search needed)
- NAO / AO index, ENSO ONI, QBO phase
- Solar cycle position (~0.68 currently, near solar max)
- Geomagnetic: magnetic north (~86.5°N, 162°E), dipole tilt (~9.4°)
- Declination at waypoints: Sulina +6.2°, Istanbul +5.8°, Gibraltar −1.2°
- Mediterranean SST seasonal average

## OUTPUT
Return a single valid JSON object with these top-level keys in order:
date, julian_day, day_of_year, updated_at, version, source,
solar, forecast, cosmic_rays, lunar, planetary, geomagnetic,
atmospheric, tides, seismic, route_corridors, fingerprint_components, chromadb_ready

Route corridors: danube_bosphorus, bosphorus_med_east, med_full_transit.
source must be "agent_collected". version must be "1.0".
Return ONLY the JSON — no explanation, no markdown.
"""


# =============================================================================
# CONVENIENCE: Generate the full prompt for a given date
# =============================================================================

def generate_agent_prompt(target_date: str = None) -> dict:
    """
    Generate system + user prompts ready for API call or Claude CLI.
    Pre-computes all deterministic identity fields so the agent doesn't waste
    tokens on date arithmetic.

    Args:
        target_date: ISO date string (YYYY-MM-DD). Defaults to today.

    Returns:
        dict with 'system' and 'user' keys, plus pre-computed 'identity' fields.
    """
    from datetime import date as dt_date

    if target_date is None:
        d = dt_date.today()
    else:
        d = dt_date.fromisoformat(target_date)

    target_date = d.isoformat()

    # Julian day number (JDN) — days since noon 1 Jan 4713 BC
    # Standard formula via Greenwich noon
    julian_day = round(
        d.toordinal() + 1721424.5 +
        (d.year // 100 - d.year // 400 - 2),  # Gregorian correction
        1
    )
    # Simpler reliable approach: offset from known J2000.0 = 2451545.0 (2000-01-01.5)
    j2000_ordinal = dt_date(2000, 1, 1).toordinal()
    julian_day = 2451545.0 + (d.toordinal() - j2000_ordinal)

    day_of_year = d.timetuple().tm_yday

    month = d.month
    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "autumn"

    day_of_week = d.strftime("%A").lower()

    user = AGENT_USER_PROMPT_TEMPLATE.format(
        target_date=target_date,
        julian_day=julian_day,
        day_of_year=day_of_year,
        season=season,
        day_of_week=day_of_week,
    ).strip()

    return {
        "system": AGENT_SYSTEM_PROMPT.strip(),
        "user": user,
        # Expose pre-computed values for caller convenience
        "identity": {
            "date": target_date,
            "julian_day": julian_day,
            "day_of_year": day_of_year,
            "season": season,
            "day_of_week": day_of_week,
        },
    }


# =============================================================================
# CONVENIENCE: Store the agent response directly
# =============================================================================

def store_fingerprint(response_json: dict, mongo_db, chromadb_collection):
    """
    Store the agent's JSON response into MongoDB and ChromaDB.

    Args:
        response_json: The parsed JSON from the agent
        mongo_db: PyMongo database instance
        chromadb_collection: ChromaDB collection instance
    """
    # --- MongoDB ---
    # Remove chromadb_ready section before storing in Mongo
    mongo_doc = {k: v for k, v in response_json.items() if k != "chromadb_ready"}

    mongo_db.planetary_fingerprints.update_one(
        {"date": mongo_doc["date"]},
        {"$set": mongo_doc},
        upsert=True
    )

    # --- ChromaDB ---
    chroma = response_json.get("chromadb_ready", {})

    chromadb_collection.upsert(
        ids=[response_json["date"]],
        embeddings=[chroma.get("embedding", [])],
        documents=[chroma.get("document", "")],
        metadatas=[chroma.get("metadata", {})]
    )

    return {
        "status": "stored",
        "date": response_json["date"],
        "mongo_collection": "planetary_fingerprints",
        "chromadb_collection": chroma.get("collection_name", "planetary_fingerprints"),
        "vector_dimensions": len(chroma.get("embedding", []))
    }


# =============================================================================
# FULL PIPELINE EXAMPLE
# =============================================================================

PIPELINE_EXAMPLE = """
# === Full daily collection pipeline ===
# Can be run as standalone script or from FastAPI endpoint

import json
import anthropic
from pymongo import MongoClient
import chromadb
from planetary_fingerprint_agent_prompt import (
    generate_agent_prompt,
    store_fingerprint
)

# 1. Generate prompt for today
prompts = generate_agent_prompt()  # defaults to today

# 2. Call Claude API with web search
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8000,
    system=prompts["system"],
    messages=[{"role": "user", "content": prompts["user"]}],
    tools=[{"type": "web_search_20250305", "name": "web_search"}]
)

# 3. Extract JSON from response
# Agent returns pure JSON, but handle potential text blocks
json_text = ""
for block in response.content:
    if block.type == "text":
        json_text += block.text

# Clean and parse
json_text = json_text.strip().strip("`").strip()
if json_text.startswith("json"):
    json_text = json_text[4:].strip()

fingerprint = json.loads(json_text)

# 4. Store in MongoDB + ChromaDB
mongo_client = MongoClient("mongodb://localhost:27017")
db = mongo_client["ids_mare_nostra"]

chroma_client = chromadb.PersistentClient(path="./chromadb_data")
collection = chroma_client.get_or_create_collection(
    name="planetary_fingerprints",
    metadata={"hnsw:space": "cosine"}  # Cosine similarity for normalized vectors
)

result = store_fingerprint(fingerprint, db, collection)
print(f"Stored: {result}")


# === Or via Claude CLI (simplest for manual runs) ===
#
# Save this to a shell script:
#
#   #!/bin/bash
#   DATE=$(date +%Y-%m-%d)
#   PROMPT=$(python -c "
#   from planetary_fingerprint_agent_prompt import generate_agent_prompt
#   import json
#   p = generate_agent_prompt('$DATE')
#   print(p['user'])
#   ")
#   
#   claude -p "$PROMPT" \\
#     --system-prompt "$(python -c "
#   from planetary_fingerprint_agent_prompt import AGENT_SYSTEM_PROMPT
#   print(AGENT_SYSTEM_PROMPT)
#   ")" \\
#     --tools web_search \\
#     --output-format json > "fingerprint_${DATE}.json"
#
#   # Then store:
#   python -c "
#   import json
#   from planetary_fingerprint_agent_prompt import store_fingerprint
#   from pymongo import MongoClient
#   import chromadb
#   
#   with open('fingerprint_${DATE}.json') as f:
#       data = json.load(f)
#   
#   db = MongoClient()['ids_mare_nostra']
#   chroma = chromadb.PersistentClient('./chromadb_data')
#   col = chroma.get_or_create_collection('planetary_fingerprints', metadata={'hnsw:space': 'cosine'})
#   print(store_fingerprint(data, db, col))
#   "
"""


# =============================================================================
# FASTAPI ENDPOINT EXAMPLE
# =============================================================================

FASTAPI_ENDPOINT_EXAMPLE = """
# Add to your existing FastAPI app in Mare Nostra

from fastapi import APIRouter, BackgroundTasks
from datetime import date

router = APIRouter(prefix="/fingerprint", tags=["planetary"])

@router.post("/collect/{target_date}")
async def collect_fingerprint(
    target_date: str = None,
    background_tasks: BackgroundTasks = None
):
    \"\"\"
    Trigger daily fingerprint collection.
    Can be called manually or via cron.
    \"\"\"
    if target_date is None:
        target_date = date.today().isoformat()

    if background_tasks:
        background_tasks.add_task(run_collection, target_date)
        return {"status": "collecting", "date": target_date}
    else:
        result = await run_collection(target_date)
        return result


async def run_collection(target_date: str):
    import anthropic
    import json

    prompts = generate_agent_prompt(target_date)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=prompts["system"],
        messages=[{"role": "user", "content": prompts["user"]}],
        tools=[{"type": "web_search_20250305", "name": "web_search"}]
    )

    json_text = ""
    for block in response.content:
        if block.type == "text":
            json_text += block.text

    json_text = json_text.strip().strip("`").strip()
    if json_text.startswith("json"):
        json_text = json_text[4:].strip()

    fingerprint = json.loads(json_text)

    # Store using your existing db connections
    from app.database import get_mongo_db, get_chromadb_collection
    result = store_fingerprint(
        fingerprint,
        get_mongo_db(),
        get_chromadb_collection("planetary_fingerprints")
    )

    return result


@router.get("/latest")
async def get_latest_fingerprint():
    \"\"\"Get the most recent fingerprint.\"\"\"
    from app.database import get_mongo_db
    db = get_mongo_db()
    doc = db.planetary_fingerprints.find_one(
        sort=[("date", -1)],
        projection={"_id": 0}
    )
    return doc


@router.get("/similar/{target_date}")
async def find_similar_days(target_date: str, n: int = 10):
    \"\"\"Find historically similar physical days.\"\"\"
    from app.database import get_mongo_db, get_chromadb_collection

    db = get_mongo_db()
    doc = db.planetary_fingerprints.find_one({"date": target_date})
    if not doc or "fingerprint_components" not in doc:
        return {"error": "No fingerprint for this date"}

    # Build vector from components
    fc = doc["fingerprint_components"]
    vector = [
        fc["solar_activity"], fc["lunar_tidal_force"], fc["lunar_phase"],
        fc["lunar_distance"], fc["planetary_perturbation"],
        fc["geomagnetic_disturbance"], fc["med_wind_strength"],
        fc["med_sea_state"], fc["med_pressure_anomaly"],
        fc["nao_state"], fc["enso_state"], fc["tidal_range_composite"],
        fc["seismic_activity"], fc["solar_cycle_position"],
        fc["lunar_node_cycle"], fc["season_position"],
        fc["gcr_intensity"], fc["phi_modulation"],
        fc["solar_wind_dynamic_pressure"], fc["imf_magnitude"],
        fc["forbush_decrease"], fc["loss_cone_state"]
    ]

    collection = get_chromadb_collection("planetary_fingerprints")
    results = collection.query(
        query_embeddings=[vector],
        n_results=n,
        include=["documents", "metadatas", "distances"]
    )

    return {
        "query_date": target_date,
        "similar_days": [
            {
                "date": meta["date"],
                "similarity": 1 - dist,  # cosine distance → similarity
                "summary": doc_text,
                "metadata": meta
            }
            for meta, dist, doc_text in zip(
                results["metadatas"][0],
                results["distances"][0],
                results["documents"][0]
            )
        ]
    }
"""


if __name__ == "__main__":
    # Print today's prompt for quick copy-paste to Claude CLI
    prompts = generate_agent_prompt()
    print("=" * 70)
    print("SYSTEM PROMPT")
    print("=" * 70)
    print(prompts["system"][:200] + "...\n")
    print("=" * 70)
    print("USER PROMPT")
    print("=" * 70)
    print(prompts["user"][:500] + "...\n")
    print("=" * 70)
    print(f"Target date: {prompts['user'].split('date: ')[1].split(chr(10))[0]}")
    print("Ready to send to Claude CLI or API")
