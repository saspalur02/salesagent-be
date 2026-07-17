from typing import Protocol, runtime_checkable


@runtime_checkable
class WhatsAppClient(Protocol):
    """
    Kontrak minimum yang harus dipenuhi tiap provider WhatsApp
    (WAHA, Evolution API, dst) agar bisa dipakai bergantian.
    """

    async def send_text(self, wa_number: str, text: str) -> dict: ...

    async def send_text_with_typing(
        self, wa_number: str, text: str, typing_ms: int = 1500
    ) -> dict: ...

    async def is_connected(self) -> bool: ...
