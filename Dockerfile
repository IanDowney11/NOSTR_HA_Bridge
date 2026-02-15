ARG BUILD_FROM=docker.io/library/python:3.11-slim-bookworm
FROM ${BUILD_FROM}

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copy application source
COPY src/ /app/src/
COPY run.sh /app/

RUN chmod a+x /app/run.sh

WORKDIR /app

CMD ["python3", "-m", "src.main"]
