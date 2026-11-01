from fastapi import FastAPI

app = FastAPI(
    title="LLM Guardrails",
    description="Screens prompts for PII and prompt injection before they reach an LLM.",
    version="1.0.0",
)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}