# Smart Support Ticket System

An AI-powered, multi-tenant customer support ticketing platform built with **FastAPI**, **PostgreSQL**, **Celery**, and **Google Gemini**. Tickets are automatically triaged, prioritized, and matched against past resolutions using semantic search — turning a traditional CRUD helpdesk into a system that actually reduces agent workload.

**Live API:** [https://support-ticket-ai-icyq.onrender.com/docs](https://support-ticket-ai-icyq.onrender.com/docs)

---

## Why This Project Exists

Most support ticketing demos are CRUD wrappers around a database table. This one isn't. It's built to demonstrate the patterns that separate a prototype from a system a real product team could actually run:

- **Multi-tenant from the schema up** — every table and every query is scoped by organization, not bolted on later
- **AI work is decoupled from the request path** — categorization and embedding happen in a background worker, so a slow or failing LLM call never breaks ticket creation
- **Semantic search, not keyword matching** — agents find previously resolved tickets by meaning, even when the wording is completely different
- **Real-time updates over a proper pub/sub bridge** — not polling, and not a naive direct call from a background worker into the web process
- **Aggregation happens in the database**, not in a Python loop over every row

Every architectural decision below is explained, not just listed — this README doubles as a design log.

---

## Feature Overview

### 🔐 Multi-Tenant Authentication & Authorization
- JWT-based auth with **role-based access control** (`admin`, `agent`, `customer`)
- Every organization is fully isolated — one company's tickets, agents, and analytics are structurally invisible to another
- Admins can **invite teammates** into their existing organization with a scoped role, rather than every signup spinning up a brand-new company
- Passwords hashed with **bcrypt**; JWTs carry `sub`, `org_id`, and `role` so authorization decisions don't require a database round-trip

### 🎫 Ticket Management with Enforced State Machine
- Full CRUD with pagination, filtering, and organization-scoped queries
- Status transitions (`open → pending → resolved → closed`) are validated server-side against a defined state machine — a client can't force a ticket from `closed` back to `open` by sending a raw PATCH request
- Composite database index on `(organization_id, status)`, matching the exact query pattern the app actually uses

### 🤖 AI-Powered Triage (Google Gemini)
On ticket creation, a background job automatically:
- **Categorizes** the ticket (billing, technical, account, feature request, general)
- **Assigns a priority** based on content, separate from any human-set priority — so AI suggestions never silently override agent judgment
- **Summarizes** the issue in one sentence
- **Drafts a suggested reply** an agent can review and send
- **Auto-assigns** the ticket to the least-loaded available agent

Categorization uses a **model fallback chain** and Gemini's structured JSON output mode, with `tenacity`-based retry logic that backs off exponentially on transient failures but fails fast on quota exhaustion or invalid credentials — so a rate-limited API never triggers a retry storm.

### 🔍 Semantic Search Over Ticket History
- Ticket content is embedded via Gemini's embedding model and stored in **PostgreSQL with `pgvector`**
- An **IVFFlat index with cosine similarity** lets agents instantly surface past tickets that resolve the *same underlying problem*, even when the wording shares almost no keywords ("can't log in" vs. "getting a 401 on sign-in")
- All similarity queries remain scoped to the requesting organization — semantic search across tenants is not possible, by design

### ⚡ Background Job Processing (Celery + Redis)
- AI categorization and embedding generation run **asynchronously**, off the request/response cycle
- A slow or unavailable LLM provider degrades gracefully: the ticket is created instantly, AI fields populate a few seconds later
- Retry logic distinguishes **transient failures** (network blips — retry) from **permanent failures** (bad API key, exhausted quota — fail fast, don't waste further calls)

### 📡 Real-Time Notifications (WebSockets + Redis Pub/Sub)
- Agents receive live updates when tickets are created or AI-processed, with zero polling
- Because the Celery worker and the FastAPI process are **separate processes with separate memory**, a worker can't call the web server's in-memory connection manager directly — a **Redis pub/sub channel bridges the two**, so any number of API instances can broadcast to whichever agents happen to be connected to them
- Connections are scoped per organization, so agents only ever see updates relevant to their own company

### 📊 Analytics Dashboard (Database-Level Aggregation)
- Ticket volume by status, category breakdown, average resolution time, daily ticket trends, and per-agent workload
- All computed with **SQL aggregation** (`GROUP BY`, `AVG`, `COUNT`) rather than pulling every row into Python — a pattern that stays fast whether the org has 50 tickets or 500,000
- Resolution time correctly excludes still-open tickets from the average, avoiding a common but subtle data-correctness bug

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API Framework | **FastAPI** | Async-native, automatic OpenAPI docs, first-class dependency injection |
| Database | **PostgreSQL** (Neon, serverless) + **pgvector** | Relational integrity and vector similarity search in a single database |
| ORM | **SQLAlchemy 2.0** (async) | Industry-standard, full async support for concurrent request handling |
| Auth | **JWT** (python-jose) + **bcrypt** (passlib) | Stateless, horizontally scalable auth |
| Background Jobs | **Celery** + **Redis** (Upstash) | Decouples slow AI work from the request path; production-grade retry semantics |
| Real-Time | **FastAPI WebSockets** + **Redis Pub/Sub** | True bidirectional push; pub/sub bridges the API/worker process boundary |
| AI / LLM | **Google Gemini** (`gemini-flash-latest`, `gemini-embedding-001`) | Categorization, summarization, and 768-dimension embeddings |
| Migrations | **Alembic** | Version-controlled schema changes, not `create_all()` |
| Containerization | **Docker** | Environment parity between local dev and deployment |
| Deployment | **Render** (API) + **Neon** (Postgres) + **Upstash** (Redis) | Managed, low-ops hosting suited to a portfolio-scale deployment |

---

## Architecture

```
                        ┌─────────────────┐
                        │   FastAPI App    │◄──── HTTP clients / Swagger UI
                        │  (Render, async) │
                        └────────┬─────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
          ┌────────────┐  ┌────────────┐  ┌──────────────┐
          │  Postgres   │  │   Redis    │  │  WebSocket    │
          │   (Neon)    │  │ (Upstash)  │  │  connections  │
          │ + pgvector  │  │            │  │ (per org)     │
          └────────────┘  └─────┬──────┘  └──────▲───────┘
                                 │                 │
                                 │  pub/sub event  │
                                 ▼                 │
                        ┌─────────────────┐        │
                        │  Celery Worker   │────────┘
                        │  (AI pipeline)   │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Google Gemini   │
                        │  (categorize +   │
                        │    embed)        │
                        └─────────────────┘
```

**Request flow for ticket creation:**
1. Client `POST`s a ticket → written to Postgres, `201` returned immediately
2. A Celery task is queued via Redis — the client never waits on this
3. The worker calls Gemini for categorization and embedding, writes results back to Postgres
4. The worker publishes a completion event to Redis
5. The API process (subscribed to that channel) rebroadcasts it over WebSocket to any connected agents in that organization

---

## Getting Started

### Prerequisites
- Python 3.12+
- Docker Desktop (for local Postgres + Redis)
- A Google Gemini API key ([aistudio.google.com](https://aistudio.google.com) — free tier, no card required)

### 1. Clone and set up the environment

```bash
git clone https://github.com/soumodeepRoy853/support_ticket-_ai.git
cd support_ticket-_ai
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start local infrastructure

```bash
docker-compose up -d
```

### 3. Configure environment variables

Create a `.env` file:

```dotenv
DATABASE_URL=postgresql+asyncpg://ticketuser:ticketpass@localhost:5432/ticketdb
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your-gemini-key
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

### 6. Start the background worker (separate terminal)

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

*(On Windows, add `--pool=solo`.)*

---

## API Overview

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | `POST` | Create a new organization + admin user |
| `/api/auth/invite` | `POST` | Admin invites a teammate into their existing org (admin only) |
| `/api/auth/login` | `POST` | Authenticate, receive a JWT |
| `/api/tickets/` | `POST` | Create a ticket (triggers async AI processing) |
| `/api/tickets/` | `GET` | List tickets, paginated and filterable by status |
| `/api/tickets/{id}` | `GET` | Retrieve a single ticket |
| `/api/tickets/{id}` | `PATCH` | Update status/priority/assignment (agent/admin only) |
| `/api/tickets/{id}/similar` | `GET` | Semantic search for related past tickets |
| `/api/analytics/dashboard` | `GET` | Aggregated metrics (agent/admin only) |
| `/ws/notifications` | `WebSocket` | Live ticket event stream, scoped per organization |

Full interactive documentation, including request/response schemas, is available at `/docs` on any running instance.

---

## Deployment Notes

The FastAPI web service is deployed on **Render's free tier**. The database runs on **Neon** (serverless Postgres with `pgvector`), and Redis runs on **Upstash** — both chosen for their genuinely free, no-card-required tiers.

**The Celery worker is intentionally not deployed to a hosted service.** Render's background workers require a paid tier (from $7/month) with no free option. For this portfolio project, the worker runs locally against the same Redis and Postgres instances used by the deployed API — the queue and database are shared, so the AI pipeline works fully during live demos without incurring ongoing hosting cost.

In a production deployment, this would run as a dedicated always-on worker service alongside the API (e.g., a Render Background Worker, or a container on Fly.io/Railway) — a genuine architectural decision documented here rather than a limitation discovered too late.

**Known free-tier tradeoffs:**
- The web service spins down after 15 minutes of inactivity; the first request afterward may take 30–60 seconds
- Gemini's free tier is rate-limited (20 requests/day per model on some tiers) — sufficient for demonstration, not production traffic

---

## Design Decisions Worth Knowing

A few choices in this codebase are deliberate and worth understanding, not just copying:

- **Every multi-tenant query filters by `organization_id`**, even when a resource is looked up by its own primary key. This is the single most important safeguard against cross-tenant data leakage in a shared-schema multi-tenant system.
- **AI-set priority and human-set priority are stored in separate columns.** The system never lets a model silently override an agent's judgment.
- **Ticket status transitions are enforced server-side** via an explicit state machine, not trusted from client input.
- **The Celery worker uses a synchronous SQLAlchemy engine**, deliberately separate from the API's async engine — Celery's worker model has no event loop, and mixing async into it adds complexity without benefit.
- **Retry logic distinguishes transient vs. permanent failures.** A `429` (quota exhausted) is treated as non-retryable within a task run, since retrying within seconds cannot possibly succeed — this avoids burning further quota on a doomed request.

---

## Possible Next Steps

- Deploy the Celery worker as an always-on service for a fully live demo
- Add a `pytest` suite with mocked LLM calls and `task_always_eager` for CI-friendly Celery testing
- Email-based invite flow (currently, admins set the invited user's initial password directly)
- Admin-triggered reprocessing endpoint for tickets that failed AI processing due to transient provider issues

---

## License

MIT