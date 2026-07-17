<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Database\Eloquent\Model;
use App\Http\Controllers\Controller;
use Illuminate\Support\Facades\Validator;
use DB;
use App;
use Log;
use \Exception;
use \DateTime;
use App\Models\orderpembelian;
use App\Models\orderpembeliandetail;
use App\Models\Api_Call_Wiser;
use App\Models\API_TaskSales;
use App\Models\API_Call_TaskSales;
use App\Models\API_Kemitraan;
use App\Models\API_Call_Kemitraan;
use Sts\PleafCore\CoreException;
use App\Models\OrderPenjualan;
use App\Models\OrderPenjualanDetail;
use App\Models\Toko;
use App\Models\Barang;
use App\Models\SubCabang;
use Carbon\Carbon;
use App\Models\DC_SalesTenantDC;
use App\Models\DC_CustomerTenantDC;
use App\Models\DC_SubTenantDC;
use App\Models\AdjRewardpoint;
use App\Models\BookingStockProgress;
use App\Models\BookingStockRequestor;
use App\Models\BookingStockSTK;
use App\Models\DC_BookingStockRequestor;
use App\Models\DC_BookingStockSTK;
use App\Models\DC_OrderPenjualanDetail;
use App\Models\Stock;
use App\Http\PostCaller;
use App\Models\SoInden;
use App\Models\SoIndenDetail;
use App\Models\AppSetting;

class OrderPembelianController extends Controller
{

	
  public function tambahapi(Request $req)
  {   
    // Insert LOG API
    $api_call = new Api_Call_Wiser();
    $api_call->base_url = url('/');
    $api_call->path = $req->path();
    $api_call->input_json = json_encode($req->all());
    $api_call->status = 'Y';
    $api_call->errormessage = '';
    $api_call->createdby = $req->tasksalesupdatedby;
    $api_call->lastupdatedby = $req->tasksalesupdatedby;
    $api_call->save();

    $api_call_id = $api_call->id;
    
    try{
      $data = null;
      $input = $req->all();
      if (isset($input["orderpembelian"]))       $orderpembelian   = $input["orderpembelian"];
      if (isset($input["orderpembeliandetail"]))   $orderpembeliandetail   = $input["orderpembeliandetail"];
      
      $no = 0 ;
      $cekkodebarang = [];
      $res = [
          'Result' => false,
          'Msg' => 'Tidak ada data'
      ];

      $vali = Validator::make($req->all(),[ 
          // 'omsetsubcabangid'=>'required',
          // 'tasksalesid'=>'required',
          'tasksalesnoso'=>'required',
          'tasksalestglso'=>'required',
          'tokoidsas'=>'required',
          'temponotabe'=>'required',
          'temponotanonbe'=>'required',
          'tipetransaksi'=>'required',
          // 'kodesales'=>'required',
          'tasksalescreatedby'=>'required',
          'tasksalescreatedon'=>'date|required',
          'tasksalesupdatedby'=>'required',
          'tasksalesupdatedon'=>'date|required',
          'tasksalestokostatusbmk'=>'required',
          'tasksalescurrency'=>'required',
          // 'tasksalesketerangan'=> 'required',
          'tasksalessotype'=> 'required',
          // 'statuspembayaran'=>'required'           
      ]);

      if($req->tipetransaksi=='T'){
          $this->validate($req, [
              'statuspembayaran' => 'required',
          ]);
      }

      if ($vali->fails()) {
        throw new \Exception($vali->errors());   
      }

      //Cek Toko apakah toko tersedia atau tidak
      $arrTokoid = explode('|', $req->tokoidsas);
      $tokoidwarisan = $arrTokoid[0];
      $tokoaliasid = (array_key_exists(1, $arrTokoid)) ? (int) $arrTokoid[1] : null;
      $memberprosaspspid = null;
      $tokoid = 0;
      $opid = 0;
      $opid2 = 0;
      $kodetoko = '';
      
      $params = ['tokoid_p' => $tokoidwarisan];      
      $registerUmum = collect(DB::SELECT("SELECT * FROM hr.registermitraumum WHERE tokoid = :tokoid_p LIMIT 1",$params))->first();
      $this->simpleLogger($this, __FUNCTION__, $registerUmum, __LINE__);
        
      $flgRegisterUmum = false;
      if ($registerUmum)
      {
        \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ UMUM +++++++++++++++++++++++++++++++++++++++++++++++");
        $flgRegisterUmum = true;
        /*
          Jika transaksi umum dimasukkan ke Master Toko yg sama CUSTOMER UMUM
        */
        $toko = collect(DB::select("
          WITH cte AS(
            SELECT k.* FROM secure.users u
            JOIN hr.karyawan k ON u.karyawanid = k.id
            WHERE u.username = :username_p LIMIT 1
          )
          SELECT tk.* FROM mstr.mappingtokocabangcustomerpsm cp
          JOIN mstr.toko tk ON cp.tokoid = tk.id
          JOIN cte ct ON cp.recordownerid = ct.recordownerid
        ",['username_p' => $req->tasksalescreatedby]))->first();
        $this->simpleLogger($this, __FUNCTION__, $toko, __LINE__);

        if ($toko == null)
        {
          throw new \Exception('Toko ONLINE SHOP tidak ditemukan');
        }
        
        $tokoidwarisan = $toko->tokoidwarisan;
        $memberprosaspspid = $registerUmum->memberprosaspspid;
      }
      else
      {
        $cektoko = collect(DB::select("SELECT * FROM mstr.toko WHERE tokoidwarisan = :tokoid_p ",$params))->first();
        if($cektoko == null){
          \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ PROSAS +++++++++++++++++++++++++++++++++++++++++++++++");
          $cekprosas = app('App\Http\Controllers\HrmsController')->getKaryawanProsas($tokoidwarisan);
          $this->simpleLogger($this, __FUNCTION__, $cekprosas, __LINE__);

          if ($cekprosas == null)
          {
            throw new \Exception('tokoid tersebut tidak ditemukan');
          }

          /*
            Jika transaksi Prosas dimasukkan ke Master Toko yg sama PERSONIL SAS (PROSAS)
          */
          $toko = collect(DB::select("SELECT * FROM mstr.toko WHERE tokoidwarisan = :tokoid_p",['tokoid_p' => '9727861']))->first();
          
          $tokoidwarisan = $toko->tokoidwarisan;
          $memberprosaspspid = $cekprosas->id;
        }
        else
        {
          $toko = $cektoko;
        }
      }

      $tokoid = $toko->id;
      $kodetoko = $toko->kodetoko;

      //Cek Noso apakah noko tersedia atau tidak
      $ceknoso = DB::select(DB::raw("Select docno from tos.orderpembelian where docno='".$req->tasksalesnoso."' and sotype = '".$req->tasksalessotype."' "));
      
      if($ceknoso != null){
        throw new \Exception('Noso tersebut sudah ada');
      } 

      $cekext = DB::select(DB::raw("Select externalid from tos.orderpembelian where externalid='".$req->tasksalesid."' and sotype = '".$req->tasksalessotype."' "));
      
      if($cekext != null){
        throw new \Exception("tasksalesid '".$req->tasksalesid."' tersebut sudah ada");
      } 

      $arrBarang = [];
      //cek apakah data kolom terisi atau kosong
      foreach ($req->tasksalessodetail as $key => $d) {        
        if($d["kodebarangsas"] == "") {
          throw new \Exception('kodebarangsas kosong');
        } 
        else if($d["takssalesdetailid"] == "") {
          throw new \Exception('takssalesdetailid kosong');
        }
        // else if($d["tasksalesproductcode"] == "") {
        //     return response()->json(['error'=>'tasksalesproductcode kosong']); 
        // } 
        else if($d["qtyorder"] == "") {
          throw new \Exception('qtyorder kosong');
        }
        else if($d["hargasatuanbmk"] == "") {
          throw new \Exception('hargasatuanbmk kosong');
        }
        else if($d["hargasatuanajuan"] == "") {
          throw new \Exception('hargasatuanajuan kosong');
        }
        else if($d["hargaitembeforetax"] == "") {
          throw new \Exception('hargaitembeforetax kosong');
        }
        else if($d["hargaitemtax"] == "") {
          throw new \Exception('hargaitemtax kosong');
        }
        else if($d["hargaitemaftertax"] == "") {
          throw new \Exception('hargaitemaftertax kosong');
        }

        $cekextid = DB::select(DB::raw("
            Select a.externaldetailid from tos.orderpembeliandetail a
            join tos.orderpembelian b on a.orderpembelianid = b.id 
            where a.externaldetailid = '" .$d['takssalesdetailid'] . "'
            and b.sotype = '".$req->tasksalessotype."'
        "));
      
        if($cekextid != null){
          throw new \Exception("takssalesdetailid '" .$d['takssalesdetailid'] . "' tersebut sudah ada");
        }

        $cek = DB::select(DB::raw
            ("Select id from mstr.stock where kodebarang='".$d["kodebarangsas"]."'"));

        //Cek kode barang sesuai atau belum
        if($cek == null)
        {
          $cekkodebarang[$no] = $d["kodebarangsas"] ;
          $no++;
        }
        else
        {
          switch (substr($d["kodebarangsas"], 0, 3)) {
            case "FB2": case "FB4":
              $arrBarang[] = 'FB';
              break;

            case "FE2": case "FE4":
              $arrBarang[] = 'FE';
              break;

            case "FAB":
              $arrBarang[] = 'FAB';
              break;

            case "FC2": case "FC2":
              $arrBarang[] = 'FC2';
              break;

            case "FC4": case "FC4":
              $arrBarang[] = 'FC4';
              break;

            case "FA2": 
              $arrBarang[] = 'FA2';
              break;

            case "FA4": 
              $arrBarang[] = 'FA4';
              break;

            case "FX2": case "FX4":
              $arrBarang[] = 'FX';
              break;

            case "FL2": case "FL4":
              $arrBarang[] = 'FL';
              break;

            case "FS2": case "FS4":
              $arrBarang[] = 'FS';
              break;

            case "FAL": case "FAL":
              $arrBarang[] = 'FAL';
              break;

            case "FAR": case "FAR":
              $arrBarang[] = 'FAR';
              break;

            case "FAT": case "FAT":
              $arrBarang[] = 'FAT';
              break;

            case "FAC": case "FAC":
              $arrBarang[] = 'FAC';
              break;

            case "FAF": case "FAF":
              $arrBarang[] = 'FAF';
              break;

            case "FAY": case "FAY":
              $arrBarang[] = 'FAY';
              break;

            case "FAQ": case "FAQ":
              $arrBarang[] = 'FAQ';
              break;

            case "FAS": case "FAS":
              $arrBarang[] = 'FAS';
              break;

            case "FAJ": case "FAJ":
              $arrBarang[] = 'FAJ';
              break;

            case "FAK": case "FAK":
              $arrBarang[] = 'FAK';
              break;

            case "FLB": case "FLB":
              $arrBarang[] = 'FLB';
              break;

            case "FAG": case "FAG":
              $arrBarang[] = 'FAG';
              break;
            
            case "FLD": case "FLD":
              $arrBarang[] = 'FLD';
              break;

            case "FAW": case "FAW":
              $arrBarang[] = 'FAW';
              break;  

            case "FAV": case "FAV":
              $arrBarang[] = 'FAV';
              break;  

            case "FAM": case "FAM":
              $arrBarang[] = 'FAM';
              break; 

            case "FLC":
              $arrBarang[] = 'FLC';
              break; 

            case "FLE":
              $arrBarang[] = 'FLE';
              break; 

            case "FLU":
              $arrBarang[] = 'FLU';
              break; 

            case "FAO":
              $arrBarang[] = 'FAO';
              break;

            case "FAN":
              $arrBarang[] = 'FAN';
              break;

            case "FAX":
              $arrBarang[] = 'FAX';
              break;

            case "FAP":
              $arrBarang[] = 'FAP';
              break;

            case "FAS":
              $arrBarang[] = 'FAS';
              break;

            case "FAU":
              $arrBarang[] = 'FAU';
              break;

            case "FAI":
              $arrBarang[] = 'FAI';
              break;

            case "FAE":
              $arrBarang[] = 'FAE';
              break;

            case "FAD":
              $arrBarang[] = 'FAD';
              break; 

            case "FAZ":
              $arrBarang[] = 'FAZ';
              break; 

            case "FDC":
              $arrBarang[] = 'FDC';
              break; 

            case "FDD":
              $arrBarang[] = 'FDD';
              break; 

            case "FDE":
              $arrBarang[] = 'FDE';
              break; 

            case "FDF":
              $arrBarang[] = 'FDF';
              break; 

            case "FDH":
              $arrBarang[] = 'FDH';
              break; 

            case "FDI":
              $arrBarang[] = 'FDI';
              break; 

            case "FDJ":
              $arrBarang[] = 'FDJ';
              break; 

            case "FDG":
              $arrBarang[] = 'FDG';
              break; 

            case "FDL":
              $arrBarang[] = 'FDL';
              break; 

            case "FDK":
              $arrBarang[] = 'FDK';
              break; 

            case "FDM":
              $arrBarang[] = 'FDM';
              break; 

            case "FDN":
              $arrBarang[] = 'FDN';
              break; 

            case "FDO":
              $arrBarang[] = 'FDO';
              break; 

            case "FDP":
              $arrBarang[] = 'FDP';
              break; 

            case "FDQ":
              $arrBarang[] = 'FDQ';
              break; 

            case "FDR":
              $arrBarang[] = 'FDR';
              break; 

            case "FDS":
              $arrBarang[] = 'FDS';
              break; 

            case "FDT":
              $arrBarang[] = 'FDT';
              break; 

            case "FDU":
              $arrBarang[] = 'FDU';
              break; 

            case "FDV":
              $arrBarang[] = 'FDV';
              break; 

            case "FDW":
              $arrBarang[] = 'FDW';
              break; 

            case "FDX":
              $arrBarang[] = 'FDX';
              break; 

            case "FDY":
              $arrBarang[] = 'FDY';
              break; 

            case "FDZ":
              $arrBarang[] = 'FDZ';
              break; 

            case "FFB":
              $arrBarang[] = 'FFB';
              break; 

            case "FFA":
              $arrBarang[] = 'FFA';
              break; 

            case "FFC":
              $arrBarang[] = 'FFC';
              break; 

            case "FFD":
              $arrBarang[] = 'FFD';
              break; 

            case "FFE":
              $arrBarang[] = 'FFE';
              break; 

            case "FFF":
              $arrBarang[] = 'FFF';
              break; 

            case "FFG":
              $arrBarang[] = 'FFG';
              break; 

            case "FFH":
              $arrBarang[] = 'FFH';
              break; 

            case "FFI":
              $arrBarang[] = 'FFI';
              break; 

            case "FFJ":
              $arrBarang[] = 'FFJ';
              break; 

            case "FFK":
              $arrBarang[] = 'FFK';
              break; 

            case "FFL":
              $arrBarang[] = 'FFL';
              break; 

            case "FFM":
              $arrBarang[] = 'FFM';
              break; 

            case "FFP":
              $arrBarang[] = 'FFP';
              break; 

            case "FFN":
              $arrBarang[] = 'FFN';
              break; 

            case "FFO":
              $arrBarang[] = 'FFO';
              break; 

            case "FFU":
              $arrBarang[] = 'FFU';
              break; 

            case "FFV":
              $arrBarang[] = 'FFV';
              break; 

            case "FFW":
              $arrBarang[] = 'FFW';
              break; 

            case "FFX":
              $arrBarang[] = 'FFX';
              break; 

            case "FFY":
              $arrBarang[] = 'FFY';
              break; 

            case "FFZ":
              $arrBarang[] = 'FFZ';
              break; 

            case "FGA":
              $arrBarang[] = 'FGA';
              break; 

            case "FGB":
              $arrBarang[] = 'FGB';
              break; 

            case "FGD":
              $arrBarang[] = 'FGD';
              break; 

            case "FGE":
              $arrBarang[] = 'FGE';
              break; 

            case "FGC":
              $arrBarang[] = 'FGC';
              break; 

            case "FGF":
              $arrBarang[] = 'FGF';
              break; 

            case "FGG":
              $arrBarang[] = 'FGG';
              break; 

            case "RAA":
              $arrBarang[] = 'RAA';
              break; 

            case "FGI":
              $arrBarang[] = 'FGI';
              break; 

            case "FGJ":
              $arrBarang[] = 'FGJ';
              break; 

            case "FGK":
              $arrBarang[] = 'FGK';
              break; 

            default:
              $arrBarang[] = 'FC';
              break;
          }
        }
      }
    } 
    catch(\Exception $ex) {
      $api_call_upd = Api_Call_Wiser::find($api_call_id);
      $api_call->status = 'N';
      $api_call->errormessage = $ex->getMessage();
      $api_call->update();

      return response()->json([
        'status'=>false, 
        'wisertosopid'=>null, 
        'errormessage'=>$ex->getMessage().' Line: '.$ex->getLine()
      ]); 
    }
    $this->simpleLogger($this, __FUNCTION__, $arrBarang, __LINE__);
    
    if ($cekkodebarang != null){
      $api_call_upd = Api_Call_Wiser::find($api_call_id);
      $api_call->status = 'N';
      $api_call->errormessage = 'kodebarangsas ' . $cekkodebarang[0] . ' tidak sesuai';
      $api_call->update();
      
      return response()->json([
        'status' => false,                    
        'errormessage' => 'kodebarangsas ' . $cekkodebarang[0] . ' tidak sesuai'
      ]);
    }
    else
    {
      try
      {
        DB::beginTransaction();
        DB::connection("pgsql_wiserdc")->beginTransaction();

        // Insert Orderpembelian
        $opid = $this->insertOrderpembelian($req->all(),$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid, $flgRegisterUmum);

        //save detail orderpembelian
        $this->insertOrderpembelianDetail($req->all(),$opid,$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid);

        foreach (array_unique($arrBarang) as $key => $value) {
          $convertSo = DB::select(DB::raw("SELECT * FROM tasksales.fn_convert_so_from_orderpembelian($opid, '$value', '$req->tasksalescreatedby')"));
          $this->simpleLogger($this, __FUNCTION__, $convertSo, __LINE__);
        }

        // Input fitur baru
        // $bookingstockrequestor = $this->insertbookingstockrequestor($req->tasksalesnoso, $req->tasksalestglso, $req->tasksalescreatedby);

        // Cek SASA order ke SAP
        $insertSo = $this->insertSoSASAToSAP($req->all(),$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid,$arrBarang,$opid);
        $this->simpleLogger($this, __FUNCTION__, $insertSo, __LINE__);

        // CREATE SO WISER TO TASKSALES OR KEMITRAAN
        $createSo = $this->createSoWiserToSobat($req->all(),$opid);
        $this->simpleLogger($this, __FUNCTION__, $createSo, __LINE__);
        
        DB::commit();
        DB::connection("pgsql_wiserdc")->commit();

        //Menampilkan user tospos yang sedang berjalan
        $user=\DB::select(\DB::raw ("select * from tos.orderpembelian where id = ". $opid ));

        return response()->json([
          'status'=>'success', 
          'wisertosopid'=>$user[0]->id, 
          'errormessage'=>'No Error Detected'
        ]);        
      }
      catch(\Exception $ex) {
        DB::rollback();
        DB::connection("pgsql_wiserdc")->rollback();
        // return($ex);
        if ($opid)
        {
          DB::select(DB::raw("SELECT * FROM tasksales.deleteorderpembelian($opid)"));
        }

        if ($opid2)
        {
          DB::select(DB::raw("SELECT * FROM tasksales.deleteorderpembelian($opid2)"));
        }

        $api_call_upd = Api_Call_Wiser::find($api_call_id);
        $api_call->status = 'N';
        $api_call->errormessage = $ex->getMessage();
        $api_call->update();

        return response()->json([
          'status'=>false, 
          'wisertosopid'=>null, 
          'errormessage'=>$ex->getMessage().' Line: '.$ex->getLine()
        ]); 
      }
    }
  }

  public function tambahapiV2(Request $req)
  {   
    // Insert LOG API
    $api_call = new Api_Call_Wiser();
    $api_call->base_url = url('/');
    $api_call->path = $req->path();
    $api_call->input_json = json_encode($req->all());
    $api_call->status = 'Y';
    $api_call->errormessage = '';
    $api_call->createdby = $req->tasksalesupdatedby;
    $api_call->lastupdatedby = $req->tasksalesupdatedby;
    $api_call->save();

    $api_call_id = $api_call->id;
    
    try{
      $data = null;
      $input = $req->all();
      if (isset($input["orderpembelian"]))       $orderpembelian   = $input["orderpembelian"];
      if (isset($input["orderpembeliandetail"]))   $orderpembeliandetail   = $input["orderpembeliandetail"];
      
      $no = 0 ;
      $cekkodebarang = [];
      $res = [
          'Result' => false,
          'Msg' => 'Tidak ada data'
      ];

      $vali = Validator::make($req->all(),[ 
          // 'omsetsubcabangid'=>'required',
          // 'tasksalesid'=>'required',
          'tasksalesnoso'=>'required',
          'tasksalestglso'=>'required',
          'tokoidsas'=>'required',
          'temponotabe'=>'required',
          'temponotanonbe'=>'required',
          'tipetransaksi'=>'required',
          // 'kodesales'=>'required',
          'tasksalescreatedby'=>'required',
          'tasksalescreatedon'=>'date|required',
          'tasksalesupdatedby'=>'required',
          'tasksalesupdatedon'=>'date|required',
          'tasksalestokostatusbmk'=>'required',
          'tasksalescurrency'=>'required',
          // 'tasksalesketerangan'=> 'required',
          'tasksalessotype'=> 'required',
          // 'statuspembayaran'=>'required'           
      ]);

      if($req->tipetransaksi=='T'){
          $this->validate($req, [
              'statuspembayaran' => 'required',
          ]);
      }

      if ($vali->fails()) {
        throw new \Exception($vali->errors());   
      }

      //Cek Toko apakah toko tersedia atau tidak
      $arrTokoid = explode('|', $req->tokoidsas);
      $tokoidwarisan = $arrTokoid[0];
      $tokoaliasid = (array_key_exists(1, $arrTokoid)) ? (int) $arrTokoid[1] : null;
      $memberprosaspspid = null;
      $tokoid = 0;
      $opid = 0;
      $opid2 = 0;
      $kodetoko = '';
      
      $params = ['tokoid_p' => $tokoidwarisan];      
      $registerUmum = collect(DB::SELECT("SELECT * FROM hr.registermitraumum WHERE tokoid = :tokoid_p LIMIT 1",$params))->first();
      $this->simpleLogger($this, __FUNCTION__, $registerUmum, __LINE__);
        
      $flgRegisterUmum = false;
      if ($registerUmum)
      {
        \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ UMUM +++++++++++++++++++++++++++++++++++++++++++++++");
        $flgRegisterUmum = true;
        /*
          Jika transaksi umum dimasukkan ke Master Toko yg sama CUSTOMER UMUM
        */
        $toko = collect(DB::select("
          WITH cte AS(
            SELECT k.* FROM secure.users u
            JOIN hr.karyawan k ON u.karyawanid = k.id
            WHERE u.username = :username_p LIMIT 1
          )
          SELECT tk.* FROM mstr.mappingtokocabangcustomerpsm cp
          JOIN mstr.toko tk ON cp.tokoid = tk.id
          JOIN cte ct ON cp.recordownerid = ct.recordownerid
        ",['username_p' => $req->tasksalescreatedby]))->first();
        $this->simpleLogger($this, __FUNCTION__, $toko, __LINE__);

        if ($toko == null)
        {
          throw new \Exception('Toko ONLINE SHOP tidak ditemukan');
        }
        
        $tokoidwarisan = $toko->tokoidwarisan;
        $memberprosaspspid = $registerUmum->memberprosaspspid;
      }
      else
      {
        $cektoko = collect(DB::select("SELECT * FROM mstr.toko WHERE tokoidwarisan = :tokoid_p ",$params))->first();
        if($cektoko == null){
          \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ PROSAS +++++++++++++++++++++++++++++++++++++++++++++++");
          $cekprosas = app('App\Http\Controllers\HrmsController')->getKaryawanProsas($tokoidwarisan);
          $this->simpleLogger($this, __FUNCTION__, $cekprosas, __LINE__);

          if ($cekprosas == null)
          {
            throw new \Exception('tokoid tersebut tidak ditemukan');
          }

          /*
            Jika transaksi Prosas dimasukkan ke Master Toko yg sama PERSONIL SAS (PROSAS)
          */
          $toko = collect(DB::select("SELECT * FROM mstr.toko WHERE tokoidwarisan = :tokoid_p",['tokoid_p' => '9727861']))->first();
          
          $tokoidwarisan = $toko->tokoidwarisan;
          $memberprosaspspid = $cekprosas->id;
        }
        else
        {
          $toko = $cektoko;
        }
      }

      $tokoid = $toko->id;
      $kodetoko = $toko->kodetoko;

      //Cek Noso apakah noko tersedia atau tidak
      $ceknoso = DB::select(DB::raw("Select docno from tos.orderpembelian where docno='".$req->tasksalesnoso."' and sotype = '".$req->tasksalessotype."' "));
      
      if($ceknoso != null){
        throw new \Exception('Noso tersebut sudah ada');
      } 

      $cekext = DB::select(DB::raw("Select externalid from tos.orderpembelian where externalid='".$req->tasksalesid."' and sotype = '".$req->tasksalessotype."' "));
      
      if($cekext != null){
        throw new \Exception("tasksalesid '".$req->tasksalesid."' tersebut sudah ada");
      } 

      $arrBarang = [];
      //cek apakah data kolom terisi atau kosong
      foreach ($req->tasksalessodetail as $key => $d) {        
        if($d["kodebarangsas"] == "") {
          throw new \Exception('kodebarangsas kosong');
        } 
        else if($d["takssalesdetailid"] == "") {
          throw new \Exception('takssalesdetailid kosong');
        }
        // else if($d["tasksalesproductcode"] == "") {
        //     return response()->json(['error'=>'tasksalesproductcode kosong']); 
        // } 
        else if($d["qtyorder"] == "") {
          throw new \Exception('qtyorder kosong');
        }
        else if($d["hargasatuanbmk"] == "") {
          throw new \Exception('hargasatuanbmk kosong');
        }
        else if($d["hargasatuanajuan"] == "") {
          throw new \Exception('hargasatuanajuan kosong');
        }
        else if($d["hargaitembeforetax"] == "") {
          throw new \Exception('hargaitembeforetax kosong');
        }
        else if($d["hargaitemtax"] == "") {
          throw new \Exception('hargaitemtax kosong');
        }
        else if($d["hargaitemaftertax"] == "") {
          throw new \Exception('hargaitemaftertax kosong');
        }

        $cekextid = DB::select(DB::raw("
            Select a.externaldetailid from tos.orderpembeliandetail a
            join tos.orderpembelian b on a.orderpembelianid = b.id 
            where a.externaldetailid = '" .$d['takssalesdetailid'] . "'
            and b.sotype = '".$req->tasksalessotype."'
        "));
      
        if($cekextid != null){
          throw new \Exception("takssalesdetailid '" .$d['takssalesdetailid'] . "' tersebut sudah ada");
        }

        $cek = DB::select(DB::raw
            ("Select id from mstr.stock where kodebarang='".$d["kodebarangsas"]."'"));

        //Cek kode barang sesuai atau belum
        if($cek == null)
        {
          $cekkodebarang[$no] = $d["kodebarangsas"] ;
          $no++;
        }
        else
        {
          switch (substr($d["kodebarangsas"], 0, 3)) {
            case "FB2": case "FB4":
              $arrBarang[] = 'FB';
              break;

            case "FE2": case "FE4":
              $arrBarang[] = 'FE';
              break;

            case "FAB":
              $arrBarang[] = 'FAB';
              break;

            case "FC2": case "FC2":
              $arrBarang[] = 'FC2';
              break;

            case "FC4": case "FC4":
              $arrBarang[] = 'FC4';
              break;

            case "FA2": 
              $arrBarang[] = 'FA2';
              break;

            case "FA4": 
              $arrBarang[] = 'FA4';
              break;

            case "FX2": case "FX4":
              $arrBarang[] = 'FX';
              break;

            case "FL2": case "FL4":
              $arrBarang[] = 'FL';
              break;

            case "FS2": case "FS4":
              $arrBarang[] = 'FS';
              break;

            case "FAL": case "FAL":
              $arrBarang[] = 'FAL';
              break;

            case "FAR": case "FAR":
              $arrBarang[] = 'FAR';
              break;

            case "FAT": case "FAT":
              $arrBarang[] = 'FAT';
              break;

            case "FAC": case "FAC":
              $arrBarang[] = 'FAC';
              break;

            case "FAF": case "FAF":
              $arrBarang[] = 'FAF';
              break;

            case "FAY": case "FAY":
              $arrBarang[] = 'FAY';
              break;

            case "FAQ": case "FAQ":
              $arrBarang[] = 'FAQ';
              break;

            case "FAS": case "FAS":
              $arrBarang[] = 'FAS';
              break;

            case "FAJ": case "FAJ":
              $arrBarang[] = 'FAJ';
              break;

            case "FAK": case "FAK":
              $arrBarang[] = 'FAK';
              break;

            case "FLB": case "FLB":
              $arrBarang[] = 'FLB';
              break;

            case "FAG": case "FAG":
              $arrBarang[] = 'FAG';
              break;
            
            case "FLD": case "FLD":
              $arrBarang[] = 'FLD';
              break;

            case "FAW": case "FAW":
              $arrBarang[] = 'FAW';
              break;  

            case "FAV": case "FAV":
              $arrBarang[] = 'FAV';
              break;  

            case "FAM": case "FAM":
              $arrBarang[] = 'FAM';
              break; 

            case "FLC":
              $arrBarang[] = 'FLC';
              break; 

            case "FLE":
              $arrBarang[] = 'FLE';
              break; 

            case "FLU":
              $arrBarang[] = 'FLU';
              break; 

            case "FAO":
              $arrBarang[] = 'FAO';
              break;

            case "FAN":
              $arrBarang[] = 'FAN';
              break;

            case "FAX":
              $arrBarang[] = 'FAX';
              break;

            case "FAP":
              $arrBarang[] = 'FAP';
              break;

            case "FAS":
              $arrBarang[] = 'FAS';
              break;

            case "FAU":
              $arrBarang[] = 'FAU';
              break;

            case "FAI":
              $arrBarang[] = 'FAI';
              break;

            case "FAE":
              $arrBarang[] = 'FAE';
              break;

            case "FAD":
              $arrBarang[] = 'FAD';
              break; 

            case "FAZ":
              $arrBarang[] = 'FAZ';
              break; 

            case "FDC":
              $arrBarang[] = 'FDC';
              break; 

            case "FDD":
              $arrBarang[] = 'FDD';
              break; 

            case "FDE":
              $arrBarang[] = 'FDE';
              break; 

            case "FDF":
              $arrBarang[] = 'FDF';
              break; 

            case "FDH":
              $arrBarang[] = 'FDH';
              break; 

            case "FDI":
              $arrBarang[] = 'FDI';
              break; 

            case "FDJ":
              $arrBarang[] = 'FDJ';
              break; 

            case "FDG":
              $arrBarang[] = 'FDG';
              break; 

            case "FDL":
              $arrBarang[] = 'FDL';
              break; 

            case "FDK":
              $arrBarang[] = 'FDK';
              break; 

            case "FDM":
              $arrBarang[] = 'FDM';
              break; 

            case "FDN":
              $arrBarang[] = 'FDN';
              break; 

            case "FDO":
              $arrBarang[] = 'FDO';
              break; 

            case "FDP":
              $arrBarang[] = 'FDP';
              break; 

            case "FDQ":
              $arrBarang[] = 'FDQ';
              break; 

            case "FDR":
              $arrBarang[] = 'FDR';
              break; 

            case "FDS":
              $arrBarang[] = 'FDS';
              break; 

            case "FDT":
              $arrBarang[] = 'FDT';
              break; 

            case "FDU":
              $arrBarang[] = 'FDU';
              break; 

            case "FDV":
              $arrBarang[] = 'FDV';
              break; 

            case "FDW":
              $arrBarang[] = 'FDW';
              break; 

            case "FDX":
              $arrBarang[] = 'FDX';
              break; 

            case "FDY":
              $arrBarang[] = 'FDY';
              break; 

            case "FDZ":
              $arrBarang[] = 'FDZ';
              break; 

            case "FFB":
              $arrBarang[] = 'FFB';
              break; 

            case "FFA":
              $arrBarang[] = 'FFA';
              break; 

            case "FFC":
              $arrBarang[] = 'FFC';
              break; 

            case "FFD":
              $arrBarang[] = 'FFD';
              break; 

            case "FFE":
              $arrBarang[] = 'FFE';
              break; 

            case "FFF":
              $arrBarang[] = 'FFF';
              break; 

            default:
              $arrBarang[] = 'FC';
              break;
          }
        }
      }
    } 
    catch(\Exception $ex) {
      $api_call_upd = Api_Call_Wiser::find($api_call_id);
      $api_call->status = 'N';
      $api_call->errormessage = $ex->getMessage();
      $api_call->update();

      return response()->json([
        'status'=>false, 
        'wisertosopid'=>null, 
        'errormessage'=>$ex->getMessage().' Line: '.$ex->getLine()
      ]); 
    }
    $this->simpleLogger($this, __FUNCTION__, $arrBarang, __LINE__);
    
    if ($cekkodebarang != null){
      $api_call_upd = Api_Call_Wiser::find($api_call_id);
      $api_call->status = 'N';
      $api_call->errormessage = 'kodebarangsas ' . $cekkodebarang[0] . ' tidak sesuai';
      $api_call->update();
      
      return response()->json([
        'status' => false,                    
        'errormessage' => 'kodebarangsas ' . $cekkodebarang[0] . ' tidak sesuai'
      ]);
    }
    else
    {
      try
      {
        DB::beginTransaction();
        DB::connection("pgsql_wiserdc")->beginTransaction();

        // Insert Orderpembelian
        $opid = $this->insertOrderpembelian($req->all(),$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid, $flgRegisterUmum);

        //save detail orderpembelian
        $this->insertOrderpembelianDetail($req->all(),$opid,$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid);

        foreach (array_unique($arrBarang) as $key => $value) {
          $kode = AppSetting::where("recordownerid", "=", $req->subcabang)->where("keyid","=","PREFER_C2")->first();
          $c1_p = $req->subcabang;
          //$c2_p = SubCabang::where("kodesubcabang", "=", $kode->value)->first();
          $c2 = DB::select(DB::raw("SELECT * FROM mstr.subcabang WHERE kodesubcabang = '" .$kode->value. "'"));
          $c2_p = $c2[0]->id;
          $convertSo = DB::select(DB::raw("SELECT * FROM tasksales.fn_convert_so_from_orderpembelian_subcabang($opid, '$value', '$req->tasksalescreatedby', $c1_p, $c2_p)"));
          $this->simpleLogger($this, __FUNCTION__, $convertSo, __LINE__);
        }

        // Input fitur baru
        // $bookingstockrequestor = $this->insertbookingstockrequestor($req->tasksalesnoso, $req->tasksalestglso, $req->tasksalescreatedby);

        // Cek SASA order ke SAP
        $insertSo = $this->insertSoSASAToSAP($req->all(),$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid,$arrBarang,$opid);
        $this->simpleLogger($this, __FUNCTION__, $insertSo, __LINE__);

        // CREATE SO WISER TO TASKSALES OR KEMITRAAN
        $createSo = $this->createSoWiserToSobat($req->all(),$opid);
        $this->simpleLogger($this, __FUNCTION__, $createSo, __LINE__);
        
        DB::commit();
        DB::connection("pgsql_wiserdc")->commit();

        //Menampilkan user tospos yang sedang berjalan
        $user=\DB::select(\DB::raw ("select * from tos.orderpembelian where id = ". $opid ));

        return response()->json([
          'status'=>'success', 
          'wisertosopid'=>$user[0]->id, 
          'errormessage'=>'No Error Detected'
        ]);        
      }
      catch(\Exception $ex) {
        DB::rollback();
        DB::connection("pgsql_wiserdc")->rollback();
        // return($ex);
        if ($opid)
        {
          DB::select(DB::raw("SELECT * FROM tasksales.deleteorderpembelian($opid)"));
        }

        if ($opid2)
        {
          DB::select(DB::raw("SELECT * FROM tasksales.deleteorderpembelian($opid2)"));
        }

        $api_call_upd = Api_Call_Wiser::find($api_call_id);
        $api_call->status = 'N';
        $api_call->errormessage = $ex->getMessage();
        $api_call->update();

        return response()->json([
          'status'=>false, 
          'wisertosopid'=>null, 
          'errormessage'=>$ex->getMessage().' Line: '.$ex->getLine()
        ]); 
      }
    }
  }


  function createSoWiserToSobat($req,$opid)
  {
    $order = DB::select(DB::raw("
      SELECT
       op.nopickinglist, op.tglpickinglist, op.recordownerid, op.temponota, sb.kodesubcabang, E.totalgross, E.totalnetto, E.totaldisc, E.totalppn
      FROM pj.orderpenjualan op
      LEFT JOIN LATERAL(
          SELECT SUM(qtyso*hrgsatuanbrutto) AS totalgross,
          SUM(qtyso*hrgsatuannetto) AS totalnetto,
          SUM(disc1*hrgsatuanbrutto) AS totaldisc,
          SUM(ppn*hrgsatuanbrutto) AS totalppn
          FROM pj.orderpenjualandetail
          WHERE orderpenjualanid = op.id
      ) E ON TRUE
      LEFT JOIN mstr.subcabang sb ON sb.id = op.recordownerid
      WHERE op.tosorderpembelianid=$opid
    "));

    $orderdetail = DB::select(DB::raw("
      SELECT
      opd.id AS line_no,
      op.nopickinglist, op.tglpickinglist, opd.hrgsatuanbrutto, opd.hrgsatuannetto, opd.qtyso, opd.disc1, opd.ppn, sb.kodesubcabang, st.kodebarang
      FROM pj.orderpenjualan op
      LEFT JOIN pj.orderpenjualandetail opd ON opd.orderpenjualanid = op.id
      LEFT JOIN mstr.subcabang sb ON sb.id = op.recordownerid
      LEFT JOIN mstr.stock st ON st.id = opd.stockid
      WHERE op.tosorderpembelianid=$opid
    "));

    $apix2 = new API_TaskSales();
    $api_call2 = new API_Call_TaskSales();
    $key = 'TASK_SALES';
    $tenant_code = 'SAS';
    $ou_code = $order[0]->kodesubcabang;

    $apikey = DB::select(DB::raw("Select api_token from tasksales.loginusers where key ='".$key."' "));

    $header = [];
    foreach ($order as $c4) {
      $doc_nohdr = $ou_code . '-' . $c4->nopickinglist;
      $header[] = [
        "ou_code"             => $ou_code,
        "doc_no"              => $doc_nohdr,
        "doc_date"            => (new \DateTime($c4->tglpickinglist))->format("Ymd"),
        "due_days"            => ($c4->temponota) ? $c4->temponota : 0,
        "total_gross_amount"  => $c4->totalgross,
        "total_disc_amount"   => $c4->totaldisc,
        "total_nett_amount"   => $c4->totalnetto,
        "total_tax_amount"    => $c4->totalppn
      ];
    }

    $detail = [];
    foreach ($orderdetail as $c5) {
      $doc_nodet = $ou_code . '-' . $c5->nopickinglist;
      $detail[] = [
        "ou_code"         => $ou_code,
        "doc_no"          => $doc_nodet,
        "doc_date"        => (new \DateTime($c5->tglpickinglist))->format("Ymd"),
        "line_no"         => $c5->line_no,
        "product_code"    => $c5->kodebarang,
        "qty_order"       => $c5->qtyso,
        "gross_price"     => $c5->hrgsatuanbrutto,
        "disc_price"      => $c5->disc1,
        "nett_price"      => $c5->hrgsatuannetto,
        "tax_price"       => $c5->ppn,
        "gross_amount"    => doubleval(intval($c5->qtyso) * doubleval($c5->hrgsatuanbrutto)),
        "disc_amount"     => doubleval(intval($c5->disc1) / 100 * doubleval($c5->hrgsatuanbrutto)),
        "nett_amount"     => doubleval(intval($c5->qtyso) * doubleval($c5->hrgsatuannetto)),
        "tax_amount"      => doubleval(intval($c5->ppn) / 100 * doubleval($c5->hrgsatuanbrutto))
      ];
    }

    $data = [
      "session_uuid" => $this->GUID(),
      "api_key"      => $apikey[0]->api_token,
      "tenant_code"  => $tenant_code,
      "datetime"     => date("YmdHis"),
      "username"     => $req['tasksalescreatedby'],
      "doc_no"       => $req['tasksalesnoso'],
      "doc_date"     => (new \DateTime($req['tasksalestglso']))->format("Ymd"),
      "so_list"      => $header,
      "so_item_list" => $detail
    
    ];

    //========= SEND API CREATE SO =========//            
    $api_call2->base_url = $apix2->host;
    $api_call2->path = $apix2->apis['CreateSOWiser']['endpoint'];
    $api_call2->input_json = json_encode($data);
    $api_call2->success = '';
    $api_call2->error_message = '';
    $api_call2->createdby  =  strtoupper($req['tasksalescreatedby']);
    $api_call2->lastupdatedby  =  strtoupper($req['tasksalescreatedby']);
    $api_call2->http_code = null;
    $api_call2->response_body = '';
    $api_call2->save();

    $apires2 = $apix2->send("CreateSOWiser", $data);
    if($apires2["result"]){
      $api_call2->error_message = $apires2['data']['error_message'];
      if($apires2['data']['success']== true){
          $api_call2->success =  'Y';
      }
      else{
          $api_call2->success =  'N';
      }
      $api_call2->http_code =  $apires2['status'];
      $api_call2->response_body = $apires2 ? json_encode($apires2) : '';
          
      $api_call2->save();

    }else{
      $api_call2->error_message = $apires2["message"];
      $api_call2->success = 'N';
      $api_call2->http_code = 500;
      $api_call2->response_body = $apires2 ? json_encode($apires2) : '';
      $api_call2->save();
    }

    $result = [
      "success" =>true,
      "message" =>"",
    ];

    return $result;
  }

  function cancelSOItemTaskSalesKemitraan($arrDetail)
  {
    foreach ($arrDetail as $var) {
      $opd     = OrderPenjualanDetail::find($var['detailid']);
      $op      = OrderPenjualan::find($opd->orderpenjualanid);
      $tos     = orderpembelian::find($op->tosorderpembelianid);
      $stock   = Barang::find($opd->stockid);

      //========= GET JSON CANCEL SO =========//
      $subcabanguser = SubCabang::find($op->recordownerid);
      $apix         = new API_TaskSales();
      $api_call     = new API_Call_TaskSales();
      $key          = 'TASK_SALES';
      $tenant_code  = 'SAS';
      $ou_code      = $subcabanguser->kodesubcabang;
      $docno        = $tos->docno;
      $docdate      = $tos->docdate;
      $doc_nodetail = $subcabanguser->kodesubcabang . '-' . $op->nopickinglist;

      $so_list[] = [
        "ou_code"   => $ou_code,
        "doc_no"    => $doc_nodetail,
        "doc_date"  => (new \DateTime($op->tglpickinglist))->format("Ymd")
      ];

      $so_item_list[] = [
        "ou_code"      => $ou_code, 
        "doc_no"       => $doc_nodetail,
        "doc_date"     => (new \DateTime($op->tglpickinglist))->format("Ymd"),
        "product_code" => $stock->kodebarang,
        "line_no"      => $var['detailid'],
        "qty_cancel"   => ($var['qtysoacc']) ? $var['qtysoacc'] : $var['qtyso']
      ]; 
    }

    $params = ['key' => $key];
    $apikey = DB::select("Select api_token from tasksales.loginusers where key = :key ",$params);

    $dat = [
        "session_uuid"    => $this->GUID(),
        "api_key"         => $apikey[0]->api_token,
        "tenant_code"     => $tenant_code,
        "datetime"        => date("YmdHis"),
        "username"        => ($tos->createdby) ? $tos->createdby : 'MITRA',
        "doc_no"          => $docno,
        "doc_date"        => (new \DateTime($docdate))->format("Ymd"),
        "so_list"         => $so_list,
        "so_item_list"    => $so_item_list
    ];
    //========= END JSON CANCEL SO =========//

    //========= SEND API CANCEL SO =========//
    $api_call->base_url = $apix->host;
    $api_call->path = $apix->apis['CancelSOItemWiser']['endpoint'];
    $api_call->input_json = json_encode($dat);
    $api_call->success = '';
    $api_call->error_message = '';
    $api_call->createdby  =  ($tos->createdby) ? $tos->createdby : 'MITRA';
    $api_call->lastupdatedby  =  ($tos->createdby) ? $tos->createdby : 'MITRA';
    $api_call->http_code = null;
    $api_call->response_body = '';
    $api_call->save();

    $apires = $apix->send("CancelSOItemWiser", $dat);
    if($apires["result"]){
        $api_call->error_message = $apires['data']['error_message'];
        if($apires['data']['success']== true){
            $api_call->success =  'Y';
        }
        else{
            $api_call->success =  'N';
        }
        $api_call->http_code =  $apires['status'];
        $api_call->response_body = $apires ? json_encode($apires) : '';
            
        $api_call->save();
    }else{
        $api_call->error_message = $apires["message"];
        $api_call->success = 'N';
        $api_call->http_code = 500;
        $api_call->response_body = $apires ? json_encode($apires) : '';
        $api_call->save();
    }
    //========= END CANCEL SO =========//

    $result = [
          "success" =>true,
          "message" =>"",
    ];

    return $result;
  }

  public function insertbookingstockrequestor($noso, $tglso, $user)
  {
    $order = OrderPenjualan::where(['noso' => $noso, 'tglso' => $tglso])->get();
    foreach ($order as $key => $op)
    {
      $opd = OrderPenjualanDetail::where('orderpenjualanid', $op->id)->where('qtysoacc','>',0)->orderBy('id', 'ASC')->get();
      $this->simpleLogger($this, __FUNCTION__, $opd, __LINE__);

      // dd($opd);
      $scb = SubCabang::where('id', $op->pengirimsubcabangid)->first();
      $perusahaan = $scb->getPerusahaan();
      if ($perusahaan->initperusahaan == 'SAP') {
        $this->simpleLogger($this, __FUNCTION__, $scb, __LINE__);
    
        $gd = DB::connection("pgsql_wiserdc")->table('mstr.gudangpendukung')->where("gudang1", $scb->kodesubcabang)->first();
        $this->simpleLogger($this, __FUNCTION__, $gd, __LINE__);
    
        foreach ($opd as $detail) {
          $brg = DB::connection("pgsql_wiserdc")->table('mstr.stock')->where("id", "=", $detail->stockid)->first();
          $cekstockg1   = collect(DB::connection("pgsql_wiserdc")->table(DB::raw("mstr.fnstokgudangtoday(null, null, '" . $this->strEscape($brg->kodebarang) . "', '" . $this->strEscape($scb->kodesubcabang) . "', null) as total"))->first())->toArray();
    
          // DB::enableQueryLog(); // Enable query log
          $cekstockg2   = collect(DB::connection("pgsql_wiserdc")->table(DB::raw("mstr.fnstokgudangtoday(null, null, '" . $this->strEscape($brg->kodebarang) . "', '" . $gd->gudang2 . "', null) as total"))->first())->toArray();
          // $this->simpleLogger($this, __FUNCTION__, DB::getQueryLog(), __LINE__); // Show results of log
          
          $stocktotal =  $cekstockg1['total'] + $cekstockg2['total'];
          $cekstockg1['total'] = $cekstockg1['total'] >= 0 ? $cekstockg1['total'] : 0;
          // if ($detail->qtysoacc > $stocktotal) {
          //   $detail->qtysoacc = $stocktotal;
          //   $detail->save();
          // } 
    
          Log::debug("qtysoacc:");
          Log::debug($detail->qtysoacc);
          Log::debug("cekstockg1:");
          Log::debug($cekstockg1['total']);
    
          if ($detail->qtysoacc > $cekstockg1['total']) {
            $bookingstokg1 = $cekstockg1['total'];
            $bookingstokg2 = $detail->qtysoacc - $cekstockg1['total'];
    
            Log::debug("cekstockg2:");
            Log::debug($cekstockg2['total']);
    
            if ($bookingstokg2 > $cekstockg2['total'] ) {
              $bookingstokg2 = $cekstockg2['total'] != null && $cekstockg2['total'] >= 0 ? $cekstockg2['total'] : 0;
            }
          } else {
            $bookingstokg1 = $detail->qtysoacc;
            $bookingstokg2 = 'null';
          }
          $detail->qtypil =  $bookingstokg1;
          $detail->qtycekstock =  $bookingstokg1;
          $detail->qtystockgudang  =  $cekstockg1['total'];
          $detail->save();
    
          Log::debug("bookingstokg1:");
          Log::debug($bookingstokg1);
          Log::debug("bookingstokg2:");
          Log::debug($bookingstokg2);
    
    
          $cekgudangtotal = $bookingstokg1 + ($bookingstokg2 != 'null' ? $bookingstokg2 : 0 );
    
          if ($cekgudangtotal > 0) {
            // wdc
            $requestor_wdc = DB::connection("pgsql_wiserdc")->select("SELECT * FROM stk.fn_insertbookingstockrequestor('" . $op->nopickinglist . "',  'so', '" .$detail->id . "', '" . $detail->qtysoacc . "',  '" . $op->c1->kodesubcabang . "', 'aktif',  " . $bookingstokg1 . ", " . $bookingstokg2 . ", null, '" . $op->c2->kodesubcabang . "', '" . $gd->gudang2 ."',  null, null, null, null, null, '" . $user ."','" . $user . "')");
            if ($requestor_wdc) {
              $bsrid = $requestor_wdc[0]->fn_insertbookingstockrequestor;
            } else {
              return 'Error';
            }
            // wiser
            $requestor = DB::select("SELECT * FROM stk.fn_insertbookingstockrequestor('" . $op->nopickinglist . "', 'so', '" .$detail->id . "', '" .$detail->qtysoacc . "', '" . $op->c1->kodesubcabang . "', 'aktif',  " . $bookingstokg1 . ", " . $bookingstokg2 . ", null, '" . $op->c2->kodesubcabang . "', '" . $gd->gudang2 ."',  null, null, null, null, null, '" . $user . "', '" . $user . "'," . $bsrid . ")");
            $this->simpleLogger($this, __FUNCTION__, $requestor, __LINE__);
            $this->insertbookingstockstk($bsrid);
          }
        }
      }
    }
  }
  public function insertbookingstockstk($bsrid)
  {
    $this->simpleLogger($this, __FUNCTION__, $bsrid, __LINE__);
    $bsr = DC_BookingStockRequestor::where('id', $bsrid)->orderBy('id', 'DESC')->first();
    $bsr_wdc = BookingStockRequestor::where('wiserdcid', $bsrid)->orderBy('id', 'DESC')->first();
    $opd = OrderPenjualanDetail::where('id', $bsr->wisersrcid)->orderBy('id', 'DESC')->first();
    $brg = DB::connection("pgsql_wiserdc")->table('mstr.stock')->where("id", "=", $opd->stockid)->first();
    $cekstockg1   = collect(DB::connection("pgsql_wiserdc")->table(DB::raw("mstr.fnstokgudangtoday(null, null, '" . $this->strEscape($brg->kodebarang) . "', '" . $this->strEscape($bsr->g1) . "', null) as total"))->first())->toArray();
    $cekstockg2   = collect(DB::connection("pgsql_wiserdc")->table(DB::raw("mstr.fnstokgudangtoday(null, null, '" . $this->strEscape($brg->kodebarang) . "', '" . $this->strEscape($bsr->g2) . "', null) as total"))->first())->toArray();

    // wiserdc
    if ($bsr->bookingstokg1 != null && $bsr->bookingstokg2 == null) {
      $bookingstock = DB::connection("pgsql_wiserdc")->statement("SELECT stk.fn_insertbookingstock(" . $bsrid . "," . $bsr->bookingstokg1 . ",  '" . $bsr->g1 . "', null, 'bookedsor',  " . $cekstockg1['total'] . ", '" . $opd->stockid . "',  null, '" . $bsr->createdby . "', '" . $bsr->createdby . "')");

      $bsg1 = DB::connection("pgsql_wiserdc")->table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsrid, 'gudangbooking' => $bsr->g1, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
      $bookingstockprogress = DB::connection("pgsql_wiserdc")->statement("SELECT stk.fn_insertbookingstockprogress(" . $bsg1->id . ",'" . Carbon::parse($bsg1->tglbooking)->format('Y-m-d') . "', '" . $bsr->wisersrcid . "', 'sor', '" . $bsr->createdby . "', '" . $bsr->createdby . "')");
    } elseif ($bsr->bookingstokg1 >= 0 && $bsr->bookingstokg2 != null) {
      // qtybookingG1
      if ($bsr->bookingstokg1 > 0) {
        $bookingstock = DB::connection("pgsql_wiserdc")->statement("SELECT stk.fn_insertbookingstock(" . $bsrid . "," . $bsr->bookingstokg1 . ",  '" . $bsr->g1 . "', null, 'bookedsor',  " . $cekstockg1['total'] . ", '" . $opd->stockid . "',  null, '" . $bsr->createdby . "', '" . $bsr->createdby . "')");
        // Booking stock progress
        $bsg1 = DB::connection("pgsql_wiserdc")->table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsrid, 'gudangbooking' => $bsr->g1, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
        $bookingstockprogress = DB::connection("pgsql_wiserdc")->statement("SELECT stk.fn_insertbookingstockprogress(" . $bsg1->id . ",'" . Carbon::parse($bsg1->tglbooking)->format('Y-m-d') . "', '" . $bsr->wisersrcid . "', 'sor', '" . $bsr->createdby . "', '" . $bsr->createdby . "')");
      }
      // qtybookingG2
      $bookingstock2 = DB::connection("pgsql_wiserdc")->statement("SELECT stk.fn_insertbookingstock(" . $bsrid . "," . $bsr->bookingstokg2 . ", '" . $bsr->g2 . "', null, 'bookedsor',  " . $cekstockg2['total'] . ", '" . $opd->stockid . "',  null, '" . $bsr->createdby . "', '" . $bsr->createdby . "')");
      $bsg2 = DB::connection("pgsql_wiserdc")->table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsrid, 'gudangbooking' => $bsr->g2, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
      $bookingstockprogress2 = DB::connection("pgsql_wiserdc")->statement("SELECT stk.fn_insertbookingstockprogress(" . $bsg2->id . ",'" . Carbon::parse($bsg2->tglbooking)->format('Y-m-d') . "',  '" . $bsr->wisersrcid . "', 'sor', '" . $bsr->createdby . "', '" . $bsr->createdby . "')");
    }
    // wiser
    $bsg1 = DB::connection("pgsql_wiserdc")->table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsrid, 'gudangbooking' => $bsr->g1, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
    $bsg2 = DB::connection("pgsql_wiserdc")->table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsrid, 'gudangbooking' => $bsr->g2, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
    if ($bsg1 != null) {
      $bookingstock_wdc = DB::statement("SELECT stk.fn_insertbookingstock(" . $bsr_wdc->id . "," . $bsr->bookingstokg1 . ", '" . $bsr->g1 . "', null, 'bookedsor',  " . $cekstockg1['total'] . ", '" . $opd->stockid . "',  null, '" . $bsr->createdby . "', '" . $bsr->createdby . "'," . $bsg1->id . ")");
      // Booking stock progress
      $bsg1_wdc = DB::table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsr_wdc->id, 'gudangbooking' => $bsr->g1, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
      $bsp = DB::connection("pgsql_wiserdc")->table('stk.bookingstockprogress')->where(['bookingstockid' => $bsg1->id, 'doctype' => 'sor'])->orderBy('id', 'DESC')->first();
      $bookingstockprogress_wdc = DB::statement("SELECT stk.fn_insertbookingstockprogress(" . $bsg1_wdc->id . ",'" . Carbon::parse($bsg1->tglbooking)->format('Y-m-d') . "',  '" . $bsr->wisersrcid . "', 'sor', '" . $bsr->createdby . "', '" . $bsr->createdby . "', " . $bsp->id . ")");
    }
    if ($bsg2 != null) {
      $bookingstock_wdc = DB::statement("SELECT stk.fn_insertbookingstock(" . $bsr_wdc->id . "," . $bsr->bookingstokg2 . ", '" . $bsr->g2 . "', null, 'bookedsor',  " . $cekstockg2['total'] . ", '" . $opd->stockid . "',  null, '" . $bsr->createdby . "', '" . $bsr->createdby . "'," . $bsg2->id . ")");

      // Booking stock progress
      $bsg2_wdc = DB::table('stk.bookingstock')->where(['bookingstockrequestorid' => $bsr_wdc->id, 'gudangbooking' => $bsr->g2, 'transactiontype' => 'bookedsor'])->orderBy('id', 'DESC')->first();
      $bsp = DB::connection("pgsql_wiserdc")->table('stk.bookingstockprogress')->where(['bookingstockid' => $bsg2->id, 'doctype' => 'sor'])->orderBy('id', 'DESC')->first();
      $bookingstockprogress_wiser = DB::statement("SELECT stk.fn_insertbookingstockprogress(" . $bsg2_wdc->id . ",'" . Carbon::parse($bsg2->tglbooking)->format('Y-m-d') . "',  '" . $bsr->wisersrcid . "', 'sor', '" . $bsr->createdby . "', '" . $bsr->createdby . "', " . $bsp->id . ")");
    }
  }
  public function batalbookingstockrequestor($opid, $bsrid, $user)
  {
    if ($bsrid != null) {
      $bsr_old = DC_BookingStockRequestor::where('id', $bsrid)->first();
      $bsrw_old = BookingStockRequestor::where('wiserdcid', $bsrid)->first();
      $opd = OrderPenjualanDetail::where('id', $opid)->first();
      $brg = Stock::where('id', $opd->stockid)->first();
      $cekstockgudang = DB::connection("pgsql_wiserdc")->select("SELECT * FROM mstr.fnstokbygudang1('$brg->kodebarang', '$bsr_old->g1')");
      // cancel so
      $booking  = DC_BookingStockSTK::select(DB::raw('sum(qtybooking) qtybooking'), 'gudangbooking', 'stockid')->where('bookingstockrequestorid', $bsrid)->groupBy('gudangbooking', 'stockid')->get();
      foreach ($booking as $book) {
        $bs = new DC_BookingStockSTK();
        $bs->bookingstockrequestorid = $bsr_old->id;
        $bs->qtybooking = -$book->qtybooking;
        $bs->tglbooking = Carbon::now();
        $bs->gudangbooking = $book->gudangbooking;
        $bs->transactiontype = 'cancelled';
        $bs->stokgudang = $book->gudangbooking == $cekstockgudang[0]->gudang1 ? $cekstockgudang[0]->stockgudang1 + $book->qtybooking : $cekstockgudang[0]->stockgudang2 + $book->qtybooking;
        $bs->stockid = $book->stockid;
        $bs->lastupdatedby          = $user;
        $bs->createdby              = $user;
        $bs->edit_batal  = 'BatalPil oleh ' . $user . ' pada ' . Carbon::now()->format('Y-m-d');

        $bsw = new BookingStockSTK();
        $bsw->bookingstockrequestorid = $bsrw_old->id;
        $bsw->tglbooking = Carbon::now();
        $bsw->gudangbooking = $bs->gudangbooking;
        $bsw->qtybooking = $bs->qtybooking;
        $bsw->transactiontype = 'cancelled';
        $bsw->stokgudang = $bs->stokgudang;
        $bsw->stockid = $bs->stockid;
        $bsw->lastupdatedby          = $user;
        $bsw->createdby              = $user;
        $bsw->edit_batal  = 'BatalPil oleh ' . $user . ' pada ' . Carbon::now()->format('Y-m-d');

        if ($bs->qtybooking != 0) {
          $bs->save();
          $bsw->wiserdcid = $bs->id;
          $bsw->save();
        }
      }
    }
  }

  public function insertOrderpembelian($req,$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid,$flgregisterumum)
  {
    //Cek perusahaan dimana toko berada  apakah toko tersedia atau tidak
    $params = ['tokoidwarisan'=>$tokoidwarisan];
    $pers = DB::select("select pt,c1id from tasksales.fn_gettokomilikperusahaancabang3(:tokoidwarisan)",$params);
          
    if ($pers == null){
      return response()->json([
        'status' => false,                    
        'errormessage' => 'sasperusahaanownerid tidak ada'
      ]);
    }

    //Proses Simpan data
    $op = new orderpembelian; 
    $op->omsetsubcabangid      = $req['omsetsubcabangid'];
    $op->externalid            = $req['tasksalesid'];
    $op->saskodesales          = $req['kodesales'];
    $op->tosrecordownerid      = '-99';
    $op->prcreateusername      = $req['kodesales'];    
    $op->docno                 = $req['tasksalesnoso'];   
    $op->docdate               = $req['tasksalestglso']; 
    $op->currcode              = $req['tasksalescurrency'];
    $op->createdby             = $req['tasksalescreatedby'];
    $op->createdon             = $req['tasksalescreatedon'];
    $op->lastupdatedby         = $req['tasksalesupdatedby'];
    $op->lastupdatedon         = $req['tasksalesupdatedon'];

    if($pers[0]->pt == 'SAP')
    {
      switch ($req['tasksalestokostatusbmk']) {
        case 'AGEN':
          $statusbmk = 'B1';
          break;

        case 'GROSIR':
          $statusbmk = 'M1';
          break;

        case 'RETAIL23': case 'RETAIL25':
          $statusbmk = 'R1';
          break;

        case 'BENGKEL3': case 'BENGKEL5':
          $statusbmk = 'M2';
          break;
        
        default:
          $statusbmk = 'K1';
          break;
      }
    }
    else
    {
      switch ($req['tasksalestokostatusbmk']) {
        case 'RETAIL':
          $statusbmk = 'B2';
          break;

        case 'BENGKEL':
          $statusbmk = 'M2';
          break;
        
        default:
          $statusbmk = 'K2';
          break;
      }
    }

    // if ($req['tipetransaksi'] == 'D'){
    //     $tipe = 'D';
    // }else{
      $tipe = ($req['temponotabe'] > 0) ? 'K' : 'T';
    // }
      
    $op->sasstatusbmk          = $statusbmk;
    $op->tipetransaksi         = $req['tipetransaksi'];
    $op->sastokoid             = $tokoidwarisan;
    $op->sotype                = $req['tasksalessotype'];
    $op->temponotabe           = $req['temponotabe'];
    $op->temponotanonbe        = $req['temponotanonbe'];
    $op->sasstatustransaksi    = ($req['tasksalessotype'] == 'TSSO') ? 'TS ACC' : 'SAMS ACC';
    $op->statuspembayaran      = ($memberprosaspspid > 0 && $req['statuspembayaran'] == 'CBD' && !$flgregisterumum ) ? 'TUNAI' : $req['statuspembayaran'];
    $op->redeempoint           = $req['redeempoint'];
    $op->sasstatusaccharga     = 'A';
    $op->tosstatusacc          = 'A';
    $op->statusdoc             = 'I';
    $op->version               = '1';
    $op->supplierid            = '-99'; 
    $op->suppliercode          = 'SAS';
    $op->sasperusahaanownerid  = $pers[0]->pt;
    $op->doctypeid             = '-99';       
    $op->sastransactionownerid = $pers[0]->c1id;
    $op->sessionuuid           = '00000000-0000-0000-0000-000000000000';
    $op->prcreatedatetime      = date("Y-m-d H:i:s");
    $op->prupdateddatetime     = date("Y-m-d H:i:s");           
    $op->extdocdate            = date("Y-m-d");
    $op->keterangan            = $req['keterangan'];
    $op->tokoaliasid           = $tokoaliasid;
    $op->memberprosaspspid     = ($memberprosaspspid > 0 ) ? $memberprosaspspid : null;
    $op->flgordersalesman      = $req['flgordersalesman'];
    $op->save();
    $opid = $op->id;
    $this->simpleLogger($this, __FUNCTION__, $op, __LINE__);

    // Pindah saat Link KP : KNR 40652
    // if ($req['redeempoint']){
    //   if ($tokoid)
    //   {
    //     $Redeem = new AdjRewardpoint;
    //     $Redeem->tokoid         = $tokoid;
    //     $Redeem->nilaiajusment  = (-1) * $req['redeempoint'];
    //     $Redeem->nodokumen      = $req['tasksalesnoso'];
    //     $Redeem->tgldokumen     = date("Y-m-d");
    //     $Redeem->pt             = 'SAP';
    //     $Redeem->createdby      = $req['tasksalescreatedby'];
    //     $Redeem->createdon      = $req['tasksalescreatedon'];
    //     $Redeem->lastupdatedby  = $req['tasksalesupdatedby'];
    //     $Redeem->lastupdatedon  = $req['tasksalesupdatedon'];
    //     $Redeem->save();
    //   }
    // }

    return $opid;
  }

  public function insertOrderpembelianDetail($req,$opid,$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid)
  {
    $cte = "
      WITH X AS (
        Select id from mstr.toko 
        where tokoidwarisan='".$tokoidwarisan."'
        and id not in (
          select tokoid from mstr.tokotodisc
        )
      )
    ";

    $where = "a.tokoid IN (SELECT id FROM X) AND";

    if ($memberprosaspspid > 0)
    {
      $cte = "
        WITH X AS (
          Select id from promo.memberprosaspsp where tokoid='".$tokoidwarisan."'
        )
      ";

      $where = "a.tokoid = ".$tokoid." AND a.memberprosasid IN (SELECT id FROM X) AND";
    }

    $arrDetail = [];
    foreach ($req['tasksalessodetail'] as $key => $d) {

      $brg = Barang::where("kodebarang", "=", $d['kodebarangsas'])->first();

        $cek_opjd = OrderPenjualan::from(DB::raw("(

        ".$cte."

        SELECT
          a.id,
          a.nopickinglist,
          a.tglpickinglist,
          b.id as detailid,
          c.qtypi,
          b.orderpembeliandetailid,
          a.id orderid
        FROM pj.orderpenjualan a
        INNER JOIN pj.orderpenjualandetail b on b.orderpenjualanid = a.id
        LEFT JOIN pj.notapenjualandetail c on c.orderpenjualandetailid = b.id
        WHERE
          
          ".$where."

          b.stockid = " . intval($brg->id) . " AND
          a.tglpickinglist::DATE > (CURRENT_DATE - INTERVAL '15 DAY') AND
          a.tglpickinglist::DATE <= CURRENT_DATE AND 
          a.tosorderpembelianid is not null AND
          (
            b.qtyso != coalesce(c.qtypi,0) OR 
            b.qtysoacc != coalesce(c.qtypi,0) OR
            b.qtypil != coalesce(c.qtypi,0) OR 
            b.qtycekstock != coalesce(c.qtypi,0)
          )
        ) Z"))->get();
          
        // if($cek_opjd != null) {
        //   $arrNopil = [];
        //   $arrTglpil = [];
        //   // $arrDetail = [];
        //   foreach ($cek_opjd as $val) {
        //     $update_qty = OrderPenjualanDetail::where("id", "=", $val->detailid)->first();
        //     $arrDetail[] = [
        //       'detailid' => $val->detailid,
        //       'qtysoacc' => $update_qty->qtysoacc,
        //       'qtyso'    => $update_qty->qtyso];
        //     $update_qty->qtysoacc       = ($val->qtypi) ? $val->qtypi : 0;
        //     $update_qty->qtyso          = ($val->qtypi) ? $val->qtypi : 0;
        //     $update_qty->qtypil         = ($val->qtypi) ? $val->qtypi : 0;
        //     $update_qty->qtycekstock    = ($val->qtypi) ? $val->qtypi : 0;
        //     $update_qty->catatan        = 'batalPIL_TokoSamaBrgSama';
        //     $update_qty->lastupdatedby  =  $req['tasksalescreatedby'];
        //     $update_qty->lastupdatedon  =  Carbon::now();
        //     $update_qty->save();

        //     $DC_update_qty = DC_OrderPenjualanDetail::where("wisersoid", "=", $val->id)->first();
        //     if ($DC_update_qty != null) {
        //       $DC_update_qty->catatan        = 'batalPIL_TokoSamaBrgSama';
        //       $DC_update_qty->lastupdatedby   =  $req['tasksalescreatedby'];
        //       $DC_update_qty->lastupdatedon   =  Carbon::now();;
        //       $DC_update_qty->save();
        //     }

        //     $bsr = BookingStockRequestor::where('wisersrcid', $val->id)->first();
        //     if (isset($bsr->status) && $bsr->status != 'pasif') {
        //       $bsrup = BookingStockRequestor::where('wisersrcid', $val->id)->update(['status' => 'pasif']);
        //       $bsrwup = DC_BookingStockRequestor::where('wisersrcid', $val->id)->update(['status' => 'pasif']);

        //       $bsrw = DC_BookingStockRequestor::where('wisersrcid', $val->id)->first();

        //       $batalTokoBarangSama = $this->batalbookingstockrequestor($val->id, $bsrw->id, $req['tasksalescreatedby']);
        //     }

        //     $opd_baru = OrderPenjualanDetail::where('orderpenjualanid', '=', intval($val->id))
        //               ->where('stockid', '=', intval($brg->id))
        //               ->first();
        //     $opd_baru->orderpembeliandetailid = $val->orderpembeliandetailid;
        //     $opd_baru->save();

        //     $arrNopil[] = $val->nopickinglist;
        //     $arrTglpil[] = Carbon::parse($val->tglpickinglist)->format('d-m-Y');

        //     $params = ['opid'=>$val->orderid];            
        //     $cek = DB::SELECT("SELECT * FROM pj.orderpenjualan a
        //                         left join lateral(
        //                             select SUM(coalesce(b.qtyso,0)) qtyso
        //                             from pj.orderpenjualandetail b 
        //                             where b.orderpenjualanid = a.id
        //                             and (b.hrgsatuanbrutto < b.hrgbmk  or b.hrgsatuannetto < b.hrgbmk)
        //                         )b on true
        //                         where b.qtyso = 0
        //                         and a.statusajuanhrg11 = 'PROSES ACC'
        //                         and a.id = :opid",$params);
        //     if($cek){
        //       $upd_header = OrderPenjualan::where("id", "=", $val->orderid)->first();
        //       $upd_header->statusajuanhrg11 = null;
        //       $upd_header->save();
        //     }
        //   }

        //   if($kodetoko){
        //     $params = [
        //       'kodebarang_p' => $d['kodebarangsas'],
        //       'kodetoko_p' => $kodetoko,
        //       'memberprosaspspid_p' => $memberprosaspspid
        //     ];
        //     $SOWDC = DB::connection("pgsql_wiserdc")->select("select crud.fn_item_so_to_cancel(:kodebarang_p,:kodetoko_p,:memberprosaspspid_p) as tmp",$params);
        //   }
          
        // }

      $addOrderDetail = DB::select(DB::raw("SELECT * FROM tasksales.fn_add_orderpembeliandetail(
      ". $opid .", '". $d['kodebarangsas'] ."', '". $d['takssalesdetailid'] ."', 
      ". $d['qtyorder'] .", ". $d['hargasatuanbmk'] .", ". $d['hargasatuanajuan'] .",
      ". $d['hargaitembeforetax'] .", ". $d['hargaitemtax'] .", ". $d['hargaitemaftertax'] .",
      '". $req['tasksalescreatedby'] ."', '". $d['tasksalesketerangan'] ."')"));
      $this->simpleLogger($this, __FUNCTION__, $addOrderDetail, __LINE__);
    };

    $this->simpleLogger($this, __FUNCTION__, $arrDetail, __LINE__);
    if ($arrDetail){
      $batalPIL = $this->cancelSOItemTaskSalesKemitraan($arrDetail);
    }
  }

  public function insertSoSASAToSAP($req,$tokoid,$tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid,$arrBarang,$opid)
  {
    $this->simpleLogger($this, __FUNCTION__, $req, __LINE__);

    $n = 0;
    $idponew = 0;
    // if ($req['flgordersalesman'] == 'Y')
    // {
    //   $params = [
    //     'tokoid_p' => $tokoid,
    //     'kelompokbarang_p' => 'FBFE'
    //   ];
    //   $c1c2 = collect(DB::SELECT("SELECT * FROM crud.fngettokoc1c2(:tokoid_p,:kelompokbarang_p)",$params))->first();
    //   if ($c1c2)
    //   {
    //     \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ MASUK C1C2 +++++++++++++++++++++++++++++++++++++++++++++++");
    //     if ($c1c2->perusahaan == 'SASA')
    //     {
    //       \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ MASUK SASA +++++++++++++++++++++++++++++++++++++++++++++++");
    //       $params2 = [
    //         'recordownerid_p' => $c1c2->c1
    //       ];
    //       $disc = collect(DB::SELECT("
    //         SELECT * FROM mstr.tokotodisc WHERE active IS TRUE
    //         AND recordownerid = :recordownerid_p
    //         ORDER BY tglaktif DESC LIMIT 1
    //       ",$params2))->first();

    //       if ($disc)
    //       {
    //         \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ ORDER DR SOBAT +++++++++++++++++++++++++++++++++++++++++++++++");
    //         $tokoDisc = Toko::find($disc->tokoid);
    //         $req['cabangpo'] = SubCabang::find($disc->recordownerid)->kodesubcabang;

    //         $params3 = [
    //           'tokoid_p' => $tokoDisc->id,
    //           'kelompokbarang_p' => 'FBFE'
    //         ];
    //         $c1c2_new = collect(DB::SELECT("SELECT * FROM crud.fngettokoc1c2(:tokoid_p,:kelompokbarang_p)",$params3))->first();
    //         $req['omsetsubcabangid'] = SubCabang::find($c1c2_new->c1)->kodesubcabang;
    //         $req['tokoidsas'] = $tokoDisc->tokoidwarisan;
    //         $req['flgantarpt'] = 'Y';

    //         // Insert Orderpembelian
    //         $opid2 = $this->insertOrderpembelian($req,$tokoDisc->id,$tokoDisc->tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid,false);
    //         $idponew = $opid2;

    //         //save detail orderpembelian
    //         $this->insertOrderpembelianDetail($req,$opid2,$tokoDisc->id,$tokoDisc->tokoidwarisan,$kodetoko,$memberprosaspspid,$tokoaliasid);

    //         $username = $req['tasksalescreatedby'];
    //         foreach (array_unique($arrBarang) as $key => $value) {
    //           $convertSo2 = DB::select(DB::raw("SELECT * FROM tasksales.fn_convert_so_from_orderpembelian($opid2, '$value', '$username')"));
    //           $this->simpleLogger($this, __FUNCTION__, $convertSo2, __LINE__);

    //           // Input fitur baru
    //           $bookingstockrequestor = $this->insertbookingstockrequestor($req['tasksalesnoso'], $req['tasksalestglso'], $username);

    //           $n++;
    //         }
    //       }
    //     }
    //   }
    // }
    // else
    if ($req['flgordersalesman'] == 'N')
    {
      $idponew = $opid;
      $params3 = [
        'tokoid_p' => $tokoid
      ];
      $disc = collect(DB::SELECT("
        SELECT td.*, sc.kodesubcabang FROM mstr.tokotodisc td
        LEFT JOIN mstr.subcabang sc ON td.recordownerid = sc.id
        LEFT JOIN mstr.cabang c ON sc.cabangid = c.id
        WHERE td.active IS TRUE
        AND td.tokoid = :tokoid_p
        AND c.perusahaanid = 4
        ORDER BY td.tglaktif DESC LIMIT 1
      ",$params3))->first();

      if ($disc)
      {
        \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ ORDER DR PSM +++++++++++++++++++++++++++++++++++++++++++++++");
        $req['cabangpo'] = $disc->kodesubcabang;
        $n = 1;
      }
    }

    if ($n > 0)
    {
      \Log::debug("+++++++++++++++++++++++++++++++++++++++++++++++ INSERT PO 2801 +++++++++++++++++++++++++++++++++++++++++++++++");
      // Insert PO di 2801
      $po = $this->insertPOSasa($req,$idponew);
      $this->simpleLogger($this, __FUNCTION__, $po, __LINE__);

      return true;
    }

    return false;
  }

  function insertPOSasa($req,$idponew)
  {
    $this->simpleLogger($this, __FUNCTION__, $req, __LINE__);
    $params4 = ['opid_p'=>$idponew];
    $detailSo = DB::SELECT("
      SELECT opd.*, op.nopickinglist FROM pj.orderpenjualan op
      LEFT JOIN pj.orderpenjualandetail opd ON opd.orderpenjualanid = op.id
      WHERE op.tosorderpembelianid = :opid_p
    ",$params4);
    
    $supplier = collect(DB::SELECT("SELECT * FROM mstr.supplier WHERE UPPER(kode) = 'KPS' AND recordownerid = 18 LIMIT 1;"))->first();
    $po = DB::table('pb.orderpembelian')->insertGetId([
      'recordownerid' => 18,
      'tglorder'      => Carbon::now()->format('Y-m-d'),
      'noorder'       => $req['cabangpo'].'-'.$detailSo[0]->nopickinglist.'-'.$req['tasksalesnoso'],
      'supplierid'    => $supplier->id,
      'tempo'         => 0,
      'keterangan'    => $req['keterangan'],
      'matauangid'    => 20,
      'createdby'     => $req['tasksalescreatedby'],
      'lastupdatedby' => $req['tasksalescreatedby'],
      'createdon'     => Carbon::now(),
      'lastupdatedon' => Carbon::now(),
    ]);

    foreach ($detailSo as $key => $value) {
      $ppn = AppSetting::where('keyid','ppn')->where('recordownerid',-99)->first();
      $ppnhrg = 100+$ppn->value;
      $brtppn =  $value->hrgsatuannetto * 100;
      $hargabruto = ($brtppn / $ppnhrg);

      $podetail = DB::table('pb.orderpembeliandetail')->insertGetId([
        'orderpembelianid' => $po,
        'stockid'          => $value->stockid,
        'qtyorder'         => $value->qtyso,
        'qtypenjualanbo'   => 0,
        'qtyrataratajual'  => 0,
        'qtystokakhir'     => $value->qtystockgudang,
        'hrgsatuanbrutto'  => $hargabruto,
        'disc1'            => $value->disc1,
        'ppn'              => $ppn->value,
        'hrgsatuannetto'   => $value->hrgsatuannetto,
        'keterangan'       => $value->catatan,
        'hargaori'         => $value->hrgsatuannetto,
        'matauangid'       => 20,
        'createdby'        => $req['tasksalescreatedby'],
        'lastupdatedby'    => $req['tasksalescreatedby'],
        'createdon'        => Carbon::now(),
        'lastupdatedon'    => Carbon::now(),
      ]);
      $this->simpleLogger($this, __FUNCTION__, $podetail, __LINE__);
    }

    return true;
  }

  public function cekSOInden(Request $req)
  {
    $this->simpleLogger($this, __FUNCTION__, $req->all(), __LINE__);
    $vali = Validator::make($req->all(),[
        'apikey' =>'required',
        'sastokoid' =>'required',
        'kodebarang' =>'required',
        'qty' =>'required',
    ]);

    if ($vali->fails()) {
      return response()->json([
        'error' => $vali->errors()
      ], 401);
    }

    try
    {
      $stock = Barang::where('kodebarang',$req->kodebarang)->first();
      $params = [
        'stockid_p' => $stock->id,
        'tokoid_p' => $req->sastokoid,
        'qty_p' => $req->qty,
      ];
      $soInden = collect(DB::SELECT("SELECT * FROM pj.cek_so_inden(:stockid_p,null,:tokoid_p,:qty_p);",$params))->first();

      return response()->json([
        "status" => 'success',
        "soinden" => ($soInden->cegatan) ? 'Y' : 'N',
        "error_message" => $soInden->msg
      ]);
            
    } 
    catch(Exception $ex)
    {
      $this->simpleLogger($this, __FUNCTION__, $ex->getMessage(), __LINE__);
      return response()->json([
        "status" => 'fail',
        "error_message" => $ex->getMessage()
      ]); 
    }
  }

 }
