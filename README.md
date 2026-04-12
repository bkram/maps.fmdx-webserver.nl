# FMDX Statistics Web App

Flask application for the public FMDX map and statistics pages.

It serves:

- `/` for the interactive receiver map
- `/statistics` for aggregated receiver statistics
- `/healthz` for lightweight container/process health checks
- `/api/servers` for the receiver dataset plus blacklist metadata
- `/api/stats` for computed statistics JSON

The app fetches receiver data from a remote API and enriches receiver
coordinates with cached reverse-geocoded location data.

## Repository Layout

```text
.
├── fmdx_statistics/
│   ├── app.py
│   ├── cache.py
│   ├── countries.py
│   ├── detectors.py
│   ├── geocoding.py
│   ├── population.py
│   ├── receiver_blacklist.py
│   ├── receivers.py
│   ├── stats.py
│   └── tuners.py
├── data/
│   └── receiver_blacklist.yaml
├── static/
│   ├── css/style.css
│   ├── js/map.js
│   ├── favicon.png
│   └── logo-fmdx.svg
├── templates/
│   ├── _header.html
│   ├── index.html
│   └── statistics.html
├── Dockerfile
└── requirements.txt
```

## Requirements

- Python 3.14 or newer
- `pip`

Redis is optional. If `REDIS_URL` is not available or Redis cannot be reached,
the app falls back to an in-memory cache.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the development server:

```bash
FLASK_DEBUG=1 python -m fmdx_statistics.app
```

The app listens on `http://127.0.0.1:8080` by default.

## Configuration

Run against the remote API:

```bash
REMOTE_API_URL=https://servers.fmdx.org/api/ python -m fmdx_statistics.app
```

Environment variables:

- `REMOTE_API_URL`: remote dataset endpoint
- `CACHE_TTL`: API/cache TTL in seconds, default `60`
- `PORT`: HTTP port, default `8080`
- `REDIS_URL`: Redis connection URL, default `redis://redis:6379/0`

## Reverse Geocoding Data

The app uses a cached city dataset for reverse geocoding. By default it reads
`data/rg_cities1000.csv`.

If the file is missing, the app downloads the GeoNames `cities1000.zip`
dataset and supporting admin-code tables, converts them to
`data/rg_cities1000.csv`, and reuses that file on later starts.

That CSV is generated runtime cache data and should not be committed to git.
The dataset is loaded lazily, so the app can start before the cache exists.

If the upstream receiver feed is unavailable and there is no cached dataset,
the JSON API returns HTTP `503`. The HTML pages still render and show a warning
banner so the UI remains reachable during upstream outages.

Optional environment variables:

- `RG_CITIES_DATA_PATH`: override the local CSV path
- `RG_CITIES_DATA_URL`: override the source dataset URL
- `RG_ADMIN1_CODES_URL`: override the admin1 source URL
- `RG_ADMIN2_CODES_URL`: override the admin2 source URL

## Docker

Build the image:

```bash
docker build -t fmdx-statistics .
```

Run it:

```bash
docker run --rm -p 8000:8000 \
  -e REMOTE_API_URL=https://servers.fmdx.org/api/ \
  fmdx-statistics
```

The container runs Gunicorn and exposes port `8000`.
It stores the generated geocoder CSV under `/tmp/rg_cities1000.csv` so the
non-root runtime user can write the cache.
Its health check uses `/healthz` instead of the main HTML pages.

### Docker Compose

For local testing with Redis:

```bash
docker compose up --build
```

The app is published on `http://127.0.0.1:8080` by default.

Optional overrides:

- `FMDX_WEB_MAP_PORT`: host port for the web app, default `8080`
- `REMOTE_API_URL`: remote dataset endpoint
- `CACHE_TTL`: cache TTL in seconds, default `60`

## Data Files

- `data/receiver_blacklist.yaml`: receiver blacklist metadata exposed by
  `/api/servers`
- `data/rg_cities1000.csv`: generated reverse-geocoder cache file created on
  demand and ignored by git
