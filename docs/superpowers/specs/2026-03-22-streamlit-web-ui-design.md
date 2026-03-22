# Streamlit Web UI Design Spec

## Overview

Add a browser-based web UI for the Polymarket prediction agent using Streamlit. Users access `tradingagent.songfamily.work`, log in with ID/PW, and run event analyses with visual progress and report display.

## Layout: Top-Down Full-Width

Three sections stacked vertically:

1. **Input Bar** — Mode toggle (Manual/Scan) + event input + Analyze button
2. **Progress** — Agent status icons + progress bar (step-by-step)
3. **Report Grid** — 2-column card grid for analyst reports, highlighted final decision card, expandable research/trader/risk sections

## Authentication

- Simple session-based login page before main UI
- Credentials stored in `.env`: `WEB_USERNAME`, `WEB_PASSWORD`
- `st.session_state["authenticated"]` controls access
- No external auth service needed

## Core Implementation

### Execution Flow

```
User inputs event → clicks Analyze
    ↓
Streamlit initializes TradingAgentsGraph with config from sidebar
    ↓
graph.graph.stream() called (reuses existing LangGraph streaming)
    ↓
Per chunk:
  - Update st.status (current agent name + icon)
  - Increment st.progress_bar
  - Fill report card placeholder (st.empty)
    ↓
Complete: Display final decision JSON as highlighted card
```

### Agent Progress Display

Each agent shown as icon + name in a horizontal row:

```
✅ Odds  ✅ News  🔄 Event  ⬜ Debate  ⬜ Trader  ⬜ Risk
████████████░░░░░░░░░░░░  50%
```

Icons: ⬜ pending, 🔄 in_progress, ✅ completed

### Report Cards

- 4 analyst cards in 2x2 grid (Odds, News, Event, Sentiment)
- Final Decision card: full-width, highlighted with action color (YES=green, NO=red, SKIP=gray)
- 3 detail cards below: Research Plan, Trader Plan, Risk Decision
- Each card uses `st.expander` for full content, preview shows first ~200 chars

### Market Scan Mode

- Button triggers `search_markets()` tool call
- Results displayed in `st.dataframe` with clickable rows
- Selecting a row populates the event input field

### LLM Settings

Collapsed in `st.sidebar`:
- Provider (OpenRouter default)
- Quick/Deep model selection
- Debate rounds (1-5)
- API key display (masked)

## File Structure

```
web/
  app.py                    # Streamlit main (login + analysis UI)
  deploy/
    tradingagent.service    # systemd unit file
```

Single file `app.py` imports from `tradingagents/` package directly.

## Deployment

### Server (36번 서버)

```bash
streamlit run web/app.py --server.port 8501 --server.address 0.0.0.0
```

Managed via systemd service for auto-restart.

### systemd Unit

```ini
[Unit]
Description=PolyAgent Streamlit Web UI
After=network.target

[Service]
Type=simple
User=<deploy-user>
WorkingDirectory=/path/to/TradingAgents
ExecStart=/path/to/.venv/bin/streamlit run web/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=5
EnvironmentFile=/path/to/TradingAgents/.env

[Install]
WantedBy=multi-user.target
```

### Cloudflare

- DNS: `tradingagent.songfamily.work` → 36번 서버 IP
- Proxy mode: Proxied (orange cloud)
- SSL: Full (Cloudflare handles HTTPS termination)
- Origin: HTTP port 8501

## Dependencies

```
streamlit   # add to requirements.txt
```

No other new dependencies — reuses existing `tradingagents/` package.

## Non-Goals

- User registration / multi-user accounts
- Analysis history / database storage
- Real-time WebSocket streaming
- Mobile-optimized layout
