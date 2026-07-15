import secrets
import string


def create_login_password() -> str:
    """Tạo mật khẩu đăng nhập: 2 chữ thường + 8 số."""
    letters = "".join(
        secrets.choice(string.ascii_lowercase) for _ in range(2)
    )
    digits = "".join(
        secrets.choice(string.digits) for _ in range(8)
    )
    return letters + digits


def create_withdraw_password() -> str:
    """Tạo mật khẩu rút tiền: đúng 4 số."""
    return "".join(
        secrets.choice(string.digits) for _ in range(4)
    )
