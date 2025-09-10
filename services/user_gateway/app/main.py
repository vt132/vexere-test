from fastapi import FastAPI
import httpx
from .routers import gateway as gateway_router
from .config import LLM_SERVICE_URL, DATA_SERVICE_URL

app = FastAPI(title="User Request Handling Layer", version="0.1.0")
app.include_router(gateway_router.router)


@app.get("/health")
async def health():
    async with httpx.AsyncClient() as client:
        llm = await client.get(f"{LLM_SERVICE_URL}/health")
        data = await client.get(f"{DATA_SERVICE_URL}/health")
    return {"status": "ok", "llm": llm.json(), "data": data.json()}
