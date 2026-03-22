# Telegram Bot Scanner Design Spec

## Overview

Telegram bot that automatically scans Polymarket for high-edge prediction markets every 6 hours and sends alerts. Also supports manual event analysis via commands.

## Commands

| Command | Description |
|---------|-------------|
| `/scan` | Immediate market scan + analysis + results |
| `/analyze <event_id>` | Deep analysis of a specific event |
| `/status` | Bot status, last scan time, next scan time |
| (automatic) | Every 6 hours: scan → filter → analyze → alert |

## Scan Logic

1. `search_markets()` fetches active events from Gamma API
2. Filter: `min_volume_24h >= 10000`, `min_liquidity >= 5000`, `max_days_to_end <= 30`
3. Cap at `max_events_per_scan = 10` (sorted by volume desc)
4. For each event: run `TradingAgentsGraph.propagate()`
5. Filter results: only alert if `abs(edge) >= 0.05` (5%)

## Message Format

### Summary (sent immediately per edge event)

```
🔮 Edge Found: {event_title}
{action} | Confidence: {confidence}% | Edge: {edge}%
https://polymarket.com/event/{slug}
```

### Detailed Report (follow-up message)

```
📊 Full Report: {event_title}

[Odds] Market: YES {price}% | Volume ${volume}
[News] {news_summary}
[Event] {event_summary}
[Decision] {action} — {reasoning}

🎯 Position: {position_size}% | Horizon: {time_horizon}
```

## File Structure

```
scanner/
  bot.py          # Telegram bot: command handlers + APScheduler
  analyzer.py     # Scan + analysis logic (wraps TradingAgentsGraph)
  formatter.py    # Message formatting (summary + detailed)
```

## Configuration (.env additions)

```
TELEGRAM_BOT_TOKEN=<from @BotFather>
TELEGRAM_CHAT_ID=<your chat/group ID>
```

## Scan Settings (default_config.py)

Already defined in `scan_defaults`:
```python
"scan_defaults": {
    "min_volume_24h": 10000,
    "min_liquidity": 5000,
    "max_days_to_end": 30,
    "categories": [],
},
```

Additional settings for scanner:
```python
"scanner": {
    "min_edge": 0.05,
    "max_events_per_scan": 10,
    "scan_interval_hours": 6,
},
```

## Dependencies

```
python-telegram-bot   # Telegram bot framework
apscheduler           # Periodic scheduling
```

## Deployment (36번 서버)

systemd service running the bot process:

```ini
[Unit]
Description=PolyAgent Telegram Scanner Bot
After=network.target

[Service]
Type=simple
User=jsong
WorkingDirectory=/home/jsong/TradingAgents
ExecStart=/home/jsong/TradingAgents/.venv/bin/python -m scanner.bot
Restart=always
RestartSec=10
EnvironmentFile=/home/jsong/TradingAgents/.env

[Install]
WantedBy=multi-user.target
```

## Non-Goals

- Multi-user support (single chat ID)
- Inline keyboard interactions
- Trade execution from Telegram
- Historical analysis storage
