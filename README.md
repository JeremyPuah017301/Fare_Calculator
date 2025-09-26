# Fare Calculator (Web UI)

A simple web app that estimates trip distance, duration, and fare.

Routing/Geocoding backends:
- Default (no API key): OpenStreetMap Nominatim for geocoding + OSRM demo server for routing
- Optional: OpenRouteService (ORS) if you provide `OPENROUTESERVICE_API_KEY`

## Features

- Enter start and dropoff addresses.
- Geocodes addresses and calculates a driving route (Nominatim+OSRM by default, ORS if key provided).
- Displays distance (km), duration (minutes), and estimated fare (RM).
- Core logic extracted to `fare_service.py` for reuse/testability.

## Requirements

- Python 3.9+

Optional:
- OpenRouteService API key (only if you want to use ORS instead of the free default)

## Installation (Linux/macOS)

1) Clone the repository

```bash
git clone https://github.com/JeremyPuah017301/Fare_Calculator.git
cd Fare_Calculator
```

2) Create and activate a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3) Install dependencies

```bash
pip install -r requirements.txt
```

## Run the App

Choose one of the following modes.

### A) No API key (free + easiest)

Uses Nominatim (geocoding) and OSRM demo server (routing).

```bash
python app.py
```

Open in your browser:
- http://localhost:5000

### B) With OpenRouteService (optional)

If you have an ORS key (free tier), set it and run:

```bash
export OPENROUTESERVICE_API_KEY=your_api_key_here
# optionally:
export FLASK_SECRET_KEY=change-me
export PORT=5000
python app.py
```

## Configuration

Environment variables:

- `OPENROUTESERVICE_API_KEY` (optional): If set, the app uses OpenRouteService. If not set, it falls back to Nominatim + OSRM.
- `FLASK_SECRET_KEY` (optional): Secret key for sessions/flash messages. Defaults to a development key.
- `PORT` (optional): Port for the Flask server (default 5000).

## Project Structure

- `app.py` — Flask web app entry point and routes.
- `fare_service.py` — Core logic: geocoding, routing, and fare calculation.
- `templates/index.html` — UI template.
- `static/style.css` — Minimal custom styles.
- `script.py` — Original console script (left intact).

## Notes & Troubleshooting

- Coordinate order is `(lon, lat)` internally.
- Fare formula: `RM 3 base + RM 1 per km + RM 0.5 per minute` (see `calculate_fare()` in `fare_service.py`).
- Public services (Nominatim/OSRM) have rate limits. If you hit errors, wait a bit, try more specific addresses, or provide an ORS API key.
- Requires outbound internet access for geocoding and routing.
