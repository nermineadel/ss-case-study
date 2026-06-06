# --- Stage 1: Build & Dependencies ---
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Minimal Runtime Execution Container ---
FROM python:3.11-slim AS runtime
WORKDIR /app

# Non-root user setup for secure cluster runtime environments
RUN useradd -u 10001 appuser && mkdir -p /app/public && chown -R appuser:appuser /app
USER appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY --allownonroot=appuser app.py .

ENV PATH=/home/appuser/.local/bin:$PATH
EXPOSE 8080

CMD ["python", "app.py"]
