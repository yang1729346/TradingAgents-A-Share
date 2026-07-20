"""今日投资 (investoday.net) MCP data provider for A-share stocks."""
import json
import logging
import os
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

_MCP_URL = "https://data-api.investoday.net/data/mcp/preset"


def _get_api_key() -> str:
    key = os.environ.get("INVESTODAY_API_KEY", "")
    if not key:
        raise ValueError("INVESTODAY_API_KEY environment variable not set")
    return key


def _mcp_call(tool_name: str, arguments: dict, session_id: str = None) -> dict:
    """Call an MCP tool and return the parsed JSON result."""
    api_key = _get_api_key()
    url = f"{_MCP_URL}?apiKey={api_key}"
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {"name": tool_name, "arguments": arguments},
    }

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        raise RuntimeError(result["error"].get("message", str(result["error"])))

    content = result.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            return json.loads(item["text"])
    return {}


def _init_session() -> str:
    """Initialize MCP session and return session ID."""
    api_key = _get_api_key()
    url = f"{_MCP_URL}?apiKey={api_key}"
    body = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 0,
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tradingagents", "version": "1.0"},
        },
    }
    resp = requests.post(url, json=body, timeout=15)
    resp.raise_for_status()
    return resp.headers.get("Mcp-Session-Id", "")


def _convert_symbol(symbol: str) -> str:
    """Convert 600519.SH -> 600519."""
    if "." in symbol:
        return symbol.split(".")[0]
    return symbol


def get_stock(symbol: str, start_date: str, end_date: str) -> str:
    """Get historical OHLCV data from investoday."""
    try:
        stock_code = _convert_symbol(symbol)
        data = _mcp_call("list_stock_adjusted_quotes", {
            "stockCode": stock_code,
            "beginDate": start_date,
            "endDate": end_date,
            "pageSize": 500,
            "pageNum": 1,
        })

        rows = data.get("data") or []
        if not rows:
            return f"No data found for {symbol} from {start_date} to {end_date}."

        rows.sort(key=lambda r: r.get("tradeDate", ""))
        lines = [
            f"# Stock data for {rows[0].get('stockName', symbol)} ({symbol})",
            f"# From {start_date} to {end_date}, {len(rows)} records",
            "Date,Open,High,Low,Close,Volume",
        ]
        for r in rows:
            date_str = r.get("tradeDate", "")[:10]
            lines.append(
                f"{date_str},{r.get('openPrice')},{r.get('highPrice')},"
                f"{r.get('lowPrice')},{r.get('closePrice')},{r.get('volume')}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error("investoday get_stock failed for %s: %s", symbol, e)
        return f"Error retrieving stock data for {symbol}: {e}"


_INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50-day Simple Moving Average - medium-term trend",
    "close_200_sma": "200-day Simple Moving Average - long-term trend",
    "close_10_ema": "10-day Exponential Moving Average - short-term momentum",
    "macd": "MACD line - trend momentum",
    "macds": "MACD Signal line - trigger for crossovers",
    "macdh": "MACD Histogram - momentum strength divergence",
    "rsi": "Relative Strength Index - overbought/oversold (30/70)",
    "boll": "Bollinger Middle Band (20 SMA)",
    "boll_ub": "Bollinger Upper Band (+2 std dev)",
    "boll_lb": "Bollinger Lower Band (-2 std dev)",
    "atr": "Average True Range - volatility measure",
    "vwma": "Volume Weighted Moving Average",
    "mfi": "Money Flow Index - volume-weighted RSI",
    "kdjk": "KDJ K line - stochastic momentum (common in A-share analysis)",
    "kdjd": "KDJ D line - smoothed K value, overbought >80 / oversold <20",
    "kdjj": "KDJ J line - divergence signal (J=3K-2D), extreme values flag reversals",
}


def get_indicators(symbol: str, indicator: str, curr_date: str, look_back_days: int) -> str:
    """Get technical indicator values using stockstats on investoday data."""
    try:
        import pandas as pd
        from stockstats import StockDataFrame
    except ImportError:
        return "Error: stockstats and pandas are required for indicators."

    try:
        end = datetime.strptime(curr_date, "%Y-%m-%d")
        start = end - timedelta(days=look_back_days + 300)
        raw = get_stock(symbol, start.strftime("%Y-%m-%d"), curr_date)

        if raw.startswith("Error") or raw.startswith("No data"):
            return raw

        import io
        lines = [l for l in raw.split("\n") if l and not l.startswith("#")]
        if len(lines) < 2:
            return f"Insufficient data for {symbol}."

        df = pd.read_csv(io.StringIO("\n".join(lines)))
        df = df.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")
        stock = StockDataFrame.retype(df)

        indicator_map = {
            "close_50_sma": "close_50_sma", "close_200_sma": "close_200_sma",
            "close_10_ema": "close_10_ema",
            "macd": "macd", "macds": "macds", "macdh": "macdh",
            "rsi": "rsi_14", "boll": "boll", "boll_ub": "boll_ub",
            "boll_lb": "boll_lb", "atr": "atr_14", "vwma": "vwma", "mfi": "mfi_14",
            "kdjk": "kdjk", "kdjd": "kdjd", "kdjj": "kdjj",
        }
        col = indicator_map.get(indicator)
        if col is None:
            return f"Unknown indicator: {indicator}. Supported: {list(indicator_map.keys())}"

        values = stock[col]
        cutoff = end - timedelta(days=look_back_days)
        window = values[values.index >= cutoff].dropna()

        desc = _INDICATOR_DESCRIPTIONS.get(indicator, indicator)
        out = [f"## {indicator} values from {cutoff.strftime('%Y-%m-%d')} to {curr_date}:"]
        for date, val in window.items():
            out.append(f"{date.strftime('%Y-%m-%d')}: {val:.4f}")
        out.append(f"\nDescription: {desc}")
        return "\n".join(out)
    except Exception as e:
        logger.error("investoday get_indicators failed for %s: %s", symbol, e)
        return f"Error computing {indicator} for {symbol}: {e}"


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamental overview from investoday."""
    try:
        stock_code = _convert_symbol(ticker)
        basic_resp = _mcp_call("get_stock_basic_info", {"stockCode": stock_code})
        quote_resp = _mcp_call("get_stock_quote_realtime", {"stockCode": stock_code})

        basic = {}
        basic_data = basic_resp.get("data", [])
        if basic_data:
            basic = basic_data[0] if isinstance(basic_data, list) else basic_data

        quote = {}
        quote_data = quote_resp.get("data", {})
        if isinstance(quote_data, dict):
            quote = quote_data

        lines = [
            f"# Company Fundamentals for {ticker}",
            "# Data source: Investoday",
            "",
        ]
        if basic:
            lines.append(f"Stock Code: {basic.get('STOCKCODE', stock_code)}")
            lines.append(f"Stock Name: {basic.get('STOCKNAME', ticker)}")
            lines.append(f"Exchange: {basic.get('EXCHANGECODE', 'N/A')}")
            lines.append(f"List Date: {basic.get('LISTDATE', 'N/A')}")
            lines.append(f"Total Shares: {basic.get('SHARESTOTAL', 'N/A')}")
            lines.append(f"Main Business: {basic.get('MAINBUSINESS', 'N/A')}")
            lines.append(f"Report Date: {basic.get('REPORTDATE', 'N/A')}")
        if quote:
            lines.append("")
            lines.append("## Realtime Quote")
            lines.append(f"Price: {quote.get('currentPrice', 'N/A')}")
            lines.append(f"Change%: {quote.get('changeRatio', 'N/A')}")
            lines.append(f"Open: {quote.get('openPrice', 'N/A')}")
            lines.append(f"High: {quote.get('highPrice', 'N/A')}")
            lines.append(f"Low: {quote.get('lowPrice', 'N/A')}")
            lines.append(f"Total Value: {quote.get('totalValue', 'N/A')}")
            lines.append(f"Circulation Value: {quote.get('circulationValue', 'N/A')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("investoday get_fundamentals failed for %s: %s", ticker, e)
        return f"Error retrieving fundamentals for {ticker}: {e}"


def _get_financial_table(ticker: str, tool_name: str, freq: str = "quarterly",
                         curr_date: str = None) -> str:
    """Fetch financial statement from investoday."""
    try:
        stock_code = _convert_symbol(ticker)
        if curr_date:
            year = int(curr_date[:4])
        else:
            year = datetime.now().year
        begin_date = f"{year - 1}-01-01"
        end_date = f"{year}-12-31"

        data = _mcp_call(tool_name, {
            "stockCode": stock_code,
            "beginDate": begin_date,
            "endDate": end_date,
            "pageSize": 4 if freq == "quarterly" else 1,
            "pageNum": 1,
        })

        rows = data.get("data") or []
        if not rows:
            return f"No {tool_name} data found for {ticker}."

        keys = list(rows[0].keys())
        lines = [",".join(keys)]
        for row in rows:
            vals = [str(row.get(k, "")) for k in keys]
            lines.append(",".join(vals))
        return "\n".join(lines)
    except Exception as e:
        logger.error("investoday %s failed for %s: %s", tool_name, ticker, e)
        return f"Error retrieving {tool_name} for {ticker}: {e}"


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _get_financial_table(ticker, "list_stock_balance_sheet", freq, curr_date)


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _get_financial_table(ticker, "list_stock_cash_flows", freq, curr_date)


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _get_financial_table(ticker, "list_stock_income_statements", freq, curr_date)


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Get company news from investoday."""
    try:
        stock_code = _convert_symbol(ticker)
        data = _mcp_call("list_news", {
            "stockCode": stock_code,
            "beginTime": f"{start_date} 00:00:00",
            "endTime": f"{end_date} 23:59:59",
            "newsType": 3,  # 公司新闻
            "pageSize": 20,
            "pageNum": 1,
        })

        items = data.get("data") or []
        if not items:
            return f"No news found for {ticker}."

        lines = [f"# News for {ticker}", ""]
        for item in items[:20]:
            title = item.get("title", "N/A")
            time_str = item.get("publishTime", "")[:10]
            lines.append(f"- {title} ({time_str})")
        return "\n".join(lines)
    except Exception as e:
        logger.error("investoday get_news failed for %s: %s", ticker, e)
        return f"Error retrieving news for {ticker}: {e}"


def get_global_news(curr_date: str, look_back_days: int = None, limit: int = None) -> str:
    """Get macro/global news from investoday."""
    try:
        end = datetime.strptime(curr_date, "%Y-%m-%d") if curr_date else datetime.now()
        start = end - timedelta(days=look_back_days or 7)
        data = _mcp_call("list_news", {
            "beginTime": f"{start.strftime('%Y-%m-%d')} 00:00:00",
            "endTime": f"{end.strftime('%Y-%m-%d')} 23:59:59",
            "newsType": 1,  # 宏观新闻
            "pageSize": limit or 20,
            "pageNum": 1,
        })

        items = data.get("data") or []
        if not items:
            return "No global news found."

        lines = ["# Global/Macro News", ""]
        for item in items[:limit or 20]:
            title = item.get("title", "N/A")
            time_str = item.get("publishTime", "")[:10]
            lines.append(f"- {title} ({time_str})")
        return "\n".join(lines)
    except Exception as e:
        logger.error("investoday get_global_news failed: %s", e)
        return f"Error retrieving global news: {e}"


def get_insider_transactions(ticker: str) -> str:
    """Get insider transactions / special notices from investoday."""
    try:
        stock_code = _convert_symbol(ticker)
        data = _mcp_call("list_stock_special_notices", {
            "stockCode": stock_code,
        })

        items = data.get("data") or []
        if not items:
            return f"No insider transactions found for {ticker}."

        lines = [f"# Insider Transactions for {ticker}", ""]
        lines.append("Date,Title")
        for item in items[:20]:
            title = item.get("title", item.get("noticeTitle", "N/A"))
            date_str = item.get("noticeDate", item.get("publishDate", ""))[:10]
            lines.append(f"{date_str},{title}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("investoday get_insider_transactions failed for %s: %s", ticker, e)
        return f"Error retrieving insider transactions for {ticker}: {e}"
