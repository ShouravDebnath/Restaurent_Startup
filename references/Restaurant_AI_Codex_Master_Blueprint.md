# RESTAURANT AI MONITORING

**Master Product Specification + Codex Build Playbook**  
**Version:** 1.0 | **Date:** 05 November 2026  
**Launch direction:** International SaaS, starting with US restaurant pilots  
**Founder location:** Bangladesh | **Development method:** OpenAI Codex with founder review

> **Purpose of this document:** Explain the complete startup idea in clear English so a coding agent can understand exactly what to build, in what order, and how to decide whether each step is finished. This is a product specification and execution plan, not a claim that the software already exists.

---

# Part A - The product we are building

## 1. Founder intent and product summary

### 1.1 The idea in one paragraph

Build a **multi-restaurant, AI-powered restaurant operations SaaS** that connects to a restaurant's existing CCTV/IP cameras, understands the occupancy of dining tables, shows each table on a real-time dashboard, starts simple timers, and tells staff when a table may require attention. Restaurant managers can see which tables are occupied, ready, or waiting for cleaning confirmation, and later review operational analytics such as occupancy patterns and table-turnaround delays. The software must eventually support many independent restaurants from one centrally managed product. Video should be processed locally whenever practical; the cloud should normally receive table events and analytics rather than continuous customer video.

### 1.2 Why the founder wants it

- Build a real international startup, not just an attractive AI demonstration.
- Begin selling to US restaurants while the founder develops and operates the company from Bangladesh.
- Use one reusable software platform for multiple restaurant customers, with separate private accounts and data.
- Build the product largely with Codex; use human review, authorized test videos, restaurant feedback, and security checks before real deployment.
- Market the idea through personalized business emails and a short demonstration video, clearly labeled as a concept if any scene is simulated.

### 1.3 Primary business promise

**"Know which dining tables are available and which may need attention using your existing cameras - without asking staff to watch CCTV all day."**

Do not claim that computer vision alone can confirm a table has been cleaned, a meal was served, or a waiter ignored a guest. Those events need staff confirmation, POS events, or other trusted inputs.

### 1.4 Product principles (non-negotiable)

1. **Useful before impressive:** prioritize reliable table states and actionable staff tasks over flashy boxes drawn on video.
2. **Camera-agnostic where possible:** support a documented set of RTSP-capable IP cameras/NVRs, and record compatibility limitations.
3. **Privacy by design:** local inference first, avoid facial recognition and audio recording, and minimize customer video storage.
4. **Separate restaurant data:** one shared codebase, strong tenant isolation, distinct locations, users, cameras, tables, and billing.
5. **Truthful alerts:** uncertain visual detections display UNKNOWN/REVIEW rather than pretending the table is ready.
6. **Human override:** staff can confirm cleaning, set tables out of service, acknowledge alerts, and correct AI states.
7. **Offline tolerant:** loss of internet must not stop local detection; upload queued events after reconnection.
8. **Codex builds in small verified stages:** each stage must run and pass tests before starting the next.

## 2. What the Reel shows vs. what the real product must deliver

The uploaded reference Reel illustrates highlighted restaurant tables, available/occupied states, customer or table timers, a dashboard, alerts about customers and dirty tables, and peak-time analytics. Some visuals are clearly demonstrations or animations. This document describes the *target experience*; it does not assume the Reel proves real-world detection accuracy.

| Reel-inspired experience | Engineering interpretation | Delivery |
|:--|:--|:--|
| Green table / red table | Reliable available/occupied indicator from visible people plus staff confirmation | MVP |
| Time counter above table | Duration in current stable state, not automatically the time since ordering | MVP |
| Alert that table needs cleaning | Occupied -> vacated -> reset pending; staff confirms when ready | MVP |
| Live control-panel map | Floor map with table ID, color, status, timers, camera health | MVP |
| Live occupancy summary | Occupied/available/reset-pending/unknown counts and simple activity charts | MVP |
| Customer count at a table | Estimate from visible person detections; show confidence and allow correction | Pilot if reliable |
| "No forgotten customer" | Alert based on seated duration; not proof of missing service | Phase 2 |
| Peak-hour charts | Aggregate events by local day/hour and location time zone | MVP basic / Phase 2 advanced |
| Next free table prediction | Statistical estimate after enough real labeled history | Phase 3 |
| Automatic proof table is clean | Not reliable from ordinary CCTV alone | **Never claim automatically** |

### 2.1 Exact customer journey (example)

At 7:10 PM, a restaurant has 12 monitored tables. The edge AI sees two guests sitting at Table 4 and waits for several stable detections. It sets Table 4 to OCCUPIED and starts an occupancy timer. At 8:05 PM, both guests leave. After a configurable empty grace period, the system marks Table 4 as RESET_PENDING and sends one actionable notification: "Table 4 may need cleaning." A staff member taps "Start cleaning" and later "Mark ready." The status becomes AVAILABLE. The next day, the manager sees occupancy duration and average reset delay in the dashboard. If the camera fails, the table is UNKNOWN, not automatically AVAILABLE.

## 3. Who uses the system

| Role | Main goal | Actions |
|:--|:--|:--|
| Company platform admin | Keep the SaaS healthy | Manage plans, support requests, system monitoring; no default access to restaurant video |
| Restaurant owner / organization admin | Manage one or more restaurant locations | Invite staff, set permissions, view analytics, configure billing |
| Location manager | Operate a dining room | Configure table labels, view alerts, review activity and camera status |
| Floor staff | Reset tables quickly | See statuses, acknowledge tasks, mark cleaning started/done |
| Edge installer | Set up local cameras and device | Pair device, test stream, draw table regions, see health checks |

A restaurant **organization** can own multiple **locations**. A restaurant location can have multiple cameras. A table belongs to exactly one location. Each human user belongs to a permitted organization and role; access to a location is explicit.

## 4. Product scope: build now, later, and never

### 4.1 MVP: must build

| ID | Requirement | Acceptance test |
|:--|:--|:--|
| F01 | Ingest MP4 demo video, webcam, and authorized RTSP stream on a local device | Demo file plays; compatible RTSP stream reconnects after interruption |
| F02 | Register a restaurant, location, camera, and tables | Two organizations never see each other's records |
| F03 | Draw and save a table region for a fixed camera view | Editable polygon persists after restart |
| F04 | Detect visible people and map them to table regions | Detection output includes timestamp, zone and confidence |
| F05 | Track stable table states | Prevent quick state flicker; UNKNOWN if camera is offline |
| F06 | Table floor map with colors, labels, and timers | Changes show live without page refresh under normal connection |
| F07 | Generate reset-pending task after a table becomes vacant | Exactly one active task per departure; manual acknowledgement works |
| F08 | Staff status controls | Staff can mark start cleaning, ready, or out of service |
| F09 | Analytics: occupancy, turnover and reset delay | Values derived from saved state events, with time zone handled |
| F10 | Edge-to-cloud event synchronization | Events survive temporary internet outage without duplicates |
| F11 | Authentication, roles, audit log, secure configuration | Unauthorized tenants cannot access each other's data |
| F12 | Demo mode and sample dataset | The entire system works with fake/synthetic examples without real CCTV |

### 4.2 Later versions: do not block MVP

- **Phase 2:** entrance/queue waiting time, POS/reservation integration, push notifications, multi-camera duplicate handling, broader device compatibility, mobile-friendly staff app/PWA.
- **Phase 3:** next-available-table prediction with calibrated uncertainty, multi-location benchmarking, integration marketplace, advanced usage billing and enterprise controls.
- **Future research:** staff workflow optimizations, demand forecasting and camera quality diagnostics, only if privacy and accuracy requirements can be met.

### 4.3 Explicitly out of scope

Facial identification, recognizing individual customers, audio monitoring, emotion detection, covert staff surveillance, exact service-time claims without POS/manual data, video scraping from unapproved cameras, guaranteed table-cleanliness recognition, or fully automated real-world deployment without an authorized installer.

# Part B - Technical system specification

## 5. The architecture Codex should implement

Use an **edge + cloud** architecture. The cloud is a shared SaaS; the edge device runs in or near each restaurant.

```text
   RESTAURANT LOCATION (US)                   CENTRAL SaaS CLOUD
  +-------------------------+           +----------------------------+
  | Existing IP CCTV / NVR  |           | REST API + Authentication  |
  | RTSP video on local LAN |           | Tenant + location scoping  |
  +------------+------------+           +--------------+-------------+
               |                                       ^
               v                                       | TLS outbound
  +-------------------------+                          | event batches
  | Local Edge AI Agent     +--------------------------+
  | 1. VideoSource          |                          |
  | 2. PersonDetector       |           +--------------v-------------+
  | 3. TableZoneMapper      |           | PostgreSQL                 |
  | 4. TableStateEngine     |           | Events, tables, alerts,    |
  | 5. SQLite event queue   |           | users, permissions         |
  | 6. Outbound secure sync |           +--------------+-------------+
  +-------------------------+                          |
                                                       v
                                        +----------------------------+
                                        | Manager / Staff Dashboard  |
                                        | Floor map, alerts, reports |
                                        +----------------------------+
```

**Why:** Always streaming every US camera to Bangladesh is expensive, fragile, difficult to scale, and creates avoidable privacy risk. Ideally the edge device analyzes frames at the restaurant and uploads only minimal events. Only explicitly authorized diagnostic clips may be uploaded, under a separate access and retention policy.

### 5.1 Local Edge AI Agent responsibilities

- Connect to one authorized video source at a time in the initial implementation.
- Read and decode frames without exposing camera passwords to the frontend.
- Run a properly licensed detector for people; start with a replaceable `Detector` interface.
- Evaluate person locations against table polygons in the camera view.
- Maintain stable per-table state and timers using monotonic clocks locally.
- Save events to a durable local SQLite outbox before network delivery.
- Retry failed deliveries using idempotency keys and backoff.
- Send device health and last-frame timestamps to cloud; never upload video by default.
- Support authorized manual calibration and securely rotate credentials.

### 5.2 Cloud responsibilities

- Authenticate users and devices; authorize every location-scoped request.
- Manage organizations, locations, tables, cameras (metadata), and edge devices.
- Accept authenticated, validated, idempotent events from edge devices.
- Store table history and alert/task state; update materialized/latest table status.
- Provide real-time dashboard updates using Server-Sent Events (SSE) or WebSockets.
- Produce reports and exported CSV; manage users, activity logs and health.
- Manage subscriptions later, only after real pilot value is demonstrated.

### 5.3 Development architecture rule

Start with a **modular monolith**: one FastAPI backend and one Next.js frontend, plus a separate edge agent process. Avoid microservices, Kubernetes, complex message brokers and distributed training in the MVP. Separate modules so they can be scaled later.

## 6. Recommended stack

| Layer | Choice | Rationale |
|:--|:--|:--|
| Web frontend | Next.js + TypeScript | Responsive dashboard, mature ecosystem |
| UI styling | Tailwind CSS + accessible components | Fast consistent interface |
| Backend/API | Python FastAPI | Clear schemas, async endpoints, OpenAPI |
| Database | PostgreSQL + SQLAlchemy + Alembic | Relationships, reliable migrations, SQL tools |
| Edge AI | Python + OpenCV/FFmpeg + replaceable detector | Works with MP4 and RTSP, straightforward testing |
| Model inference | ONNX Runtime initially | Portable inference without hard-coding one model provider |
| Local event store | SQLite | Simple offline durable outbox |
| Live events | SSE initially | Simpler one-way server-to-dashboard updates |
| Deployment | Docker Compose initially | Repeatable local dev and first pilots |
| Observability | Structured logs + metrics + error tracking | Debugging, health and response times |
| Testing | pytest, Ruff, type checks, Playwright smoke tests | Verify each stage before proceeding |

**Model licensing gate:** Ultralytics YOLO is often useful for prototypes but its AGPL/Enterprise licensing must be reviewed for a proprietary commercial SaaS. Codex must not select a detector/weights for production without recording the exact license and obligations. Other detector models and model weights also need separate license checks.

## 7. Table states and business rules

### 7.1 Canonical table states

| State | Meaning | How it is entered |
|:--|:--|:--|
| `UNKNOWN` | Camera is offline, occluded, or model is not confident | Automatic safety fallback |
| `AVAILABLE` | Table is visually unoccupied **and confirmed ready** | Staff confirmation or verified initial setup |
| `OCCUPIED` | Stable visual evidence someone is seated | AI after minimum observation time |
| `RESET_PENDING` | Previously occupied; now vacant; cleaning needs confirmation | AI after departure grace period |
| `CLEANING` | Staff is cleaning or preparing the table | Manual staff action |
| `OUT_OF_SERVICE` | Table cannot be assigned | Manual manager action |

**Critical:** "Nobody detected" does **not** necessarily mean "clean" or "available." The app must not silently change `RESET_PENDING` to `AVAILABLE` without a permitted confirmation path.

### 7.2 Rules with configurable values

1. A fixed camera maps to one or more human-drawn table polygons. For initial pilots, one table should have one primary camera to avoid duplicate counts.
2. Person association should use a documented anchor point (e.g., lower center of bounding box), polygon overlap, and exclusion zones. Validate on the restaurant's real camera angle.
3. Set `OCCUPIED` only after positive detections persist for a period (example starting configuration: 10 seconds).
4. Mark `RESET_PENDING` only after a previously occupied table has reliably been empty for a grace period (example: 25 seconds).
5. If the last reliable frame is older than a health threshold (example: 10 seconds), mark `UNKNOWN` and stop implying availability.
6. Prevent flicker by using hysteresis, minimum durations, and stable evidence; manual overrides have priority where applicable.
7. Track occupancy timer from a recorded state-entry timestamp. All cloud event timestamps are UTC; display using restaurant IANA time zone.
8. Create only one open reset task for a table for each occupancy session. Do not spam staff on every frame.
9. An alert may say "Table 4 may need cleaning" rather than "Table 4 is dirty."
10. A long seated-duration alert must never be labeled "customer not served" until a POS or manual service event exists.

### 7.3 Event transition examples

```text
UNKNOWN --(initial calibration + staff ready confirmation)--> AVAILABLE
AVAILABLE --(stable person evidence)-----------------------> OCCUPIED
OCCUPIED --(stable vacancy after guests leave)------------> RESET_PENDING
RESET_PENDING --(staff taps Start cleaning)----------------> CLEANING
CLEANING --(staff taps Mark ready + no occupant)-----------> AVAILABLE
ANY --(camera stale / confidence lost)---------------------> UNKNOWN
ANY --(manager closes table)------------------------------> OUT_OF_SERVICE
```

When AI evidence conflicts with a manual state, preserve an audit record and apply a documented rule; do not silently change `OUT_OF_SERVICE` or `CLEANING` to `AVAILABLE`.

## 8. The visual AI pipeline

```text
Authorized camera / test MP4
  -> Decode frames and timestamps
  -> Sample frames at configurable rate (start 1-3 FPS)
  -> Person detection with confidence threshold
  -> Associate people with manually calibrated table zones
  -> Combine evidence across consecutive frames
  -> Per-table state machine and event creation
  -> Local SQLite outbox and secure cloud sync
  -> API, real-time floor map, task alerts and reports
```

**Do not start by training a model from scratch.** First establish a reproducible end-to-end demo using a pretrained, license-reviewed detector and manually mapped table regions. A model that detects people generally does not know which table they belong to; that association must be tested separately. Add tracking only when it measurably reduces duplicate counts or unstable state changes.

### 8.1 Handling difficult video

- Low light, reflections, occlusion, staff crossing, people standing nearby and tight tables must have explicit test clips.
- If a dining table is not visible in a camera frame, do not attempt to infer its status.
- Video interruptions must never clear a table to AVAILABLE.
- Fast staff movement should not register as a new dining party without persistence rules.
- If edge CPU/GPU falls behind, drop old frames instead of processing a growing backlog and reporting stale occupancy.
- Keep raw people detections transient where possible; persist state transitions and quality metrics rather than identities.

## 9. Minimum data model (first database migrations)

Use `organization_id` to isolate tenants and `location_id` to isolate restaurant locations. The schema should include at least these entities:

| Entity | Important fields |
|:--|:--|
| `organizations` | id, name, plan, created_at |
| `locations` | id, organization_id, name, time_zone, address_optional |
| `memberships` | id, user_id, organization_id, role, enabled |
| `users` | id, email, display_name, identity_provider_id |
| `edge_devices` | id, location_id, public_key/fingerprint, status, last_seen_at |
| `cameras` | id, location_id, edge_device_id, label, safe_source_reference, status |
| `tables` | id, location_id, label, seats_optional, current_state, state_since |
| `table_zones` | id, table_id, camera_id, polygon_normalized, revision |
| `table_events` | id, organization_id, location_id, table_id, event_type, occurred_at, ingested_at, source, confidence, idempotency_key |
| `staff_tasks` | id, location_id, table_id, type, status, created_at, acknowledged_at, completed_at |
| `audit_logs` | id, actor_type, actor_id, organization_id, action, occurred_at, details |

Store **normalized polygon points** (0..1) so calibration survives resolution changes, while also storing source resolution and calibration version. Passwords and camera RTSP credentials must be encrypted in a secure local store, not logged or sent to browsers. For important tenant-scoped tables, include `organization_id` directly or enforce it via joins and permissions; test for cross-tenant leakage.

### 9.1 Example signed edge event (shape, not actual credentials)

```json
{
  "event_id": "evt_01JEXAMPLE",
  "organization_id": "org_demo_a",
  "location_id": "loc_demo_1",
  "edge_device_id": "edge_demo_1",
  "camera_id": "cam_01",
  "table_id": "table_04",
  "event_type": "table.state_changed",
  "previous_state": "OCCUPIED",
  "new_state": "RESET_PENDING",
  "occurred_at": "2026-11-05T14:10:30Z",
  "confidence": 0.92,
  "evidence": "stable_vacancy_after_occupied",
  "schema_version": 1
}
```

Cloud must validate that the authenticated device is actually paired with the claimed location. Never trust an `organization_id` supplied by the event without server-side device mapping. Enforce event uniqueness using `event_id`; reject unknown types/schema versions with useful errors. Duplicate delivery must be safe.

## 10. API contract (initial routes)

| Method | Route | Role / purpose |
|:--|:--|:--|
| `POST` | `/v1/auth/session` or managed identity callback | Establish authenticated user session |
| `GET` | `/v1/me` | User + permitted organizations/locations |
| `GET` | `/v1/locations/{id}/tables` | Authorized staff: list current table states |
| `POST` | `/v1/locations/{id}/tables` | Manager: register a table |
| `PUT` | `/v1/locations/{id}/table-zones/{id}` | Installer/manager: save normalized polygon |
| `POST` | `/v1/tables/{id}/actions` | Staff: acknowledge, start clean, mark ready, block |
| `GET` | `/v1/locations/{id}/tasks` | Staff: list tasks and current statuses |
| `GET` | `/v1/locations/{id}/analytics` | Manager: aggregated history |
| `GET` | `/v1/locations/{id}/stream` | Authenticated SSE event stream |
| `POST` | `/v1/edge/events` | Device credential: authenticated event batches |
| `POST` | `/v1/edge/heartbeat` | Device credential: current health |

All request/response bodies must have typed schemas. Put example requests in generated OpenAPI. Add pagination for history routes. Enforce backend authorization for every endpoint - never rely only on frontend hidden buttons.

## 11. Web dashboard - exact pages Codex should design

### 11.1 Sign-in and restaurant switcher

- Secure sign-in; display only organizations/locations this user can access.
- Organization admin can choose location; an ordinary staff member sees only allowed locations.
- Demo mode must use isolated, non-customer data.

### 11.2 Live floor view (home page)

- Header: location name, local time, edge online/offline indicator, last update time.
- KPI strip: total, available, occupied, reset pending, unknown/out-of-service.
- Main canvas: table shapes placed on a 2D floor plan, with readable labels and status colors.
- Table card: table ID, state, time in current state, optional estimated people, last update, confidence/uncertainty message.
- Sidebar: active staff tasks sorted by age; acknowledge, start cleaning, mark ready controls.
- Status legend must use text labels and icons in addition to colors.
- Show clear stale/offline banner and avoid presenting old observations as live.

### 11.3 Camera + table setup

- Add/edit camera name and choose an authorized local video source on the edge agent.
- Show preview only to authenticated installer after explicit restaurant permission.
- Draw/edit polygon zones, bind zone to table ID, save revision history.
- Test table coverage and display a simple calibration confidence diagnostic.

### 11.4 Analytics

- Occupancy by hour/day; average occupied duration; reset pending duration; count of completed resets.
- Date filter using the location's time zone, download CSV, simple chart explanations.
- Always label estimated metrics and missing-camera periods.

### 11.5 Administration

- Organization profile; locations; invite/disable users; assign roles; device health.
- Plan/billing UI comes later, after pilot validation.
- Activity/audit log and data retention settings.

## 12. Security, privacy and operational requirements

1. **Authorized inputs only:** Camera streams require permission from the restaurant operator. Do not ask for public RTSP exposure or unrestricted NVR admin credentials.
2. **Outbound connectivity:** Edge agent should initiate outbound authenticated TLS connections to cloud; no open inbound CCTV ports on the public internet.
3. **Strong auth:** Use a mature identity provider or secure session management; enforce MFA for admins where supported. Device credentials must be separate from human credentials.
4. **Data isolation:** Tenant filtering on every query, with authorization tests and preferably database-level row security or similarly strong isolation controls.
5. **Video minimization:** Default = process locally, do not upload or store raw video in cloud. Optional diagnostics require explicit permission, encryption, narrow access and retention limits.
6. **No biometrics:** No face recognition, identity matching, employee performance scoring, audio recording or emotion analysis.
7. **Least privilege:** Support installer, staff, manager and admin role restrictions; keep secrets out of Git, logs and browser storage.
8. **Auditability:** Every manual table override and sensitive configuration change is logged.
9. **Safe retention:** Define retention periods for events, logs and optional clips in customer agreements; support export/deletion and backups.
10. **Incidents:** Provide device revocation, password rotation, a security contact, and a tested incident response procedure.
11. **Law review:** US CCTV, employment and privacy obligations vary by state and context; review contracts, customer/employee notices, cross-border access and any applicable privacy laws with qualified counsel before pilots.
12. **Bias/accuracy:** Test different lighting conditions, clothing, ages, mobility aids and dining configurations; document detection limitations.

## 13. Reliability and measurable quality gates

These are **pilot targets**, not results already achieved.

| Metric | Initial acceptance target / method |
|:--|:--|
| Table state accuracy | Aim >= 90% on a diverse, independently labeled pilot test set; report per-state precision/recall and UNKNOWN coverage |
| Update delay | Aim < 5 seconds from edge event receipt to visible dashboard under normal network conditions |
| False reset alerts | Aim <= 1 false reset alert per table per full shift; measure and adjust after pilot |
| Offline delivery | Queue remains intact across process restart; replay has no duplicate cloud effects |
| Tenant isolation | 100% of negative cross-tenant security tests blocked |
| Camera failure | Device disconnect or stale frames show UNKNOWN, never AVAILABLE |
| Availability | Record uptime and camera coverage; no unsupported uptime guarantee in MVP |
| Privacy | No raw video leaves edge by default; verify with network and logging tests |

Minimum evaluation set: at least two camera placements, daylight and evening, busy/empty periods, occlusion, staff crossing, an interrupted stream, and a low-confidence/UNKNOWN case. Use manually annotated ground-truth intervals and save metrics as reproducible artifacts. Do not report accuracy measured only on training or development clips.

## 14. Repository layout and team conventions

```text
restaurant-ai/
  README.md
  AGENTS.md                     # Codex operating instructions
  .env.example                  # Placeholder values only
  docker-compose.yml
  docs/
    MASTER_SPEC.md
    architecture.md
    api_contract.md
    threat_model.md
    deployment_runbook.md
    decisions/                    # Short architecture decision records
  apps/
    web/                          # Next.js dashboard
  services/
    api/                          # FastAPI cloud backend
    edge-agent/                   # Frame processing + local queue
  packages/
    contracts/                    # Versioned event/OpenAPI schemas
  tests/
    fixtures/                     # Synthetic/authorized sample assets
    integration/
    e2e/
  infra/
    docker/
    scripts/
```

**Engineering conventions:** typed code, lint/format hooks, environment variables for secrets, dependency lock files, database migrations, predictable local setup, unit tests for business logic, and a short technical decision record when the stack changes. Use Git commits/branches by milestone. Never invent test output or say a feature works without running its tests or explicitly marking it unverified.

# Part C - Codex execution playbook

## 15. Important rules for using Codex

1. Put this document in the repository as `docs/MASTER_SPEC.md` (a Markdown version is supplied with the PDF). The Markdown copy is easier for coding agents to search and quote.
2. Copy the master instruction in Section 16 into the initial Codex conversation.
3. Give Codex **one milestone at a time**, using the numbered prompts in Section 17. Do not ask it to implement the entire platform in one turn.
4. Before each milestone: require a short plan, files to be changed, dependencies, known risks and acceptance tests.
5. After each milestone: Codex runs automated tests and gives a report: what changed, commands run, actual results, remaining issues, manual verification steps.
6. You inspect a running demo and keep the working code before unlocking the next milestone.
7. Codex must never connect to real restaurant cameras without written authorization or pretend a simulated dashboard is live.
8. When Codex cannot test hardware/cloud services locally, it must clearly label them **NOT VERIFIED** and provide exact manual steps.

## 16. MASTER PROMPT - paste this to Codex first

> You are the principal software engineer for a startup called **Restaurant AI Monitoring** (working title). Read `docs/MASTER_SPEC.md` completely before writing code. Build one international multi-tenant SaaS product that uses authorized local restaurant CCTV video to estimate table occupancy, show a live floor map and timers, create reset-pending staff alerts, and produce analytics. The founder operates from Bangladesh; first customers will be US restaurants. The system must be privacy-first: video processing should run on a local edge agent, and the cloud should receive minimal validated events by default. Do not implement facial recognition, audio recording, unapproved camera access, or automatic claims that a table is clean. Use a modular monolith with FastAPI/PostgreSQL, Next.js/TypeScript, and a separate Python edge agent with a replaceable detector. Keep camera and model licensing decisions explicit. For every stage: (1) summarize the requirements, (2) propose the smallest implementation plan, (3) implement only the requested stage, (4) run relevant tests and show real results, (5) document setup and unresolved issues. Do not generate production secrets, skip authorization checks, or claim deployment success without verification. **Start by preparing the repository plan and Phase 0 only. Do not implement all phases now.**

## 17. Codex milestones and prompts

### Phase 0 - Freeze the specification and create an implementation plan

**Goal:** Codex understands the product before creating code.

**Paste:**

> Read `docs/MASTER_SPEC.md`. Create `docs/architecture.md`, `docs/api_contract.md`, `docs/threat_model.md`, and `docs/implementation_plan.md`. State every assumption, list MVP versus later features, define key table states, tenant boundaries, UI pages, versioned event contract, and test strategy. Identify license decisions still requiring human review. Do not build application features yet. Return a checklist for founder approval.

**Done when:** Requirements are traceable to milestones and unresolved decisions are visible; no software features were implemented prematurely.

### Phase 1 - Repository foundation + one-command local startup

**Paste:**

> Implement the approved monorepo structure. Scaffold Next.js/TypeScript web app, FastAPI API, PostgreSQL with Alembic migrations, and the Python edge-agent package. Add Docker Compose, `.env.example`, README startup steps, health endpoints, lint/type/test commands and CI workflow. Use synthetic credentials only. Create a local demo tenant. Do not include real CCTV or model inference yet.

**Done when:** A new developer can clone, copy environment template, launch locally, open a health page, and run passing starter tests.

### Phase 2 - Multi-tenant backend + authentication

**Paste:**

> Implement organizations, locations, users, memberships, roles, cameras (metadata), tables and table-zone schemas with migrations. Add authenticated API routes, tenant and location authorization, audit records and seed demo data. Build automated tests proving one restaurant cannot read or modify another restaurant's resources, including guessed IDs and altered request bodies. Do not add billing yet.

**Done when:** Two seeded restaurant tenants are fully isolated by tested backend enforcement, not merely UI filtering.

### Phase 3 - First working dashboard with simulation

**Paste:**

> Build the responsive live floor-view dashboard and supporting pages using API-backed demo events. Show table cards and colored floor layout for AVAILABLE, OCCUPIED, RESET_PENDING, CLEANING, UNKNOWN and OUT_OF_SERVICE. Add table timers, staff task list, clear offline indicators, and actions for Start cleaning, Mark ready, and Out of service. Use SSE or a justified equivalent for updates. Include accessible labels and mobile layout. No real AI yet: mark all data as DEMO.

**Done when:** Two demo restaurants show different tables and events; staff actions and timers work end-to-end; video is not required to demonstrate the UI.

### Phase 4 - Local video input and camera calibration

**Paste:**

> Build a local edge-agent interface for MP4 files, webcam and authorized RTSP streams. Implement reconnect behavior, frame timestamps, configurable FPS, stale-frame detection, and a secure local test preview. Add a calibration tool to draw/save normalized table polygons and associate them with one camera/table. Use an abstract VideoSource class; never expose camera passwords in web responses. Include tests using authorized or synthetic video.

**Done when:** An MP4 file can be played through the edge pipeline, table polygons persist, and disconnects are visible as health failures.

### Phase 5 - AI detector + table occupancy state engine

**Paste:**

> Add a pluggable person detector using a model whose software and weight licenses are documented. Map detections to calibrated table polygons, with a confidence threshold and temporal filtering. Implement a deterministic table state machine and tests for: arrival, departure, brief occlusion, staff crossing, low confidence, camera outage, manual override and resume. Never turn RESET_PENDING into AVAILABLE from vision alone. Export annotated debug overlays only in local authorized development mode.

**Done when:** Deterministic tests pass; authorized videos produce table events; unknown states are handled safely; no accuracy claim is invented.

### Phase 6 - Reliable edge-to-cloud synchronization

**Paste:**

> Add an SQLite outbox that durably stores events before network transmission. Securely pair an edge device to exactly one location, send events in authenticated batches over TLS, verify device/location mapping server-side, and deduplicate by event_id. Implement retries/backoff, replay after restart, heartbeat metrics and a device-offline UI banner. Test duplicate posts, 15-minute network outage, out-of-order delivery and revoked device credentials.

**Done when:** Events survive disconnect and restart; duplicate sends do not create duplicate tasks; revoked devices are rejected.

### Phase 7 - Cleaning workflow, analytics and exports

**Paste:**

> Connect edge state-change events to staff tasks and dashboard updates. Implement one open reset-pending task per relevant table session, task acknowledgement, Start cleaning, Mark ready, and full audit logging. Implement daily/hourly occupancy, state durations, reset delay and simple CSV export with correct IANA time-zone handling. Add tests for date boundaries, missing-camera periods and manual overrides.

**Done when:** A complete occupied-to-clean-to-available workflow is visible and reported correctly.

### Phase 8 - Pilot installation, observability and security hardening

**Paste:**

> Prepare a safe pilot release: production-like Compose deployment, secrets handling, device pairing instructions, health/metrics endpoints, log redaction, database backup/restore instructions, dependency checks, role/tenant security tests and an installer runbook. Default to no cloud raw-video upload. Document customer consent, legal review requirements and manual camera onboarding. Do not declare this production-compliant without external review.

**Done when:** A technician can follow the runbook on authorized hardware and a reviewer can reproduce security/restore tests.

### Phase 9 - Measured pilot evaluation and corrective improvements

**Paste:**

> Create a reproducible evaluation toolkit for real authorized restaurant clips. Support manually labeled table-state intervals, report confusion matrix, per-state precision/recall, UNKNOWN coverage, false reset alerts per table-shift and event-to-dashboard delay. Save source clip identifiers and model/config versions. Do not run evaluation on unapproved videos. Summarize weaknesses and prioritize fixes, without fabricating metrics.

**Done when:** Real pilot results are reproducible and the founder has evidence of accuracy and operational value.

### Phase 10 - Commercial SaaS after successful pilot

**Paste:**

> Only after Phase 9 and founder approval, add plan definitions, billing integration behind a feature flag, signup/onboarding improvements, organization subscription state, camera limits, usage metering, secure support tooling and account lifecycle management. Document payment-provider eligibility for a Bangladesh-based founder rather than assuming a provider supports the company. Add billing-webhook idempotency and cancellation/refund edge cases.

**Done when:** Subscription access, billing states and customer isolation work in integration tests and the intended payment provider has approved the account.

## 18. End-to-end acceptance script (founder should test manually)

1. Start the system locally using documented commands.
2. Log in as Restaurant A manager; see a floor of 6 example tables.
3. Log in as Restaurant B manager in another browser; confirm completely separate tables and events.
4. Load an authorized MP4 into the edge-agent demo for Restaurant A and calibrate Table A4.
5. See `UNKNOWN -> AVAILABLE` after a manual initial ready confirmation.
6. Simulate guests sitting; confirm `OCCUPIED` occurs only after stable evidence.
7. Simulate departure; wait for the configured grace period and see `RESET_PENDING` plus one task.
8. Open staff view, tap Start cleaning, then Mark ready; verify `AVAILABLE` and accurate reset timer.
9. Cut network access from edge to cloud for several minutes; restore it; verify queued events appear once.
10. Disconnect the camera; verify `UNKNOWN`/offline rather than misleading availability.
11. Try to request Restaurant B data using Restaurant A's token; server must return unauthorized/forbidden.
12. Open daily analytics and confirm events, time zone, and durations match the source event log.

**Release blocker:** Any failure of tenant isolation, insecure camera access, misleading AVAILABLE status during video outage, or unapproved cloud video transfer must block a real pilot.

# Part D - Realistic startup and launch plan

## 19. Suggested development schedule (planning targets)

| Weeks | Technical target | Business target |
|:--|:--|:--|
| 1-2 | Phase 0 + repository foundation | Interview 10 US restaurant managers |
| 3-4 | Auth, multi-tenant data, mock dashboard | Contact 30-50 carefully selected restaurants |
| 5-7 | Video ingestion, calibration, detector, table states | Show labeled 30-45 second concept video |
| 8-9 | Reliable sync, staff workflows, analytics | Find 2-3 operators willing to discuss a pilot |
| 10-12 | Pilot hardening and evaluation kit | Secure at least one authorized pilot and written terms |
| 13-16 | Real pilot feedback, fixes, usability | Test paid demand and installation economics |

This is an estimated sequence, not a guaranteed calendar. Hardware logistics, video rights, legal reviews, and difficult camera angles may require additional time.

## 20. Getting US footage and camera access from Bangladesh

**Do not ask for admin passwords or public live CCTV URLs.** Use this order:

1. Build and demonstrate the system with your own staged footage or properly licensed/authorized video.
2. Find US restaurant leads through legitimate research of publicly listed businesses and their own websites; respect website terms and email laws.
3. Send personalized outreach asking for a brief discovery call and include a **clearly labeled concept-video link**, not a large MP4 attachment.
4. If interested, ask for a short **operator-authorized recorded dining-area clip** with written terms defining permitted use, retention and deletion. Obtain appropriate notices/permissions, and avoid customer-identifiable clips where possible.
5. For live pilot access, have the restaurant or a US-based technician install the edge device on-site; pair it securely using a time-limited enrollment workflow.
6. Keep video local and make the founder's remote access limited to approved dashboards and diagnostics.
7. Conduct a pilot review with the owner: false alerts, reset delays, cost savings and willingness to pay.

### 20.1 Short concept-video storyboard

| Seconds | Visual | Message |
|:--|:--|:--|
| 0-5 | Busy restaurant and one operational problem | "Busy restaurant? Tables take time to reset." |
| 5-15 | Authorized test footage + table overlays | "Your existing cameras can help detect occupancy." |
| 15-25 | Live-style dashboard marked DEMO if simulated | "See occupied, available, and pending tables." |
| 25-35 | Reset-pending task and staff confirmation | "Staff know which table to check next." |
| 35-45 | Summary chart + invitation | "Would you test a privacy-first pilot?" |

Do not copy the original Reel's assets or claim your concept animation is footage of a deployed product.

## 21. Pricing hypothesis and unit economics

Initial *hypotheses for interviews*, not validated market prices:

- **Starter:** around USD 149/location/month for a limited number of cameras and basic alerts.
- **Growth:** around USD 299/location/month for more cameras, analytics and team workflows.
- **One-time setup fee:** may be appropriate to cover installer labor and edge hardware; determine after field testing.

Track monthly gross margin only after including cloud hosting, edge hardware/support, payment processing, customer acquisition, installation, and model licensing. One shared SaaS codebase does not mean every restaurant installs itself; camera calibration and support can be significant costs.

## 22. Business and product decision gates

| Gate | Evidence required | Decision |
|:--|:--|:--|
| G0 - Customer problem | 15-20 interviews with repeatable operational pain | Continue or change target segment |
| G1 - Demo quality | Owner can understand the dashboard in under 2 minutes | Improve the explanation if not |
| G2 - Pilot interest | At least one written owner-authorized pilot offer | Proceed to physical installation |
| G3 - Technical truth | State quality, false alerts, reliability and privacy verified | Continue, revise or stop pilot |
| G4 - Paid demand | At least 1-2 locations willing to pay real money | Enable commercial billing |
| G5 - Repeatability | Second location installs with minimal custom code | Start scaling outreach |

Be willing to narrow the product to **table turnover + reset workflow** even if more advanced Reel features look impressive. Selling one measurable outcome is often easier than selling a long list of unvalidated AI features.

## 23. Major risks and mitigations

| Risk | Practical mitigation |
|:--|:--|
| Restaurants won't share video | Start with operator-approved short clips and local-only edge inference |
| Camera view does not show every table | Calibrate only visible tables, label unmonitored ones, advise camera repositioning |
| AI frequently mistakes staff for diners | Add zone logic, state persistence, manual overrides and labeled evaluation |
| Product creates too many alerts | Alert deduplication, configurable thresholds, staff feedback and quiet hours |
| False claim of a clean/ready table | Require staff ready confirmation and UNKNOWN fallback |
| SaaS tenant data leak | Explicit backend authorization, RLS where appropriate, adversarial tests |
| RTSP model compatibility or license issues | Adapter interfaces, commercial license review, controlled supported-device list |
| Difficult US installation from abroad | Partner with local CCTV technician or authorized managed-service provider |
| Cross-border privacy concern | Local inference, minimal data transfer, contracts and jurisdiction-specific legal review |
| No paying customers | Conduct discovery before overbuilding; stop at validation gates |

## 24. Decisions founder must make before launch

Record answers in `docs/decisions/` rather than leaving critical assumptions hidden:

- Working brand/domain and company registration jurisdiction.
- Single first US segment (e.g., casual dining with table service) and one target state/metro for outreach.
- Supported first camera/NVR models; whether edge hardware is provided or installed on existing equipment.
- Model inference license and third-party library/weight compliance.
- Identity/billing vendors only after verifying availability for a Bangladesh-based business.
- Video retention, consent, access controls, and customer contract language.
- Actual alert thresholds and accuracy gates learned from real data.
- Who is responsible for US on-site installation and customer support.

## 25. Useful official reference links

This is an implementation reference list, not a substitute for security or legal review. Check these documents again before production:

1. ONVIF video interoperability profiles: https://www.onvif.org/profiles/
2. ONVIF Profile S (streaming, deprecation notice): https://www.onvif.org/profiles/profile-s/
3. Ultralytics commercial licensing guidance: https://www.ultralytics.com/license
4. FTC business security recommendations: https://www.ftc.gov/business-guidance/resources/start-security-guide-business
5. NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
6. FTC CAN-SPAM compliance: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
7. FastAPI documentation: https://fastapi.tiangolo.com/
8. PostgreSQL row-level security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
9. Docker Compose documentation: https://docs.docker.com/compose/

---

## Final instructions to Codex and founder

**Build one excellent vertical slice first:** authorized test video -> person detection -> stable table state -> edge event -> cloud event -> live dashboard -> staff cleaning confirmation -> analytics. Then harden it for a real pilot, and only then scale it across many restaurants.

**Codex owns code generation and automated tests. The founder owns product decisions, permission to use footage, human validation, contracts, security review, and customer interviews.**

*End of master blueprint - version 1.0.*
