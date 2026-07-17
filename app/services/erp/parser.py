import json
from litellm import acompletion
from app.core.settings import get_settings

settings = get_settings()

async def parse_store_query_with_llm(user_input: str) -> dict:
    """
    Memotong chat natural user menjadi entitas terstruktur (nama dipecah jadi 2 kata kunci).
    """
    system_prompt = """
    Kamu adalah AI yang bertugas mengekstrak komponen pencarian toko dari chat user ke dalam format JSON.
    Hancurkan kata-kata basa-basi seperti "toko", "dengan", "di", "kecamatan", "kota", "alamat".
    
    ⚠️ PERINTAH PENTING:
    Pecah nama toko menjadi 2 kata kunci utama (nama1 dan nama2). 
    Jika ada kata yang terpecah typo spasi (contoh: "lampun gmotor"), perbaiki dulu menjadi kata yang benar ("Lampung", "Motor").

    Format JSON yang WAJIB kamu kembalikan:
    {
        "nama1": "kata kunci pertama nama toko atau kosong",
        "nama2": "kata kunci kedua nama toko atau kosong",
        "alamat": "string kata kunci nama jalan/spesifik atau kosong",
        "kota": "string kata kunci kota atau kosong",
        "kecamatan": "string kata kunci kecamatan atau kosong"
    }

    CONTOH:
    Input: "Toko lampun gmotor di grogo l"
    Output JSON: {"nama1": "Lampung", "nama2": "Motor", "alamat": "", "kota": "", "kecamatan": "Grogol"}

    Input: "Cari Berkat Motor Grogol Petamburan"
    Output JSON: {"nama1": "Berkat", "nama2": "Motor", "alamat": "", "kota": "", "kecamatan": "Grogol Petamburan"}
    """

    try:
        response = await acompletion(
            model=settings.litellm_model,
            api_key=settings.litellm_api_key,
            api_base=settings.litellm_api_base,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.0,
            response_format={ "type": "json_object" }
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"nama1": user_input, "nama2": "", "alamat": "", "kota": "", "kecamatan": ""}