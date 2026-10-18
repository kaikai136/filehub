FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY deploy/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/backend-entrypoint \
    && chmod +x /usr/local/bin/backend-entrypoint \
    && mkdir -p /data /app/backend/staticfiles

EXPOSE 8000
ENTRYPOINT ["backend-entrypoint"]
