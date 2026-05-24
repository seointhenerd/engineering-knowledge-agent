"""FastAPI backend for the engineering knowledge agent."""

import logging
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from agent import run_agent

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Engineering Knowledge Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]


@app.get("/")
def serve_ui():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"[{ts}] Q: \"{req.question}\"")
    t0 = time.perf_counter()

    answer, tools_used = run_agent(req.question)

    latency = time.perf_counter() - t0
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"[{ts}] Tools used: {', '.join(tools_used) if tools_used else 'none'}")
    log.info(f"[{ts}] A: \"{answer[:120]}{'...' if len(answer) > 120 else ''}\"")
    log.info(f"[{ts}] Latency: {latency:.1f}s")

    return ChatResponse(answer=answer, tools_used=tools_used)
