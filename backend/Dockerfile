FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
ARG INSTALL_VOICE=0
# Voice mode (local speech-to-text and text-to-speech) adds about 400 MB; build with INSTALL_VOICE=1 to include it.
RUN mkdir -p app && touch app/__init__.py && pip install ".$( [ "$INSTALL_VOICE" = "1" ] && echo '[voice]' )"
COPY app ./app
COPY scripts ./scripts
# Run as an unprivileged user; data and uploads live on volumes owned by it.
RUN useradd --create-home --uid 1000 appuser && mkdir -p data uploads && chown -R appuser:appuser /srv
USER appuser
VOLUME ["/srv/data", "/srv/uploads"]
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
