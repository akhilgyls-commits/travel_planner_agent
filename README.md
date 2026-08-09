# ✈️ Travel Planning Agent

A production-ready AI travel planning agent built with **FastAPI**, **LangGraph**, and **Docker**.
It generates personalized itineraries, recommends attractions/restaurants/hotels,
suggests transportation, estimates costs, and answers follow-up questions with
conversational memory — all backed by tool-calling (weather, maps, and place
search, mockable for demo/offline use).

---

## Features

- 🗺️ **Personalized itineraries** — day-by-day plans based on destination, dates, budget, interests, and travelers
- 🏨 **Recommendations** — attractions, restaurants, and hotels matched to budget tier and interests
- 🚗 **Transportation guidance** — getting to the destination and getting around locally
- 💰 **Cost estimation** — deterministic cost breakdown (lodging, food, transport, flights, misc.)
- 💬 **Conversational memory** — ask follow-up questions; the agent remembers prior context per session
- 🔧 **Tool-calling architecture** — LLM decides when to call weather/maps/places/cost tools (ReAct pattern via LangGraph)
- 🧪 **Mock API mode** — fully demoable without any external API keys (`USE_MOCK_APIS=true`)
- 🪵 **Structured logging**, **centralized config**, **graceful error handling**
- 🐳 **Dockerized**, with a non-root runtime user and container healthcheck
- ✅ **Unit tests** covering tools, schemas, session management, and API endpoints

---

## Architecture

```
                          ┌─────────────────────────┐
                          │        FastAPI           │
                          │  (app/main.py, api/)     │
                          │  /trip/plan              │
                          │  /trip/followup          │
                          │  /trip/session/{id}      │
                          │  /health                 │
                          └────────────┬─────────────┘
                                       │
                          ┌────────────▼─────────────┐
                          │     SessionService        │
                          │ (session_service.py)      │
                          │  session id lifecycle/TTL │
                          └────────────┬─────────────┘
                                       │
                          ┌────────────▼─────────────┐
                          │      TravelAgent          │
                          │      (agent/graph.py)     │
                          │  LangGraph ReAct agent +  │
                          │  MemorySaver checkpointer │
                          │  (short-term memory)      │
                          └────────────┬─────────────┘
                                       │ tool calls
              ┌────────────┬──────────┼──────────┬───────────────┐
              ▼            ▼          ▼          ▼               ▼
        weather_tool  maps_tool  places_tool  cost_estimator_tool
        (OpenWeather   (Google    (Google      (pure computation)
         or mock)       Maps or    Places or
                        mock)      mock)
```

**Design choices:**
- **LangGraph `create_react_agent`** implements the reason → call tool → observe
  loop as a compiled graph, giving us tool orchestration without hand-rolling
  a loop.
- **`MemorySaver` checkpointer** keyed by `session_id` (as LangGraph's
  `thread_id`) provides short-term conversational memory "for free" — no
  manual message re-assembly needed for follow-ups.
- **Tools are pure, independently testable functions** decorated with
  `@tool`, each with a mock/real-API dual-path so the system is fully
  demoable offline and a drop-in for real API keys in production.
- **`SessionService`** is a thin, swappable registry for session metadata
  and TTL eviction — the interface is small so it's easy to back with Redis
  or Postgres in a multi-instance deployment (see [Scaling Notes](#scaling-notes)).

---

## Folder Structure

```
travel-planner-agent/
├── app/
│   ├── main.py                    # FastAPI app, middleware, exception handlers
│   ├── config.py                  # Centralized settings (env vars)
│   ├── logging_config.py          # Structured logging setup
│   ├── models/
│   │   └── schemas.py             # Pydantic request/response models
│   ├── agent/
│   │   ├── graph.py                # LangGraph agent (tools + memory)
│   │   ├── llm.py                  # LLM provider factory (OpenAI/Anthropic)
│   │   ├── prompts.py              # System prompt
│   │   └── prompt_builder.py       # Structured request -> NL prompt
│   ├── tools/
│   │   ├── weather_tool.py         # Weather forecast (mock/OpenWeatherMap)
│   │   ├── maps_tool.py            # Distance + local transport (mock/Google Maps)
│   │   ├── places_tool.py          # Attractions/restaurants/hotels (mock/Google Places)
│   │   └── cost_estimator_tool.py  # Cost breakdown computation
│   ├── services/
│   │   └── session_service.py      # Session id lifecycle & TTL
│   └── api/
│       └── routes.py                # REST endpoints
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_tools.py
│   ├── test_schemas.py
│   ├── test_session_service.py
│   ├── test_agent.py
│   └── test_api.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
└── README.md
```

---

## Getting Started

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
- To run **fully offline / without any API keys**, leave `USE_MOCK_APIS=true`
  and just set `LLM_PROVIDER` + the matching API key (an LLM key is still
  required — it's the agent's "brain").
- To use **real weather/maps/places data**, set `USE_MOCK_APIS=false` and
  fill in `OPENWEATHER_API_KEY`, `GOOGLE_MAPS_API_KEY`, `GOOGLE_PLACES_API_KEY`.
  Each tool independently falls back to mock data if its specific key is
  missing or the API call fails, so partial configuration is safe.

### 2. Run locally (Python)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for interactive Swagger docs.

### 3. Run with Docker

```bash
docker compose up --build
```

or directly with the Docker CLI:

```bash
docker build -t travel-planner-agent .
docker run -p 8000:8000 --env-file .env travel-planner-agent
```

### 4. Run tests

```bash
pip install -r requirements.txt
pytest -v
```

Tests run entirely against **mocked tools and a fake agent** — no real LLM
or external API calls are made, so the suite is fast, free, and deterministic.

---

## API Reference

Base path: `/api/v1`

### `GET /health`
Health check — confirms the service is up and reports LLM/mock-API configuration.

```bash
curl http://localhost:8000/api/v1/health
```

### `POST /trip/plan`
Generate a full itinerary. Starts a new session (or continues one if
`session_id` is provided).

```bash
curl -X POST http://localhost:8000/api/v1/trip/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Kyoto, Japan",
    "start_date": "2026-10-10",
    "end_date": "2026-10-17",
    "travelers": 2,
    "budget_amount": 3000,
    "budget_currency": "USD",
    "budget_level": "mid_range",
    "interests": ["food", "history", "culture"],
    "origin_city": "New York, USA",
    "additional_notes": "Vegetarian, prefer a relaxed pace"
  }'
```

Response:
```json
{
  "session_id": "b3f1c2b0-...",
  "destination": "Kyoto, Japan",
  "duration_days": 7,
  "itinerary": "## Trip Overview\n...",
  "tools_used": ["get_weather_forecast", "search_attractions", "search_hotels", "estimate_trip_cost"]
}
```

### `POST /trip/followup`
Ask a follow-up question using the memory from a prior `/trip/plan` call.

```bash
curl -X POST http://localhost:8000/api/v1/trip/followup \
  -H "Content-Type: application/json" \
  -d '{"session_id": "b3f1c2b0-...", "question": "Can you suggest a vegan-friendly dinner for day 3?"}'
```

### `GET /trip/session/{session_id}`
Retrieve full conversation history for a session.

### `DELETE /trip/session/{session_id}`
Clear a session's memory.

Full interactive documentation (with schemas and try-it-out) is always
available at **`/docs`** (Swagger) and **`/redoc`**.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Anthropic model name |
| `LLM_TEMPERATURE` | `0.3` | Sampling temperature |
| `USE_MOCK_APIS` | `true` | Use deterministic mock data instead of real weather/maps/places APIs |
| `OPENWEATHER_API_KEY` | — | Used only if `USE_MOCK_APIS=false` |
| `GOOGLE_MAPS_API_KEY` | — | Used only if `USE_MOCK_APIS=false` |
| `GOOGLE_PLACES_API_KEY` | — | Used only if `USE_MOCK_APIS=false` |
| `APP_ENV` | `development` | `development`, `staging`, `production`, `test` |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `MEMORY_MAX_MESSAGES` | `20` | Soft cap referenced for memory hygiene |
| `SESSION_TTL_SECONDS` | `3600` | In-memory session expiry |

---

## Error Handling & Resilience

- Every external tool call (weather/maps/places) uses `tenacity` retries
  (exponential backoff, 3 attempts) and **falls back to mock data** on
  persistent failure, so a flaky third-party API never takes the whole
  agent down.
- Pydantic validation rejects malformed trip requests (bad dates, negative
  budgets, invalid enums) at the API boundary with clear `422` errors.
- Missing LLM credentials produce a clear `503` rather than a stack trace.
- A global exception handler ensures unhandled errors return a structured
  `500` JSON body instead of leaking tracebacks.
- Requests are logged with a correlation id (`x-request-id`) and duration
  for observability.

## Scaling Notes

This reference implementation uses **in-process memory** (LangGraph's
`MemorySaver` + a local `SessionService` dict) for simplicity, which is
correct for a single-instance deployment or demo. For a multi-instance /
production deployment:

- Swap `MemorySaver` for a persistent LangGraph checkpointer (e.g. Postgres
  or Redis-backed) so sessions survive restarts and are shared across
  instances.
- Back `SessionService` with the same store (or drop it in favor of reading
  session metadata straight from the checkpointer).
- Put the API behind a load balancer; the app itself is stateless aside from
  the pluggable memory backend.

---

## License

MIT — use freely as a reference implementation.
"# travel_planner_agent" 
