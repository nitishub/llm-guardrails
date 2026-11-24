import json
import logging
import os
import secrets
import time
import uuid
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.security import APIKeyHeader
from openai import OpenAIError
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.llm import call_llm
from app.classifier import warmup_classifier
from app.pipeline import Action, screen_prompt

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("guardrails")


def log_event(**fields) -> None:
    logger.info(json.dumps(fields))

# Custom lifespan context manager to handle startup and shutdown events, including classifier warmup.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ready = False #custom attribute to track readiness of the app
    app.state.classifier_status = "starting" #custom attribute to track classifier status
    started = time.perf_counter()
    try:
        loaded = warmup_classifier()
        app.state.classifier_status = "loaded" if loaded else "disabled"
        app.state.ready = True
        log_event(
            event="startup",
            classifier=app.state.classifier_status,
            warmup_ms=round((time.perf_counter() - started) * 1000, 1),
        )
    except Exception as exc:
        app.state.classifier_status = "failed"
        app.state.ready = False
        log_event(event="startup_error", error=type(exc).__name__)
    yield
    app.state.ready = False


app = FastAPI(
    title="LLM Guardrails",
    description="Screens prompts for PII and prompt injection before they reach an LLM.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.ready = False
app.state.classifier_status = "starting"

API_KEY = os.environ.get("GUARDRAILS_API_KEY", "")
if not API_KEY:
    raise RuntimeError("GUARDRAILS_API_KEY is not set; refusing to start without authentication.")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> None:
    # Compare bytes: compare_digest raises on non-ASCII strings, which would turn a bad key into a 500.
    if api_key is None or not secrets.compare_digest(api_key.encode(), API_KEY.encode()):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
RATE_LIMIT = os.environ.get("GUARDRAILS_RATE_LIMIT", "20/minute")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("GUARDRAILS_RATE_LIMIT_STORAGE", "memory://"),
    strategy="sliding-window-counter",
    headers_enabled=True,
    in_memory_fallback_enabled=True,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)


class ChatResponse(BaseModel):
    action: Action
    reasons: List[str]
    sanitized_prompt: Optional[str] = None
    response: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/ready")
def ready(response: Response) -> dict:
    if not app.state.ready:
        response.status_code = 503
        return {"status": "not_ready", "classifier": app.state.classifier_status}
    return {"status": "ready", "classifier": app.state.classifier_status}


@app.post("/chat", dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT)
def chat(request: Request, body: ChatRequest, response: Response) -> ChatResponse:
    request_id = uuid.uuid4().hex
    response.headers["X-Request-ID"] = request_id
    started = time.perf_counter()

    decision = screen_prompt(body.prompt)
    fields = {
        "event": "chat",
        "request_id": request_id,
        "action": decision.action.value,
        "reasons": decision.reasons,
        "classifier_score": round(decision.classifier.score, 4) if decision.classifier else None,
        "judge_injection": decision.judge.is_injection if decision.judge else None,
        "judge_error": decision.judge.error if decision.judge else None,
        "prompt_chars": len(body.prompt),
        "screen_ms": round((time.perf_counter() - started) * 1000, 1),
    }

    if decision.action == Action.BLOCK:
        log_event(**fields)
        return ChatResponse(action=decision.action, reasons=decision.reasons)

    llm_started = time.perf_counter()
    try:
        answer = call_llm(decision.text)
    except OpenAIError as exc:
        log_event(**fields, llm_error=type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="LLM provider unavailable",
            headers={"X-Request-ID": request_id},
        )
    log_event(**fields, llm_ms=round((time.perf_counter() - llm_started) * 1000, 1))

    return ChatResponse(
        action=decision.action,
        reasons=decision.reasons,
        sanitized_prompt=decision.text,
        response=answer,
    )