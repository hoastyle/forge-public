FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/
COPY automation /app/automation

RUN uv sync --frozen --no-dev --extra server --extra llm

EXPOSE 8000

CMD ["python", "-m", "automation.pipeline", "serve", "--app-root", "/app", "--repo-root", "/var/lib/forge/repo", "--state-root", "/var/lib/forge/state", "--host", "0.0.0.0", "--port", "8000"]
