# ClipFlow notifier: outbound-only Telegram alerts (change 066).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd --system --uid 10001 --no-create-home notifier
COPY notifier.py .
# 142: shared/ (digest, payouts, campaigns, …) from the compose additional_contexts entry
COPY --from=shared . /app/shared
ENV PYTHONPATH=/app

# State lives in /data/notifier (host dir must be writable by uid 10001).
USER 10001
CMD ["python", "-u", "/app/notifier.py"]
