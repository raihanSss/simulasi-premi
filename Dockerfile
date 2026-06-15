# API Simulasi Premi Kendaraan — PHP built-in server di port 1234.
# (premi.py adalah MCP server berbasis stdio — tidak mendengarkan port,
#  jadi yang dikontainerkan & diekspos di port 1234 adalah PHP API-nya.)
FROM php:8.3-cli-alpine

WORKDIR /app

# Hanya butuh file API + router (tidak ada dependency eksternal / DB).
COPY api-simulasi-kendaraan.php router.php ./
# Sertakan juga spec/docs supaya bisa diakses bila diperlukan.
COPY api-simulasi-kendaraan.yaml api-simulasi-kendaraan.md ./

EXPOSE 1234

# Jalankan PHP built-in web server dengan router.
CMD ["php", "-S", "0.0.0.0:1234", "router.php"]
