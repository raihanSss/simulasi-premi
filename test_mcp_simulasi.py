"""
Unit tests for mcp-simulasi.py — FastMCP premi asuransi server.
"""
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Load module (filename has a hyphen, so standard import won't work)
# ---------------------------------------------------------------------------
_MODULE_PATH = Path(__file__).parent / "mcp-simulasi.py"
_spec = importlib.util.spec_from_file_location("mcp_simulasi", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

mcp = _mod.mcp
hitung_premi_kendaraan = _mod.hitung_premi_kendaraan
_TOOLS_SCHEMA = _mod._TOOLS_SCHEMA

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_API_SUCCESS = {
    "success": True,
    "input": {
        "tipe_kendaraan": "non-bus-non-truck",
        "tipe_kendaraan_label": "Non Bus & Non Truck",
        "region": "region2",
        "region_label": "Region 2 (Jakarta, Banten, Jawa Barat)",
        "kegunaan": "non-komersial",
        "tipe_asuransi": "Comprehensive",
        "pilihan_rate": "bawah",
        "harga_pasar": 300000000,
        "pa_driver_price": 0,
        "pa_passenger_price": 0,
        "third_party_price": 0,
        "benefits": [],
    },
    "result": {
        "ojk_rate_pct": 2.08,
        "premi_dasar": 6240000,
        "surcharge_komersial": 0,
        "premi_benefit": 0,
        "biaya_admin": 0,
        "total_premi": 6240000,
        "total_premi_per": "tahun",
        "benefit_rows": [],
    },
    "meta": {
        "referensi": "SE OJK No. 6/SEOJK.05/2017",
        "catatan": "Estimasi indikatif.",
        "timestamp": "2026-06-15T10:00:00+07:00",
    },
}

MOCK_API_WITH_BENEFITS = {
    **MOCK_API_SUCCESS,
    "result": {
        **MOCK_API_SUCCESS["result"],
        "premi_benefit": 225000,
        "total_premi": 6465000,
        "benefit_rows": [
            {
                "id": "flood-hurricane",
                "label": "Banjir, Angin Topan & Badai",
                "rate": 0.075,
                "formula": "0.075% × Rp 300.000.000",
                "amount": 225000,
                "note": "",
            }
        ],
    },
}


def _make_mock_response(data: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = 200
    return mock_resp


def _patch_httpx(response_data: dict):
    """Context manager: mock httpx.AsyncClient.post to return response_data."""
    mock_resp = _make_mock_response(response_data)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=mock_ctx)


# ===========================================================================
# HTTP endpoint tests (GET /tools)
# ===========================================================================

@pytest.mark.asyncio
async def test_tools_endpoint_status_200():
    app = mcp.sse_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tools")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tools_endpoint_content_type_json():
    app = mcp.sse_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tools")
    assert "application/json" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_tools_endpoint_returns_tools_key():
    app = mcp.sse_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tools")
    body = resp.json()
    assert "tools" in body


@pytest.mark.asyncio
async def test_tools_endpoint_has_hitung_premi_tool():
    app = mcp.sse_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tools")
    tools = resp.json()["tools"]
    names = [t["name"] for t in tools]
    assert "hitung_premi_kendaraan" in names


@pytest.mark.asyncio
async def test_tools_endpoint_schema_has_required_fields():
    app = mcp.sse_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tools")
    tool = resp.json()["tools"][0]
    required = tool["inputSchema"]["required"]
    for field in ["tipe_kendaraan", "region", "harga_pasar", "tipe_asuransi", "pilihan_rate", "kegunaan"]:
        assert field in required, f"Required field missing: {field}"


@pytest.mark.asyncio
async def test_tools_endpoint_post_not_allowed():
    app = mcp.sse_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/tools", json={})
    assert resp.status_code == 405


# ===========================================================================
# Tool registration
# ===========================================================================

def test_tool_is_registered():
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "hitung_premi_kendaraan" in tool_names


def test_tool_schema_has_enums():
    schema = _TOOLS_SCHEMA[0]["inputSchema"]
    assert schema["properties"]["tipe_kendaraan"]["enum"] == [
        "non-bus-non-truck", "truck-pickup", "bus", "motor"
    ]
    assert schema["properties"]["region"]["enum"] == ["region1", "region2", "region3"]
    assert schema["properties"]["tipe_asuransi"]["enum"] == ["Comprehensive", "TLO"]
    assert schema["properties"]["pilihan_rate"]["enum"] == ["bawah", "atas"]
    assert schema["properties"]["kegunaan"]["enum"] == ["non-komersial", "komersial"]


# ===========================================================================
# hitung_premi_kendaraan — happy path
# ===========================================================================

@pytest.mark.asyncio
async def test_hitung_premi_returns_string():
    with _patch_httpx(MOCK_API_SUCCESS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_hitung_premi_contains_total_premi():
    with _patch_httpx(MOCK_API_SUCCESS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "6.240.000" in result
    assert "TOTAL PREMI" in result


@pytest.mark.asyncio
async def test_hitung_premi_contains_kendaraan_label():
    with _patch_httpx(MOCK_API_SUCCESS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "Non Bus & Non Truck" in result


@pytest.mark.asyncio
async def test_hitung_premi_contains_region_label():
    with _patch_httpx(MOCK_API_SUCCESS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "Region 2" in result


@pytest.mark.asyncio
async def test_hitung_premi_contains_referensi():
    with _patch_httpx(MOCK_API_SUCCESS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "SE OJK" in result


@pytest.mark.asyncio
async def test_hitung_premi_with_benefits_shows_detail():
    with _patch_httpx(MOCK_API_WITH_BENEFITS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
            benefits=["flood-hurricane"],
        )
    assert "DETAIL BENEFIT" in result
    assert "Banjir" in result


@pytest.mark.asyncio
async def test_hitung_premi_rupiah_format():
    with _patch_httpx(MOCK_API_SUCCESS):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    # harga_pasar Rp 300.000.000
    assert "300.000.000" in result


# ===========================================================================
# hitung_premi_kendaraan — error handling
# ===========================================================================

@pytest.mark.asyncio
async def test_hitung_premi_connect_error():
    with patch("httpx.AsyncClient") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_ctx

        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "Tidak bisa konek" in result


@pytest.mark.asyncio
async def test_hitung_premi_http_status_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 422
    mock_resp.text = "Unprocessable Entity"

    error = httpx.HTTPStatusError(
        "422",
        request=MagicMock(),
        response=mock_resp,
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=error)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "HTTP Error 422" in result


@pytest.mark.asyncio
async def test_hitung_premi_api_success_false():
    api_error = {
        "success": False,
        "errors": ["harga_pasar wajib diisi dan harus lebih dari 0"],
    }
    with _patch_httpx(api_error):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=0,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "API mengembalikan error" in result


@pytest.mark.asyncio
async def test_hitung_premi_unexpected_exception():
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected"))
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        result = await hitung_premi_kendaraan(
            tipe_kendaraan="non-bus-non-truck",
            region="region2",
            harga_pasar=300_000_000,
            tipe_asuransi="Comprehensive",
            pilihan_rate="bawah",
            kegunaan="non-komersial",
        )
    assert "Error" in result
