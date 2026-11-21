import json
import logging
import os
import secrets
import time
import uuid
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Response, Security
from fastapi.security import APIKeyHeader
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.llm import call_llm
from app.pipeline import Action, screen_prompt

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("guardrails")


def log_event(**fields) -> None:
    logger.info(json.dumps(fields))
app = FastAPI(
    title="LLM Guardrails",
    description="Screens prompts for PII and prompt injection before they reach an LLM.",
    version="0.1.0",
)

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


@app.post("/chat", dependencies=[Depends(require_api_key)])
def chat(request: ChatRequest, http_response: Response) -> ChatResponse:
    request_id = uuid.uuid4().hex
    http_response.headers["X-Request-ID"] = request_id
    started = time.perf_counter()

    decision = screen_prompt(request.prompt)
    fields = {
        "event": "chat",
        "request_id": request_id,
        "action": decision.action.value,
        "reasons": decision.reasons,
        "classifier_score": round(decision.classifier.score, 4) if decision.classifier else None,
        "judge_injection": decision.judge.is_injection if decision.judge else None,
        "judge_error": decision.judge.error if decision.judge else None,
        "prompt_chars": len(request.prompt),
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