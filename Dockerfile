ARG BUILD_FROM=docker.io/library/python:3.11-slim-bookworm
FROM ${BUILD_FROM}

# Create non-root user for runtime
RUN groupadd -r bridge && useradd -r -g bridge -s /sbin/nologin bridge

# Install gosu for dropping privileges at runtime
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copy application source
COPY src/ /app/src/
COPY run.sh /app/

RUN chmod a+x /app/run.sh && chown -R bridge:bridge /app

WORKDIR /app

CMD ["/app/run.sh"]
