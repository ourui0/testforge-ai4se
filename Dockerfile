FROM python:3.12-slim AS runtime
RUN useradd --uid 10001 --create-home testforge
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN python -m pip install --no-cache-dir .
USER 10001
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "testforge.web.app:create_demo_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
