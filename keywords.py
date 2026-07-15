import re
import unicodedata


LOGIN_KEYWORDS = [
    "mk dn",
    "mkdn",
    "mk dang nhap",
    "mat khau dang nhap",
    "xin mk dang nhap",
    "xin mat khau dang nhap",
    "xin mk dn",
    "dang nhap",
    "login",
]

WITHDRAW_KEYWORDS = [
    "mk rt",
    "mkrt",
    "mat khau rt",
    "mk rut tien",
    "mat khau rut tien",
    "xin mk rt",
    "xin mat khau rut tien",
    "rut tien",
    "withdraw",
]

FILLER_WORDS = {
    "xin", "cho", "em", "anh", "chi", "oi", "voi", "giup",
    "cap", "doi", "lay", "can", "ho", "minh", "admin",
    "onbet", "please",
}


def remove_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return normalized.replace("đ", "d").replace("Đ", "D")


def normalize_text(text: str) -> str:
    text = remove_accents(text.lower())
    text = re.sub(r"[，,;|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_keyword(text: str, keywords: list[str]) -> str | None:
    for keyword in sorted(keywords, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text):
            return keyword
    return None


def extract_account(original_text: str, keyword: str) -> str | None:
    text = normalize_text(original_text)
    remaining = re.sub(
        rf"(?<!\w){re.escape(keyword)}(?!\w)",
        " ",
        text,
        count=1,
    )
    words = [
        word for word in re.split(r"\s+", remaining)
        if word and word not in FILLER_WORDS
    ]

    for word in words:
        cleaned = word.strip(":=_-")
        if re.fullmatch(r"[a-z0-9_.@\-]{2,64}", cleaned):
            return cleaned

    return None


def detect_request(text: str) -> tuple[str | None, str | None]:
    normalized = normalize_text(text)

    withdraw_keyword = find_keyword(normalized, WITHDRAW_KEYWORDS)
    if withdraw_keyword:
        return "withdraw", extract_account(text, withdraw_keyword)

    login_keyword = find_keyword(normalized, LOGIN_KEYWORDS)
    if login_keyword:
        return "login", extract_account(text, login_keyword)

    return None, None


def is_done_command(text: str) -> bool:
    normalized = text.strip().upper().replace(" ", "")
    return normalized in {"DONE", "DONE✅", "✅"}
