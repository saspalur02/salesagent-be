import re

def normalize_phone(number: str) -> str:
    """Hanya bersihkan nomor jika itu memang nomor HP murni (digit)."""
    # Jika sudah ada format @, jangan di-normalize pakai regex digit
    if "@" in number:
        return number
        
    digits = re.sub(r"\D", "", number)
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits

def to_waha_id(number: str) -> str:
    """Konversi cerdas: Tetap pakai @lid jika aslinya @lid."""
    if "@" in number:
        return number  # Biarkan apa adanya (misal: @lid atau @g.us)
    
    # Jika hanya angka, baru tambahkan @c.us
    return f"{normalize_phone(number)}@c.us"

def from_waha_id(waha_id: str) -> str:
    """Ekstrak nomor tanpa peduli @c.us atau @lid."""
    return waha_id.split("@")[0]