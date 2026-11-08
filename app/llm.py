import os

from openai import OpenAI

MODEL = os.getenv("GUARDRAILS_LLM_MODEL", "gpt-5-nano")
TIMEOUT_SECONDS = float(os.getenv("GUARDRAILS_LLM_TIMEOUT", "30"))
MAX_OUTPUT_TOKENS = int(os.getenv("GUARDRAILS_LLM_MAX_TOKENS", "1000"))
SYSTEM_PROMPT = "You are a helpful assistant. Answer concisely."

_client = OpenAI(timeout=TIMEOUT_SECONDS, max_retries=2)


def call_llm(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        reasoning_effort="minimal",
        max_completion_tokens=MAX_OUTPUT_TOKENS,
    )
    return response.choices[0].message.content or ""