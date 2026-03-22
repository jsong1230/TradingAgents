"""PolyAgent — Streamlit Web UI for Polymarket Prediction Analysis."""
import os
import sys
import json
import time

import streamlit as st
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

st.set_page_config(
    page_title="PolyAgent",
    page_icon="🔮",
    layout="wide",
)

# ── Authentication ──────────────────────────────────────────────────────────

def check_auth():
    """Simple session-based authentication."""
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<h1 style='text-align:center;margin-top:15vh'>🔮 PolyAgent</h1>"
        "<p style='text-align:center;color:#888'>Polymarket Prediction Analyzer</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            expected_user = os.getenv("WEB_USERNAME", "admin")
            expected_pass = os.getenv("WEB_PASSWORD", "admin")
            if username == expected_user and password == expected_pass:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid credentials")

    return False


# ── Agent definitions ───────────────────────────────────────────────────────

ANALYST_ORDER = ["odds", "social", "news", "event"]
ANALYST_NAMES = {
    "odds": "Odds Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "event": "Event Analyst",
}
ANALYST_REPORT_MAP = {
    "odds": "odds_report",
    "social": "sentiment_report",
    "news": "news_report",
    "event": "event_report",
}

ALL_AGENTS = [
    "Odds Analyst", "Social Analyst", "News Analyst", "Event Analyst",
    "YES Advocate", "NO Advocate", "Timing Advocate", "Research Manager",
    "Trader",
    "Aggressive Analyst", "Conservative Analyst", "Neutral Analyst",
    "Risk Manager",
]


# ── Analysis runner ─────────────────────────────────────────────────────────

def run_analysis(event_id, event_question, config, selected_analysts, progress_placeholder, report_placeholders, decision_placeholder):
    """Run the full analysis pipeline with progress updates."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    graph = TradingAgentsGraph(
        selected_analysts=selected_analysts,
        config=config,
        debug=False,
    )

    init_state = graph.propagator.create_initial_state(event_id, event_question, time.strftime("%Y-%m-%d"))
    args = graph.propagator.get_graph_args()

    # Track agent status
    agent_status = {a: "⬜" for a in ALL_AGENTS}
    reports = {}
    trace = []
    total_agents = len(ALL_AGENTS)
    completed_count = 0

    def update_progress():
        nonlocal completed_count
        completed_count = sum(1 for v in agent_status.values() if v == "✅")
        pct = completed_count / total_agents
        status_line = "  ".join(f"{v} {k}" for k, v in agent_status.items() if v != "⬜" or k in [ANALYST_NAMES.get(a, a) for a in selected_analysts])
        progress_placeholder.progress(pct, text=status_line)

    def update_report(key, content):
        reports[key] = content
        if key in report_placeholders and content:
            with report_placeholders[key]:
                st.markdown(content[:3000])

    # Set first analyst active
    first_analyst = ANALYST_NAMES.get(selected_analysts[0], "Odds Analyst")
    agent_status[first_analyst] = "🔄"
    update_progress()

    for chunk in graph.graph.stream(init_state, **args):
        trace.append(chunk)

        # Analyst reports
        for analyst_key in ANALYST_ORDER:
            if analyst_key not in selected_analysts:
                continue
            report_key = ANALYST_REPORT_MAP[analyst_key]
            agent_name = ANALYST_NAMES[analyst_key]
            if chunk.get(report_key):
                agent_status[agent_name] = "✅"
                update_report(report_key, chunk[report_key])
                # Activate next pending analyst
                for next_key in ANALYST_ORDER:
                    if next_key in selected_analysts:
                        next_name = ANALYST_NAMES[next_key]
                        if agent_status[next_name] == "⬜":
                            agent_status[next_name] = "🔄"
                            break
                update_progress()

        # Research debate
        if chunk.get("investment_debate_state"):
            ds = chunk["investment_debate_state"]
            if ds.get("yes_history", "").strip() or ds.get("no_history", "").strip():
                for adv in ["YES Advocate", "NO Advocate", "Timing Advocate"]:
                    if agent_status[adv] == "⬜":
                        agent_status[adv] = "🔄"
                update_progress()
            if ds.get("yes_history", "").strip():
                update_report("yes_advocate", ds["yes_history"])
            if ds.get("no_history", "").strip():
                update_report("no_advocate", ds["no_history"])
            if ds.get("timing_history", "").strip():
                update_report("timing_advocate", ds["timing_history"])
            if ds.get("judge_decision", "").strip():
                for adv in ["YES Advocate", "NO Advocate", "Timing Advocate", "Research Manager"]:
                    agent_status[adv] = "✅"
                update_report("investment_plan", ds["judge_decision"])
                agent_status["Trader"] = "🔄"
                update_progress()

        # Trader
        if chunk.get("trader_plan"):
            agent_status["Trader"] = "✅"
            update_report("trader_plan", chunk["trader_plan"])
            agent_status["Aggressive Analyst"] = "🔄"
            update_progress()

        # Risk debate
        if chunk.get("risk_debate_state"):
            rs = chunk["risk_debate_state"]
            if rs.get("aggressive_history", "").strip():
                agent_status["Aggressive Analyst"] = "🔄"
            if rs.get("conservative_history", "").strip():
                agent_status["Conservative Analyst"] = "🔄"
            if rs.get("neutral_history", "").strip():
                agent_status["Neutral Analyst"] = "🔄"
            if rs.get("judge_decision", "").strip():
                for a in ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Risk Manager"]:
                    agent_status[a] = "✅"
                update_report("final_decision", rs["judge_decision"])
                update_progress()

    # Final
    final_state = trace[-1] if trace else {}
    for a in agent_status:
        agent_status[a] = "✅"
    update_progress()

    # Process signal
    decision_json = graph.process_signal(final_state.get("final_decision", ""))

    # Display final decision
    try:
        dec = json.loads(decision_json)
    except (json.JSONDecodeError, TypeError):
        dec = {"action": "SKIP", "confidence": 0, "edge": 0, "position_size": 0, "reasoning": str(decision_json), "time_horizon": "unknown"}

    color = {"YES": "#22c55e", "NO": "#ef4444", "SKIP": "#6b7280"}.get(dec.get("action", "SKIP"), "#6b7280")

    with decision_placeholder:
        st.markdown(f"""
        <div style="border:2px solid {color};border-radius:12px;padding:20px;margin:10px 0;background:{color}15">
            <h2 style="color:{color};margin:0">🎯 {dec.get('action', 'SKIP')}</h2>
            <div style="display:flex;gap:24px;margin:12px 0;font-size:18px">
                <span><b>Confidence:</b> {dec.get('confidence', 0):.0%}</span>
                <span><b>Edge:</b> {dec.get('edge', 0):.1%}</span>
                <span><b>Position:</b> {dec.get('position_size', 0):.1%}</span>
                <span><b>Horizon:</b> {dec.get('time_horizon', 'N/A')}</span>
            </div>
            <p style="color:#ccc;margin:0">{dec.get('reasoning', '')}</p>
        </div>
        """, unsafe_allow_html=True)

    return final_state, dec


# ── Main UI ─────────────────────────────────────────────────────────────────

def main():
    if not check_auth():
        return

    # Header
    st.markdown("# 🔮 PolyAgent")
    st.caption("Polymarket Prediction Market Analyzer")

    # Sidebar: LLM settings
    with st.sidebar:
        st.header("⚙️ Settings")
        provider = st.selectbox("LLM Provider", ["openrouter", "openai", "anthropic", "google"], index=0)
        quick_model = st.text_input("Quick Model", value="nvidia/nemotron-3-nano-30b-a3b:free")
        deep_model = st.text_input("Deep Model", value="z-ai/glm-4.5-air:free")
        debate_rounds = st.slider("Debate Rounds", 1, 5, 1)
        selected_analysts = st.multiselect(
            "Analysts",
            options=ANALYST_ORDER,
            default=ANALYST_ORDER,
            format_func=lambda x: ANALYST_NAMES.get(x, x),
        )
        if not selected_analysts:
            selected_analysts = ANALYST_ORDER

        st.divider()
        if st.button("🚪 Logout"):
            st.session_state["authenticated"] = False
            st.rerun()

    # Input bar
    col_mode, col_input, col_btn = st.columns([1, 4, 1])
    with col_mode:
        mode = st.selectbox("Mode", ["Manual", "Scan"], label_visibility="collapsed")
    with col_input:
        event_input = st.text_input("Event", placeholder="Event ID, slug, or URL...", label_visibility="collapsed")
    with col_btn:
        analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")

    # Scan mode
    if mode == "Scan":
        if st.button("📡 Scan Active Markets"):
            with st.spinner("Searching markets..."):
                from tradingagents.agents.utils.polymarket_tools import search_markets
                results = search_markets.invoke({"min_volume": 10000, "limit": 15})
            st.markdown(results)
            st.info("Copy an event ID from above and paste it in the input field, then click Analyze.")

    # Analysis
    if analyze_btn and event_input.strip():
        event_id = event_input.strip()
        # Parse URL
        if "polymarket.com" in event_id:
            event_id = event_id.rstrip("/").split("/")[-1]

        # Try to get event question from API
        event_question = event_id
        try:
            from tradingagents.agents.utils.polymarket_tools import _resolve_event
            evt = _resolve_event(event_id)
            event_question = evt.get("title", evt.get("question", event_id))
            st.info(f"📋 **{event_question}**")
        except Exception:
            st.warning(f"Could not resolve event title. Using ID: {event_id}")

        # Build config
        from tradingagents.default_config import DEFAULT_CONFIG
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = provider
        config["quick_think_llm"] = quick_model
        config["deep_think_llm"] = deep_model
        config["max_debate_rounds"] = debate_rounds
        config["max_risk_discuss_rounds"] = debate_rounds

        provider_urls = {
            "openrouter": "https://openrouter.ai/api/v1",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/",
            "google": "https://generativelanguage.googleapis.com/v1",
        }
        config["backend_url"] = provider_urls.get(provider, config["backend_url"])

        # Progress
        st.divider()
        progress_placeholder = st.empty()
        progress_placeholder.progress(0, text="Starting analysis...")

        # Decision placeholder
        decision_placeholder = st.empty()

        # Report cards
        st.divider()
        st.subheader("📊 Analyst Reports")
        c1, c2 = st.columns(2)
        report_placeholders = {}
        with c1:
            with st.expander("📈 Odds Report", expanded=True):
                report_placeholders["odds_report"] = st.empty()
            with st.expander("📰 News Report", expanded=True):
                report_placeholders["news_report"] = st.empty()
        with c2:
            with st.expander("💬 Sentiment Report", expanded=True):
                report_placeholders["sentiment_report"] = st.empty()
            with st.expander("📋 Event Report", expanded=True):
                report_placeholders["event_report"] = st.empty()

        st.subheader("🤝 Research & Trading")
        c3, c4, c5 = st.columns(3)
        with c3:
            with st.expander("🔬 Research Plan"):
                report_placeholders["investment_plan"] = st.empty()
        with c4:
            with st.expander("💰 Trader Plan"):
                report_placeholders["trader_plan"] = st.empty()
        with c5:
            with st.expander("⚖️ Risk Decision"):
                report_placeholders["final_decision"] = st.empty()

        st.subheader("🗣️ Debate")
        c6, c7, c8 = st.columns(3)
        with c6:
            with st.expander("✅ YES Advocate"):
                report_placeholders["yes_advocate"] = st.empty()
        with c7:
            with st.expander("❌ NO Advocate"):
                report_placeholders["no_advocate"] = st.empty()
        with c8:
            with st.expander("⏰ Timing Advocate"):
                report_placeholders["timing_advocate"] = st.empty()

        # Run
        try:
            final_state, decision = run_analysis(
                event_id, event_question, config, selected_analysts,
                progress_placeholder, report_placeholders, decision_placeholder,
            )
            st.balloons()
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            import traceback
            st.code(traceback.format_exc())

    elif analyze_btn:
        st.warning("Please enter an event ID or URL.")


if __name__ == "__main__":
    main()
