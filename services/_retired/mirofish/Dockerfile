FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pip -U

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 3003

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import httpx; r=httpx.get('http://localhost:3003/api/v1/health'); exit(0 if r.status_code==200 else 1)"

CMD ["python", "-m", "mirofish.main"]
