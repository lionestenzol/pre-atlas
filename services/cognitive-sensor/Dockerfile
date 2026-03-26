FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pip -U

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

CMD ["python", "run_daily.py"]
