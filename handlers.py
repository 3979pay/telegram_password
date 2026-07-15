import asyncio
import logging
from datetime import datetime

from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from config import (
    ADMIN_CHAT_IDS,
    DELETE_NOTICE_AFTER_SECONDS,
    OWNER_USER_IDS,
)
from database import (
    delete_pending_password,
    get_last_account,
    get_pending_password,
    is_processed,
    mark_processed,
    save_history,
    save_last_account,
    save_pending_password,
)
from keywords import detect_request, is_done_command
from passwords import create_login_password, create_withdraw_password

logger = logging.getLogger(__name__)


def copy_keyboard(password: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                text="📋 Sao chép mật khẩu",
                copy_text=CopyTextButton(text=password),
            )
        ]]
    )


async def send_password_to_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    request_type: str,
    account: str,
    password: str,
) -> None:
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


async def send_admin_copies(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    request_type: str,
    account: str,
    password: str,
    recipient,
    confirmer,
    group_name: str,
) -> None:
    if not ADMIN_CHAT_IDS:
        return

    type_name = (
        "Mật khẩu đăng nhập"
        if request_type == "login"
        else "Mật khẩu rút tiền"
    )

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

    for admin_chat_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=copy_keyboard(password),
            )
        except (Forbidden, BadRequest) as exc:
            logger.error(
                "Không gửi được bản sao cho admin %s: %s",
                admin_chat_id,
                exc,
            )


async def delete_after(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
) -> None:
    await asyncio.sleep(DELETE_NOTICE_AFTER_SECONDS)
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )
    except (BadRequest, Forbidden):
        pass


async def can_use_done(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
) -> bool:
    if OWNER_USER_IDS:
        return user_id in OWNER_USER_IDS

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in {"administrator", "creator"}
    except Exception:
        return False


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not user or not chat or not message:
        return

    if chat.type != ChatType.PRIVATE:
        await message.reply_text(
            "Hãy mở chat riêng với bot rồi bấm Start."
        )
        return

    pending = get_pending_password(user.id)

    if pending:
        request_type, account, password = pending
        await send_password_to_user(
            context,
            user.id,
            request_type,
            account,
            password,
        )
        delete_pending_password(user.id)
        return

    await message.reply_text(
        "✅ Bạn đã kết nối với bot.\n\n"
        f"Telegram ID của bạn: <code>{user.id}</code>\n\n"
        "Bot chỉ xử lý khi admin reply DONE vào tin nhắn yêu cầu.",
        parse_mode=ParseMode.HTML,
    )


async def myid_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user and message:
        await message.reply_text(
            f"Telegram ID của bạn: <code>{user.id}</code>",
            parse_mode=ParseMode.HTML,
        )


async def handle_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    confirmer = update.effective_user
    chat = update.effective_chat

    if not message or not confirmer or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    if not is_done_command(message.text or ""):
        return

    if not message.reply_to_message:
        return

    if not await can_use_done(context, chat.id, confirmer.id):
        return

    original_message = message.reply_to_message
    original_user = original_message.from_user

    if not original_user or original_user.is_bot:
        return

    if is_processed(chat.id, original_message.message_id):
        await message.reply_text(
            "⚠️ Yêu cầu này đã được xử lý trước đó."
        )
        return

    request_type, account = detect_request(original_message.text or "")

    if request_type is None:
        await message.reply_text(
            "⚠️ Bot không nhận diện được loại mật khẩu."
        )
        return

    if not account:
        account = get_last_account(original_user.id)

    if not account:
        await message.reply_text(
            "⚠️ Không tìm thấy tên tài khoản trong tin nhắn."
        )
        return

    save_last_account(original_user.id, account)

    if request_type == "login":
        password = create_login_password()
        group_notice = "✅ Đã gửi mật khẩu đăng nhập vào tin nhắn riêng."
    else:
        password = create_withdraw_password()
        group_notice = "✅ Đã gửi mật khẩu rút tiền vào tin nhắn riêng."

    try:
        await send_password_to_user(
            context,
            original_user.id,
            request_type,
            account,
            password,
        )

        await send_admin_copies(
            context,
            request_type=request_type,
            account=account,
            password=password,
            recipient=original_user,
            confirmer=confirmer,
            group_name=chat.title or "Không rõ",
        )

        save_history(
            group_name=chat.title or "Không rõ",
            group_id=chat.id,
            confirmer_id=confirmer.id,
            confirmer_name=confirmer.full_name,
            recipient_id=original_user.id,
            recipient_name=original_user.full_name,
            request_type=request_type,
            account=account,
            password=password,
        )

        mark_processed(chat.id, original_message.message_id)

        reply = await original_message.reply_text(
            f"{original_user.mention_html()} {group_notice}",
            parse_mode=ParseMode.HTML,
        )

        asyncio.create_task(
            delete_after(context, reply.chat_id, reply.message_id)
        )

    except Forbidden:
        save_pending_password(
            original_user.id,
            request_type,
            account,
            password,
        )

        bot_info = await context.bot.get_me()
        open_bot_url = f"https://t.me/{bot_info.username}?start=nhanmatkhau"

        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    text="🔐 Nhận mật khẩu riêng",
                    url=open_bot_url,
                )
            ]]
        )

        await original_message.reply_text(
            f"{original_user.mention_html()} hãy nhấn nút bên dưới rồi bấm Start.",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
