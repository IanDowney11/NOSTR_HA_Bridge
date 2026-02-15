ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18
FROM ${BUILD_FROM}

# Install build dependencies for Python packages that need compilation
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copy application source
COPY src/ /app/src/
COPY run.sh /app/

RUN chmod a+x /app/run.sh

WORKDIR /app

CMD ["/app/run.sh"]
