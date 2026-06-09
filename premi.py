import asyncio
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types


API_URL = "http://localhost:8080/intraasia_new/api-simulasi-kendaraan.php"
#Log file
LOG_FILE = Path(__file__).parent / "premi_mcp.log"

#Setup logging — tulis ke file sekaligus tampil di console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("premi-mcp")

app = Server("premi-asuransi")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="hitung_premi_kendaraan",
            description=(
                "Hitung simulasi premi asuransi kendaraan bermotor berdasarkan "
                "regulasi OJK (SE OJK No. 6/SEOJK.05/2017). "
                "Mengembalikan premi dasar, surcharge, benefit, dan total premi per tahun."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tipe_kendaraan": {
                        "type": "string",
                        "description": (
                            "Tipe kendaraan. Nilai: "
                            "'non-bus-non-truck' = Mobil/kendaraan umum, "
                            "'truck-pickup' = Truk/pickup, "
                            "'bus' = Bus, "
                            "'motor' = Sepeda motor"
                        ),
                        "enum": ["non-bus-non-truck", "truck-pickup", "bus", "motor"],
                    },
                    "region": {
                        "type": "string",
                        "description": (
                            "Region wilayah sesuai OJK. Nilai: "
                            "'region1' = Wilayah 1 (Sumatera & sekitarnya), "
                            "'region2' = Wilayah 2 (DKI Jakarta, Jabar, Banten), "
                            "'region3' = Wilayah 3 (Jawa & lainnya)"
                        ),
                        "enum": ["region1", "region2", "region3"],
                    },
                    "harga_pasar": {
                        "type": "number",
                        "description": "Harga pasar kendaraan dalam Rupiah, contoh: 250000000",
                    },
                    "tipe_asuransi": {
                        "type": "string",
                        "description": "Tipe asuransi: 'Comprehensive' (all risk) atau 'TLO' (Total Loss Only)",
                        "enum": ["Comprehensive", "TLO"],
                    },
                    "pilihan_rate": {
                        "type": "string",
                        "description": "Pilihan rate OJK: 'bawah' untuk rate minimum, 'atas' untuk rate maksimum",
                        "enum": ["bawah", "atas"],
                    },
                    "kegunaan": {
                        "type": "string",
                        "description": "Kegunaan kendaraan: 'non-komersial' untuk pribadi, 'komersial' untuk usaha",
                        "enum": ["non-komersial", "komersial"],
                    },
                    "benefits": {
                        "type": "array",
                        "description": (
                            "Daftar benefit tambahan. Kosongkan jika tidak ada: []. "
                            "Contoh nilai: 'flood-hurricane' (banjir/angin topan), 'authorized' (bengkel resmi), "
                            "'earthquake' (gempa bumi), 'riot' (kerusuhan), 'personal-accident-driver' (PA pengemudi)"
                        ),
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "pa_driver_price": {
                        "type": "number",
                        "description": "Nilai pertanggungan PA pengemudi dalam Rupiah. Isi 0 jika tidak ada.",
                        "default": 0,
                    },
                    "pa_passenger_price": {
                        "type": "number",
                        "description": "Nilai pertanggungan PA penumpang dalam Rupiah. Isi 0 jika tidak ada.",
                        "default": 0,
                    },
                    "third_party_price": {
                        "type": "number",
                        "description": "Nilai pertanggungan tanggung gugat pihak ketiga dalam Rupiah. Isi 0 jika tidak ada.",
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
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "hitung_premi_kendaraan":
        logger.warning(f"Tool tidak dikenal: {name}")
        return [types.TextContent(type="text", text=f"Tool '{name}' tidak ditemukan.")]

    # Set default optional fields
    payload = {
        "benefits": [],
        "pa_driver_price": 0,
        "pa_passenger_price": 0,
        "third_party_price": 0,
        **arguments,
    }

    logger.info(f"Request payload: {json.dumps(payload, ensure_ascii=False)}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")

            response.raise_for_status()
            data = response.json()

    except httpx.ConnectError as e:
        logger.error(f"ConnectError - tidak bisa konek ke {API_URL}: {e}")
        return [
            types.TextContent(
                type="text",
                text=(
                    f"Tidak bisa konek ke API: {API_URL}\n"
                    "Pastikan server PHP lokal kamu sudah berjalan."
                ),
            )
        ]
    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTPStatusError {e.response.status_code}: {e.response.text}\n"
            f"Payload yang dikirim: {json.dumps(payload, ensure_ascii=False)}"
        )
        return [
            types.TextContent(
                type="text",
                text=f"HTTP Error {e.response.status_code}: {e.response.text}",
            )
        ]
    except Exception as e:
        logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    # API success = false
    if not data.get("success"):
        logger.warning(f"API mengembalikan success=false: {json.dumps(data, ensure_ascii=False)}")
        return [
            types.TextContent(
                type="text",
                text=f"API mengembalikan error:\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            )
        ]

    logger.info("Perhitungan premi berhasil")

    result = data.get("result", {})
    inp = data.get("input", {})
    meta = data.get("meta", {})

    def rupiah(val):
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
  ─────────────────────────────
  TOTAL PREMI    : {rupiah(result.get('total_premi', 0))} / {result.get('total_premi_per', 'tahun')}

INFO
  Referensi : {meta.get('referensi', '-')}
  Catatan   : {meta.get('catatan', '-')}
"""

    benefit_rows = result.get("benefit_rows", [])
    if benefit_rows:
        output += "\n DETAIL BENEFIT\n"
        for b in benefit_rows:
            output += f"  - {b}\n"

    return [types.TextContent(type="text", text=output)]


async def main():
    logger.info(f"MCP Server premi-asuransi starting... (log: {LOG_FILE})")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())