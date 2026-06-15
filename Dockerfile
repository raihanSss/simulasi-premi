FROM python:3.13-slim

# Install PHP CLI for the internal pricing-API backend
RUN apt-get update \
    && apt-get install -y --no-install-recommends php-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies — separate layer for better cache reuse
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# PHP API backend files
COPY api-simulasi-kendaraan.php router.php ./

# Documentation (served as static files via router.php)
COPY api-simulasi-kendaraan.yaml api-simulasi-kendaraan.md ./

# MCP server + entrypoint
COPY mcp-simulasi.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# MCP HTTP server (SSE transport)
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
