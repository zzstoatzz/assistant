FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1

COPY instructions.md .
COPY main.py .

CMD ["uv", "run", "main.py"]