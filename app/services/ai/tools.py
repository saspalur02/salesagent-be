"""
Tool definitions untuk AI Agent.
Ada 2 set tools: untuk mode toko dan mode admin.
"""

# ── Tools untuk mode TOKO ────────────────────────────────────────
TOKO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cari_toko",
            "description": (
                "Cari data toko di database berdasarkan nama dan/atau alamat. "
                "Gunakan saat toko menyebutkan identitasnya."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nama_toko": {
                        "type": "string",
                        "description": "Nama toko yang disebutkan user",
                    },
                    "alamat": {
                        "type": "string",
                        "description": "Alamat atau kota toko",
                    },
                },
                "required": ["nama_toko"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cari_produk",
            "description": (
                "Cari produk berdasarkan nama atau deskripsi. "
                "Gunakan saat toko menyebut produk yang ingin dipesan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nama atau deskripsi produk",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kirim_ke_admin",
            "description": (
                "Kirim draft order ke admin penjualan setelah toko konfirmasi. "
                "HANYA panggil setelah toko mengkonfirmasi semua item order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "toko_id": {
                        "type": "string",
                        "description": "ID toko dari hasil cari_toko, atau 'UNKNOWN' jika tidak ditemukan",
                    },
                    "toko_name": {
                        "type": "string",
                        "description": "Nama toko",
                    },
                    "toko_address": {
                        "type": "string",
                        "description": "Alamat toko",
                    },
                    "items": {
                        "type": "array",
                        "description": "Daftar item yang dipesan",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_code": {"type": "string"},
                                "product_name": {"type": "string"},
                                "qty": {"type": "number"},
                                "uom": {"type": "string"},
                                "price": {"type": "number"},
                            },
                            "required": ["product_name", "qty", "uom"],
                        },
                    },
                    "note": {
                        "type": "string",
                        "description": "Catatan tambahan dari toko (opsional)",
                    },
                },
                "required": ["toko_name", "toko_address", "items"],
            },
        },
    },
]

# ── Tools untuk mode ADMIN ───────────────────────────────────────
ADMIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cari_produk",
            "description": "Cari dan validasi produk di ERP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cek_stok",
            "description": "Cek ketersediaan stok produk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_code": {"type": "string"},
                },
                "required": ["product_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buat_sales_order",
            "description": (
                "Buat Sales Order di ERP dari final order admin. "
                "Panggil setelah semua detail divalidasi."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "toko_id": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_code": {"type": "string"},
                                "qty": {"type": "number"},
                                "uom": {"type": "string"},
                                "price": {"type": "number"},
                            },
                            "required": ["product_code", "qty", "uom", "price"],
                        },
                    },
                    "note": {"type": "string"},
                },
                "required": ["toko_id", "items"],
            },
        },
    },
]
