# PolyAgent — Polymarket Prediction Market Analyzer

Multi-agent AI system that analyzes Polymarket prediction markets using LLM-powered agents.

## Architecture

```
Input (Event ID/URL or Auto-Scan)
    ↓
Phase 1: 4 Analysts (parallel)
├─ Odds Analyst    → market prices, orderbook, price trends
├─ News Analyst    → event-related news via Tavily
├─ Social Analyst  → social sentiment, whale activity
└─ Event Analyst   → resolution criteria, deadline, top traders
    ↓
Phase 2: 3-Way Debate (sequential)
├─ YES Advocate    → argues event WILL occur
├─ NO Advocate     → argues event will NOT occur
├─ Timing Advocate → market efficiency, edge vs current odds
└─ Research Manager (Judge) → YES/NO/SKIP + confidence
    ↓
Phase 3: Trader → position sizing, edge calculation
    ↓
Phase 4: Risk Debate
├─ Aggressive / Conservative / Neutral analysts
└─ Risk Manager → final decision
    ↓
Output: { action, confidence, edge, position_size, reasoning, time_horizon }
```

## Interfaces

### Telegram Bot (Primary)
```bash
python -m scanner.bot
```
| Command | Description |
|---------|-------------|
| `/analyze <event>` | Analyze event (no betting) |
| `/bet <event>` | Analyze + bet (dry run by default) |
| `/scan` | Scan active markets |
| `/autobet` | Toggle auto-betting on/off |
| `/dryrun` | Toggle simulation/live mode |
| `/limits` | Show betting limits |
| `/status` | Bot status |

### Web UI
```bash
streamlit run web/app.py
```
Access: https://tradingagent.songfamily.work

### CLI
```bash
python -m cli.main
```

## Deployment (36번 서버)

Services running via systemd:
- `polyagent-bot.service` — Telegram bot
- `polyagent-web.service` — Streamlit UI
- `cloudflared` — Cloudflare tunnel for web access

```bash
# Check status
sudo systemctl status polyagent-bot polyagent-web

# Restart
sudo systemctl restart polyagent-bot polyagent-web

# Update code
cd ~/TradingAgents && git pull && sudo systemctl restart polyagent-bot polyagent-web
```

## Configuration (.env)

```
# LLM
OPENAI_API_KEY=<GLM API key>       # Using GLM-4.5-flash (subscription)

# Data
TAVILY_API_KEY=<key>               # News search

# Telegram
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat_id>

# Polymarket Trading
POLYMARKET_PRIVATE_KEY=<key>
POLYMARKET_API_KEY=<key>
POLYMARKET_API_SECRET=<secret>
POLYMARKET_API_PASSPHRASE=<passphrase>

# Web UI
WEB_USERNAME=<user>
WEB_PASSWORD=<pass>
```

## Safety Limits (Auto-Betting)

| Setting | Default |
|---------|---------|
| Max single bet | $50 |
| Max daily total | $200 |
| Min edge to bet | 5% |
| Min confidence | 50% |
| Default mode | Dry Run (simulation) |

## LLM Model

Currently using **GLM-4.5-flash** via Z.AI direct API (subscription plan, no per-call cost).
Config: `tradingagents/default_config.py`
