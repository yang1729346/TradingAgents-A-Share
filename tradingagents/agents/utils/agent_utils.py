from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def is_a_share(ticker: str) -> bool:
    """Return True if the ticker is a Chinese A-share stock."""
    upper = ticker.upper()
    return upper.endswith(".SZ") or upper.endswith(".SH")


_A_SHARE_MARKET_RULES = (
    "\n\n## A-share market rules (critical for analysis accuracy)\n"
    "- T+1 trading: shares bought today cannot be sold until the next trading day.\n"
    "- Price limits: main board ±10%, ChiNext/STAR ±20%, ST stocks ±5%. "
    "A stock hitting the limit signals extreme sentiment, not just a large move.\n"
    "- Trading hours: 09:30-11:30, 13:00-15:00 (CST). Call auction 09:15-09:25.\n"
    "- No short selling for most retail investors; margin trading is restricted.\n"
    "- Financial reports: annual (April 30 deadline), semi-annual (Aug 31), "
    "quarterly (Q1 by Apr 30, Q3 by Oct 31).\n"
    "- Key sentiment drivers: Northbound capital flow (via Stock Connect), "
    "PBOC policy (RRR cuts, MLF, LPR), CSRC regulatory announcements, "
    "state media commentary (People's Daily, Xinhua).\n"
    "- Technical indicator caveats: RSI and Bollinger Bands can stay at extremes "
    "longer due to price limits; volume spikes at limit-up/limit-down are "
    "meaningful signals.\n"
)


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    base = (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `.SZ`, `.SH`)."
    )
    if is_a_share(ticker):
        base += _A_SHARE_MARKET_RULES
    return base

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
