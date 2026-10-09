"""Run with: uvicorn experiments.karen_vane.app:app --host 127.0.0.1 --port 8011."""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .adapter import KarenAnswer, PublicQuestion, Settings, VaneAdapter


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.adapter = VaneAdapter(client, Settings.from_env())
        yield


app = FastAPI(title="Karen × Vane — public trial", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    return Path(__file__).with_name("index.html").read_text()


@app.post("/api/answer", response_model=KarenAnswer)
async def answer(request: PublicQuestion):
    return await app.state.adapter.answer(request)
