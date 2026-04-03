FROM istresearch/golden-image:python-3.12

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml .

# Install dependencies
RUN python -m venv --copies /app/venv \
 && . /app/venv/bin/activate \
 && pip install uv \
 && uv sync --active

ENV PATH="/app/venv/bin:$PATH"

# Copy the application code
COPY . .

# Expose the port (configurable via environment variable)
EXPOSE 3099

# Set environment variables
ENV PYTHONPATH=/app
ENV HTTP_SERVER_BIND_ADDRESS=0.0.0.0
ENV HTTP_SERVER_PORT=3099

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run via entrypoint (handles database generation if needed)
ENTRYPOINT ["/app/entrypoint.sh"]
