FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . /app

ENV UV_NO_DEV=1

RUN uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8083", "--reload"]