# Telegram Password Bot V2

## Tính năng

- Nhận diện yêu cầu đăng nhập và rút tiền.
- Chỉ xử lý khi admin reply trực tiếp bằng `DONE`, `DONE✅` hoặc `✅`.
- Gửi riêng tài khoản và mật khẩu cho người yêu cầu.
- Gửi bản sao cho một hoặc nhiều admin.
- Có nút sao chép mật khẩu.
- Chống xử lý trùng.
- Lưu lịch sử trong SQLite.
- Mật khẩu đăng nhập: 2 chữ thường + 8 số.
- Mật khẩu rút tiền: 4 số.

## Từ khóa đăng nhập

- `mk dn`
- `mkdn`
- `mk đăng nhập`
- `xin mk đăng nhập`
- `mật khẩu đăng nhập`
- `login`

## Từ khóa rút tiền

- `mk rt`
- `mkrt`
- `mk rút tiền`
- `xin mk rt`
- `mật khẩu rút tiền`
- `rút tiền`

## Cài trên VPS

```bash
git clone URL_REPOSITORY
cd telegram_password

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env

python bot.py
```

## File `.env`

```env
BOT_TOKEN=TOKEN_MOI_CUA_BAN
ADMIN_CHAT_IDS=7028707015
OWNER_USER_IDS=7028707015
DELETE_NOTICE_AFTER_SECONDS=10
```

Có nhiều admin thì ngăn cách bằng dấu phẩy:

```env
ADMIN_CHAT_IDS=111111111,222222222
OWNER_USER_IDS=111111111,222222222
```

## BotFather

Mở `@BotFather`:

1. Gửi `/setprivacy`
2. Chọn bot
3. Chọn `Disable`

## Quy trình sử dụng

Người dùng gửi:

```text
0837317243 xin mk đăng nhập
```

Admin reply trực tiếp:

```text
DONE
```

Bot gửi riêng:

```text
Tài khoản: 0837317243
Mật khẩu đăng nhập: ab12345678
```
