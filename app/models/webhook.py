from pydantic import BaseModel, Field
from typing import Any


class WAHAContact(BaseModel):
    id: str               # e.g. "6281234567890@c.us"
    name: str | None = None
    pushname: str | None = None


class WAHAMessage(BaseModel):
    id: str
    timestamp: int
    from_: str = Field(alias="_data")
    body: str | None = None
    type: str = "chat"    # chat | image | document | audio | etc
    hasMedia: bool = False

    model_config = {"populate_by_name": True}


class WAHAPayload(BaseModel):
    """
    Payload standar dari WAHA webhook.
    Referensi: https://waha.devlike.pro/docs/how-to/webhooks/
    """
    event: str                        # message | message.ack | session.status
    session: str
    me: dict | None = None
    payload: dict = {}                # raw payload dari WAHA

    def get_wa_number(self) -> str | None:
        """Ekstrak nomor pengirim dari payload."""
        from_ = self.payload.get("from", "")
        # Format WAHA: "6281234567890@c.us" — ambil bagian sebelum @
        if "@c.us" in from_:
            return from_.split("@")[0]
        return None

    def get_message_body(self) -> str | None:
        """Ekstrak isi pesan teks."""
        return self.payload.get("body")

    def get_message_type(self) -> str:
        return self.payload.get("type", "chat")

    def is_from_me(self) -> bool:
        return self.payload.get("fromMe", False)

    def is_group_message(self) -> bool:
        from_ = self.payload.get("from", "")
        return "@g.us" in from_
