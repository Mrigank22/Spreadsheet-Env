# OpenEnv server image: docker build -f docker/server/Dockerfile -t spreadsheet-env .
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY spreadsheet_env ./spreadsheet_env
RUN pip install --no-cache-dir .
ENV SSE_MAX_SESSIONS=16
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "spreadsheet_env.server.app", "--host", "0.0.0.0", "--port", "8000"]
