from pydantic import BaseModel, Field
from typing import Any


class WAHAContact(BaseModel):
    id: str
    name: str | None = None
    pushname: str | None = None


class WAHAMessage(BaseModel):
    id: str
    timestamp: int
    from_: str = Field(alias="_data")
    body: str | None = None
    type: str = "chat"
    hasMedia: bool = False

    model_config = {"populate_by_name": True}


class WAHAPayload(BaseModel):
    """Payload standar dari WAHA webhook."""
    event: str
    session: str
    me: dict | None = None
    payload: dict = {}

    def get_wa_number(self) -> str | None:
        """Ekstrak nomor pengirim — handle @c.us dan @lid."""
        from_ = self.payload.get("from", "")
        if "@c.us" in from_ or "@lid" in from_:
            return from_.split("@")[0]
        return None

    def get_message_body(self) -> str | None:
        return self.payload.get("body")

    def get_message_type(self) -> str:
        return self.payload.get("type", "chat")

    def is_from_me(self) -> bool:
        return self.payload.get("fromMe", False)

    def is_group_message(self) -> bool:
        from_ = self.payload.get("from", "")
        return "@g.us" in from_
