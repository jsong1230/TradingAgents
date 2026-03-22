"""PolyAgent Telegram Bot — auto scanner + manual analysis."""
import os
import sys
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from scanner.analyzer import scan_and_analyze, analyze_single
from scanner.formatter import (
    format_summary,
    format_detailed,
    format_scan_start,
    format_scan_complete,
    format_no_edge,
    format_status,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCAN_INTERVAL_HOURS = 6
MIN_EDGE = 0.05
MAX_EVENTS = 10

# State
last_scan_time = "Never"
is_scanning = False


def get_config() -> dict:
    """Build analysis config from defaults."""
    from tradingagents.default_config import DEFAULT_CONFIG
    config = DEFAULT_CONFIG.copy()
    return config


# ── Command Handlers ────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🔮 *PolyAgent Bot*\n\n"
        "Commands:\n"
        "/scan \\- Scan markets now\n"
        "/analyze \\<event\\_id\\> \\- Analyze specific event\n"
        "/status \\- Bot status\n\n"
        f"Auto\\-scan every {SCAN_INTERVAL_HOURS}h",
        parse_mode="MarkdownV2",
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command — immediate market scan."""
    await _run_scan(context, chat_id=update.effective_chat.id)


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze <event_id> command."""
    if not context.args:
        await update.message.reply_text("Usage: /analyze <event_id or slug>")
        return

    event_id = " ".join(context.args)
    await update.message.reply_text(f"🔍 Analyzing: {event_id}...")

    try:
        result = analyze_single(event_id, config_overrides=get_config())

        # Send summary
        summary = format_summary(
            result["event_title"],
            result["decision"],
            result.get("event_slug", ""),
        )
        await update.message.reply_text(summary, parse_mode="MarkdownV2")

        # Send detailed report
        detailed = format_detailed(
            result["event_title"],
            result["decision"],
            result["reports"],
        )
        await update.message.reply_text(detailed, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        await update.message.reply_text(f"❌ Analysis failed: {e}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    next_scan = "N/A"
    if last_scan_time != "Never":
        try:
            last_dt = datetime.strptime(last_scan_time, "%Y-%m-%d %H:%M")
            next_dt = last_dt + timedelta(hours=SCAN_INTERVAL_HOURS)
            next_scan = next_dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    msg = format_status(last_scan_time, next_scan, is_scanning)
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


# ── Scheduled Scan ──────────────────────────────────────────────────────────

async def _run_scan(context: ContextTypes.DEFAULT_TYPE, chat_id: int = None):
    """Execute a full market scan and send alerts."""
    global last_scan_time, is_scanning

    target_chat = chat_id or CHAT_ID
    if not target_chat:
        logger.error("No TELEGRAM_CHAT_ID configured.")
        return

    is_scanning = True

    try:
        # Notify scan start
        await context.bot.send_message(
            chat_id=target_chat,
            text=format_scan_start(MAX_EVENTS),
            parse_mode="MarkdownV2",
        )

        # Run scan
        results = scan_and_analyze(
            min_edge=MIN_EDGE,
            max_events=MAX_EVENTS,
            config_overrides=get_config(),
        )

        last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        if not results:
            await context.bot.send_message(
                chat_id=target_chat,
                text=format_no_edge(),
                parse_mode="MarkdownV2",
            )
        else:
            # Send summary for each edge event
            for r in results:
                summary = format_summary(
                    r["event_title"],
                    r["decision"],
                    r.get("event_slug", ""),
                )
                await context.bot.send_message(
                    chat_id=target_chat,
                    text=summary,
                    parse_mode="MarkdownV2",
                )

                # Send detailed report
                detailed = format_detailed(
                    r["event_title"],
                    r["decision"],
                    r["reports"],
                )
                await context.bot.send_message(
                    chat_id=target_chat,
                    text=detailed,
                    parse_mode="MarkdownV2",
                )

            # Send completion summary
            await context.bot.send_message(
                chat_id=target_chat,
                text=format_scan_complete(MAX_EVENTS, len(results)),
                parse_mode="MarkdownV2",
            )

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        try:
            await context.bot.send_message(
                chat_id=target_chat,
                text=f"❌ Scan failed: {e}",
            )
        except Exception:
            pass
    finally:
        is_scanning = False


async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    """Callback for scheduled scans."""
    await _run_scan(context, chat_id=int(CHAT_ID))


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)
    if not CHAT_ID:
        print("ERROR: TELEGRAM_CHAT_ID not set in .env")
        sys.exit(1)

    logger.info("Starting PolyAgent Telegram Bot...")
    logger.info(f"Chat ID: {CHAT_ID}")
    logger.info(f"Scan interval: {SCAN_INTERVAL_HOURS}h")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("status", cmd_status))

    # Schedule periodic scan
    job_queue = app.job_queue
    job_queue.run_repeating(
        scheduled_scan,
        interval=SCAN_INTERVAL_HOURS * 3600,
        first=10,  # first scan 10 seconds after startup
    )

    logger.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
