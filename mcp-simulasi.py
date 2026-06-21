import json
import logging
import os
import traceback
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# In Docker: PHP API runs on localhost:1234 (same container).
# Override with API_URL env var for other deployments.
API_URL = os.environ.get(
    "API_URL",
    "http://localhost:1234/api-simulasi-kendaraan.php",
)
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN")
LOG_FILE = Path(__file__).parent / "premi_mcp.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("premi-mcp")

mcp = FastMCP(
    "premi-asuransi",
    instructions=(
        "Server MCP untuk simulasi premi asuransi kendaraan bermotor "
        "PT Asuransi Intra Asia, sesuai tarif OJK SE No. 6/SEOJK.05/2017."
    ),
)

# ---------------------------------------------------------------------------
# Privas-compatible tool schema — used by GET /tools and POST /tools/call.
# Format: flat {paramName: {type, required, description, enum?, default?}}
# topic_hints drives automatic topic detection in the Privas inference layer.
# ---------------------------------------------------------------------------
_PRIVAS_TOOLS = [
    {
        "name": "hitung_premi_kendaraan",
        "description": (
            "Hitung simulasi premi asuransi kendaraan bermotor berdasarkan "
            "regulasi OJK (SE OJK No. 6/SEOJK.05/2017). "
            "Mengembalikan premi dasar, surcharge, benefit, dan total premi per tahun."
        ),
        "parameters": {
            "tipe_kendaraan": {
                "type": "string",
                "required": True,
                "description": (
                    "Tipe kendaraan: non-bus-non-truck (Mobil), "
                    "truck-pickup (Truk/Pickup), bus (Bus), motor (Sepeda Motor)"
                ),
                "enum": ["non-bus-non-truck", "truck-pickup", "bus", "motor"],
            },
            "region": {
                "type": "string",
                "required": True,
                "description": (
                    "Wilayah OJK: region1 (Sumatera & sekitarnya), "
                    "region2 (DKI Jakarta, Jabar, Banten), region3 (Jawa & lainnya)"
                ),
                "enum": ["region1", "region2", "region3"],
            },
            "harga_pasar": {
                "type": "number",
                "required": True,
                "description": "Harga pasar kendaraan dalam Rupiah, contoh: 250000000",
            },
            "tipe_asuransi": {
                "type": "string",
                "required": True,
                "description": "Tipe asuransi: Comprehensive (all risk) atau TLO (Total Loss Only)",
                "enum": ["Comprehensive", "TLO"],
            },
            "pilihan_rate": {
                "type": "string",
                "required": True,
                "description": "Pilihan tarif OJK: bawah (rate minimum) atau atas (rate maksimum)",
                "enum": ["bawah", "atas"],
            },
            "kegunaan": {
                "type": "string",
                "required": True,
                "description": "Kegunaan kendaraan: non-komersial (pribadi) atau komersial (usaha)",
                "enum": ["non-komersial", "komersial"],
            },
            "benefits": {
                "type": "string",
                "required": False,
                "description": (
                    "Daftar benefit tambahan dipisah koma. Kosongkan jika tidak ada. "
                    "Pilihan: flood-hurricane, earthquake-tsunami, strike-riot, "
                    "terrorism-sabotage, personal-accident-driver, "
                    "personal-accident-passenger, liability, authorized"
                ),
                "default": "",
            },
            "pa_driver_price": {
                "type": "number",
                "required": False,
                "description": "Nilai pertanggungan PA pengemudi (Rupiah). Default 0.",
                "default": 0,
            },
            "pa_passenger_price": {
                "type": "number",
                "required": False,
                "description": "Nilai pertanggungan PA penumpang per seat (Rupiah). Default 0.",
                "default": 0,
            },
            "third_party_price": {
                "type": "number",
                "required": False,
                "description": "Nilai pertanggungan tanggung gugat pihak ketiga (Rupiah). Default 0.",
                "default": 0,
            },
        },
        "topic_hints": [
            "premi",
            "asuransi",
            "kendaraan",
            "simulasi premi",
            "intra asia",
            "asuransi kendaraan",
            "motor",
            "mobil",
            "tlo",
            "comprehensive",
            "ojk",
        ],
        # Display contract for the Privas chat result card: per result field
        # (from _build_result_dict below) — label + format so the card renders
        # with our own labels/units, no guessing on the platform side.
        # format ∈ {currency, percent, number, relative, text}; empty_text shows
        # a natural-language note instead of hiding an empty value; hidden=true
        # excludes a non-scalar field from the card (still in the raw dump).
        "output_fields": {
            "tipe_kendaraan": {"label": "Tipe Kendaraan", "format": "text"},
            "region": {"label": "Wilayah", "format": "text"},
            "kegunaan": {"label": "Kegunaan", "format": "text"},
            "tipe_asuransi": {"label": "Tipe Asuransi", "format": "text"},
            "harga_pasar": {"label": "Harga Pasar Kendaraan", "format": "currency"},
            "ojk_rate_pct": {"label": "Rate OJK", "format": "percent"},
            "premi_dasar": {"label": "Premi Dasar", "format": "currency"},
            "surcharge_komersial": {"label": "Surcharge Komersial", "format": "currency"},
            "premi_benefit": {"label": "Premi Benefit", "format": "currency"},
            "biaya_admin": {"label": "Biaya Admin", "format": "currency"},
            "total_premi": {"label": "Total Premi", "format": "currency"},
            "total_premi_per": {"label": "Periode Premi", "format": "text"},
            # Array of benefit objects {id,label,rate,formula,amount,note} — not a
            # scalar, so keep it out of the summary card (visible in the raw dump
            # and already enumerated in the AI's prose answer).
            "benefit_rows": {"label": "Rincian Benefit", "hidden": True},
            "referensi": {"label": "Referensi", "format": "text"},
            "catatan": {"label": "Catatan", "format": "text"},
        },
        "trigger_intent": "simulasi_premi_kendaraan",
        "version": "2.0",
    }
]

# MCP SSE native schema — used by FastMCP tool registration (inputSchema format).
_TOOLS_SCHEMA = [
    {
        "name": "hitung_premi_kendaraan",
        "description": (
            "Hitung simulasi premi asuransi kendaraan bermotor berdasarkan "
            "regulasi OJK (SE OJK No. 6/SEOJK.05/2017). "
            "Mengembalikan premi dasar, surcharge, benefit, dan total premi per tahun."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tipe_kendaraan": {
                    "type": "string",
                    "enum": ["non-bus-non-truck", "truck-pickup", "bus", "motor"],
                    "description": (
                        "Tipe kendaraan: "
                        "non-bus-non-truck (Mobil), truck-pickup (Truk/Pickup), "
                        "bus (Bus), motor (Sepeda Motor)"
                    ),
                },
                "region": {
                    "type": "string",
                    "enum": ["region1", "region2", "region3"],
                    "description": (
                        "Wilayah OJK: "
                        "region1 (Sumatera & sekitarnya), "
                        "region2 (DKI Jakarta, Jabar, Banten), "
                        "region3 (Jawa & lainnya)"
                    ),
                },
                "harga_pasar": {
                    "type": "number",
                    "description": "Harga pasar kendaraan dalam Rupiah, contoh: 250000000",
                },
                "tipe_asuransi": {
                    "type": "string",
                    "enum": ["Comprehensive", "TLO"],
                    "description": "Tipe asuransi: Comprehensive (all risk) atau TLO (Total Loss Only)",
                },
                "pilihan_rate": {
                    "type": "string",
                    "enum": ["bawah", "atas"],
                    "description": "Pilihan tarif OJK: bawah (rate minimum) atau atas (rate maksimum)",
                },
                "kegunaan": {
                    "type": "string",
                    "enum": ["non-komersial", "komersial"],
                    "description": "Kegunaan kendaraan: non-komersial (pribadi) atau komersial (usaha)",
                },
                "benefits": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "flood-hurricane",
                            "earthquake-tsunami",
                            "strike-riot",
                            "terrorism-sabotage",
                            "personal-accident-driver",
                            "personal-accident-passenger",
                            "liability",
                            "authorized",
                        ],
                    },
                    "description": "Daftar benefit tambahan. Kosongkan jika tidak ada.",
                    "default": [],
                },
                "pa_driver_price": {
                    "type": "number",
                    "description": "Nilai pertanggungan PA pengemudi (Rupiah). Default 0.",
                    "default": 0,
                },
                "pa_passenger_price": {
                    "type": "number",
                    "description": "Nilai pertanggungan PA penumpang per seat (Rupiah). Default 0.",
                    "default": 0,
                },
                "third_party_price": {
                    "type": "number",
                    "description": "Nilai pertanggungan tanggung gugat pihak ketiga (Rupiah). Default 0.",
                    "default": 0,
                },
            },
            "required": [
                "tipe_kendaraan",
                "region",
                "harga_pasar",
                "tipe_asuransi",
                "pilihan_rate",
                "kegunaan",
            ],
        },
    }
]


# ---------------------------------------------------------------------------
# Auth helper — shared by /tools and /tools/call (not /health)
# ---------------------------------------------------------------------------

def _check_auth(request: Request):
    """Returns a 401 JSONResponse if Bearer auth fails, None if OK."""
    if not MCP_AUTH_TOKEN:
        return None
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {MCP_AUTH_TOKEN}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return None


# ---------------------------------------------------------------------------
# Core PHP API caller — shared by FastMCP tool and REST /tools/call
# ---------------------------------------------------------------------------

async def _call_php_api(payload: dict) -> dict:
    """POST to PHP pricing API and return the parsed JSON response."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


def _format_premi_text(data: dict) -> str:
    """Format PHP API response as a human-readable string (for MCP SSE clients)."""
    result = data.get("result", {})
    inp = data.get("input", {})
    meta = data.get("meta", {})

    def rupiah(val: float) -> str:
        return f"Rp {int(val):,}".replace(",", ".")

    output = f"""Hasil Simulasi Premi Asuransi Kendaraan
{'='*50}
KENDARAAN
  Tipe     : {inp.get('tipe_kendaraan_label', '-')}
  Region   : {inp.get('region_label', '-')}
  Kegunaan : {inp.get('kegunaan', '-')}
  Asuransi : {inp.get('tipe_asuransi', '-').upper()}
  Harga Pasar: {rupiah(inp.get('harga_pasar', 0))}

HASIL PERHITUNGAN
  Rate OJK       : {result.get('ojk_rate_pct', 0)}%
  Premi Dasar    : {rupiah(result.get('premi_dasar', 0))}
  Surcharge      : {rupiah(result.get('surcharge_komersial', 0))}
  Premi Benefit  : {rupiah(result.get('premi_benefit', 0))}
  Biaya Admin    : {rupiah(result.get('biaya_admin', 0))}
  ─────────────────────────────────────────────
  TOTAL PREMI    : {rupiah(result.get('total_premi', 0))} / {result.get('total_premi_per', 'tahun')}

INFO
  Referensi : {meta.get('referensi', '-')}
  Catatan   : {meta.get('catatan', '-')}
"""
    benefit_rows = result.get("benefit_rows", [])
    if benefit_rows:
        output += "\nDETAIL BENEFIT\n"
        for b in benefit_rows:
            output += f"  - {b}\n"
    return output


def _build_result_dict(data: dict, args: dict) -> dict:
    """Convert PHP API response to a structured dict for REST /tools/call."""
    result = data.get("result", {})
    inp = data.get("input", {})
    meta = data.get("meta", {})
    return {
        "tipe_kendaraan": inp.get("tipe_kendaraan_label", args.get("tipe_kendaraan")),
        "region": inp.get("region_label", args.get("region")),
        "kegunaan": inp.get("kegunaan", args.get("kegunaan")),
        "tipe_asuransi": inp.get("tipe_asuransi", args.get("tipe_asuransi")),
        "harga_pasar": inp.get("harga_pasar", args.get("harga_pasar")),
        "ojk_rate_pct": result.get("ojk_rate_pct"),
        "premi_dasar": result.get("premi_dasar"),
        "surcharge_komersial": result.get("surcharge_komersial"),
        "premi_benefit": result.get("premi_benefit"),
        "biaya_admin": result.get("biaya_admin"),
        "total_premi": result.get("total_premi"),
        "total_premi_per": result.get("total_premi_per", "tahun"),
        "benefit_rows": result.get("benefit_rows", []),
        "referensi": meta.get("referensi"),
        "catatan": meta.get("catatan"),
    }


# ---------------------------------------------------------------------------
# FastMCP tool — for SSE/MCP native clients
# ---------------------------------------------------------------------------

@mcp.tool()
async def hitung_premi_kendaraan(
    tipe_kendaraan: str,
    region: str,
    harga_pasar: float,
    tipe_asuransi: str,
    pilihan_rate: str,
    kegunaan: str,
    benefits: list[str] = [],
    pa_driver_price: float = 0,
    pa_passenger_price: float = 0,
    third_party_price: float = 0,
) -> str:
    """
    Hitung simulasi premi asuransi kendaraan bermotor (OJK SE No. 6/SEOJK.05/2017).

    tipe_kendaraan: non-bus-non-truck | truck-pickup | bus | motor
    region: region1 (Sumatera) | region2 (DKI/Jabar/Banten) | region3 (Jawa & lainnya)
    tipe_asuransi: Comprehensive | TLO
    pilihan_rate: bawah (minimum) | atas (maksimum)
    kegunaan: non-komersial | komersial
    benefits: flood-hurricane | earthquake-tsunami | strike-riot | terrorism-sabotage |
              personal-accident-driver | personal-accident-passenger | liability | authorized
    """
    payload = {
        "tipe_kendaraan": tipe_kendaraan,
        "region": region,
        "harga_pasar": harga_pasar,
        "tipe_asuransi": tipe_asuransi,
        "pilihan_rate": pilihan_rate,
        "kegunaan": kegunaan,
        "benefits": benefits,
        "pa_driver_price": pa_driver_price,
        "pa_passenger_price": pa_passenger_price,
        "third_party_price": third_party_price,
    }

    logger.info(f"[SSE] Request: {json.dumps(payload, ensure_ascii=False)}")

    try:
        data = await _call_php_api(payload)
    except httpx.ConnectError:
        return f"Tidak bisa konek ke API: {API_URL}. Pastikan server PHP sudah berjalan."
    except httpx.HTTPStatusError as e:
        return f"HTTP Error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        logger.error(traceback.format_exc())
        return f"Error tidak terduga: {str(e)}"

    if not data.get("success"):
        return f"API mengembalikan error:\n{json.dumps(data, indent=2, ensure_ascii=False)}"

    logger.info("[SSE] Perhitungan premi berhasil")
    return _format_premi_text(data)


# ---------------------------------------------------------------------------
# REST endpoints — compatible with Privas MCP integration layer
# ---------------------------------------------------------------------------

@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Request) -> JSONResponse:
    """Liveness check. No auth required. Privas calls this to verify connectivity."""
    php_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(API_URL, timeout=3.0)
            php_status = "ok" if r.status_code < 500 else "error"
    except Exception:
        php_status = "error"

    return JSONResponse({
        "status": "ok",
        "version": "2.0.0",
        "tools_count": 1,
        "php_backend": php_status,
    })


@mcp.custom_route("/tools", methods=["GET"])
async def tools_endpoint(request: Request) -> JSONResponse:
    """
    REST tool discovery for Privas platform (GET /tools).
    Returns a bare JSON array — NOT wrapped in {"tools": [...]}.
    Each tool uses flat {paramName: {type, required, ...}} parameters format.
    """
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err
    return JSONResponse(_PRIVAS_TOOLS)


@mcp.custom_route("/tools/call", methods=["POST"])
async def tools_call_endpoint(request: Request) -> JSONResponse:
    """
    REST tool execution for Privas platform (POST /tools/call).
    Body: {"tool_name": str, "args": dict}
    Response: {"success": true, "result": dict} | {"success": false, "error": {"type", "message"}}
    """
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"type": "invalid_request", "message": "Invalid JSON body"}},
            status_code=400,
        )

    tool_name = body.get("tool_name", "")
    args = body.get("args") or {}

    if tool_name != "hitung_premi_kendaraan":
        return JSONResponse({
            "success": False,
            "error": {"type": "tool_not_found", "message": f"Unknown tool: {tool_name}"},
        })

    # Normalize benefits: Privas passes a list; accept both list and comma-string for safety
    benefits_raw = args.get("benefits", [])
    if isinstance(benefits_raw, str):
        benefits = [b.strip() for b in benefits_raw.split(",") if b.strip()]
    else:
        benefits = list(benefits_raw) if benefits_raw else []

    payload = {
        "tipe_kendaraan": args.get("tipe_kendaraan"),
        "region": args.get("region"),
        "harga_pasar": args.get("harga_pasar"),
        "tipe_asuransi": args.get("tipe_asuransi"),
        "pilihan_rate": args.get("pilihan_rate"),
        "kegunaan": args.get("kegunaan"),
        "benefits": benefits,
        "pa_driver_price": args.get("pa_driver_price", 0),
        "pa_passenger_price": args.get("pa_passenger_price", 0),
        "third_party_price": args.get("third_party_price", 0),
    }

    logger.info(f"[REST] /tools/call tool={tool_name} args={json.dumps(payload, ensure_ascii=False)}")

    try:
        data = await _call_php_api(payload)
    except httpx.ConnectError:
        return JSONResponse({
            "success": False,
            "error": {"type": "connection_error", "message": f"Cannot connect to PHP API: {API_URL}"},
        })
    except httpx.HTTPStatusError as e:
        return JSONResponse({
            "success": False,
            "error": {"type": "upstream_error", "message": f"HTTP {e.response.status_code}"},
        })
    except Exception as e:
        logger.error(traceback.format_exc())
        return JSONResponse({
            "success": False,
            "error": {"type": "unexpected_error", "message": str(e)},
        })

    if not data.get("success"):
        return JSONResponse({
            "success": False,
            "error": {
                "type": "api_error",
                "message": data.get("message", "PHP API returned error"),
            },
        })

    result_dict = _build_result_dict(data, args)
    logger.info(f"[REST] /tools/call success total_premi={result_dict.get('total_premi')}")
    return JSONResponse({"success": True, "result": result_dict})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    logger.info(f"Starting premi-asuransi MCP HTTP server on port {port} (log: {LOG_FILE})")
    mcp.run(transport="sse")
