"""PolyAgent Telegram Bot — auto scanner + manual analysis + auto betting."""
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
from scanner.trader import (
    should_execute,
    execute_bet,
    format_bet_message,
    reset_daily_limit,
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

# Auto-bet mode (off by default, toggle with /autobet)
auto_bet_enabled = False
dry_run_mode = True  # Start in dry run (simulation)

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
        "*Analysis:*\n"
        "/scan \\- Scan markets now\n"
        "/analyze \\<event\\_id\\> \\- Analyze specific event\n"
        "/status \\- Bot status\n\n"
        "*Trading:*\n"
        "/autobet \\- Toggle auto\\-betting on/off\n"
        "/dryrun \\- Toggle dry run \\(simulation\\) mode\n"
        "/bet \\<event\\_id\\> \\- Analyze \\+ bet on specific event\n"
        "/limits \\- Show betting limits\n\n"
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

        summary = format_summary(
            result["event_title"],
            result["decision"],
            result.get("event_slug", ""),
        )
        await update.message.reply_text(summary, parse_mode="MarkdownV2")

        detailed = format_detailed(
            result["event_title"],
            result["decision"],
            result["reports"],
        )
        await update.message.reply_text(detailed, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        await update.message.reply_text(f"❌ Analysis failed: {e}")


async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bet <event_id> — analyze and place bet if edge found."""
    if not context.args:
        await update.message.reply_text("Usage: /bet <event_id or slug>")
        return

    event_id = " ".join(context.args)
    await update.message.reply_text(f"🔍 Analyzing for bet: {event_id}...")

    try:
        result = analyze_single(event_id, config_overrides=get_config())
        decision = result["decision"]

        # Send analysis first
        summary = format_summary(
            result["event_title"],
            decision,
            result.get("event_slug", ""),
        )
        await update.message.reply_text(summary, parse_mode="MarkdownV2")

        # Check if we should bet
        should_bet, reason = should_execute(decision)
        if not should_bet:
            await update.message.reply_text(f"⏭️ No bet: {reason}")
            return

        # Get token ID for the market
        token_id = _get_token_id(event_id)
        if not token_id:
            await update.message.reply_text("❌ Could not find token ID for this event")
            return

        # Execute bet
        bet_result = execute_bet(
            decision=decision,
            token_id=token_id,
            dry_run=dry_run_mode,
        )

        msg = format_bet_message(bet_result, result["event_title"])
        await update.message.reply_text(msg, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Bet failed: {e}")
        await update.message.reply_text(f"❌ Bet failed: {e}")


async def cmd_autobet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle auto-betting on/off."""
    global auto_bet_enabled
    auto_bet_enabled = not auto_bet_enabled
    status = "ON ✅" if auto_bet_enabled else "OFF ❌"
    mode = "DRY RUN 🧪" if dry_run_mode else "LIVE 💰"
    await update.message.reply_text(
        f"Auto-betting: {status}\nMode: {mode}\n\n"
        f"When ON, scan results with edge will automatically place bets."
    )


async def cmd_dryrun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle dry run mode."""
    global dry_run_mode
    dry_run_mode = not dry_run_mode
    status = "DRY RUN 🧪 (simulation)" if dry_run_mode else "LIVE 💰 (real money!)"
    await update.message.reply_text(f"Mode: {status}")


async def cmd_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current betting limits."""
    from scanner.trader import MAX_BET_USDC, MAX_DAILY_USDC, MIN_EDGE, MIN_CONFIDENCE, _daily_spent
    await update.message.reply_text(
        f"📊 Betting Limits\n\n"
        f"Max single bet: ${MAX_BET_USDC}\n"
        f"Max daily total: ${MAX_DAILY_USDC}\n"
        f"Min edge: {MIN_EDGE:.0%}\n"
        f"Min confidence: {MIN_CONFIDENCE:.0%}\n"
        f"Spent today: ${_daily_spent:.2f}\n"
        f"Auto-bet: {'ON' if auto_bet_enabled else 'OFF'}\n"
        f"Mode: {'DRY RUN' if dry_run_mode else 'LIVE'}"
    )


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


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_token_id(event_id: str) -> str:
    """Get the YES token ID for an event."""
    try:
        from tradingagents.agents.utils.polymarket_tools import _resolve_event
        import json as _json
        evt = _resolve_event(event_id)
        markets = evt.get("markets", [])
        if markets:
            # Pick the first active market with the highest volume
            best = max(markets, key=lambda m: float(m.get("volume", 0) or 0))
            token_ids = best.get("clobTokenIds", "[]")
            if isinstance(token_ids, str):
                token_ids = _json.loads(token_ids)
            if token_ids:
                return token_ids[0]  # First token is YES
    except Exception as e:
        logger.error(f"Could not get token ID: {e}")
    return ""


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
        await context.bot.send_message(
            chat_id=target_chat,
            text=format_scan_start(MAX_EVENTS),
            parse_mode="MarkdownV2",
        )

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
            for r in results:
                # Send analysis
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

                # Auto-bet if enabled
                if auto_bet_enabled:
                    should_bet, reason = should_execute(r["decision"])
                    if should_bet:
                        token_id = _get_token_id(r.get("event_slug", ""))
                        if token_id:
                            bet_result = execute_bet(
                                decision=r["decision"],
                                token_id=token_id,
                                dry_run=dry_run_mode,
                            )
                            msg = format_bet_message(bet_result, r["event_title"])
                            await context.bot.send_message(
                                chat_id=target_chat,
                                text=msg,
                                parse_mode="MarkdownV2",
                            )

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


async def daily_reset(context: ContextTypes.DEFAULT_TYPE):
    """Reset daily spending limit at midnight."""
    reset_daily_limit()


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
    logger.info(f"Auto-bet: {'ON' if auto_bet_enabled else 'OFF'} | Mode: {'DRY RUN' if dry_run_mode else 'LIVE'}")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("bet", cmd_bet))
    app.add_handler(CommandHandler("autobet", cmd_autobet))
    app.add_handler(CommandHandler("dryrun", cmd_dryrun))
    app.add_handler(CommandHandler("limits", cmd_limits))

    # Scheduled jobs
    job_queue = app.job_queue
    job_queue.run_repeating(
        scheduled_scan,
        interval=SCAN_INTERVAL_HOURS * 3600,
        first=10,
    )
    # Daily limit reset at midnight
    job_queue.run_daily(daily_reset, time=datetime.strptime("00:00", "%H:%M").time())

    logger.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
