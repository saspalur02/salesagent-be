import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.settings import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class ERPClient:
    """
    HTTP client untuk custom ERP.
    Sesuaikan endpoint di setiap method dengan API ERP kamu.
    """

    def __init__(self):
        self.base_url = settings.erp_base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.erp_api_key}",
        }
        self.timeout = settings.erp_timeout_seconds

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
        )

    # ── Customer ─────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def find_customer_by_phone(self, phone: str) -> dict | None:
        """
        Cari customer berdasarkan nomor HP.
        Sesuaikan endpoint dan field name dengan ERP kamu.

        Expected response:
        {
            "id": "CUST-001",
            "name": "PT Maju Jaya",
            "contact_name": "Budi",
            "phone": "6281234567890",
            "address": "...",
            "credit_limit": 50000000,
            "payment_term": 30
        }
        """
        async with self._client() as client:
            resp = await client.get(
                f"{self.base_url}/customers",
                params={"phone": phone},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            # Kalau ERP return list, ambil yang pertama
            if isinstance(data, list):
                return data[0] if data else None
            return data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_customer(self, customer_id: str) -> dict | None:
        """Ambil detail customer by ID."""
        async with self._client() as client:
            resp = await client.get(
                f"{self.base_url}/customers/{customer_id}"
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    # ── Product ──────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_products(self, active_only: bool = True) -> list[dict]:
        """
        Ambil semua produk aktif — dipakai saat indexing ke vector store.

        Expected response (list):
        [
          {
            "code": "MGREF5L",
            "name": "Minyak Goreng Refina 5L",
            "alias": "minyak refina cooking oil",
            "category": "FMCG",
            "uom": "Karton",
            "price": 150000,
            "description": "Minyak goreng sawit kemasan karton"
          }, ...
        ]
        """
        async with self._client() as client:
            resp = await client.get(
                f"{self.base_url}/products",
                params={"active": active_only},
            )
            resp.raise_for_status()
            return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_stock(self, product_code: str) -> dict:
        """
        Cek stok real-time per produk.

        Expected response:
        {
            "product_code": "MGREF5L",
            "qty_available": 100,
            "qty_on_order": 20,
            "uom": "Karton",
            "warehouse": "Gudang Utama"
        }
        """
        async with self._client() as client:
            resp = await client.get(
                f"{self.base_url}/products/{product_code}/stock"
            )
            resp.raise_for_status()
            return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    async def get_price(self, product_code: str, customer_id: str) -> dict:
        """
        Ambil harga produk untuk customer tertentu (bisa ada pricelist khusus).

        Expected response:
        {
            "product_code": "MGREF5L",
            "customer_id": "CUST-001",
            "price": 148000,
            "discount_pct": 1.33,
            "currency": "IDR"
        }
        """
        async with self._client() as client:
            resp = await client.get(
                f"{self.base_url}/pricing",
                params={
                    "product_code": product_code,
                    "customer_id": customer_id,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Sales Order ──────────────────────────────────────────────

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=3))
    async def create_sales_order(self, payload: dict) -> dict:
        """
        Buat Sales Order baru di ERP.

        Payload yang dikirim:
        {
            "customer_id": "CUST-001",
            "note": "Order via WhatsApp",
            "lines": [
                {
                    "product_code": "MGREF5L",
                    "qty": 10,
                    "uom": "Karton",
                    "price": 148000
                }
            ]
        }

        Expected response:
        {
            "so_number": "SO-2026-00123",
            "status": "draft",
            "total": 1480000,
            "estimated_delivery": "2026-03-28"
        }
        """
        async with self._client() as client:
            resp = await client.post(
                f"{self.base_url}/sales-orders",
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("sales_order_created",
                        so_number=result.get("so_number"),
                        customer_id=payload.get("customer_id"))
            return result

    async def get_customer_ar(self, customer_id: str) -> dict:
        """
        Cek piutang (AR) customer — untuk validasi sebelum proses order.

        Expected response:
        {
            "customer_id": "CUST-001",
            "outstanding": 5000000,
            "overdue": 0,
            "credit_limit": 50000000,
            "available_credit": 45000000
        }
        """
        async with self._client() as client:
            resp = await client.get(
                f"{self.base_url}/customers/{customer_id}/ar"
            )
            resp.raise_for_status()
            return resp.json()
