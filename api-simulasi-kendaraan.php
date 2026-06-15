<?php
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
    echo json_encode(array('success' => false, 'error' => 'Method not allowed. Use POST.'));
    exit;
}

class SimulasiPremiKendaraan
{

    private static $TLO_RATES = array(
        'bawah' => array(
            'region1' => array(array(125000000, 0.47), array(200000000, 0.63), array(400000000, 0.41), array(800000000, 0.25), array(PHP_INT_MAX, 0.20)),
            'region2' => array(array(125000000, 0.65), array(200000000, 0.44), array(400000000, 0.38), array(800000000, 0.25), array(PHP_INT_MAX, 0.20)),
            'region3' => array(array(125000000, 0.51), array(200000000, 0.44), array(400000000, 0.29), array(800000000, 0.23), array(PHP_INT_MAX, 0.20)),
        ),
        'atas' => array(
            'region1' => array(array(125000000, 0.56), array(200000000, 0.69), array(400000000, 0.46), array(800000000, 0.30), array(PHP_INT_MAX, 0.24)),
            'region2' => array(array(125000000, 0.78), array(200000000, 0.53), array(400000000, 0.42), array(800000000, 0.30), array(PHP_INT_MAX, 0.24)),
            'region3' => array(array(125000000, 0.56), array(200000000, 0.48), array(400000000, 0.35), array(800000000, 0.27), array(PHP_INT_MAX, 0.24)),
        ),
    );

    private static $COMP_RATES = array(
        'bawah' => array(
            'region1' => array(array(125000000, 3.82), array(200000000, 2.67), array(400000000, 2.18), array(800000000, 1.20), array(PHP_INT_MAX, 1.05)),
            'region2' => array(array(125000000, 3.26), array(200000000, 2.47), array(400000000, 2.08), array(800000000, 1.20), array(PHP_INT_MAX, 1.05)),
            'region3' => array(array(125000000, 2.53), array(200000000, 2.69), array(400000000, 1.79), array(800000000, 1.14), array(PHP_INT_MAX, 1.05)),
        ),
        'atas' => array(
            'region1' => array(array(125000000, 4.20), array(200000000, 2.94), array(400000000, 2.40), array(800000000, 1.32), array(PHP_INT_MAX, 1.16)),
            'region2' => array(array(125000000, 3.59), array(200000000, 2.72), array(400000000, 2.29), array(800000000, 1.32), array(PHP_INT_MAX, 1.16)),
            'region3' => array(array(125000000, 2.78), array(200000000, 2.96), array(400000000, 1.97), array(800000000, 1.25), array(PHP_INT_MAX, 1.16)),
        ),
    );

    private static $FLAT_RATES = array(
        'bawah' => array(
            'TLO' => array(
                'truck-pickup' => array('region1' => 0.88, 'region2' => 1.68, 'region3' => 0.81),
                'bus'          => array('region1' => 0.23, 'region2' => 0.23, 'region3' => 0.18),
                'motor'        => array('region1' => 1.76, 'region2' => 1.80, 'region3' => 0.67),
            ),
            'Comprehensive' => array(
                'truck-pickup' => array('region1' => 2.42, 'region2' => 2.39, 'region3' => 2.23),
                'bus'          => array('region1' => 1.04, 'region2' => 1.04, 'region3' => 0.88),
                'motor'        => array('region1' => 3.18, 'region2' => 3.18, 'region3' => 3.18),
            ),
        ),
        'atas' => array(
            'TLO' => array(
                'truck-pickup' => array('region1' => 1.07, 'region2' => 2.02, 'region3' => 0.98),
                'bus'          => array('region1' => 0.29, 'region2' => 0.29, 'region3' => 0.22),
                'motor'        => array('region1' => 2.11, 'region2' => 2.16, 'region3' => 0.80),
            ),
            'Comprehensive' => array(
                'truck-pickup' => array('region1' => 2.67, 'region2' => 2.63, 'region3' => 2.46),
                'bus'          => array('region1' => 1.14, 'region2' => 1.14, 'region3' => 0.97),
                'motor'        => array('region1' => 3.50, 'region2' => 3.50, 'region3' => 3.50),
            ),
        ),
    );

    private static $BANJIR_RATES = array(
        'region1' => array('TLO' => 0.050, 'Comprehensive' => 0.075),
        'region2' => array('TLO' => 0.075, 'Comprehensive' => 0.100),
        'region3' => array('TLO' => 0.050, 'Comprehensive' => 0.075),
    );

    private static $GEMPA_RATES = array(
        'region1' => array('TLO' => 0.085, 'Comprehensive' => 0.120),
        'region2' => array('TLO' => 0.075, 'Comprehensive' => 0.100),
        'region3' => array('TLO' => 0.050, 'Comprehensive' => 0.075),
    );

    private $input;

    private $tipe_kendaraan;
    private $brand_kendaraan;
    private $tahun_kendaraan;
    private $kapasitas_penumpang;
    private $region;
    private $kegunaan;
    private $tipe_asuransi;
    private $pilihan_rate;
    private $benefits;
    private $harga_pasar;
    private $pa_driver_price;
    private $pa_pass_price;
    private $third_party_price;

    public function __construct(array $input)
    {
        $this->input = $input;
        $this->parseInput();
    }

    public function run()
    {
        $errors = $this->validate();
        if (!empty($errors)) {
            http_response_code(422);
            return array('success' => false, 'errors' => $errors);
        }

        $rate        = $this->getOJKRate();
        $premi_dasar = $this->harga_pasar * $rate / 100;

        $surcharge_komersial = ($this->kegunaan === 'komersial') ? $premi_dasar * 0.25 : 0;

        $benefit_result = $this->hitungBenefits($premi_dasar);
        $benefit_rows   = $benefit_result[0];
        $premi_benefit  = $benefit_result[1];

        $total_premi = $premi_dasar + $surcharge_komersial + $premi_benefit;

        return array(
            'success' => true,
            'input'   => $this->buildInputSummary(),
            'result'  => array(
                'ojk_rate_pct'        => (float) $rate,
                'premi_dasar'         => (float) round($premi_dasar),
                'surcharge_komersial' => (float) round($surcharge_komersial),
                'benefit_rows'        => $benefit_rows,
                'premi_benefit'       => (float) round($premi_benefit),
                'biaya_admin'         => 0.0,
                'total_premi'         => (float) round($total_premi),
                'total_premi_per'     => 'tahun',
            ),
            'meta' => array(
                'referensi' => 'SE OJK No. 6/SEOJK.05/2017',
                'catatan'   => 'Estimasi indikatif. Premi final dapat berbeda sesuai survei dan kebijakan underwriting.',
                'timestamp' => date('c'),
            ),
        );
    }

   
    private function parseInput()
    {
        $this->tipe_kendaraan      = $this->getString('tipe_kendaraan');
        $this->brand_kendaraan     = $this->getString('brand_kendaraan');
        $this->tahun_kendaraan     = $this->getString('tahun_kendaraan');
        $this->kapasitas_penumpang = max(0, (int) $this->getVal('kapasitas_penumpang', 0));
        $this->region              = $this->getString('region');
        $this->kegunaan            = $this->getString('kegunaan', 'non-komersial');
        $this->tipe_asuransi       = $this->getString('tipe_asuransi', 'TLO');
        $this->pilihan_rate        = $this->getString('pilihan_rate', 'bawah');
        $this->benefits            = $this->getBenefits();

        $this->harga_pasar       = $this->getMoney('harga_pasar');
        $this->pa_driver_price   = $this->getMoney('pa_driver_price');
        $this->pa_pass_price     = $this->getMoney('pa_passenger_price');
        $this->third_party_price = $this->getMoney('third_party_price');

        if (!in_array($this->pilihan_rate, array('bawah', 'atas'))) {
            $this->pilihan_rate = 'bawah';
        }
    }

    private function getVal($key, $default = '')
    {
        return isset($this->input[$key]) ? $this->input[$key] : $default;
    }

    private function getString($key, $default = '')
    {
        return strip_tags(trim((string) $this->getVal($key, $default)));
    }

    private function getMoney($key)
    {
        return (int) preg_replace('/[^0-9]/', '', (string) $this->getVal($key, 0));
    }

    private function getBenefits()
    {
        $val = $this->getVal('benefits', array());
        return is_array($val) ? $val : array();
    }


    private function validate()
    {
        $errors = array();

        $valid_tipe     = array('non-bus-non-truck', 'truck-pickup', 'bus', 'motor');
        $valid_region   = array('region1', 'region2', 'region3');
        $valid_asuransi = array('TLO', 'Comprehensive');

        if (empty($this->tipe_kendaraan) || !in_array($this->tipe_kendaraan, $valid_tipe)) {
            $errors[] = 'tipe_kendaraan wajib diisi: non-bus-non-truck | truck-pickup | bus | motor';
        }
        if (empty($this->region) || !in_array($this->region, $valid_region)) {
            $errors[] = 'region wajib diisi: region1 | region2 | region3';
        }
        if ($this->harga_pasar <= 0) {
            $errors[] = 'harga_pasar wajib diisi dan harus lebih dari 0';
        }
        if (!in_array($this->tipe_asuransi, $valid_asuransi)) {
            $errors[] = 'tipe_asuransi wajib diisi: TLO | Comprehensive';
        }

        return $errors;
    }

    private function getOJKRate()
    {
        $flat_rates = self::$FLAT_RATES;

        // Truk, Bus, Motor pakai flat rate
        if (isset($flat_rates[$this->pilihan_rate][$this->tipe_asuransi][$this->tipe_kendaraan])) {
            $flat = $flat_rates[$this->pilihan_rate][$this->tipe_asuransi][$this->tipe_kendaraan];
            return (float) (isset($flat[$this->region]) ? $flat[$this->region] : 0);
        }

        // Non-bus-non-truck pakai tabel bracket
        $table = ($this->tipe_asuransi === 'TLO')
            ? self::$TLO_RATES[$this->pilihan_rate]
            : self::$COMP_RATES[$this->pilihan_rate];

        return $this->lookupBracketRate($table, $this->region, $this->harga_pasar);
    }

    private function lookupBracketRate(array $table, $region, $harga)
    {
        if (!isset($table[$region])) {
            return 0.0;
        }
        foreach ($table[$region] as $bracket) {
            if ($harga <= $bracket[0]) {
                return (float) $bracket[1];
            }
        }
        $last = end($table[$region]);
        return (float) $last[1];
    }

    private function hitungBenefits($premi_dasar)
    {
        $rows        = array();
        $total_premi = 0.0;
        $banjir      = self::$BANJIR_RATES;
        $gempa       = self::$GEMPA_RATES;

        // Banjir, Angin Topan & Badai
        if (in_array('flood-hurricane', $this->benefits)) {
            $rate = isset($banjir[$this->region][$this->tipe_asuransi]) ? $banjir[$this->region][$this->tipe_asuransi] : 0.05;
            $amt  = $this->harga_pasar * $rate / 100;
            $total_premi += $amt;
            $rows[] = $this->makeBenefitRow(
                'flood-hurricane',
                'Banjir, Angin Topan & Badai',
                $rate,
                round($rate, 3) . '% x Rp ' . $this->fmt($this->harga_pasar),
                $amt,
                'Risiko sendiri banjir: min. 10% dari nilai klaim, minimum Rp500.000 per kejadian (SE OJK No. 6/2017).'
            );
        }

        // Gempa Bumi & Tsunami
        if (in_array('earthquake-tsunami', $this->benefits)) {
            $rate = isset($gempa[$this->region][$this->tipe_asuransi]) ? $gempa[$this->region][$this->tipe_asuransi] : 0.05;
            $amt  = $this->harga_pasar * $rate / 100;
            $total_premi += $amt;
            $rows[] = $this->makeBenefitRow(
                'earthquake-tsunami',
                'Gempa Bumi & Tsunami',
                $rate,
                round($rate, 3) . '% x Rp ' . $this->fmt($this->harga_pasar),
                $amt
            );
        }

        // Mogok, Kerusuhan, Huru Hara (SRCC)
        if (in_array('strike-riot', $this->benefits)) {
            $rate = ($this->tipe_asuransi === 'Comprehensive') ? 0.05 : 0.035;
            $amt  = $this->harga_pasar * $rate / 100;
            $total_premi += $amt;
            $rows[] = $this->makeBenefitRow(
                'strike-riot',
                'Mogok, Kerusuhan, Huru Hara',
                $rate,
                round($rate, 3) . '% x Rp ' . $this->fmt($this->harga_pasar),
                $amt
            );
        }

        // Terorisme & Sabotase
        if (in_array('terrorism-sabotage', $this->benefits)) {
            $rate = ($this->tipe_asuransi === 'Comprehensive') ? 0.05 : 0.035;
            $amt  = $this->harga_pasar * $rate / 100;
            $total_premi += $amt;
            $rows[] = $this->makeBenefitRow(
                'terrorism-sabotage',
                'Terorisme & Sabotase',
                $rate,
                round($rate, 3) . '% x Rp ' . $this->fmt($this->harga_pasar),
                $amt
            );
        }

        // PA Pengemudi
        if (in_array('personal-accident-driver', $this->benefits) && $this->pa_driver_price > 0) {
            $rate = 0.50;
            $amt  = $this->pa_driver_price * $rate / 100;
            $total_premi += $amt;
            $rows[] = $this->makeBenefitRow(
                'personal-accident-driver',
                'Kecelakaan Diri Pengemudi',
                $rate,
                '0.50% x Rp ' . $this->fmt($this->pa_driver_price) . ' (UP)',
                $amt
            );
        }

        // PA Penumpang
        if (in_array('personal-accident-passenger', $this->benefits) && $this->pa_pass_price > 0) {
            $seat = max(1, $this->kapasitas_penumpang);
            $rate = 0.10;
            $amt  = $this->pa_pass_price * $rate / 100 * $seat;
            $total_premi += $amt;
            $row = $this->makeBenefitRow(
                'personal-accident-passenger',
                'Kecelakaan Diri Penumpang (' . $seat . ' seat)',
                $rate,
                '0.10% x Rp ' . $this->fmt($this->pa_pass_price) . ' x ' . $seat . ' seat',
                $amt
            );
            $row['multiplier'] = $seat;
            $rows[] = $row;
        }

        // Tanggung Jawab Hukum Pihak Ketiga (progresif OJK)
        if (in_array('liability', $this->benefits) && $this->third_party_price > 0) {
            $amt  = $this->hitungLiability($this->third_party_price);
            $total_premi += $amt;
            $note = ($this->third_party_price > 100000000)
                ? 'UP > Rp100 juta: rate ditentukan underwriter, simulasi pakai asumsi 0.15%.'
                : '';
            $rows[] = $this->makeBenefitRow(
                'liability',
                'Tanggung Jawab Hukum Pihak Ketiga',
                null,
                'Progresif OJK - Rp ' . $this->fmt($this->third_party_price) . ' (UP)',
                $amt,
                $note
            );
        }

        // Bengkel Resmi (estimasi industri: 5% dari premi dasar)
        if (in_array('authorized', $this->benefits)) {
            $rate = 5.0;
            $amt  = $premi_dasar * $rate / 100;
            $total_premi += $amt;
            $rows[] = $this->makeBenefitRow(
                'authorized',
                'Bengkel Resmi',
                $rate,
                '5% x Rp ' . $this->fmt((int) $premi_dasar) . ' (premi dasar)',
                $amt,
                'Rate ditentukan perusahaan asuransi, bukan tarif OJK.'
            );
        }

        return array($rows, $total_premi);
    }

    // Perhitungan progresif untuk TJH Pihak Ketiga
    private function hitungLiability($up)
    {
        if ($up <= 25000000) {
            return $up * 1.0 / 100;
        }
        if ($up <= 50000000) {
            return (25000000 * 1.0 / 100) + (($up - 25000000) * 0.5 / 100);
        }
        if ($up <= 100000000) {
            return (25000000 * 1.0 / 100) + (25000000 * 0.5 / 100) + (($up - 50000000) * 0.25 / 100);
        }
        return (25000000 * 1.0 / 100) + (25000000 * 0.5 / 100) + (50000000 * 0.25 / 100) + (($up - 100000000) * 0.15 / 100);
    }

    // ---- Helpers ----

    private function makeBenefitRow($id, $label, $rate, $formula, $amount, $note = '')
    {
        return array(
            'id'      => $id,
            'label'   => $label,
            'rate'    => $rate,
            'formula' => $formula,
            'amount'  => (float) round($amount),
            'note'    => $note,
        );
    }

    private function fmt($number)
    {
        return number_format((int) $number, 0, ',', '.');
    }

    private function buildInputSummary()
    {
        $tipe_label = array(
            'non-bus-non-truck' => 'Non Bus & Non Truck',
            'truck-pickup'      => 'Truk & Pick Up',
            'bus'               => 'Bus',
            'motor'             => '2 Wheel Vehicle (Motor)',
        );
        $region_label = array(
            'region1' => 'Region 1 (Sumatera)',
            'region2' => 'Region 2 (Jakarta, Banten, Jawa Barat)',
            'region3' => 'Region 3 (Lainnya)',
        );

        return array(
            'tipe_kendaraan'       => $this->tipe_kendaraan,
            'tipe_kendaraan_label' => isset($tipe_label[$this->tipe_kendaraan]) ? $tipe_label[$this->tipe_kendaraan] : $this->tipe_kendaraan,
            'brand_kendaraan'      => $this->brand_kendaraan,
            'tahun_kendaraan'      => $this->tahun_kendaraan,
            'kapasitas_penumpang'  => $this->kapasitas_penumpang,
            'region'               => $this->region,
            'region_label'         => isset($region_label[$this->region]) ? $region_label[$this->region] : $this->region,
            'kegunaan'             => $this->kegunaan,
            'tipe_asuransi'        => $this->tipe_asuransi,
            'pilihan_rate'         => $this->pilihan_rate,
            'harga_pasar'          => $this->harga_pasar,
            'pa_driver_price'      => $this->pa_driver_price,
            'pa_passenger_price'   => $this->pa_pass_price,
            'third_party_price'    => $this->third_party_price,
            'benefits'             => $this->benefits,
        );
    }
}

$body  = file_get_contents('php://input');
$input = json_decode($body, true);
if (!is_array($input)) {
    $input = $_POST;
}

$simulasi = new SimulasiPremiKendaraan($input);
$response = $simulasi->run();

echo json_encode($response, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
