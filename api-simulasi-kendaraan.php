<?php
/**
 * API Simulasi Premi Kendaraan
 * POST JSON → JSON
 *
 * Tarif dasar: SE OJK No. 6/SEOJK.05/2017, Lampiran IV KBM
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed. Use POST.']);
    exit;
}

// ---- Parse input (JSON body or form-data) ----
$body = file_get_contents('php://input');
$input = json_decode($body, true);
if (!is_array($input)) {
    $input = $_POST;
}

function get_param($input, $key, $default = '') {
    return isset($input[$key]) ? $input[$key] : $default;
}

$tipe_kendaraan      = strip_tags(trim(get_param($input, 'tipe_kendaraan', '')));
$brand_kendaraan     = strip_tags(trim(get_param($input, 'brand_kendaraan', '')));
$tahun_kendaraan     = strip_tags(trim(get_param($input, 'tahun_kendaraan', '')));
$kapasitas_penumpang = max(0, (int)get_param($input, 'kapasitas_penumpang', 0));
$region              = strip_tags(trim(get_param($input, 'region', '')));
$kegunaan            = strip_tags(trim(get_param($input, 'kegunaan', 'non-komersial')));
$tipe_asuransi       = strip_tags(trim(get_param($input, 'tipe_asuransi', 'TLO')));
$pilihan_rate        = strip_tags(trim(get_param($input, 'pilihan_rate', 'bawah')));
$benefits            = get_param($input, 'benefits', []);

$harga_pasar       = (int)preg_replace('/[^0-9]/', '', (string)get_param($input, 'harga_pasar', 0));
$pa_driver_price   = (int)preg_replace('/[^0-9]/', '', (string)get_param($input, 'pa_driver_price', 0));
$pa_pass_price     = (int)preg_replace('/[^0-9]/', '', (string)get_param($input, 'pa_passenger_price', 0));
$third_party_price = (int)preg_replace('/[^0-9]/', '', (string)get_param($input, 'third_party_price', 0));

if (!is_array($benefits)) {
    $benefits = [];
}
if (!in_array($pilihan_rate, ['bawah', 'atas'])) {
    $pilihan_rate = 'bawah';
}

// ---- Validate ----
$errors = [];
$valid_tipe    = ['non-bus-non-truck', 'truck-pickup', 'bus', 'motor'];
$valid_region  = ['region1', 'region2', 'region3'];
$valid_asuransi = ['TLO', 'Comprehensive'];

if (empty($tipe_kendaraan) || !in_array($tipe_kendaraan, $valid_tipe)) {
    $errors[] = 'tipe_kendaraan wajib diisi: non-bus-non-truck | truck-pickup | bus | motor';
}
if (empty($region) || !in_array($region, $valid_region)) {
    $errors[] = 'region wajib diisi: region1 | region2 | region3';
}
if ($harga_pasar <= 0) {
    $errors[] = 'harga_pasar wajib diisi dan harus lebih dari 0';
}
if (!in_array($tipe_asuransi, $valid_asuransi)) {
    $errors[] = 'tipe_asuransi wajib diisi: TLO | Comprehensive';
}

if (!empty($errors)) {
    http_response_code(422);
    echo json_encode(['success' => false, 'errors' => $errors]);
    exit;
}

// ---- OJK Rate Tables ----
$TLO_RATES = [
    'region1' => [[125000000, 0.47], [200000000, 0.63], [400000000, 0.41], [800000000, 0.25], [PHP_INT_MAX, 0.20]],
    'region2' => [[125000000, 0.65], [200000000, 0.44], [400000000, 0.38], [800000000, 0.25], [PHP_INT_MAX, 0.20]],
    'region3' => [[125000000, 0.51], [200000000, 0.44], [400000000, 0.29], [800000000, 0.23], [PHP_INT_MAX, 0.20]],
];
$TLO_RATES_ATAS = [
    'region1' => [[125000000, 0.56], [200000000, 0.69], [400000000, 0.46], [800000000, 0.30], [PHP_INT_MAX, 0.24]],
    'region2' => [[125000000, 0.78], [200000000, 0.53], [400000000, 0.42], [800000000, 0.30], [PHP_INT_MAX, 0.24]],
    'region3' => [[125000000, 0.56], [200000000, 0.48], [400000000, 0.35], [800000000, 0.27], [PHP_INT_MAX, 0.24]],
];
$COMP_RATES = [
    'region1' => [[125000000, 3.82], [200000000, 2.67], [400000000, 2.18], [800000000, 1.20], [PHP_INT_MAX, 1.05]],
    'region2' => [[125000000, 3.26], [200000000, 2.47], [400000000, 2.08], [800000000, 1.20], [PHP_INT_MAX, 1.05]],
    'region3' => [[125000000, 2.53], [200000000, 2.69], [400000000, 1.79], [800000000, 1.14], [PHP_INT_MAX, 1.05]],
];
$COMP_RATES_ATAS = [
    'region1' => [[125000000, 4.20], [200000000, 2.94], [400000000, 2.40], [800000000, 1.32], [PHP_INT_MAX, 1.16]],
    'region2' => [[125000000, 3.59], [200000000, 2.72], [400000000, 2.29], [800000000, 1.32], [PHP_INT_MAX, 1.16]],
    'region3' => [[125000000, 2.78], [200000000, 2.96], [400000000, 1.97], [800000000, 1.25], [PHP_INT_MAX, 1.16]],
];

// Flat rates Truk/Bus/Motor
$flat_rates = [
    'bawah' => [
        'TLO' => [
            'truck-pickup' => ['region1' => 0.88, 'region2' => 1.68, 'region3' => 0.81],
            'bus'          => ['region1' => 0.23, 'region2' => 0.23, 'region3' => 0.18],
            'motor'        => ['region1' => 1.76, 'region2' => 1.80, 'region3' => 0.67],
        ],
        'Comprehensive' => [
            'truck-pickup' => ['region1' => 2.42, 'region2' => 2.39, 'region3' => 2.23],
            'bus'          => ['region1' => 1.04, 'region2' => 1.04, 'region3' => 0.88],
            'motor'        => ['region1' => 3.18, 'region2' => 3.18, 'region3' => 3.18],
        ],
    ],
    'atas' => [
        'TLO' => [
            'truck-pickup' => ['region1' => 1.07, 'region2' => 2.02, 'region3' => 0.98],
            'bus'          => ['region1' => 0.29, 'region2' => 0.29, 'region3' => 0.22],
            'motor'        => ['region1' => 2.11, 'region2' => 2.16, 'region3' => 0.80],
        ],
        'Comprehensive' => [
            'truck-pickup' => ['region1' => 2.67, 'region2' => 2.63, 'region3' => 2.46],
            'bus'          => ['region1' => 1.14, 'region2' => 1.14, 'region3' => 0.97],
            'motor'        => ['region1' => 3.50, 'region2' => 3.50, 'region3' => 3.50],
        ],
    ],
];

// Benefit rates
$BANJIR_RATES = [
    'region1' => ['TLO' => 0.05,  'Comprehensive' => 0.075],
    'region2' => ['TLO' => 0.075, 'Comprehensive' => 0.10],
    'region3' => ['TLO' => 0.05,  'Comprehensive' => 0.075],
];
$GEMPA_RATES = [
    'region1' => ['TLO' => 0.085, 'Comprehensive' => 0.12],
    'region2' => ['TLO' => 0.075, 'Comprehensive' => 0.10],
    'region3' => ['TLO' => 0.05,  'Comprehensive' => 0.075],
];

// ---- Helper: bracket lookup ----
function lookupRate($table, $region, $harga) {
    if (!isset($table[$region])) return 0;
    foreach ($table[$region] as $bracket) {
        if ($harga <= $bracket[0]) return $bracket[1];
    }
    $last = end($table[$region]);
    return $last[1];
}

// ---- Get OJK rate ----
function getOJKRate($tipe, $region, $harga, $jenis, $pilihan_rate) {
    global $flat_rates, $TLO_RATES, $TLO_RATES_ATAS, $COMP_RATES, $COMP_RATES_ATAS;
    if (isset($flat_rates[$pilihan_rate][$jenis][$tipe])) {
        $r = $flat_rates[$pilihan_rate][$jenis][$tipe];
        return isset($r[$region]) ? $r[$region] : 0;
    }
    if ($jenis === 'TLO') {
        $table = ($pilihan_rate === 'atas') ? $TLO_RATES_ATAS : $TLO_RATES;
    } else {
        $table = ($pilihan_rate === 'atas') ? $COMP_RATES_ATAS : $COMP_RATES;
    }
    return lookupRate($table, $region, $harga);
}

// ---- Calculate ----
$rate        = getOJKRate($tipe_kendaraan, $region, $harga_pasar, $tipe_asuransi, $pilihan_rate);
$premi_dasar = $harga_pasar * $rate / 100;

$surcharge_komersial = ($kegunaan === 'komersial') ? $premi_dasar * 0.25 : 0;

$benefit_rows  = [];
$premi_benefit = 0;

// Banjir, Angin Topan & Badai
if (in_array('flood-hurricane', $benefits)) {
    $br  = isset($BANJIR_RATES[$region][$tipe_asuransi]) ? $BANJIR_RATES[$region][$tipe_asuransi] : 0.05;
    $amt = $harga_pasar * $br / 100;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'flood-hurricane',
        'label'   => 'Banjir, Angin Topan & Badai',
        'rate'    => $br,
        'formula' => round($br, 3) . '% × Rp ' . number_format($harga_pasar, 0, ',', '.'),
        'amount'  => (float)round($amt),
        'note'    => 'Risiko sendiri banjir: min. 10% dari nilai klaim, minimum Rp500.000 per kejadian (SE OJK No. 6/2017).',
    ];
}

// Gempa Bumi & Tsunami
if (in_array('earthquake-tsunami', $benefits)) {
    $gr  = isset($GEMPA_RATES[$region][$tipe_asuransi]) ? $GEMPA_RATES[$region][$tipe_asuransi] : 0.05;
    $amt = $harga_pasar * $gr / 100;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'earthquake-tsunami',
        'label'   => 'Gempa Bumi & Tsunami',
        'rate'    => $gr,
        'formula' => round($gr, 3) . '% × Rp ' . number_format($harga_pasar, 0, ',', '.'),
        'amount'  => (float)round($amt),
        'note'    => '',
    ];
}

// Huru-hara & Kerusuhan (SRCC)
if (in_array('strike-riot', $benefits)) {
    $br  = ($tipe_asuransi === 'Comprehensive') ? 0.05 : 0.035;
    $amt = $harga_pasar * $br / 100;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'strike-riot',
        'label'   => 'Mogok, Kerusuhan, Huru Hara',
        'rate'    => $br,
        'formula' => round($br, 3) . '% × Rp ' . number_format($harga_pasar, 0, ',', '.'),
        'amount'  => (float)round($amt),
        'note'    => '',
    ];
}

// Terorisme & Sabotase
if (in_array('terrorism-sabotage', $benefits)) {
    $br  = ($tipe_asuransi === 'Comprehensive') ? 0.05 : 0.035;
    $amt = $harga_pasar * $br / 100;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'terrorism-sabotage',
        'label'   => 'Terorisme & Sabotase',
        'rate'    => $br,
        'formula' => round($br, 3) . '% × Rp ' . number_format($harga_pasar, 0, ',', '.'),
        'amount'  => (float)round($amt),
        'note'    => '',
    ];
}

// PA Pengemudi
if (in_array('personal-accident-driver', $benefits) && $pa_driver_price > 0) {
    $amt = $pa_driver_price * 0.50 / 100;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'personal-accident-driver',
        'label'   => 'Kecelakaan Diri Pengemudi',
        'rate'    => 0.50,
        'formula' => '0.50% × Rp ' . number_format($pa_driver_price, 0, ',', '.') . ' (UP)',
        'amount'  => (float)round($amt),
        'note'    => '',
    ];
}

// PA Penumpang
if (in_array('personal-accident-passenger', $benefits) && $pa_pass_price > 0) {
    $multiplier = max(1, $kapasitas_penumpang);
    $amt = $pa_pass_price * 0.10 / 100 * $multiplier;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'         => 'personal-accident-passenger',
        'label'      => 'Kecelakaan Diri Penumpang (' . $multiplier . ' seat)',
        'rate'       => 0.10,
        'multiplier' => $multiplier,
        'formula'    => '0.10% × Rp ' . number_format($pa_pass_price, 0, ',', '.') . ' × ' . $multiplier . ' seat',
        'amount'     => (float)round($amt),
        'note'       => '',
    ];
}

// Tanggung Jawab Hukum Pihak Ketiga (progresif OJK)
if (in_array('liability', $benefits) && $third_party_price > 0) {
    $up  = $third_party_price;
    $amt = 0;
    if ($up <= 25000000) {
        $amt = $up * 1.0 / 100;
    } elseif ($up <= 50000000) {
        $amt  = 25000000 * 1.0 / 100;
        $amt += ($up - 25000000) * 0.5 / 100;
    } elseif ($up <= 100000000) {
        $amt  = 25000000 * 1.0 / 100;
        $amt += 25000000 * 0.5 / 100;
        $amt += ($up - 50000000) * 0.25 / 100;
    } else {
        $amt  = 25000000 * 1.0 / 100;
        $amt += 25000000 * 0.5 / 100;
        $amt += 50000000 * 0.25 / 100;
        $amt += ($up - 100000000) * 0.15 / 100;
    }
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'liability',
        'label'   => 'Tanggung Jawab Hukum Pihak Ketiga',
        'rate'    => null,
        'formula' => 'Progresif OJK — Rp ' . number_format($up, 0, ',', '.') . ' (UP)',
        'amount'  => (float)round($amt),
        'note'    => ($up > 100000000) ? 'UP > Rp100 juta: rate ditentukan underwriter, simulasi pakai asumsi 0.15%.' : '',
    ];
}

// Bengkel Resmi (5% dari premi dasar, estimasi industri)
if (in_array('authorized', $benefits)) {
    $amt = $premi_dasar * 0.05;
    $premi_benefit += $amt;
    $benefit_rows[] = [
        'id'      => 'authorized',
        'label'   => 'Bengkel Resmi',
        'rate'    => 5.0,
        'formula' => '5% × Rp ' . number_format($premi_dasar, 0, ',', '.') . ' (premi dasar)',
        'amount'  => (float)round($amt),
        'note'    => 'Rate ditentukan perusahaan asuransi, bukan tarif OJK.',
    ];
}

$total_premi = $premi_dasar + $surcharge_komersial + $premi_benefit;
$biaya_admin = 0;

// ---- Response ----
$region_label = [
    'region1' => 'Region 1 (Sumatera)',
    'region2' => 'Region 2 (Jakarta, Banten, Jawa Barat)',
    'region3' => 'Region 3 (Lainnya)',
];
$tipe_label = [
    'non-bus-non-truck' => 'Non Bus & Non Truck',
    'truck-pickup'      => 'Truk & Pick Up',
    'bus'               => 'Bus',
    'motor'             => '2 Wheel Vehicle (Motor)',
];

echo json_encode([
    'success'    => true,
    'input' => [
        'tipe_kendaraan'      => $tipe_kendaraan,
        'tipe_kendaraan_label'=> isset($tipe_label[$tipe_kendaraan]) ? $tipe_label[$tipe_kendaraan] : $tipe_kendaraan,
        'brand_kendaraan'     => $brand_kendaraan,
        'tahun_kendaraan'     => $tahun_kendaraan,
        'kapasitas_penumpang' => $kapasitas_penumpang,
        'region'              => $region,
        'region_label'        => isset($region_label[$region]) ? $region_label[$region] : $region,
        'kegunaan'            => $kegunaan,
        'tipe_asuransi'       => $tipe_asuransi,
        'pilihan_rate'        => $pilihan_rate,
        'harga_pasar'         => $harga_pasar,
        'pa_driver_price'     => $pa_driver_price,
        'pa_passenger_price'  => $pa_pass_price,
        'third_party_price'   => $third_party_price,
        'benefits'            => $benefits,
    ],
    'result' => [
        'ojk_rate_pct'        => (float)$rate,
        'premi_dasar'         => (float)round($premi_dasar),
        'surcharge_komersial' => (float)round($surcharge_komersial),
        'benefit_rows'        => $benefit_rows,
        'premi_benefit'       => (float)round($premi_benefit),
        'biaya_admin'         => (float)$biaya_admin,
        'total_premi'         => (float)round($total_premi),
        'total_premi_per'     => 'tahun',
    ],
    'meta' => [
        'referensi' => 'SE OJK No. 6/SEOJK.05/2017',
        'catatan'   => 'Estimasi indikatif. Premi final dapat berbeda sesuai survei dan kebijakan underwriting.',
        'timestamp' => date('c'),
    ],
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
