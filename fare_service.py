import os
from typing import Tuple, Dict, Any, Optional, List

import openrouteservice
import requests
import math
import re


def _strip_whatsapp_metadata(s: str) -> str:
    """
    Remove common WhatsApp export artifacts at the start of a line, e.g.:
    [14:04, 26/09/2025] +60167231646: From
    """
    if not s:
        return s
    t = s.strip()
    # Drop leading [timestamp, date] blocks
    t = re.sub(r"^\s*\[[^\]]+\]\s*", "", t)
    # Drop leading phone/name with trailing colon
    t = re.sub(r"^\s*[+\d][\d\s()\-]*:\s*", "", t)
    # Drop leading From/To labels (with optional colon)
    t = re.sub(r"^(from|to)\s*:?,?\s*", "", t, flags=re.IGNORECASE)
    return t


def normalize_address(address: str) -> str:
    """
    Normalize a free-form, potentially messy address string so geocoders can
    handle it better.

    - Trim surrounding whitespace
    - Collapse multiple commas into a single comma
    - Trim whitespace around commas
    - Collapse multiple internal spaces
    - Remove empty segments
    """
    if not address:
        return ""

    # If multiple lines are provided (e.g., WhatsApp paste), choose the most
    # address-like line (with the most commas); fall back to last non-empty.
    lines = [ln.strip() for ln in str(address).splitlines() if ln.strip()]
    if lines:
        # Strip WhatsApp metadata from each line
        lines = [_strip_whatsapp_metadata(ln) for ln in lines]
        candidate = max(lines, key=lambda x: (x.count(','), len(x)))
    else:
        candidate = str(address)

    # Replace multiple commas with a single comma on the candidate
    a = candidate
    a = a.replace("\n", " ")
    while ",," in a:
        a = a.replace(",,", ",")

    # Split by comma, trim each segment, drop empties
    parts = [p.strip() for p in a.split(",")]
    parts = [p for p in parts if p]

    # Expand common Malaysian abbreviations and aliases within each part
    def expand_abbrev(part: str) -> str:
        p = part
        # Remove standalone 5-digit postal codes
        p = re.sub(r"\b\d{5}\b", "", p)
        # Common road and place abbreviations
        replacements = {
            r"\bJln\b": "Jalan",
            r"\bJl\b": "Jalan",
            r"\bLbh\b": "Lebuh",
            r"\bLor\b": "Lorong",
            r"\bKg\b": "Kampung",
            r"\bTmn\b": "Taman",
            r"\bBt\b": "Batu",
        }
        for pat, rep in replacements.items():
            p = re.sub(pat, rep, p, flags=re.IGNORECASE)

        # Common local aliases that improve geocoding
        alias_map = {
            "ioi resort": "IOI Resort City",
            "putrajya": "Putrajaya",
        }
        lower = p.lower()
        for k, v in alias_map.items():
            if k in lower:
                p = re.sub(re.escape(k), v, lower, flags=re.IGNORECASE)
                break
        return p.strip()

    parts = [expand_abbrev(p) for p in parts]

    # Re-join with single comma+space
    a = ", ".join([p for p in parts if p])

    # Collapse multiple spaces within segments
    a = " ".join(a.split())
    # Append country if missing to aid global geocoders
    if not re.search(r"\b(Malaysia)\b", a, flags=re.IGNORECASE):
        a = f"{a}, Malaysia"
    return a


def _simplify_address_for_retry(address: str) -> Optional[str]:
    """
    Try to simplify a very detailed address by keeping only the last few
    comma-separated segments (typically neighborhood/city/state/country).
    This helps when a building/tower/floor info confuses the geocoder.

    Returns a simplified string or None if it can't be simplified further.
    """
    if not address:
        return None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) <= 1:
        return None
    # Keep the last up-to-3 segments (e.g., city, state, country)
    keep = parts[-3:] if len(parts) >= 3 else parts[-2:]
    simplified = ", ".join(keep)
    # Ensure we actually simplified something
    if simplified and simplified != address:
        return simplified
    return None


def get_client() -> openrouteservice.Client:
    """
    Create an OpenRouteService client using the API key from the environment variable
    OPENROUTESERVICE_API_KEY.
    """
    api_key = os.environ.get("OPENROUTESERVICE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTESERVICE_API_KEY is not set. Please set it in your environment or .env file."
        )
    return openrouteservice.Client(key=api_key)


def geocode_address(client: openrouteservice.Client, address: str) -> Tuple[float, float]:
    """
    Geocode an address string to (lon, lat) tuple using Pelias Search.
    Returns: (lon, lat)
    Raises ValueError if no results.
    """
    # Optional country bias for Pelias/ORS, e.g., "MY" for Malaysia
    # Default bias to Malaysia if not provided, helps with local detailed addresses
    country = (os.environ.get("GEOCODER_COUNTRY") or "MY").strip()
    pelias_params: Dict[str, Any] = {"text": address}
    if country:
        # ORS Pelias expects ISO 3166-1 alpha-2 code(s)
        pelias_params["boundary.country"] = [country.upper()]

    result = client.pelias_search(**pelias_params)
    features = result.get("features", [])
    if not features:
        raise ValueError(f"No results found for address: {address}")
    coords = features[0]["geometry"]["coordinates"]
    # API returns [lon, lat]
    return float(coords[0]), float(coords[1])


def geocode_address_nominatim(address: str) -> Tuple[float, float]:
    """
    Geocode using OpenStreetMap Nominatim public API (no API key required).
    Returns (lon, lat).
    """
    url = "https://nominatim.openstreetmap.org/search"
    # Default bias to Malaysia if not provided
    country = (os.environ.get("GEOCODER_COUNTRY") or "my").strip().lower()
    params = {
        "q": address,
        "format": "jsonv2",
        # Ask for more candidates and we'll pick the top
        "limit": 3,
        # Help Nominatim disambiguate detailed addresses
        "addressdetails": 1,
    }
    if country:
        # Nominatim expects lower-case comma-separated country codes
        params["countrycodes"] = country
    headers = {
        "User-Agent": "FareCalculator/1.0 (+https://example.com)"
    }
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"No results found for address: {address}")
    # Prefer highest importance
    item = sorted(data, key=lambda x: float(x.get("importance", 0)), reverse=True)[0]
    # Nominatim returns lat/lon as strings
    lat = float(item["lat"])  # lat, lon order
    lon = float(item["lon"])  # convert to float
    return lon, lat  # return (lon, lat)


def robust_geocode(address: str) -> Tuple[float, float]:
    """
    Geocode with multiple strategies:
    1) If ORS API key is present, try ORS Pelias with country bias.
    2) Fall back to Nominatim with country bias.
    3) If both fail, try a simplified version of the address with both providers.
    Raises ValueError with a helpful message if all attempts fail.
    """
    # 0) Accept raw coordinates like "lat, lon" or "lon, lat", even with extra text
    def _try_parse_coords(s: str) -> Optional[Tuple[float, float]]:
        if not s:
            return None
        # Find all numbers in the string (integers or decimals with optional sign)
        nums = re.findall(r"[+-]?(?:\d+(?:\.\d+)?)", s)
        if len(nums) < 2:
            return None
        a = float(nums[0])
        b = float(nums[1])
        # Heuristic: if first looks like lat (-90..90) and second like lon (-180..180), interpret as lat,lon
        if -90.0 <= a <= 90.0 and -180.0 <= b <= 180.0:
            lat, lon = a, b
        else:
            # Otherwise assume lon,lat
            lon, lat = a, b
        return (lon, lat)

    parsed = _try_parse_coords(address)
    if parsed:
        return parsed
    api_key = os.environ.get("OPENROUTESERVICE_API_KEY")

    # 1) Primary attempt(s)
    if api_key:
        try:
            client = get_client()
            return geocode_address(client, address)
        except Exception:
            pass  # fall through to Nominatim

    try:
        return geocode_address_nominatim(address)
    except Exception:
        pass

    # 2) Simplify and retry
    simplified = _simplify_address_for_retry(address)
    if simplified:
        if api_key:
            try:
                client = get_client()
                return geocode_address(client, simplified)
            except Exception:
                pass
        try:
            return geocode_address_nominatim(simplified)
        except Exception:
            pass

    raise ValueError(
        "No results found for address after multiple attempts: "
        f"'{address}'. Try a simpler form like 'Area, City, State' or ensure it includes the city/state."
    )


def haversine_meters(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    Compute haversine distance in meters between two (lon, lat) coordinates.
    """
    lon1, lat1 = a
    lon2, lat2 = b
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(h))


def _ors_profile(mode: str) -> str:
    """Map generic mode to an OpenRouteService profile."""
    m = (mode or "car").lower()
    if m in ("bike", "bicycle", "cycling"):
        return "cycling-regular"
    if m in ("foot", "walk", "walking", "pedestrian"):
        return "foot-walking"
    return "driving-car"


def _osrm_profile(mode: str) -> str:
    """Map generic mode to an OSRM profile path fragment."""
    m = (mode or "car").lower()
    if m in ("bike", "bicycle", "cycling", "cycle"):
        return "cycling"
    if m in ("foot", "walk", "walking", "pedestrian"):
        # OSRM demo server uses 'walking' as the profile name
        return "walking"
    return "driving"


def route_summary(
    client: openrouteservice.Client,
    start: Tuple[float, float],
    end: Tuple[float, float],
    mode: str = "car",
) -> Dict[str, Any]:
    """
    Fetch a route using OpenRouteService with geometry and steps.
    Returns dict with distance_m, duration_s, geometry (list[[lon,lat], ...]), and steps if available.
    """
    profile = _ors_profile(mode)
    route = client.directions(
        coordinates=[start, end],
        profile=profile,
        format="geojson",
        instructions=True,
        elevation=False,
    )
    feat = route["features"][0]
    props = feat["properties"]
    summary = props["summary"]
    geometry: List[List[float]] = feat.get("geometry", {}).get("coordinates", [])  # [lon, lat]

    steps: List[Dict[str, Any]] = []
    segs = props.get("segments") or []
    if segs:
        for seg in segs:
            for s in seg.get("steps", []):
                steps.append({
                    "distance": s.get("distance"),
                    "duration": s.get("duration"),
                    "instruction": s.get("instruction"),
                })

    return {
        "provider": "ors",
        "profile": profile,
        "distance_m": summary["distance"],
        "duration_s": summary["duration"],
        "geometry": geometry,
        "steps": steps,
        "traffic": False,
    }


def route_summary_osrm(
    start: Tuple[float, float],
    end: Tuple[float, float],
    mode: str = "car",
) -> Dict[str, Any]:
    """
    Fetch route using the public OSRM demo server with geometry and steps.
    Returns dict with distance_m, duration_s, geometry (list[[lon,lat], ...]).
    """
    profile = _osrm_profile(mode)
    base = f"https://router.project-osrm.org/route/v1/{profile}"
    coords = f"{start[0]},{start[1]};{end[0]},{end[1]}"
    url = f"{base}/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "false",
        "annotations": "false",
    }
    headers = {
        "User-Agent": "FareCalculator/1.0 (+https://example.com)"
    }
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    routes = data.get("routes") or []
    if not routes:
        raise ValueError("No route found between the provided locations.")
    r0 = routes[0]
    geometry: List[List[float]] = r0.get("geometry", {}).get("coordinates", [])

    steps: List[Dict[str, Any]] = []
    legs = r0.get("legs") or []
    for leg in legs:
        for s in leg.get("steps", []):
            steps.append({
                "distance": s.get("distance"),
                "duration": s.get("duration"),
                "name": s.get("name"),
                "maneuver": (s.get("maneuver") or {}).get("instruction"),
            })

    return {
        "provider": "osrm",
        "profile": profile,
        "distance_m": float(r0.get("distance", 0.0)),
        "duration_s": float(r0.get("duration", 0.0)),
        "geometry": geometry,
        "steps": steps,
        "traffic": False,
    }


# --- Google Directions (traffic-aware) optional backend ---
def _google_mode(mode: str) -> str:
    m = (mode or "car").lower()
    if m in ("bike", "bicycle", "cycling", "cycle"):
        return "bicycling"
    if m in ("foot", "walk", "walking", "pedestrian"):
        return "walking"
    return "driving"


def _polyline_decode(encoded: str) -> List[List[float]]:
    """Decode Google encoded polyline into [[lon, lat], ...]."""
    if not encoded:
        return []
    coords: List[List[float]] = []
    index = lat = lng = 0
    length = len(encoded)

    while index < length:
        result = shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        result = shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coords.append([lng / 1e5, lat / 1e5])  # [lon, lat]
    return coords


def route_summary_google(
    start: Tuple[float, float],
    end: Tuple[float, float],
    mode: str = "car",
) -> Dict[str, Any]:
    """
    Google Directions API. Uses duration_in_traffic for driving if available.
    Returns dict like other backends with geometry and 'traffic' bool.
    Requires GOOGLE_MAPS_API_KEY in env.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set")

    gmode = _google_mode(mode)
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{start[1]},{start[0]}",  # lat,lon
        "destination": f"{end[1]},{end[0]}",  # lat,lon
        "mode": gmode,
        "alternatives": "false",
        "key": api_key,
    }
    # For driving, ask for traffic now
    if gmode == "driving":
        import time
        params["departure_time"] = int(time.time())
        params["traffic_model"] = "best_guess"

    headers = {"User-Agent": "FareCalculator/1.0 (+https://example.com)"}
    resp = requests.get(url, params=params, headers=headers, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    routes = data.get("routes") or []
    if not routes:
        raise ValueError("No route found from Google Directions")
    r0 = routes[0]
    legs = r0.get("legs") or []
    if not legs:
        raise ValueError("No legs returned from Google Directions")
    leg0 = legs[0]
    dist_m = float((leg0.get("distance") or {}).get("value", 0))
    # Prefer traffic duration when available
    dur_obj = (leg0.get("duration_in_traffic") if gmode == "driving" else None) or leg0.get("duration")
    dur_s = float((dur_obj or {}).get("value", 0))
    encoded = (r0.get("overview_polyline") or {}).get("points")
    geometry = _polyline_decode(encoded)

    # Steps (optional; keep consistent shape)
    steps: List[Dict[str, Any]] = []
    for s in (leg0.get("steps") or []):
        steps.append({
            "distance": (s.get("distance") or {}).get("value"),
            "duration": (s.get("duration") or {}).get("value"),
            "instruction": (s.get("html_instructions") or "").replace("<div style=\"font-size:0.9em\">", " ").replace("</div>", " "),
        })

    return {
        "provider": "google",
        "profile": gmode,
        "distance_m": dist_m,
        "duration_s": dur_s,
        "geometry": geometry,
        "steps": steps,
        "traffic": gmode == "driving",
    }


def calculate_fare(distance_m: float, duration_s: float) -> float:
    """
    Simple fare calculation formula:
      base RM 3 + RM 1 per km + RM 0.5 per minute.
    """
    return 3 + (distance_m / 1000.0) + ((duration_s / 60.0) * 0.5)


def compute_trip(
    start_address: str,
    end_address: str,
    mode: str = "car",
) -> Dict[str, Any]:
    """
    High-level function to compute trip details and fare given two addresses.
    Returns dict with: distance_km, duration_min, fare_rm, start, end
    """
    # Normalize inputs to better handle messy or detailed addresses
    start_address = normalize_address(start_address)
    end_address = normalize_address(end_address)

    # Geocode with robust multi-provider fallback
    start = robust_geocode(start_address)
    end = robust_geocode(end_address)

    # If start and end are effectively the same location (e.g., user entered the same detailed address),
    # return a zero-distance, zero-duration route to avoid routing API errors.
    same_point_threshold_m = 20.0
    if haversine_meters(start, end) <= same_point_threshold_m:
        summary = {"provider": "direct", "profile": mode, "distance_m": 0.0, "duration_s": 0.0, "geometry": [list(start), list(end)], "steps": []}
    else:
        # Route using the best available backend (Google > ORS > OSRM)
        gkey = os.environ.get("GOOGLE_MAPS_API_KEY")
        if gkey:
            try:
                summary = route_summary_google(start, end, mode=mode)
            except Exception:
                summary = None
        else:
            summary = None

        if not summary:
            api_key = os.environ.get("OPENROUTESERVICE_API_KEY")
            if api_key:
                try:
                    client = get_client()
                    summary = route_summary(client, start, end, mode=mode)
                except Exception as e:
                    raise ValueError(f"Routing failed: {e}")
            else:
                try:
                    summary = route_summary_osrm(start, end, mode=mode)
                except Exception as e:
                    raise ValueError(f"Routing failed: {e}")

    distance_km = summary["distance_m"] / 1000.0
    duration_min = summary["duration_s"] / 60.0
    fare_rm = calculate_fare(summary["distance_m"], summary["duration_s"])

    return {
        "distance_km": distance_km,
        "duration_min": duration_min,
        "fare_rm": fare_rm,
        "start": start,
        "end": end,
        "mode": mode,
        "provider": summary.get("provider"),
        "profile": summary.get("profile"),
        "geometry": summary.get("geometry", []),  # list of [lon, lat]
        "steps": summary.get("steps", []),
        "traffic": summary.get("traffic", False),
    }
