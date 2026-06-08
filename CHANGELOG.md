# Changelog

All notable changes to Silver OPC UA Toolkit will be documented in this file.

This project follows semantic versioning principles where possible.

Pre-release versions may contain breaking changes during active alpha development.

---

## [v0.4.0-alpha] - 2026-06-04

### Added

#### Backend
- OPC UA Security foundation:
  - Security mode selection: `None` / `Sign` / `SignAndEncrypt`
  - Security policy selection: `Basic256Sha256`, `Aes128Sha256RsaOaep`, `Aes256Sha256RsaPss`
  - Authentication: `Anonymous` / `Username + Password`
  - File-based certificate handling (no PKI UI)
  - Application URI extracted from certificate for server handshake compliance
- Client certificate generation endpoint (`POST /api/v1/certificates/generate`):
  - RSA 2048-bit key
  - SHA-256 signature
  - Key Usage extension (Digital Signature, Key Encipherment)
  - Extended Key Usage (Client Authentication)
  - Subject Alternative Name with configurable Application URI
  - Subject Key Identifier
  - Certificates stored in `CERTS_DIR` (persistent Docker volume)
- Certificate info endpoint (`GET /api/v1/certificates/info`)
- Connection health check background task (10s interval):
  - Pings active connections via server state node read
  - Marks connection as inactive in DB when server drops
  - Human-readable `last_error` on disconnect
- `CERTS_DIR` environment variable for configurable certificate storage
- Human-readable OPC UA error messages
- OPC UA node ID parser fix: supports String-type identifiers (`ns=3;s=TagName`)
- Simulator security support:
  - Self-signed server certificate generation
  - Username/password authentication (`admin/admin123`, `operator/op456`)
  - Security policies: None / Basic256Sha256 Sign / Basic256Sha256 SignAndEncrypt

#### Frontend
- Security configuration UI in Add Connection dialog:
  - Security mode selector (None / Sign / SignAndEncrypt)
  - Security policy dropdown
  - Auth type selector (Anonymous / Username+Password)
  - Certificate and private key path inputs
  - "Generate Client Certificate" button (auto-fills paths after generation)
- Security badge on connection rows
- Human-readable connection error messages displayed inline

#### Infrastructure
- `backend/.dockerignore` added
- `CERTS_DIR` volume mount in `docker-compose.yml`

---

### Fixed
- OPC UA connection health not reflected in UI after server restart
- Tag Browser browse failure with String-type node IDs (Siemens S7 compatibility)
- Auto-reconnect on startup now passes full security credentials from DB
- Username/password credentials set before `connect()` (not after)
- Vite dev server proxy config missing — API calls returned 404 in development
- Docker containers downloading dev dependencies (`ruff`, `pytest`) at runtime due to stale `uv.lock`

---

### Changed
- `OPCUAManager.connect()` now returns `(success, error_message)` tuple
- Connection model extended with security fields
- `main.py` lifespan passes full security params during auto-reconnect

---

## [v0.3.0-alpha] - 2026-05-29

### Added

#### Frontend
- Persistent watchlist via `localStorage` (`silver_opcua_watchlist`)
- CSV export dialog with time-window slider and per-tag columns
- Alarm and threshold visualization (Warning / Critical, High / Low per tag)
- Threshold lines on trend chart
- System Status panel in sidebar with real-time indicators
- Auto-restart stream when watchlist changes during active monitoring
- UI Refinement Pass: sidebar navigation, industrial SaaS aesthetic

#### Simulator
- Realistic 5-mode industrial signal simulation: normal / alarm / step / frozen / recovering

### Fixed
- Watchlist tags removed correctly when parent connection is deleted
- WebSocket status accurately reflects live connection state

### Changed
- Navigation migrated from horizontal top bar to vertical sidebar
- System Status footer replaced static text with live runtime indicators

---

## [v0.2.0-alpha] - 2026-05-24

### Added

#### Backend
- Structured logging (text dev / JSON prod)
- Centralized configuration via `Settings` class
- Connection state machine with `last_connected_at`, `last_error`, `retry_count`
- OPC UA lifecycle cleanup via `_force_cleanup()`
- WebSocket ping/pong loop and handshake timeout
- `DB_PATH` environment variable
- Docker healthcheck for simulator

#### Frontend
- Watchlist-based monitoring workflow
- Recursive Tag Browser with search and details panel
- Boolean tag visualization (ON/OFF)
- Chart pause / resume
- Configurable monitoring windows and update intervals

#### Infrastructure
- Multi-stage Docker builds
- nginx reverse proxy
- Automatic dev/prod URL switching

### Fixed
- Memory leak during OPC UA connection failures
- Docker startup race condition

---

## [v0.1.0-alpha] - 2026-05-21

### Added
- OPC UA Connection Manager
- Recursive OPC UA Tag Browser
- Live monitoring via WebSockets
- Realtime multi-tag charting
- Industrial OPC UA simulator
- FastAPI backend + React frontend
- SQLite persistence

---

## Roadmap

### v0.3.0-alpha ✅ Released 2026-05-29
- Persistent watchlist, CSV export, Alarm visualization, UI Refinement

### v0.4.0-alpha ✅ Released 2026-06-04
- OPC UA security (None/Sign/SignAndEncrypt)
- Authentication (Anonymous/Username+Password)
- Client certificate generation
- Connection health monitoring
- Siemens S7 compatibility fixes

### v0.5.0-beta
- Multi-connection monitoring
- Endpoint discovery
- Production deployment documentation
- Performance validation

### v0.6.x
- Historical Data Logging
- Historical Trend Viewer
- OPC UA Write Support
- MQTT Integration
- Connection Profiles

### v0.7.x
- Alarm Management Workspace
- Event Handling
- Advanced Diagnostics
- Industrial Reporting

### v1.0
- Stable Monitoring Platform
- Production Deployment Ready
- Mature Security Workflow
- Plugin / Extension Foundation