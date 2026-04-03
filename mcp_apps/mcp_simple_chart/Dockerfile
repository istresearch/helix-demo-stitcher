FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY mcp_server/ ./mcp_server/

EXPOSE 3100

CMD ["python", "-m", "mcp_server.server"]
