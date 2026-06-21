# premi-asuransi MCP Server

MCP (Model Context Protocol) server for vehicle insurance premium simulation — PT Asuransi Intra Asia.  
Implements OJK regulation **SE OJK No. 6/SEOJK.05/2017**.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Container               │
│                                             │
│  ┌────────────────────┐                     │
│  │  mcp-simulasi.py   │ :8000  ◄── clients  │
│  │  (FastMCP / SSE)   │                     │
│  └─────────┬──────────┘                     │
│            │ HTTP POST (internal)            │
│  ┌─────────▼──────────┐                     │
│  │ api-simulasi-       │ :1234  (internal)   │
│  │ kendaraan.php       │                     │
│  └────────────────────┘                     │
└─────────────────────────────────────────────┘
```

| Service | Port | Description |
|---|---|---|
| MCP HTTP server | `8000` | Public — SSE transport + REST `/tools` |
| PHP pricing API | `1234` | Internal — premium calculation engine |

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/sse` | MCP SSE connection (MCP clients) |
| `POST` | `/messages/` | MCP message posting |
| `GET` | `/tools` | REST tool discovery (platform sync) |
| `GET` | `/health` | Health check (PHP backend) |

## Tool

### `hitung_premi_kendaraan`

Calculates vehicle insurance premium based on OJK tariff tables.

**Required parameters:**

| Parameter | Type | Values |
|---|---|---|
| `tipe_kendaraan` | string | `non-bus-non-truck` \| `truck-pickup` \| `bus` \| `motor` |
| `region` | string | `region1` (Sumatera) \| `region2` (DKI/Jabar/Banten) \| `region3` (Jawa & lainnya) |
| `harga_pasar` | number | Market value in IDR, e.g. `250000000` |
| `tipe_asuransi` | string | `Comprehensive` \| `TLO` |
| `pilihan_rate` | string | `bawah` (minimum rate) \| `atas` (maximum rate) |
| `kegunaan` | string | `non-komersial` \| `komersial` |

**Optional parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `benefits` | string[] | `[]` | `flood-hurricane`, `earthquake-tsunami`, `strike-riot`, `terrorism-sabotage`, `personal-accident-driver`, `personal-accident-passenger`, `liability`, `authorized` |
| `pa_driver_price` | number | `0` | Personal accident driver coverage (IDR) |
| `pa_passenger_price` | number | `0` | Personal accident passenger coverage per seat (IDR) |
| `third_party_price` | number | `0` | Third-party liability coverage (IDR) |

**Result display metadata (`output_fields`):**

`GET /tools` also returns an `output_fields` map so the Privas chat result card renders each
result field with the right label/format — the platform does no per-tool guessing. Keep it in sync
with the keys returned by `_build_result_dict`.

| Key in `output_fields` | Meaning |
|---|---|
| `label` | Display label for the field |
| `format` | `currency` (IDR) \| `percent` \| `number` \| `relative` (time) \| `text` |
| `empty_text` | Note shown instead of hiding the row when the value is empty |
| `hidden` | `true` to keep a non-scalar field (e.g. `benefit_rows`, an array of objects) out of the summary card — it still appears in the card's "Detail Tool" raw dump |

Here `harga_pasar`/`premi_*`/`total_premi`/`biaya_admin`/`surcharge_komersial` use `currency`,
`ojk_rate_pct` uses `percent`, and `benefit_rows` is `hidden`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | MCP server listening port |
| `PHP_PORT` | `1234` | Internal PHP API port |
| `API_URL` | `http://localhost:1234/api-simulasi-kendaraan.php` | Full URL to the PHP pricing API |

## Quickstart — Docker

### Build

```bash
docker build -t premi-asuransi-mcp .
```

### Run

```bash
docker run -d \
  --name premi-mcp \
  -p 8000:8000 \
  premi-asuransi-mcp
```

Verify the server is up:

```bash
# Tool discovery
curl http://localhost:8000/tools

# PHP backend health
curl http://localhost:8000/health   # proxied via router.php
```

### Custom environment

```bash
docker run -d \
  --name premi-mcp \
  -p 8000:8000 \
  -e PORT=8000 \
  -e PHP_PORT=1234 \
  premi-asuransi-mcp
```

### Logs

```bash
docker logs -f premi-mcp
```

## Local Development

### Prerequisites

- Python 3.13+
- PHP 8.x CLI

### Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Terminal 1 — start PHP API
php -S 0.0.0.0:1234 router.php

# Terminal 2 — start MCP server
python mcp-simulasi.py
```

For a local XAMPP/Laragon environment, override `API_URL`:

```bash
API_URL="http://localhost:8080/intraasia_new/api-simulasi-kendaraan.php" python mcp-simulasi.py
```

## Running Tests

```bash
pip install pytest pytest-asyncio
python -m pytest test_mcp_simulasi.py -v
```

Expected output: **19 passed**.

Tests cover:

- `GET /tools` — status, content-type, schema, POST → 405
- Tool registration and enum schema
- Happy path: total premium, labels, format, benefit detail
- Error handling: `ConnectError`, `HTTPStatusError`, `success=false`, unexpected exception

## Deployment Notes

- Only port `8000` needs to be exposed publicly — the PHP API on `:1234` stays internal.
- The `/tools` endpoint allows platforms (e.g. privas.ai) to sync tool definitions via `GET /tools`.
- The MCP SSE connection is at `/sse`; clients post messages to `/messages/`.
- Log file is written to `premi_mcp.log` in the working directory. Mount a volume if log persistence is needed:
  ```bash
  docker run -d -p 8000:8000 -v $(pwd)/logs:/app premi-asuransi-mcp
  ```
