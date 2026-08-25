FROM python:3.11-slim
WORKDIR /app
ARG BUILD_DATE=
ARG GIT_SHA=unknown
ARG GIT_REF=unknown
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
RUN mkdir -p /data \
 && BD="$BUILD_DATE"; \
    if [ -z "$BD" ] || [ "$BD" = "unknown" ]; then BD=$(date -u +%Y-%m-%dT%H:%M:%SZ); fi; \
    printf '%s' "$BD" > /app/BUILD_DATE \
 && printf '%s' "$GIT_SHA" > /app/GIT_SHA \
 && printf '%s' "$GIT_REF" > /app/GIT_REF
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
