FROM python:3.11.10-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN echo 'Acquire::http::Pipeline-Depth 0;\nAcquire::http::No-Cache true;\nAcquire::BrokenProxy true;\n' > /etc/apt/apt.conf.d/99fixbadproxy
RUN apt-get update --allow-releaseinfo-change --fix-missing

# Install build dependencies
RUN apt-get install -y build-essential libpq5 libz-dev libssl-dev postgresql-client

ENV POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH=/opt/poetry/bin:$PATH

RUN pip3 install --upgrade pip setuptools
RUN pip3 install poetry

# Copy and install dependencies
COPY autogpt_libs /app/autogpt_platform/autogpt_libs
COPY backend/poetry.lock backend/pyproject.toml /app/autogpt_platform/backend/
WORKDIR /app/autogpt_platform/backend
RUN poetry install --no-ansi --no-root

# Generate Prisma client
COPY backend/schema.prisma ./
RUN poetry run prisma generate

# ========== STAGE 2 ========== #
FROM python:3.11.10-slim-bookworm AS server_dependencies

WORKDIR /app

ENV POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH=/opt/poetry/bin:$PATH

RUN pip3 install --upgrade pip setuptools
RUN pip3 install poetry

COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/prisma-python/binaries /root/.cache/prisma-python/binaries

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/autogpt_platform/autogpt_libs /app/autogpt_platform/backend

COPY autogpt_libs /app/autogpt_platform/autogpt_libs
COPY backend/poetry.lock backend/pyproject.toml /app/autogpt_platform/backend/
WORKDIR /app/autogpt_platform/backend

# ========== STAGE 3 ========== #
FROM server_dependencies AS server

COPY backend /app/autogpt_platform/backend
RUN poetry install --no-ansi --only-root
RUN pip install beautifulsoup4
RUN pip install requests

ENV DATABASE_URL=""
ENV PORT=8000

CMD ["poetry", "run", "rest"]
