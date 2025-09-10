# Vexere Test: Multi-Layer FastAPI Services

Three services working together:

- LLM service: retrieval-augmented FAQ answers, an LLM-based intent planner, and a tool-calling agent.
- Data service: simple in-memory endpoints for trips and orders (can be swapped with a DB later).
- User gateway: orchestrates intents by calling the planner and executing mapped actions.

Ports (default):
- LLM service: 8001
- Data service: 8002
- User gateway: 8000

## Quick start (Windows)

1) Create env and install deps

```powershell
conda create -n ml-env python=3.11 -y
conda activate ml-env
pip install -U pip
pip install -e .
```

2) Start all services (opens 3 terminals)

```powershell
./run_services.bat
```

If you don’t use conda or your env name isn’t `ml-env`, edit `run_services.bat` or run each service manually:

```powershell
python -m uvicorn services.llm_service.app.main:app --port 8001 --reload
python -m uvicorn services.data_service.app.main:app --port 8002 --reload
python -m uvicorn services.user_gateway.app.main:app --port 8000 --reload
```

## Configuration

- LLM service config: `services/llm_service/app/config.py`
  - `BASE_URL`: OpenAI-compatible endpoint base URL
  - `LLM_MODEL`: default chat model id
  - `EMBEDDING_MODEL`: sentence-transformers model id
  - `FAQ_DATA_PATH`: path to CSV FAQ file (indexed at startup)
  - `DATA_SERVICE_URL`: used by tools
  - `HTTP_TIMEOUT_SECONDS`: outgoing HTTP timeout

- User gateway config: `services/user_gateway/app/config.py`
  - `LLM_SERVICE_URL`, `DATA_SERVICE_URL`
  - `HTTP_TIMEOUT_SECONDS`

Data service runs in-memory and needs no config.

## Endpoints overview

### LLM service (`http://localhost:8001`)

- `POST /faq/ask`
  - Body: `{ "question": string, "stream": false? }`
  - Returns: `{ "answer": string, "context": string }`
  - RAG retrieves by question text only and reconstructs Q/A in the context.

- `POST /intents/plan`
  - Body: `{ "text": string, "user_id"?: number }`
  - Returns a JSON plan with `intent`, `slots`, `action`.

- `POST /agent/change_time`
  - Body: `{ "question": string }`
  - Tool-calling agent that can call `update_ticket_time` against the data service.

### Data service (`http://localhost:8002`)

- `GET /orders/{user_id}/pending`
- `GET /trips/{route_id}`
- `POST /orders/update_time` with `{ order_id, new_time_iso }`

### User gateway (`http://localhost:8000`)

- `POST /query`
  - Basic path that enriches and calls the LLM service.

- `POST /intents/plan`
  - Orchestrates the planner and executes the mapped action.
  - If required arguments are missing (e.g., `new_time_iso`), returns a clarification payload with `needs_clarification: true` and `missing` keys.


## Testing

Unit tests run offline. The LLM service tests stub embeddings/FAISS/LLM; gateway tests mock HTTP calls.

```powershell
conda activate ml-env
pytest -q
```

Run a single test file:

```powershell
pytest tests/test_llm_service.py -q
```

Note: You do NOT need to start any server for unit tests. Start services only for manual testing or end-to-end checks.

## Troubleshooting

- Conda env not found: edit `run_services.bat` to use your environment name or activate your env before running uvicorn commands.
- Port already in use: change `--port` or stop the existing process(es).
- Planner timeouts: gateway converts planner timeouts to HTTP 504; adjust `HTTP_TIMEOUT_SECONDS` if needed.
- Import errors during pytest: ensure you run `pytest` from the repo root; `tests/conftest.py` adds the project root to `sys.path`.

## Roadmap

- Swap in real OpenAI/vLLM backends, add auth and rate limiting.
- Persist data service state in a DB.
- Improve tool coverage and add more intents.
- Add caching (Redis) and CI.
