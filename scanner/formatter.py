"""Message formatting for Telegram alerts."""
import json


def format_summary(event_title: str, decision: dict, event_slug: str = "") -> str:
    """Format a short summary alert message."""
    action = decision.get("action", "SKIP")
    emoji = {"YES": "🟢", "NO": "🔴", "SKIP": "⬜"}.get(action, "⬜")
    confidence = decision.get("confidence", 0)
    edge = decision.get("edge", 0)

    link = ""
    if event_slug:
        link = f"\nhttps://polymarket.com/event/{event_slug}"

    return (
        f"🔮 *Edge Found:* {_escape(event_title)}\n"
        f"{emoji} *{action}* \\| Confidence: {confidence:.0%} \\| Edge: {edge:.1%}"
        f"{link}"
    )


def format_detailed(event_title: str, decision: dict, reports: dict) -> str:
    """Format a detailed analysis report message."""
    action = decision.get("action", "SKIP")
    confidence = decision.get("confidence", 0)
    edge = decision.get("edge", 0)
    reasoning = decision.get("reasoning", "N/A")
    position = decision.get("position_size", 0)
    horizon = decision.get("time_horizon", "N/A")

    odds_summary = _truncate(reports.get("odds_report", ""), 200)
    news_summary = _truncate(reports.get("news_report", ""), 200)
    event_summary = _truncate(reports.get("event_report", ""), 200)

    return (
        f"📊 *Full Report:* {_escape(event_title)}\n\n"
        f"*\\[Odds\\]* {_escape(odds_summary)}\n"
        f"*\\[News\\]* {_escape(news_summary)}\n"
        f"*\\[Event\\]* {_escape(event_summary)}\n\n"
        f"*\\[Decision\\]* {action} — {_escape(reasoning)}\n\n"
        f"🎯 Position: {position:.1%} \\| Horizon: {_escape(horizon)}"
    )


def format_scan_start(event_count: int) -> str:
    """Format scan start notification."""
    return f"🔍 *Scanning {event_count} markets\\.\\.\\.*"


def format_scan_complete(total: int, alerts: int) -> str:
    """Format scan completion summary."""
    return f"✅ *Scan complete:* {total} analyzed, {alerts} edge events found"


def format_no_edge() -> str:
    """Format no-edge-found message."""
    return "✅ Scan complete — no significant edge found this round\\."


def format_status(last_scan: str, next_scan: str, is_running: bool) -> str:
    """Format bot status message."""
    status = "🟢 Running" if not is_running else "🔄 Scanning"
    return (
        f"*PolyAgent Bot Status*\n\n"
        f"Status: {status}\n"
        f"Last scan: {_escape(last_scan)}\n"
        f"Next scan: {_escape(next_scan)}"
    )


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length."""
    text = text.strip().replace("\n", " ")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text if text else "N/A"


def _escape(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!"
    result = ""
    for ch in str(text):
        if ch in special:
            result += "\\" + ch
        else:
            result += ch
    return result
