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

    logger.info(f"Request: {json.dumps(payload, ensure_ascii=False)}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError:
        return f"Tidak bisa konek ke API: {API_URL}. Pastikan server PHP sudah berjalan."
    except httpx.HTTPStatusError as e:
        return f"HTTP Error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        logger.error(traceback.format_exc())
        return f"Error tidak terduga: {str(e)}"

    if not data.get("success"):
        return f"API mengembalikan error:\n{json.dumps(data, indent=2, ensure_ascii=False)}"

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

    logger.info("Perhitungan premi berhasil")
    return output


@mcp.custom_route("/tools", methods=["GET"])
async def tools_endpoint(request: Request) -> JSONResponse:
    """REST endpoint untuk tool discovery (kompatibilitas platform privas.ai)."""
    return JSONResponse({"tools": _TOOLS_SCHEMA})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting premi-asuransi MCP HTTP server on port {port} (log: {LOG_FILE})")
    mcp.run(transport="sse", host="0.0.0.0", port=port)
