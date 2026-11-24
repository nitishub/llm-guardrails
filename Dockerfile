FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install CPU-only PyTorch first; the default Linux build pulls several GB of GPU libraries.
# Keep this version in sync with requirements-ml.txt.
COPY requirements.txt requirements-ml.txt ./
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements-ml.txt

RUN useradd --create-home app
USER app

# Download the model at build time so containers start without contacting Hugging Face.
ENV HF_HOME=/home/app/.cache/huggingface \
    GUARDRAILS_CLASSIFIER_MODEL=protectai/deberta-v3-base-prompt-injection-v2
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
AutoTokenizer.from_pretrained('$GUARDRAILS_CLASSIFIER_MODEL'); \
AutoModelForSequenceClassification.from_pretrained('$GUARDRAILS_CLASSIFIER_MODEL')"
ENV HF_HUB_OFFLINE=1

COPY app/ ./app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]