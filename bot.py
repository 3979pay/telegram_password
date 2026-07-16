import logging

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, LOG_PATH
from database import cleanup_old_data, init_database
from handlers import handle_done, myid_command, remember_request, start_command


def configure_logging():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )


def main():
    configure_logging()
    init_database()

    cleanup_result = cleanup_old_data()
    logging.info(
        'Đã dọn dữ liệu cũ: history=%s processed=%s pending=%s',
        cleanup_result['history'],
        cleanup_result['processed'],
        cleanup_result['pending'],
    )

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('myid', myid_command))
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            remember_request,
        ),
        group=0,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_done,
        ),
        group=1,
    )

    print('Bot đang chạy...')
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
