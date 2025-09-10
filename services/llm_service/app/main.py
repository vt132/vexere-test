from fastapi import FastAPI

from .routers import llm

# Simple abstraction layer for multiple model backends


app = FastAPI(title="LLM Serving Layer", version="0.1.0")
app.include_router(llm.router)

"""LLM service main module.

GPT-5 preview is now enabled for all clients by default. To (optionally) disable
it for emergency rollback, set environment variable DISABLE_GPT5_PREVIEW=true.
"""


@app.get("/health")
def health():
    return {"status": "ok"}
