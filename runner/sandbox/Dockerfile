FROM python:3.12-alpine
COPY --chown=65534:65534 launcher.py /opt/aia/launcher.py
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "-B", "-u", "/opt/aia/launcher.py"]
