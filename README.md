## SEO Marketing Tool Analytics Tracker

FastAPI application that connects to Google Search Console (GSC) via OAuth, lets users select a verified property, create clusters of links for that property, and fetches the last ~90 days of Search Analytics data per link (with optional device and multi-country filters). Data is stored in MongoDB and displayed via Jinja2 templates with a simple UI and flash messaging.

### Features

- **Google OAuth**: Sign in with Google and grant read-only access to Search Console.
- **Property sync**: List your GSC properties and mirror them into local `domain_properties`.
- **Clusters**: Create named clusters scoped to a selected site, with device and country filters.
- **Links**: Add/edit links under a cluster. Domain consistency is validated.
- **Performance aggregation**:
  - Fetches ~90 days (GSC trailing ~3 days) of daily rows per link.
  - Applies cluster device and country filters.
  - Aggregates CTR and position correctly (impression-weighted).
  - Stores per-link, per-date results in `link_performance` with an index on `(linkId, date, deleted)`.
- **Trash and restore**: Soft-delete clusters/links and restore or permanently delete later.
- **Sessions in MongoDB**: Custom session middleware backed by Mongo.
- **Global error handling**: JSON or HTML error pages depending on Accept header.

---

### Tech Stack

- **Backend**: FastAPI, Starlette, Uvicorn
- **Templating**: Jinja2
- **DB**: MongoDB (`pymongo`)
- **Google APIs**: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`
- **Runtime**: Python 3.12
- **Container**: Dockerfile included (Cloud Run–friendly)

---

### Project Structure

```text
.
├─ app.py                       # FastAPI app factory, middlewares, routers
├─ db_client.py                 # Mongo client init + index creation
├─ mongo_session.py             # Mongo-backed session middleware
├─ routes/
│  ├─ main.py                   # Landing page
│  ├─ auth.py                   # Google OAuth flow (authorize/callback/logout)
│  ├─ dashboard.py              # GSC properties sync + selection
│  ├─ clusters.py               # Clusters, Links, Performance, Trash logic
│  ├─ flash.py                  # Flash message helpers backed by session
│  ├─ utils.py                  # Helpers (e.g., credentials serialization)
│  └─ global_exception_handler.py
├─ templates/                   # Jinja2 templates (Dashboard, Performance, etc.)
├─ static/                      # CSS/JS assets
├─ requirements.txt             # Python dependencies
├─ Dockerfile                   # Production container
└─ client_secret.json           # Google OAuth client (see setup)
```

---

### Prerequisites

- Python 3.12+
- MongoDB (Atlas or local)
- A Google Cloud project with OAuth 2.0 Client ID (type: Web application)

---

### Environment Variables

Set via shell or `.env` (loaded by `python-dotenv`).

- `MONGODB_URI` (required): Mongo connection string, e.g. `mongodb://localhost:27017` or Atlas URI.
- `ENV` (optional): `development` or `production` (defaults to `development`). Controls OAuth insecure transport.
- `PORT` (optional): Only used when running `python app.py` locally (defaults `8000`).

Notes:

- In development `ENV=development`, `OAUTHLIB_INSECURE_TRANSPORT=1` is enabled to allow http redirect URIs.
- For production use HTTPS and set `ENV=production`.

---

### Google OAuth Setup

1. In the Google Cloud Console, create OAuth 2.0 credentials (Web application).
2. Add Authorized redirect URIs (include those you need):
   - Local dev (run `python app.py`): `http://localhost:8000/auth/oauth2callback`
   - Docker (container exposes 8080): `http://localhost:8080/auth/oauth2callback`
   - Your production domain: `https://YOUR_DOMAIN/auth/oauth2callback`
3. Download the JSON and save it at the repository root as `client_secret.json`.
4. Ensure your OAuth consent screen is Published and the Scopes include:
   - `https://www.googleapis.com/auth/webmasters.readonly`
   - `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/userinfo.profile`

`routes/auth.py` expects the file name `client_secret.json` in the project root.

---

### Local Development

```bash
# 1) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate  # PowerShell on Windows

# 2) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3) Set environment
setx MONGODB_URI "mongodb://localhost:27017"  # Windows PowerShell
# Optionally: setx ENV "development"

# 4) Run the app
python app.py
# App runs on http://localhost:8000 (docs at /docs)
```

Alternatively, use Uvicorn directly:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload --proxy-headers
```

---

### Run with Docker

```bash
# Build
docker build -t gsc-tracker .

# Run (maps container 8080 to host 8080)
docker run --rm -p 8080:8080 \
  -e MONGODB_URI="mongodb://host.docker.internal:27017" \
  -e ENV=production \
  -v %cd%/client_secret.json:/app/client_secret.json:ro \
  gsc-tracker

# App available at http://localhost:8080
```

Notes:

- The container entrypoint uses `uvicorn` on port `8080` with `--proxy-headers` for reverse proxy friendliness.
- Mount `client_secret.json` into the container or bake it into the image per your security policy.

---

### Data Model (MongoDB Collections)

- `users`: `{ email, name, createdAt, updatedAt }`
- `domain_properties`: `{ userId, siteUrl, permissionLevel, active, createdAt, updatedAt }`
- `clusters`: `{ userId, domain, clusterName, deviceFilter, countryFilter, deleted, deletedAt, createdAt, updatedAt }`
- `links`: `{ clusterId, url, status, deleted, deletedAt, createdAt, updatedAt }`
- `link_performance`: `{ linkId, date, clicks, impressions, ctr, position, createdAt, updatedAt, deleted }`
  - Index created automatically on `(linkId, date, deleted)` in `db_client.py`.
- `fastapi_sessions`: `{ _id, data, expiresAt }` (custom Mongo session store)

All soft deletes set `deleted=true` and `deletedAt` timestamps; restore operations flip these back.

---

### Core Flows

1) Authentication

- Visit `/auth/authorize` to start Google OAuth.
- Callback at `/auth/oauth2callback` stores tokens and user info in session and upserts the user in Mongo.

2) Select a Property

- Visit `/dashboard/properties` to sync GSC sites and mark removed ones inactive locally.
- Choose a site via POST `/dashboard/properties/select` which stores `selected_site` in session.

3) Clusters and Links

- List clusters: `GET /clusters` (requires `selected_site` and `user_id` in session)
- Create clusters: `POST /clusters/new-json` with body:

```json
{
  "clusters": [
    { "clusterName": "MyCluster", "deviceFilter": "MOBILE", "countryFilter": "usa,can" },
    { "clusterName": "AnotherCluster" }
  ]
}
```

- Add links: `POST /clusters/{cluster_id}/links/add-json` with body:

```json
{ "links": ["https://example.com/page-a", "https://example.com/page-b"] }
```

- Domain consistency is enforced against the cluster's `domain`.

4) Fetching Performance

- Link creation and manual refresh (`POST /clusters/{cluster_id}/links/{link_id}/refresh`) enqueue a background task to fetch ~90 days of Search Analytics rows for that link.
- Device/country filters from the cluster are applied to the GSC query.
- Results are aggregated by `date` and stored in `link_performance` (impression-weighted averages for position).

5) Viewing Performance

- Link-level: `GET /links/{link_id}/performance?start=YYYY-MM-DD&end=YYYY-MM-DD`
- Cluster-level: `GET /clusters/{cluster_id}/performance?start=YYYY-MM-DD&end=YYYY-MM-DD`

6) Trash/Restore

- Move to trash: `POST /clusters/{cluster_id}/trash`, `POST /links/{link_id}/trash`
- Restore: `POST /clusters/{cluster_id}/restore`, `POST /links/{link_id}/restore`
- Permanent delete: `POST /clusters/{cluster_id}/delete-permanently`, `POST /links/{link_id}/delete-permanently`
- View trash for a domain: `GET /trash/{domain}`

---

### Templates and Static Assets

- Templates live under `templates/` with subfolders for Dashboard/Clusters/Links/Performance/Trash.
- Static assets under `static/` are mounted at `/static`.
- Flash messages pulled from the session are injected into contexts via a helper in `app.py`.

---

### Sessions and Flash Messages

- Custom middleware (`MongoSessionMiddleware`) stores a `session_id` cookie and a session doc in Mongo.
- Request handlers access `request.state.session`.
- Flash messages are appended to session under `flash_messages` and then consumed per request.

---

### Deployment Notes

- Set `ENV=production` and use HTTPS. Consider setting the session cookie `secure=True` in `mongo_session.py` when serving over TLS.
- If deployed behind a reverse proxy or on Cloud Run, `proxy_headers=True` and a custom middleware honor `X-Forwarded-Proto` to build correct callback URLs.
- Configure your production OAuth redirect URI accordingly.

---

### Troubleshooting

- Missing `MONGODB_URI`: The app will fail fast. Provide a valid connection string.
- OAuth redirect URI mismatch: Update Authorized redirect URIs in Google Cloud Console to match your environment.
- No properties shown: Ensure your Google account has verified properties in Search Console.
- Empty performance: Ensure the link URLs belong to the selected property and have impressions in the selected window.
- Atlas IP allowlist: If using MongoDB Atlas, add your server/runner IP.

---

### API Docs

- Interactive docs: `/docs`
- ReDoc: `/redoc`

---

### License

This project does not include a license. Add one if you plan to distribute.
