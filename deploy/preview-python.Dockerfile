# Trusted runtime only; no customer requirements or source in this build.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
RUN python -m pip install --no-cache-dir --disable-pip-version-check 'fastapi>=0.115.6,<1' 'uvicorn>=0.34.0,<1'
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
WORKDIR /workspace
