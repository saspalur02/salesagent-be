# Kontrak API — Tambah Order Pembelian (`tambahapi`)

> Dokumen acuan untuk aplikasi **pemanggil** API ini.
> Berisi: kontrak request/response, aturan validasi, alur logika server, dan cuplikan source code yang relevan.
> Source: `app/Http/Controllers/OrderPembelianController.php` (method `tambahapi`), `routes/api.php`, `app/Http/Middleware/VerifyToken.php`.

---

## 1. Ringkasan Endpoint

| Item | Nilai |
|---|---|
| **URL** | `http://wisertasksales.sas-autoparts.com/api/transaksi/orderpembelian/tambahapi` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |
| **Controller** | `OrderPembelianController@tambahapi` |
| **Middleware** | `access-log`, `token` |
| **Versi lain** | `POST .../tambahapiV2` → `OrderPembelianController@tambahapiV2` (untuk skenario sub-cabang) |

Route (`routes/api.php`):

```php
Route::group([ 'middleware' => ['access-log','token'] ], function () {
  // ...
  Route::post('/transaksi/orderpembelian/tambahapi', 'OrderPembelianController@tambahapi');
  Route::post('/transaksi/orderpembelian/tambahapiV2', 'OrderPembelianController@tambahapiV2');
});
```

---

## 2. Autentikasi

Field **`apikey`** dikirim di **body JSON** (bukan header). Diverifikasi oleh middleware `token` (`app/Http/Middleware/VerifyToken.php`):

```php
public function handle($request, Closure $next)
{
    $token = $request->apikey;
    if (! $token) {
        throw new \Exception('Access forbidden.');
    }
    $user = LoginUsers::where("api_token",$token)->where("status", true)->first();
    if ($user == null) {
        throw new \Exception('Invalid access token.');
    }
    $request->userinfo = $user;
    return $next($request);
}
```

- `apikey` dicocokkan ke kolom `api_token` di tabel `tasksales.loginusers` dengan `status = true`.
- Kalau `apikey` kosong → `{"status":"error","message":"Access forbidden."}`
- Kalau `apikey` tidak valid → `{"status":"error","message":"Invalid access token."}`

**API key produksi (contoh nyata):**
```
aAU7XGzxjaZxYMwSD5HfeKRBX0otzV42yc9JcJmiXxa22UY4CdxRIj000001
```

---

## 3. Struktur Request

### 3.1 Header (root JSON)

| Field | Wajib | Tipe / Format | Keterangan |
|---|:---:|---|---|
| `apikey` | ✅ | string | Token autentikasi (lihat bagian 2) |
| `tasksalesnoso` | ✅ | string | No SO, mis. `SOT/2606/00009`. Unik per `sotype` |
| `tasksalestglso` | ✅ | string `Ymd` | Tgl SO, mis. `20260625` |
| `tokoidsas` | ✅ | string | Format `"tokoidwarisan\|tokoaliasid"`, mis. `1045764\|248`. Bagian setelah `\|` opsional |
| `temponotabe` | ✅ | string/number | Tempo nota BE. `>0` ⇒ transaksi dianggap kredit (`K`) |
| `temponotanonbe` | ✅ | string/number | Tempo nota non-BE |
| `tipetransaksi` | ✅ | string | `K` (kredit) / `T` (tunai) / `D`. Jika `T` ⇒ `statuspembayaran` wajib |
| `tasksalescreatedby` | ✅ | string | Username pembuat (umumnya = `kodesales`) |
| `tasksalescreatedon` | ✅ | date | Tanggal dibuat (valid date) |
| `tasksalesupdatedby` | ✅ | string | Username update |
| `tasksalesupdatedon` | ✅ | date | Tanggal update (valid date) |
| `tasksalestokostatusbmk` | ✅ | string | Status BMK toko. Lihat mapping di bagian 6 |
| `tasksalescurrency` | ✅ | string | Mata uang, mis. `IDR` |
| `tasksalessotype` | ✅ | string | Tipe SO, mis. `TSSO`. Dipakai sbg kunci unik bersama noso/externalid |
| `statuspembayaran` | ⚠️ | string | Wajib **hanya jika** `tipetransaksi='T'`. Nilai: `KREDIT`/`CBD`/`TUNAI` |
| `tasksalesid` | ➖ | number | Dipakai sbg `externalid` di server (dicek duplikat) |
| `omsetsubcabangid` | ➖ | string | Disimpan ke `omsetsubcabangid` |
| `kodesales` | ➖ | string | Kode sales |
| `keterangan` | ➖ | string/null | Keterangan header |
| `redeempoint` | ➖ | number | Default 0 |
| `flgordersalesman` | ➖ | string | `Y`/`N` |
| `tasksalestokoid` | ➖ | number | Referensi tokoid sisi pemanggil |
| `subcabang` | ➖ | number | Hanya relevan untuk `tambahapiV2` |

### 3.2 Detail — array `tasksalessodetail[]`

| Field | Wajib | Tipe | Keterangan |
|---|:---:|---|---|
| `takssalesdetailid` | ✅ | string | ID detail (perhatikan ejaan: `takss...`). Dicek duplikat |
| `kodebarangsas` | ✅ | string | Harus ada di `mstr.stock` |
| `qtyorder` | ✅ | number | Qty order |
| `hargasatuanbmk` | ✅ | number | Harga satuan BMK |
| `hargasatuanajuan` | ✅ | number | Harga satuan ajuan |
| `hargaitembeforetax` | ✅ | number | Harga item sebelum pajak |
| `hargaitemtax` | ✅ | number | Nilai pajak item |
| `hargaitemaftertax` | ✅ | number | Harga item setelah pajak |
| `tasksalesketerangan` | ➖ | string/null | Keterangan item |
| `orderid` | ➖ | number | Referensi order sisi pemanggil |
| `flg_inden_so` | ➖ | string | `Y`/`N` |

> ⚠️ **Penting:** key detail dieja **`takssalesdetailid`** (dobel `s`), bukan `tasksalesdetailid`. Ikuti persis ejaan ini.

---

## 4. Contoh Request (payload produksi nyata)

```json
{
  "apikey": "aAU7XGzxjaZxYMwSD5HfeKRBX0otzV42yc9JcJmiXxa22UY4CdxRIj000001",
  "omsetsubcabangid": "0901",
  "tasksalesid": 298994,
  "tasksalesnoso": "SOT/2606/00009",
  "tasksalestglso": "20260625",
  "tokoidsas": "1045764|248",
  "tasksalestokoid": 698472,
  "temponotabe": "90",
  "temponotanonbe": "0",
  "tipetransaksi": "K",
  "statuspembayaran": "KREDIT",
  "kodesales": "09-095-WIW",
  "tasksalescreatedby": "09-095-WIW",
  "tasksalescreatedon": "20260625",
  "tasksalesupdatedby": "09-095-WIW",
  "tasksalesupdatedon": "20260625",
  "tasksalestokostatusbmk": "AGEN",
  "tasksalescurrency": "IDR",
  "keterangan": null,
  "tasksalessotype": "TSSO",
  "flgordersalesman": "Y",
  "redeempoint": 0,
  "subcabang": 3,
  "tasksalessodetail": [
    {
      "orderid": 298994,
      "takssalesdetailid": "1098544",
      "kodebarangsas": "FE4NAPF077UA",
      "qtyorder": "38",
      "hargasatuanbmk": "152000",
      "hargasatuanajuan": "152000",
      "hargaitembeforetax": "5776000",
      "hargaitemtax": "0",
      "hargaitemaftertax": "5776000",
      "tasksalesketerangan": null,
      "flg_inden_so": "N"
    }
  ]
}
```

---

## 5. Response

### 5.1 Sukses
```json
{
  "status": "success",
  "wisertosopid": 12345,
  "errormessage": "No Error Detected"
}
```
`wisertosopid` = `id` baris baru di `tos.orderpembelian`.

### 5.2 Gagal (validasi / bisnis / exception)
```json
{
  "status": false,
  "wisertosopid": null,
  "errormessage": "<pesan error> Line: <nomor baris>"
}
```

### 5.3 Gagal khusus — kode barang tidak ada di master
```json
{
  "status": false,
  "errormessage": "kodebarangsas FE4NAPF077UA tidak sesuai"
}
```

### 5.4 Gagal autentikasi (dari middleware)
```json
{ "status": "error", "message": "Access forbidden." }
{ "status": "error", "message": "Invalid access token." }
```

> Catatan: cek `status` bisa bernilai string `"success"` / `"error"` atau boolean `false` tergantung jalur error. Di sisi pemanggil, perlakukan **sukses hanya bila `status === "success"`**.

---

## 6. Aturan Validasi & Logika Server (ground truth)

### 6.1 Validator field wajib

```php
$vali = Validator::make($req->all(),[
    'tasksalesnoso'=>'required',
    'tasksalestglso'=>'required',
    'tokoidsas'=>'required',
    'temponotabe'=>'required',
    'temponotanonbe'=>'required',
    'tipetransaksi'=>'required',
    'tasksalescreatedby'=>'required',
    'tasksalescreatedon'=>'date|required',
    'tasksalesupdatedby'=>'required',
    'tasksalesupdatedon'=>'date|required',
    'tasksalestokostatusbmk'=>'required',
    'tasksalescurrency'=>'required',
    'tasksalessotype'=> 'required',
]);

if($req->tipetransaksi=='T'){
    $this->validate($req, [ 'statuspembayaran' => 'required' ]);
}
```

### 6.2 Resolusi toko dari `tokoidsas`

```php
$arrTokoid     = explode('|', $req->tokoidsas);
$tokoidwarisan = $arrTokoid[0];
$tokoaliasid   = array_key_exists(1, $arrTokoid) ? (int) $arrTokoid[1] : null;
```

Urutan pencarian toko:
1. **UMUM** — kalau `tokoidwarisan` ada di `hr.registermitraumum` ⇒ transaksi dipetakan ke toko **ONLINE SHOP** milik user (`tasksalescreatedby`). Kalau toko online shop tak ditemukan ⇒ `"Toko ONLINE SHOP tidak ditemukan"`.
2. **Master toko biasa** — cari di `mstr.toko` (`tokoidwarisan = ...`).
3. **PROSAS** — kalau tidak ada di master, cek karyawan Prosas (`HrmsController@getKaryawanProsas`). Kalau ada ⇒ dipetakan ke toko `tokoidwarisan = 9727861`. Kalau tidak ada ⇒ `"tokoid tersebut tidak ditemukan"`.

### 6.3 Cek duplikat (idempotensi)

```php
// No SO unik per sotype
$ceknoso = DB::select("Select docno from tos.orderpembelian
                       where docno='$req->tasksalesnoso' and sotype='$req->tasksalessotype'");
if($ceknoso != null) throw new \Exception('Noso tersebut sudah ada');

// externalid (tasksalesid) unik per sotype
$cekext = DB::select("Select externalid from tos.orderpembelian
                      where externalid='$req->tasksalesid' and sotype='$req->tasksalessotype'");
if($cekext != null) throw new \Exception("tasksalesid '$req->tasksalesid' tersebut sudah ada");
```

Per item detail juga dicek:
```php
// takssalesdetailid unik per sotype
"Select a.externaldetailid from tos.orderpembeliandetail a
 join tos.orderpembelian b on a.orderpembelianid = b.id
 where a.externaldetailid = '<takssalesdetailid>' and b.sotype = '<sotype>'"
// jika ada => throw "takssalesdetailid '...' tersebut sudah ada"
```

### 6.4 Validasi tiap item detail (semua tidak boleh string kosong)

```php
foreach ($req->tasksalessodetail as $d) {
    if($d["kodebarangsas"]       == "") throw new \Exception('kodebarangsas kosong');
    if($d["takssalesdetailid"]   == "") throw new \Exception('takssalesdetailid kosong');
    if($d["qtyorder"]            == "") throw new \Exception('qtyorder kosong');
    if($d["hargasatuanbmk"]      == "") throw new \Exception('hargasatuanbmk kosong');
    if($d["hargasatuanajuan"]    == "") throw new \Exception('hargasatuanajuan kosong');
    if($d["hargaitembeforetax"]  == "") throw new \Exception('hargaitembeforetax kosong');
    if($d["hargaitemtax"]        == "") throw new \Exception('hargaitemtax kosong');
    if($d["hargaitemaftertax"]   == "") throw new \Exception('hargaitemaftertax kosong');

    // kodebarangsas harus ada di mstr.stock, kalau tidak -> "kodebarangsas xxx tidak sesuai"
}
```

### 6.5 Mapping `tasksalestokostatusbmk` → `sasstatusbmk` (internal)

Tergantung perusahaan toko (`SAP` vs non-SAP, dari `tasksales.fn_gettokomilikperusahaancabang3`):

**Jika PT = `SAP`:**
| `tasksalestokostatusbmk` | `sasstatusbmk` |
|---|---|
| `AGEN` | `B1` |
| `GROSIR` | `M1` |
| `RETAIL23`, `RETAIL25` | `R1` |
| `BENGKEL3`, `BENGKEL5` | `M2` |
| (lainnya) | `K1` |

**Jika PT non-SAP:**
| `tasksalestokostatusbmk` | `sasstatusbmk` |
|---|---|
| `RETAIL` | `B2` |
| `BENGKEL` | `M2` |
| (lainnya) | `K2` |

> Mapping ini dilakukan **di server**, pemanggil cukup mengirim nilai `tasksalestokostatusbmk` apa adanya.

### 6.6 Prefix kode barang → grup (internal)

Server memetakan 3 huruf awal `kodebarangsas` (mis. `FB2`/`FE4`/`FAB`/`FC2`…) ke grup barang (`FB`, `FE`, `FAB`, dst) untuk proses konversi SO (`tasksales.fn_convert_so_from_orderpembelian`). **Ini murni logika internal server — pemanggil tidak perlu mengirim apa pun terkait ini.**

---

## 7. Alur Eksekusi (high level)

1. Catat request ke `Api_Call_Wiser` (audit log).
2. Validasi field header (6.1) + aturan `tipetransaksi='T'`.
3. Resolusi toko dari `tokoidsas` (6.2).
4. Cek duplikat noso & externalid (6.3).
5. Loop detail: validasi tidak kosong, cek duplikat detailid, cek kode barang ada di master (6.4).
6. Jika ada kode barang tak valid ⇒ balas gagal `"... tidak sesuai"`.
7. Jika lolos, dalam **DB transaction** (2 koneksi: utama + `pgsql_wiserdc`):
   - `insertOrderpembelian` → simpan header ke `tos.orderpembelian`.
   - `insertOrderpembelianDetail` → simpan detail via `tasksales.fn_add_orderpembeliandetail`.
   - `fn_convert_so_from_orderpembelian` per grup barang.
   - `insertSoSASAToSAP` (push ke SAP) + `createSoWiserToSobat`.
   - `commit`. Jika error ⇒ `rollback` + `tasksales.deleteorderpembelian(opid)`.
8. Balas `wisertosopid`.

---

## 8. Pemetaan field request → kolom DB (header)

Dari `insertOrderpembelian()`:

| Kolom `tos.orderpembelian` | Sumber |
|---|---|
| `omsetsubcabangid` | `omsetsubcabangid` |
| `externalid` | `tasksalesid` |
| `saskodesales`, `prcreateusername` | `kodesales` |
| `docno` | `tasksalesnoso` |
| `docdate` | `tasksalestglso` |
| `currcode` | `tasksalescurrency` |
| `createdby` / `createdon` | `tasksalescreatedby` / `tasksalescreatedon` |
| `lastupdatedby` / `lastupdatedon` | `tasksalesupdatedby` / `tasksalesupdatedon` |
| `sasstatusbmk` | hasil mapping `tasksalestokostatusbmk` (6.5) |
| `tipetransaksi` | `tipetransaksi` |
| `sastokoid` | `tokoidwarisan` (hasil resolusi) |
| `sotype` | `tasksalessotype` |
| `temponotabe` / `temponotanonbe` | idem |
| `sasstatustransaksi` | `TSSO` ⇒ `TS ACC`, selain itu `SAMS ACC` |
| `statuspembayaran` | `statuspembayaran` (dengan penyesuaian Prosas/CBD) |
| `redeempoint` | `redeempoint` |
| `keterangan` | `keterangan` |
| `tokoaliasid` | bagian setelah `\|` di `tokoidsas` |
| `flgordersalesman` | `flgordersalesman` |
| (konstanta) | `suppliercode='SAS'`, `statusdoc='I'`, `version='1'`, dll |

Detail via fungsi DB:
```php
tasksales.fn_add_orderpembeliandetail(
  opid, kodebarangsas, takssalesdetailid,
  qtyorder, hargasatuanbmk, hargasatuanajuan,
  hargaitembeforetax, hargaitemtax, hargaitemaftertax,
  tasksalescreatedby, tasksalesketerangan
)
```

---

## 9. Checklist untuk sisi pemanggil

- [ ] Kirim `POST` JSON dengan `Content-Type: application/json`.
- [ ] Sertakan `apikey` di body.
- [ ] Lengkapi semua field wajib header (bagian 3.1) + `statuspembayaran` bila `tipetransaksi='T'`.
- [ ] `tasksalessodetail` minimal 1 item, semua field wajibnya terisi (bukan string kosong).
- [ ] Pakai ejaan `takssalesdetailid` (dobel `s`).
- [ ] Jamin keunikan `tasksalesnoso`, `tasksalesid`, dan tiap `takssalesdetailid` (kalau dikirim ulang akan ditolak "sudah ada").
- [ ] Pastikan semua `kodebarangsas` valid di master SAS.
- [ ] Perlakukan sukses hanya bila response `status === "success"`; selain itu baca `errormessage`.
- [ ] Idempotensi/retry: aman karena duplikat ditolak, tapi tangani pesan "sudah ada" sebagai kondisi terpisah dari error sungguhan.

---

## 10. Perbedaan `tambahapiV2`

Hampir identik dengan `tambahapi`, tetapi konversi SO memakai fungsi sub-cabang:
```php
tasksales.fn_convert_so_from_orderpembelian_subcabang($opid, '$grup', '$createdby', $c1_p, $c2_p)
```
Gunakan V2 untuk skenario yang membutuhkan parameter sub-cabang (`subcabang`, c1/c2). Untuk kebutuhan standar, `tambahapi` sudah cukup.
