#!/bin/sh
set -e

PHP_PORT="${PHP_PORT:-1234}"
PORT="${PORT:-8000}"

echo "[entrypoint] Starting PHP API backend on port ${PHP_PORT}..."
php -S "0.0.0.0:${PHP_PORT}" router.php &

# Give PHP a moment to bind the port before MCP server starts accepting calls
sleep 1

echo "[entrypoint] Starting MCP HTTP server on port ${PORT}..."
exec python mcp-simulasi.py
