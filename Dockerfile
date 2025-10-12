# UBI9-based Dockerfile for running this project's interactive CLI
# - Uses UBI9 minimal base
# - Installs Python 3.9 and pip
# - Copies the repository into /app and installs python deps if present
# - Runs as non-root user and defaults to an interactive shell so you can
#   run the CLI and connect to a separate ramalama host container.

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.3

LABEL maintainer="GeoDerp"

# Install basic tools & bash for an interactive shell
RUN microdnf -y update \
 && microdnf -y install bash git tar podman \
 && microdnf clean all

# Create a non-root user to run the CLI
RUN useradd -u 1000 -m appuser || true

WORKDIR /app

# Copy project files. In typical usage you'll mount your workspace over /app
# during development to avoid rebuilding the image on every change.
COPY . /app

# Ensure /app is writable by the runtime user so the venv is created with
# correct ownership and doesn't point into /root.
RUN chown -R appuser:appuser /app || true

# Run the remaining setup steps as the non-root runtime user so uv installs
# into /home/appuser/.local and any created virtualenv references files under
# /home/appuser instead of /root.
USER appuser

ENV HOME=/home/appuser
ENV PATH=$HOME/.local/bin:$PATH

# Install uv (into the appuser's home) and create the virtualenv / install deps.
# Use POSIX-compatible dot (.) to source the env file in /bin/sh.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN $HOME/.local/bin/uv sync --dev
RUN $HOME/.local/bin/uv pip install ramalama || $HOME/.local/bin/uv pip install ramalama --use-feature=in-tree-build || true

# Run the packaged example using the venv python directly. Using uv as the
# entrypoint causes uv to perform sync/pip actions on start which can emit
# noise and interfere with tty/stdin behavior; running the venv python is
# simpler and more predictable for an interactive CLI inside a container.
ENTRYPOINT ["uv", "run", "research-agent", "--in-container"]
CMD ["--mode", "interactive"]