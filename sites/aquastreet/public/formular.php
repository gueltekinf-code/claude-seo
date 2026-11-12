<?php
/**
 * Aquastreet – Formular-Versand (Kontakt + Kundenkartenantrag).
 *
 * Nimmt POST-Daten der Formulare entgegen, prüft sie, verschickt eine
 * Klartext-E-Mail an EMPFAENGER und leitet auf /danke/ bzw. /fehler/ weiter.
 * Kein Speichern auf dem Server, keine Cookies, keine externen Dienste.
 *
 * Schutz: nur POST, Honeypot-Feld, Längenlimits, Header-Injection-Filter,
 * einfache Drosselung pro IP (max. 5 Nachrichten / 10 Minuten, im Temp-Ordner).
 */

const EMPFAENGER = 'info@aquastreet.de';
const ABSENDER   = 'website@aquastreet.de';   // muss eine Adresse der eigenen Domain sein (STRATO)

function weiter(string $ziel): void {
    header('Location: ' . $ziel, true, 303);
    exit;
}

function feld(string $name, int $max = 200): string {
    $v = isset($_POST[$name]) && is_string($_POST[$name]) ? trim($_POST[$name]) : '';
    $v = str_replace(["\r\n", "\r"], "\n", $v);
    if ($name !== 'nachricht' && $name !== 'kennzeichen') {
        $v = str_replace("\n", ' ', $v);
    }
    return mb_substr(strip_tags($v), 0, $max);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    weiter('/');
}

// Honeypot: echte Besucher sehen das Feld nicht
if (!empty($_POST['website'])) {
    weiter('/danke/');
}

// Drosselung pro IP
$ip    = $_SERVER['REMOTE_ADDR'] ?? '0';
$datei = sys_get_temp_dir() . '/aquastreet_' . hash('sha256', $ip . __FILE__);
$jetzt = time();
$log   = is_file($datei) ? array_filter(array_map('intval', explode(',', (string) @file_get_contents($datei))), fn($t) => $t > $jetzt - 600) : [];
if (count($log) >= 5) {
    weiter('/fehler/');
}
$log[] = $jetzt;
@file_put_contents($datei, implode(',', $log), LOCK_EX);

$formular = feld('formular', 20);
$email    = feld('email', 120);
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    weiter('/fehler/');
}

if ($formular === 'kundenkarte') {
    $art = feld('kartenart', 20) === 'Firmenkarte' ? 'Firmenkarte' : 'Privatkarte';
    $d = [
        'Kartenart'   => $art,
        'Vorname'     => feld('vorname', 80),
        'Nachname'    => feld('nachname', 80),
        'Firma'       => feld('firma', 120),
        'Straße'      => feld('strasse', 120),
        'PLZ'         => feld('plz', 5),
        'Ort'         => feld('ort', 80),
        'E-Mail'      => $email,
        'Telefon'     => feld('telefon', 40),
        'Kennzeichen' => feld('kennzeichen', 300),
    ];
    foreach (['Vorname', 'Nachname', 'Straße', 'Ort'] as $pflicht) {
        if ($d[$pflicht] === '') weiter('/fehler/');
    }
    if (!preg_match('/^\d{5}$/', $d['PLZ'])) weiter('/fehler/');
    $betreff = 'Neuer Kundenkartenantrag (' . $art . '): ' . $d['Vorname'] . ' ' . $d['Nachname'];
} elseif ($formular === 'kontakt') {
    $themen = ['Allgemeine Frage', 'Fahrzeugaufbereitung / Angebot', 'Kundenkarte / Firmenkarte', 'Lob & Kritik'];
    $thema  = feld('thema', 60);
    $d = [
        'Name'      => feld('name', 120),
        'E-Mail'    => $email,
        'Telefon'   => feld('telefon', 40),
        'Thema'     => in_array($thema, $themen, true) ? $thema : 'Allgemeine Frage',
        'Nachricht' => feld('nachricht', 4000),
    ];
    if ($d['Name'] === '' || $d['Nachricht'] === '') weiter('/fehler/');
    $betreff = 'Kontaktanfrage: ' . $d['Thema'] . ' – ' . $d['Name'];
} else {
    weiter('/fehler/');
}

$text = '';
foreach ($d as $k => $v) {
    if ($v !== '') $text .= $k . ': ' . $v . "\n";
}
$text .= "\nGesendet über www.aquastreet.de am " . date('d.m.Y H:i') . " Uhr.\n";

$betreff = '=?UTF-8?B?' . base64_encode(str_replace(["\r", "\n"], ' ', $betreff)) . '?=';
$kopf = [
    'From: Aquastreet Website <' . ABSENDER . '>',
    'Reply-To: ' . $email,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: 8bit',
];

$ok = mail(EMPFAENGER, $betreff, $text, implode("\r\n", $kopf), '-f' . ABSENDER);
weiter($ok ? '/danke/' : '/fehler/');
