ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

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
