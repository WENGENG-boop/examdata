# Main branch integration

The original Python API and CLI are retained. The latest closure candidate's integration package, contracts, quality models, revision store, bounded operations readers, provider registry, API assembly and compatibility code are merged under `src/examdata/integration/`. Historical staging copies remain for provenance.

## Start from a VPS checkout

Requires Python >=3.11 and Node >=20.

```sh
git clone https://github.com/WENGENG-boop/examdata.git
cd examdata
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/examdata workspace --check
.venv/bin/examdata workspace --host 0.0.0.0 --port 8000
```

The launcher starts the Python API on loopback port 8001, the classic frontend on loopback port 8002 and Web on the selected public host/port. It refuses occupied ports and stops its own sibling processes on failure or shutdown. All modules use explicit paths inside this checkout.

- `/`: main Web interface
- `/classic/`: previous frontend
- `/api/v1/*`: existing CIE, Edexcel, IELTS, TOEFL, materials and timetable APIs
- `/docs`: Python API documentation
- `/health`: backend health

If `EXAMDATA_API_KEY` is set in the process environment, direct API requests require X-API-Key. Frontend gateway routes retain their existing limited read-only proxy behavior. Export environment variables or provide them through systemd; copying a .env file alone does not export Node/launcher settings.

## v2 state

The v2 implementation is merged as actual package code. Real production provider assembly is still required: set `EXAMDATA_INTEGRATION_ROOT` and `EXAMDATA_V2_FACTORY=module:function`, where that callable returns a `ProductionAssembly` assembled from real sources. The workspace launcher sets the integration root. Without a real assembly factory, `/api/v2/*` responds 503 with `production_sources_not_configured`; it never serves rehearsal content. This code merge does not establish real-data migration or real-source acceptance for v2.

Database, PDF/audio downloads, caches and credentials are not in Git. Export or transfer those separately before expecting local data on a VPS. Historical reports and rehearsal fixtures are not production data.
