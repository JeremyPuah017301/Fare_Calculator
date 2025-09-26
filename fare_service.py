import os
from typing import Tuple, Dict, Any

import openrouteservice
import requests


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
    result = client.pelias_search(text=address)
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
    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 1,
    }
    headers = {
        "User-Agent": "FareCalculator/1.0 (+https://example.com)"
    }
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"No results found for address: {address}")
    item = data[0]
    # Nominatim returns lat/lon as strings
    lat = float(item["lat"])  # lat, lon order
    lon = float(item["lon"])  # convert to float
    return lon, lat  # return (lon, lat)


def route_summary(
    client: openrouteservice.Client,
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> Dict[str, Any]:
    """
    Fetch a driving route summary (distance in meters, duration in seconds) between two coordinates.
    Coordinates must be (lon, lat).
    Returns dict: {"distance_m": int|float, "duration_s": int|float}
    """
    route = client.directions(
        coordinates=[start, end],
        profile="driving-car",
        format="geojson",
    )
    summary = route["features"][0]["properties"]["summary"]
    return {
        "distance_m": summary["distance"],
        "duration_s": summary["duration"],
    }


def route_summary_osrm(
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> Dict[str, Any]:
    """
    Fetch route summary using the public OSRM demo server (no API key required).
    Coordinates must be (lon, lat).
    Returns dict: {"distance_m": float, "duration_s": float}
    """
    base = "https://router.project-osrm.org/route/v1/driving"
    coords = f"{start[0]},{start[1]};{end[0]},{end[1]}"
    url = f"{base}/{coords}"
    params = {
        "overview": "false",
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
    return {
        "distance_m": float(r0.get("distance", 0.0)),
        "duration_s": float(r0.get("duration", 0.0)),
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
) -> Dict[str, Any]:
    """
    High-level function to compute trip details and fare given two addresses.
    Returns dict with: distance_km, duration_min, fare_rm, start, end
    """
    api_key = os.environ.get("OPENROUTESERVICE_API_KEY")
    if api_key:
        # Use OpenRouteService when key is provided
        client = get_client()
        start = geocode_address(client, start_address)
        end = geocode_address(client, end_address)
        summary = route_summary(client, start, end)
    else:
        # Fallback: Use Nominatim + OSRM without any API key
        start = geocode_address_nominatim(start_address)
        end = geocode_address_nominatim(end_address)
        summary = route_summary_osrm(start, end)

    distance_km = summary["distance_m"] / 1000.0
    duration_min = summary["duration_s"] / 60.0
    fare_rm = calculate_fare(summary["distance_m"], summary["duration_s"])

    return {
        "distance_km": distance_km,
        "duration_min": duration_min,
        "fare_rm": fare_rm,
        "start": start,
        "end": end,
    }
