FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS api-server

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app/llm-cp-server

COPY llm-cp-server/pyproject.toml llm-cp-server/uv.lock llm-cp-server/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY llm-cp-server/ ./
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "llm-cp", "server", "start"]

FROM node:22-alpine AS dashboard-build

WORKDIR /app/dashboard
ARG VITE_API_BASE_URL
ARG VITE_API_PORT
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_PORT=$VITE_API_PORT

COPY dashboard/package.json dashboard/package-lock.json dashboard/.npmrc ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build

FROM nginx:1.27-alpine AS dashboard

COPY --from=dashboard-build /app/dashboard/dist /usr/share/nginx/html
EXPOSE 80
