import logging
import re
from datetime import datetime

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from config import OWNER_USER_IDS
from database import (
    delete_pending_password,
    delete_pending_request,
    get_last_account,
    get_pending_password,
    get_pending_request,
    is_processed,
    mark_processed,
    save_history,
    save_last_account,
    save_pending_password,
    save_pending_request,
)
from keywords import detect_request
from passwords import create_login_password, create_withdraw_password

logger = logging.getLogger(__name__)


def copy_keyboard(password):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="📋 Sao chép mật khẩu",
            copy_text=CopyTextButton(text=password),
        )
    ]])


def parse_done_command(text):
    raw = (text or "").strip()
    if not raw:
        return False, None

    normalized = re.sub(r"\s+", " ", raw).strip()
    done_pattern = re.compile(r"(?i)(?<!\w)(?:DONE✅?|✅)(?!\w)")

    if not done_pattern.search(normalized):
        return False, None

    account_text = done_pattern.sub(" ", normalized, count=1)
    account_text = re.sub(r"\s+", " ", account_text).strip()

    if not account_text:
        return True, None

    candidates = re.findall(r"[A-Za-z0-9_.@\-]{2,64}", account_text)
    return True, candidates[0] if candidates else None


async def remember_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat or user.is_bot:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    content = message.text or message.caption or ""
    is_done, _ = parse_done_command(content)
    if is_done:
        return

    request_type, account = detect_request(content)
    if request_type is None:
        return

    if not account:
        account = get_last_account(user.id)
    if not account:
        return

    save_last_account(user.id, account)
    save_pending_request(
        user.id,
        request_type,
        account,
        chat.id,
        message.message_id,
    )


async def send_password_to_user(context, user_id, request_type, account, password):
    if request_type == "login":
        title = "🔐 Thông tin đăng nhập"
        label = "Mật khẩu đăng nhập"
    else:
        title = "💰 Thông tin rút tiền"
        label = "Mật khẩu rút tiền"

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"{title}\n\n"
            f"Tài khoản: <code>{account}</code>\n"
            f"{label}: <code>{password}</code>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=copy_keyboard(password),
    )


async def send_confirmer_copy(
    context,
    request_type,
    account,
    password,
    recipient,
    confirmer,
    group_name,
):
    """Gửi bản sao riêng cho đúng người vừa xác nhận DONE."""
    type_name = "Mật khẩu đăng nhập" if request_type == "login" else "Mật khẩu rút tiền"

    text = (
        "📋 <b>BẢN SAO ĐÃ GỬI</b>\n\n"
        f"Loại: <b>{type_name}</b>\n"
        f"Tài khoản: <code>{account}</code>\n"
        f"Mật khẩu: <code>{password}</code>\n\n"
        f"Người nhận: {recipient.full_name}\n"
        f"User ID: <code>{recipient.id}</code>\n"
        f"Người xác nhận: {confirmer.full_name}\n"
        f"Nhóm: {group_name}\n"
        f"Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

    try:
        await context.bot.send_message(
            chat_id=confirmer.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=copy_keyboard(password),
        )
    except Forbidden:
        logger.warning(
            "Không gửi được bản sao cho người xác nhận %s; "
            "người này cần mở chat riêng với bot và bấm Start.",
            confirmer.id,
        )
    except BadRequest as exc:
        logger.error(
            "Lỗi gửi bản sao cho người xác nhận %s: %s",
            confirmer.id,
            exc,
        )


async def can_use_done(context, chat_id, user_id):
    if OWNER_USER_IDS:
        return user_id in OWNER_USER_IDS

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not user or not chat or not message:
        return

    if chat.type != ChatType.PRIVATE:
        await message.reply_text("Hãy mở chat riêng với bot rồi bấm Start.")
        return

    pending = get_pending_password(user.id)
    if pending:
        request_type, account, password = pending
        await send_password_to_user(context, user.id, request_type, account, password)
        delete_pending_password(user.id)
        return

    await message.reply_text(
        f"✅ Bạn đã kết nối với bot.\n\nTelegram ID của bạn: <code>{user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_message:
        await update.effective_message.reply_text(
            f"Telegram ID của bạn: <code>{update.effective_user.id}</code>",
            parse_mode=ParseMode.HTML,
        )


async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    confirmer = update.effective_user
    chat = update.effective_chat

    if not message or not confirmer or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    is_done, account_override = parse_done_command(message.text or "")
    if not is_done or not message.reply_to_message:
        return
    if not await can_use_done(context, chat.id, confirmer.id):
        return

    replied_message = message.reply_to_message
    recipient = replied_message.from_user

    if not recipient or recipient.is_bot:
        return

    pending_request = get_pending_request(recipient.id)

    if pending_request:
        request_type, stored_account, source_chat_id, source_message_id = pending_request
    else:
        source_content = replied_message.text or replied_message.caption or ""
        request_type, stored_account = detect_request(source_content)
        if request_type is None:
            await message.reply_text("⚠️ Người này chưa có yêu cầu mật khẩu đang chờ.")
            return
        source_chat_id = chat.id
        source_message_id = replied_message.message_id

    account = account_override or stored_account or get_last_account(recipient.id)
    if not account:
        await message.reply_text("⚠️ Không tìm thấy tên tài khoản.")
        return

    if is_processed(source_chat_id, source_message_id):
        await message.reply_text("⚠️ Yêu cầu này đã được xử lý trước đó.")
        return

    save_last_account(recipient.id, account)

    if request_type == "login":
        password = create_login_password()
        notice = "✅ Đã gửi mật khẩu đăng nhập vào tin nhắn riêng."
    else:
        password = create_withdraw_password()
        notice = "✅ Đã gửi mật khẩu rút tiền vào tin nhắn riêng."

    try:
        await send_password_to_user(
            context,
            recipient.id,
            request_type,
            account,
            password,
        )

        await send_confirmer_copy(
            context,
            request_type,
            account,
            password,
            recipient,
            confirmer,
            chat.title or "Không rõ",
        )

        save_history(
            group_name=chat.title or "Không rõ",
            group_id=chat.id,
            confirmer_id=confirmer.id,
            confirmer_name=confirmer.full_name,
            recipient_id=recipient.id,
            recipient_name=recipient.full_name,
            request_type=request_type,
            account=account,
        )

        mark_processed(source_chat_id, source_message_id)
        delete_pending_request(recipient.id)

        await replied_message.reply_text(
            f"{recipient.mention_html()} {notice}",
            parse_mode=ParseMode.HTML,
        )

    except Forbidden:
        save_pending_password(recipient.id, request_type, account, password)
        bot_info = await context.bot.get_me()
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                text="🔐 Nhận mật khẩu riêng",
                url=f"https://t.me/{bot_info.username}?start=nhanmatkhau",
            )
        ]])

        await replied_message.reply_text(
            f"{recipient.mention_html()} hãy nhấn nút bên dưới rồi bấm Start.",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
