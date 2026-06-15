<?php
// Router untuk PHP built-in server.
// Semua request (path apa pun) diarahkan ke API simulasi premi,
// supaya kompatibel dengan path lama "/intraasia_new/api-simulasi-kendaraan.php"
// maupun root "/".

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// Health check sederhana (GET /health) — tanpa menyentuh API.
if ($path === '/health') {
    header('Content-Type: application/json');
    echo json_encode(['status' => 'ok']);
    return true;
}

// Layani file statis yang benar-benar ada (mis. .yaml / .md) apa adanya.
$full = __DIR__ . $path;
if ($path !== '/' && is_file($full)) {
    return false;
}

// Selain itu, jalankan API.
require __DIR__ . '/api-simulasi-kendaraan.php';
