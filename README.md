# Fare Calculator (Basic Command Line Version)
Simple app that uses the command line to interact with, uses OpenRouteService to estimate distance, estimated duration and fare. 

before running script.py, make sure you have python installed with "add python to path" enabled. Do "pip install openrouteservice" in your command prompt"


# Fare Calculator (Web UI Version)

A simple web app that estimates trip distance, duration, and fare.

Routing/Geocoding backends:
- Default (no API key): OpenStreetMap Nominatim for geocoding + OSRM demo server for routing
- Optional: OpenRouteService (ORS) if you provide `OPENROUTESERVICE_API_KEY`

## Features

- Enter start and dropoff addresses.
- Geocodes addresses and calculates a driving route (Nominatim+OSRM by default, ORS if key provided).
- Displays distance (km), duration (minutes), and estimated fare (RM).
- Core logic extracted to `fare_service.py` for reuse/testability.
 - Accepts messy/detailed address inputs (normalization cleans things like WhatsApp timestamps/labels, phone numbers, extra commas/spaces).

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

### Messy Address Handling

You can paste addresses copied from chats (e.g., WhatsApp) including timestamps, phone numbers, and labels like "From" / "To". The app normalizes these before geocoding.

Example input (multi-line WhatsApp export):

```
[14:04, 26/09/2025] +60167231646: Can you type a more specific address in it
[14:04, 26/09/2025] +60167231646: From
Lingkaran Silikon, 63000 Cyberjaya, Selangor
[14:05, 26/09/2025] +60167231646: To 
IOI City Tower Two, Lbh IRC, Ioi Resort, 62502 Putrajaya, Selangor
```

Normalized addresses used by the app:

```
Lingkaran Silikon, 63000 Cyberjaya, Selangor
IOI City Tower Two, Lbh IRC, Ioi Resort, 62502 Putrajaya, Selangor
```

Normalization is implemented in `fare_service.py` via `normalize_address()`:

- Strips WhatsApp-style timestamps/phone prefixes and From/To labels
- Collapses repeated commas and trims whitespace around parts
- Removes empty segments and collapses multiple spaces


