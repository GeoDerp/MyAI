# UBI9-based Dockerfile for running the Deep Research Agent API
# - Uses UBI9 minimal base
# - Installs Python 3.9 and pip
# - Copies the repository into /app and installs python deps
# - Runs as non-root user and starts the FastAPI server

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.3

LABEL maintainer="GeoDerp"

# Install basic tools & bash for an interactive shell
RUN microdnf -y update \
 && microdnf -y install bash git tar python39 python39-pip \
 && microdnf clean all

# Create a non-root user to run the application
RUN useradd -u 1000 -m appuser || true

WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip3 install --no-cache-dir -e .

# Ensure /app is writable by the runtime user
RUN chown -R appuser:appuser /app || true

# Make entrypoint executable
RUN chmod +x /app/scripts/entrypoint.sh || true

# Switch to the non-root user
USER appuser

# Expose the ports for API and web UI
EXPOSE 8000 8081

# Default to server mode; support 'cli' and 'webui' via entrypoint args
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["server"]