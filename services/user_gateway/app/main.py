import httpx
from fastapi import FastAPI

from .config import DATA_SERVICE_URL, LLM_SERVICE_URL
from .routers import gateway as gateway_router

app = FastAPI(title="User Request Handling Layer", version="0.1.0")
app.include_router(gateway_router.router)


@app.get("/health")
async def health():
    async with httpx.AsyncClient() as client:
        llm = await client.get(f"{LLM_SERVICE_URL}/health")
        data = await client.get(f"{DATA_SERVICE_URL}/health")
    return {"status": "ok", "llm": llm.json(), "data": data.json()}
