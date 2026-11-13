import json
import logging
import time
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Response
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


@app.post("/chat")
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