import hashlib

def get_text_hash(text: str) -> str:
    if not text:
        return ""
    clean = "".join(text.split()).lower()
    return hashlib.sha256(clean.encode()).hexdigest()
