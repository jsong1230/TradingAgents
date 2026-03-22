"""Market scanning and analysis logic."""
import json
import logging
import time

from tradingagents.agents.utils.polymarket_tools import search_markets, _resolve_event
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


def scan_and_analyze(
    min_edge: float = 0.05,
    max_events: int = 10,
    config_overrides: dict = None,
) -> list[dict]:
    """Scan active markets, analyze each, and return events with significant edge.

    Returns a list of dicts: {event_title, event_slug, decision, reports}
    """
    config = DEFAULT_CONFIG.copy()
    if config_overrides:
        config.update(config_overrides)

    # 1. Fetch active events
    logger.info("Searching active markets...")
    scan_defaults = config.get("scan_defaults", {})
    raw_results = search_markets.invoke({
        "min_volume": scan_defaults.get("min_volume_24h", 10000),
        "limit": max_events * 3,  # fetch extra, filter later
    })

    # 2. Parse events from search results
    events = _parse_scan_results(raw_results, max_events)
    if not events:
        logger.info("No events found matching criteria.")
        return []

    logger.info(f"Found {len(events)} events to analyze.")

    # 3. Analyze each event
    results = []
    for evt in events:
        event_id = evt["event_id"]
        event_title = evt["title"]
        event_slug = evt.get("slug", event_id)

        logger.info(f"Analyzing: {event_title}")
        try:
            decision, reports = _analyze_event(event_id, event_title, config)
        except Exception as e:
            logger.error(f"Failed to analyze {event_title}: {e}")
            continue

        # 4. Filter by edge
        edge = abs(decision.get("edge", 0))
        if edge >= min_edge:
            logger.info(f"Edge found: {event_title} → {decision['action']} (edge: {edge:.1%})")
            results.append({
                "event_title": event_title,
                "event_slug": event_slug,
                "decision": decision,
                "reports": reports,
            })
        else:
            logger.info(f"No edge: {event_title} (edge: {edge:.1%})")

    return results


def analyze_single(event_id: str, config_overrides: dict = None) -> dict:
    """Analyze a single event by ID/slug. Returns {event_title, event_slug, decision, reports}."""
    config = DEFAULT_CONFIG.copy()
    if config_overrides:
        config.update(config_overrides)

    # Resolve event
    try:
        evt = _resolve_event(event_id)
        event_title = evt.get("title", event_id)
        event_slug = evt.get("slug", event_id)
    except Exception:
        event_title = event_id
        event_slug = event_id

    decision, reports = _analyze_event(event_id, event_title, config)
    return {
        "event_title": event_title,
        "event_slug": event_slug,
        "decision": decision,
        "reports": reports,
    }


def _analyze_event(event_id: str, event_question: str, config: dict) -> tuple[dict, dict]:
    """Run full agent analysis on an event. Returns (decision_dict, reports_dict)."""
    graph = TradingAgentsGraph(
        selected_analysts=["odds", "social", "news", "event"],
        config=config,
        debug=False,
    )

    final_state, decision_json = graph.propagate(event_id, event_question, time.strftime("%Y-%m-%d"))

    # Parse decision
    try:
        decision = json.loads(decision_json)
    except (json.JSONDecodeError, TypeError):
        decision = {
            "action": "SKIP",
            "confidence": 0,
            "edge": 0,
            "position_size": 0,
            "reasoning": str(decision_json),
            "time_horizon": "unknown",
        }

    reports = {
        "odds_report": final_state.get("odds_report", ""),
        "news_report": final_state.get("news_report", ""),
        "event_report": final_state.get("event_report", ""),
        "sentiment_report": final_state.get("sentiment_report", ""),
        "investment_plan": final_state.get("investment_plan", ""),
        "trader_plan": final_state.get("trader_plan", ""),
        "final_decision": final_state.get("final_decision", ""),
    }

    return decision, reports


def _parse_scan_results(raw_text: str, max_events: int) -> list[dict]:
    """Parse search_markets output text into event list."""
    events = []
    lines = raw_text.split("\n")

    current_event = None
    for line in lines:
        line = line.strip()
        if line.startswith("## ") and "." in line[:6]:
            # New event header like "## 1. Event Title"
            if current_event:
                events.append(current_event)
            title = line.split(". ", 1)[-1] if ". " in line else line[3:]
            current_event = {"title": title, "event_id": "", "slug": ""}
        elif current_event:
            if "**Event ID**:" in line:
                current_event["event_id"] = line.split("**Event ID**:")[-1].strip()
            elif "**Market ID**:" in line:
                if not current_event["event_id"]:
                    current_event["event_id"] = line.split("**Market ID**:")[-1].strip()

    if current_event:
        events.append(current_event)

    # Filter out events without IDs and limit
    events = [e for e in events if e["event_id"]]
    return events[:max_events]
