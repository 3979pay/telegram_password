import logging
from datetime import datetime
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_IDS, OWNER_USER_IDS
from database import (
    delete_pending_password, delete_pending_request, get_last_account,
    get_pending_password, get_pending_request, is_processed, mark_processed,
    save_history, save_last_account, save_pending_password, save_pending_request,
)
from keywords import detect_request, is_done_command
from passwords import create_login_password, create_withdraw_password

logger = logging.getLogger(__name__)

def copy_keyboard(password):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text='📋 Sao chép mật khẩu', copy_text=CopyTextButton(text=password))]])

async def remember_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or not chat or user.is_bot:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    content = message.text or message.caption or ''
    if is_done_command(content):
        return
    request_type, account = detect_request(content)
    if request_type is None:
        return
    if not account:
        account = get_last_account(user.id)
    if not account:
        return
    save_last_account(user.id, account)
    save_pending_request(user.id, request_type, account, chat.id, message.message_id)

async def send_password_to_user(context, user_id, request_type, account, password):
    if request_type == 'login':
        title, label = '🔐 Thông tin đăng nhập', 'Mật khẩu đăng nhập'
    else:
        title, label = '💰 Thông tin rút tiền', 'Mật khẩu rút tiền'
    await context.bot.send_message(
        chat_id=user_id,
        text=f'{title}\n\nTài khoản: <code>{account}</code>\n{label}: <code>{password}</code>',
        parse_mode=ParseMode.HTML,
        reply_markup=copy_keyboard(password),
    )

async def send_admin_copies(context, request_type, account, password, recipient, confirmer, group_name):
    if not ADMIN_CHAT_IDS:
        return
    type_name = 'Mật khẩu đăng nhập' if request_type == 'login' else 'Mật khẩu rút tiền'
    text = (
        '📋 <b>BẢN SAO ĐÃ GỬI</b>\n\n'
        f'Loại: <b>{type_name}</b>\nTài khoản: <code>{account}</code>\n'
        f'Mật khẩu: <code>{password}</code>\n\nNgười nhận: {recipient.full_name}\n'
        f'User ID: <code>{recipient.id}</code>\nNgười xác nhận: {confirmer.full_name}\n'
        f'Nhóm: {group_name}\nThời gian: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
    )
    for admin_chat_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=admin_chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=copy_keyboard(password))
        except (Forbidden, BadRequest) as exc:
            logger.error('Không gửi được bản sao cho admin %s: %s', admin_chat_id, exc)

async def can_use_done(context, chat_id, user_id):
    if OWNER_USER_IDS:
        return user_id in OWNER_USER_IDS
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in {'administrator', 'creator'}
    except Exception:
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, chat, message = update.effective_user, update.effective_chat, update.effective_message
    if not user or not chat or not message:
        return
    if chat.type != ChatType.PRIVATE:
        await message.reply_text('Hãy mở chat riêng với bot rồi bấm Start.')
        return
    pending = get_pending_password(user.id)
    if pending:
        request_type, account, password = pending
        await send_password_to_user(context, user.id, request_type, account, password)
        delete_pending_password(user.id)
        return
    await message.reply_text(f'✅ Bạn đã kết nối với bot.\n\nTelegram ID của bạn: <code>{user.id}</code>', parse_mode=ParseMode.HTML)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_message:
        await update.effective_message.reply_text(f'Telegram ID của bạn: <code>{update.effective_user.id}</code>', parse_mode=ParseMode.HTML)

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, confirmer, chat = update.effective_message, update.effective_user, update.effective_chat
    if not message or not confirmer or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not is_done_command(message.text or '') or not message.reply_to_message:
        return
    if not await can_use_done(context, chat.id, confirmer.id):
        return

    recipient = message.reply_to_message.from_user
    if not recipient or recipient.is_bot:
        return

    pending = get_pending_request(recipient.id)
    if not pending:
        await message.reply_text('⚠️ Người này chưa có yêu cầu mật khẩu đang chờ.')
        return

    request_type, account, source_chat_id, source_message_id = pending
    if is_processed(source_chat_id, source_message_id):
        await message.reply_text('⚠️ Yêu cầu gần nhất của người này đã được xử lý.')
        return

    if request_type == 'login':
        password = create_login_password()
        notice = '✅ Đã gửi mật khẩu đăng nhập vào tin nhắn riêng.'
    else:
        password = create_withdraw_password()
        notice = '✅ Đã gửi mật khẩu rút tiền vào tin nhắn riêng.'

    try:
        await send_password_to_user(context, recipient.id, request_type, account, password)
        await send_admin_copies(context, request_type, account, password, recipient, confirmer, chat.title or 'Không rõ')
        save_history(
            group_name=chat.title or 'Không rõ', group_id=chat.id,
            confirmer_id=confirmer.id, confirmer_name=confirmer.full_name,
            recipient_id=recipient.id, recipient_name=recipient.full_name,
            request_type=request_type, account=account, password=password,
        )
        mark_processed(source_chat_id, source_message_id)
        delete_pending_request(recipient.id)
        await message.reply_to_message.reply_text(f'{recipient.mention_html()} {notice}', parse_mode=ParseMode.HTML)
    except Forbidden:
        save_pending_password(recipient.id, request_type, account, password)
        bot_info = await context.bot.get_me()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='🔐 Nhận mật khẩu riêng', url=f'https://t.me/{bot_info.username}?start=nhanmatkhau')]])
        await message.reply_to_message.reply_text(
            f'{recipient.mention_html()} hãy nhấn nút bên dưới rồi bấm Start.',
            parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
