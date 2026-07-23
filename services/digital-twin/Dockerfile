# Canonical service Dockerfile  Eevery service under services/ copies this pattern
# (scripts/new-service.sh substitutes only the service name and its extra dependencies).
#
# Build context is the REPO ROOT, not this directory (see
# infra/docker-compose/docker-compose.yml's build.context/build.dockerfile) --
# this service's pyproject.toml references shared packages via a relative
# Poetry path dependency (e.g. `../../libs/api-common`), which only resolves
# if libs/ is actually reachable from here. Copying libs/ to /libs (two
# levels above /app, exactly like /libs is two levels above services/digital-twin/
# in the source tree) makes that relative path resolve identically inside
# the image.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false
RUN pip install --no-cache-dir poetry==1.8.4

COPY libs/ /libs/

WORKDIR /app
COPY services/digital-twin/pyproject.toml services/digital-twin/poetry.lock* ./
RUN poetry install --no-root --only main

COPY services/digital-twin/ .

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
