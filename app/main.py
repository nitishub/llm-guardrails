from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.llm import call_llm
from app.pipeline import Action, screen_prompt

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
def chat(request: ChatRequest) -> ChatResponse:
    decision = screen_prompt(request.prompt)
    if decision.action == Action.BLOCK:
        return ChatResponse(action=decision.action, reasons=decision.reasons)
    return ChatResponse(
        action=decision.action,
        reasons=decision.reasons,
        sanitized_prompt=decision.text,
        response=call_llm(decision.text),
    )