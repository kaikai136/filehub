# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-build
WORKDIR /src

COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
RUN npm run build

FROM python:3.12-slim AS backend
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

FROM nginx:1.27-alpine AS frontend
COPY --from=frontend-build /src/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
