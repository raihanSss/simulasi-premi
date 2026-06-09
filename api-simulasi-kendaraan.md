# Cara Test API Simulasi Premi Kendaraan

> Pastikan **XAMPP Apache** sudah running sebelum mulai.
>
> Base URL: `http://localhost/intraasia_new/api-simulasi-kendaraan.php`

---

## Postman

### Langkah Setup

1. Buka Postman → klik **New** → **HTTP Request**
2. Set method ke **POST**
3. Isi URL: `http://localhost/intraasia_new/api-simulasi-kendaraan.php`
4. Tab **Headers** → tambahkan:

   | Key | Value |
   |---|---|
   | `Content-Type` | `application/json` |

5. Tab **Body** → pilih **raw** → dropdown format pilih **JSON**
6. Paste salah satu contoh body di bawah → klik **Send**

---

### Test Case 1 — Non Bus/Truck, Comprehensive, Rate Bawah

```json
{
  "tipe_kendaraan": "non-bus-non-truck",
  "region": "region2",
  "harga_pasar": 300000000,
  "tipe_asuransi": "Comprehensive",
  "pilihan_rate": "bawah",
  "kegunaan": "non-komersial",
  "benefits": ["flood-hurricane", "authorized"]
}
```

Expected: `200` — premi dasar + benefit banjir + bengkel resmi.

---

### Test Case 2 — Motor, TLO, tanpa benefit

```json
{
  "tipe_kendaraan": "motor",
  "region": "region1",
  "harga_pasar": 25000000,
  "tipe_asuransi": "TLO"
}
```

Expected: `200` — premi dasar saja.

---

### Test Case 3 — Komersial + PA Driver + PA Penumpang + Liability

```json
{
  "tipe_kendaraan": "non-bus-non-truck",
  "region": "region3",
  "harga_pasar": 200000000,
  "tipe_asuransi": "Comprehensive",
  "pilihan_rate": "atas",
  "kegunaan": "komersial",
  "kapasitas_penumpang": 4,
  "pa_driver_price": 100000000,
  "pa_passenger_price": 50000000,
  "third_party_price": 50000000,
  "benefits": [
    "personal-accident-driver",
    "personal-accident-passenger",
    "liability",
    "strike-riot",
    "terrorism-sabotage"
  ]
}
```

Expected: `200` — premi dasar + surcharge komersial 25% + semua benefit.

---

### Test Case 4 — Semua Benefit (Truk, TLO, Rate Atas)

```json
{
  "tipe_kendaraan": "truck-pickup",
  "region": "region2",
  "harga_pasar": 500000000,
  "tipe_asuransi": "TLO",
  "pilihan_rate": "atas",
  "kegunaan": "komersial",
  "kapasitas_penumpang": 2,
  "pa_driver_price": 75000000,
  "pa_passenger_price": 50000000,
  "third_party_price": 100000000,
  "benefits": [
    "flood-hurricane",
    "earthquake-tsunami",
    "strike-riot",
    "terrorism-sabotage",
    "personal-accident-driver",
    "personal-accident-passenger",
    "liability"
  ]
}
```

Expected: `200` — seluruh komponen premi.

---

### Test Case 5 — Validasi Gagal

```json
{
  "tipe_kendaraan": "non-bus-non-truck",
  "region": "region2"
}
```

Expected: `422` — error karena `harga_pasar` dan `tipe_asuransi` tidak diisi.

---

### Test Case 6 — Method Salah

Ganti method ke **GET** lalu klik Send.

Expected: `405` — `"Method not allowed. Use POST."`

---

## Swagger UI

### Langkah Setup

1. Buka browser → akses: `http://localhost/intraasia_new/swagger-simulasi.html`
2. Swagger UI akan load spec dari `api-simulasi-kendaraan.yaml` secara otomatis
3. Klik endpoint **POST /api-simulasi-kendaraan.php** untuk expand
4. Klik tombol **Try it out**
5. Edit body JSON di kolom **Request body**
6. Klik **Execute**
7. Lihat response di bagian **Responses** di bawahnya

### Menggunakan Example Bawaan

Swagger sudah menyediakan 4 contoh siap pakai. Setelah klik **Try it out**:

1. Klik dropdown **Examples** di atas kolom body
2. Pilih salah satu:
   - `non_bus_comprehensive` — Non Bus/Truck Comprehensive + flood & bengkel resmi
   - `motor_tlo` — Motor TLO Region 1
   - `komersial_dengan_pa` — Komersial + PA Driver + PA Penumpang + Liability
   - `truck_full_benefit` — Truk TLO Rate Atas + semua benefit
3. Klik **Execute**

---

## Struktur Response Sukses (200)

```json
{
  "success": true,
  "input": { ... },
  "result": {
    "ojk_rate_pct": 2.08,
    "premi_dasar": 6240000,
    "surcharge_komersial": 0,
    "benefit_rows": [
      {
        "id": "flood-hurricane",
        "label": "Banjir, Angin Topan & Badai",
        "rate": 0.1,
        "formula": "0.1% × Rp 300.000.000",
        "amount": 300000,
        "note": "..."
      }
    ],
    "premi_benefit": 612000,
    "biaya_admin": 0,
    "total_premi": 6852000,
    "total_premi_per": "tahun"
  },
  "meta": {
    "referensi": "SE OJK No. 6/SEOJK.05/2017",
    "catatan": "Estimasi indikatif...",
    "timestamp": "2026-06-09T10:00:00+07:00"
  }
}
```
