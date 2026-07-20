"""East Money (dongcaifuwang) data provider for A-share stocks."""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# East Money API base URLs
_EM_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_EM_DATA_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_FUND_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxAction"
_EM_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
})


def _convert_symbol(code: str) -> str:
    """Convert ticker to East Money secid format.

    000630.SZ -> 0.000630
    600519.SH -> 1.600519
    """
    if "." in code:
        num, exchange = code.split(".", 1)
        prefix = "1" if exchange.upper() == "SH" else "0"
        return f"{prefix}.{num}"
    return code


def _convert_symbol_em(code: str) -> str:
    """Convert ticker to EM code format for financial APIs.

    000630.SZ -> SZ000630
    600519.SH -> SH600519
    """
    if "." in code:
        num, exchange = code.split(".", 1)
        return f"{exchange.upper()}{num}"
    return code


def _format_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD."""
    return date_str.replace("-", "")


def get_stock(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get historical OHLCV data from East Money."""
    secid = _convert_symbol(symbol)
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",  # daily
        "fqt": "1",    # forward-adjusted
        "beg": _format_date(start_date),
        "end": _format_date(end_date),
    }
    try:
        resp = _SESSION.get(_EM_KLINE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        stock_data = data.get("data") or {}
        klines = stock_data.get("klines") or []
        name = stock_data.get("name", symbol)

        if not klines:
            return f"No data found for {symbol} from {start_date} to {end_date}."

        lines = [f"# Stock data for {name} ({symbol})"]
        lines.append(f"# From {start_date} to {end_date}, {len(klines)} records")
        lines.append("Date,Open,High,Low,Close,Volume")
        for kline in klines:
            # kline format: date,open,close,high,low,vol,amount,...
            parts = kline.split(",")
            lines.append(f"{parts[0]},{parts[1]},{parts[3]},{parts[4]},{parts[2]},{parts[5]}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to get stock data for %s: %s", symbol, e)
        return f"Error retrieving stock data for {symbol}: {e}"



# Technical indicator descriptions for LLM context
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


def get_indicators(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    """Get technical indicator values using stockstats."""
    try:
        import pandas as pd
        from stockstats import StockDataFrame
    except ImportError:
        return "Error: stockstats and pandas are required for indicators."

    try:
        end = datetime.strptime(curr_date, "%Y-%m-%d")
        # Need extra data for indicator warm-up
        start = end - timedelta(days=look_back_days + 300)
        raw = get_stock(symbol, start.strftime("%Y-%m-%d"), curr_date)

        if raw.startswith("Error") or raw.startswith("No data"):
            return raw

        # Parse CSV into DataFrame
        lines = [l for l in raw.split("\n") if l and not l.startswith("#")]
        if len(lines) < 2:
            return f"Insufficient data for {symbol}."

        import io
        df = pd.read_csv(io.StringIO("\n".join(lines)))
        df = df.rename(columns={"Date": "date", "Open": "open", "High": "high",
                                "Low": "low", "Close": "close", "Volume": "volume"})
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")

        stock = StockDataFrame.retype(df)

        # Map indicator names to stockstats column accessors
        indicator_map = {
            "close_50_sma": "close_50_sma",
            "close_200_sma": "close_200_sma",
            "close_10_ema": "close_10_ema",
            "macd": "macd",
            "macds": "macds",
            "macdh": "macdh",
            "rsi": "rsi_14",
            "boll": "boll",
            "boll_ub": "boll_ub",
            "boll_lb": "boll_lb",
            "atr": "atr_14",
            "vwma": "vwma",
            "mfi": "mfi_14",
            "kdjk": "kdjk",
            "kdjd": "kdjd",
            "kdjj": "kdjj",
        }

        col = indicator_map.get(indicator)
        if col is None:
            return f"Unknown indicator: {indicator}. Supported: {list(indicator_map.keys())}"

        values = stock[col]
        cutoff = end - timedelta(days=look_back_days)
        window = values[values.index >= cutoff].dropna()

        desc = _INDICATOR_DESCRIPTIONS.get(indicator, indicator)
        lines_out = [f"## {indicator} values from {cutoff.strftime('%Y-%m-%d')} to {curr_date}:"]
        for date, val in window.items():
            lines_out.append(f"{date.strftime('%Y-%m-%d')}: {val:.4f}")
        lines_out.append(f"\nDescription: {desc}")

        return "\n".join(lines_out)
    except Exception as e:
        logger.error("Failed to get indicators for %s: %s", symbol, e)
        return f"Error computing {indicator} for {symbol}: {e}"



def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamental overview from East Money."""
    try:
        # Get latest income statement for revenue/profit
        stock_code = ticker.split('.')[0]
        inc_params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "1",
            "pageNumber": "1",
            "reportName": "RPT_DMSK_FN_INCOME",
            "columns": "SECURITY_NAME_ABBR,REPORT_DATE,TOTAL_OPERATE_INCOME,OPERATE_PROFIT,TOTAL_PROFIT,PARENT_NETPROFIT",
            "filter": f'(SECURITY_CODE="{stock_code}")',
        }
        inc_resp = _SESSION.get(_EM_DATA_URL, params=inc_params, timeout=15)
        inc_data = inc_resp.json().get("result", {}).get("data", [{}])[0] if inc_resp.json().get("result") else {}

        # Get latest balance sheet for assets/liabilities
        bs_params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "1",
            "pageNumber": "1",
            "reportName": "RPT_DMSK_FN_BALANCE",
            "columns": "SECURITY_NAME_ABBR,REPORT_DATE,TOTAL_ASSETS,TOTAL_LIABILITIES,TOTAL_EQUITY,MONETARYFUNDS",
            "filter": f'(SECURITY_CODE="{ticker.split(".")[0]}")',
        }
        bs_resp = _SESSION.get(_EM_DATA_URL, params=bs_params, timeout=15)
        bs_data = bs_resp.json().get("result", {}).get("data", [{}])[0] if bs_resp.json().get("result") else {}

        name = inc_data.get("SECURITY_NAME_ABBR", ticker)
        lines = [
            f"# Company Fundamentals for {name} ({ticker})",
            "# Data source: East Money",
            "",
            f"Name: {name}",
            f"Code: {ticker}",
            f"Report Date: {inc_data.get('REPORT_DATE', 'N/A')}",
            "",
            "## Financial Highlights",
            f"Total Revenue: {inc_data.get('TOTAL_OPERATE_INCOME', 'N/A')}",
            f"Operating Profit: {inc_data.get('OPERATE_PROFIT', 'N/A')}",
            f"Net Profit: {inc_data.get('PARENT_NETPROFIT', 'N/A')}",
            "",
            "## Balance Sheet",
            f"Total Assets: {bs_data.get('TOTAL_ASSETS', 'N/A')}",
            f"Total Liabilities: {bs_data.get('TOTAL_LIABILITIES', 'N/A')}",
            f"Total Equity: {bs_data.get('TOTAL_EQUITY', 'N/A')}",
            f"Cash: {bs_data.get('MONETARYFUNDS', 'N/A')}",
        ]
        return chr(10).join(lines)
    except Exception as e:
        logger.error("Failed to get fundamentals for %s: %s", ticker, e)
        return f"Error retrieving fundamentals for {ticker}: {e}"


def _get_financial_table(ticker: str, report_name: str, columns: str,
                         freq: str = "quarterly", curr_date: str = None) -> str:
    """Fetch financial statement with core columns only."""
    try:
        report_type_map = {
            "balance": "RPT_DMSK_FN_BALANCE",
            "cashflow": "RPT_DMSK_FN_CASHFLOW",
            "income": "RPT_DMSK_FN_INCOME",
        }
        rn = report_type_map.get(report_name, report_name)

        # Core columns per report type (reduces token usage)
        core_columns_map = {
            "income": "REPORT_DATE,TOTAL_OPERATE_INCOME,TOTAL_OPERATE_COST,OPERATE_PROFIT,TOTAL_PROFIT,PARENT_NETPROFIT,DEDUCT_PARENT_NETPROFIT,INCOME_TAX",
            "balance": "REPORT_DATE,TOTAL_ASSETS,TOTAL_LIABILITIES,TOTAL_EQUITY,MONETARYFUNDS,ACCOUNTS_RECE,INVENTORY,FIXED_ASSET,ACCOUNTS_PAYABLE,DEBT_ASSET_RATIO",
            "cashflow": "REPORT_DATE,NETCASH_OPERATE,NETCASH_INVEST,NETCASH_FINANCE,CCE_ADD,SALES_SERVICES,PAY_STAFF_CASH",
        }
        cols = core_columns_map.get(report_name, "ALL")

        stock_code = ticker.split(".")[0]
        date_filter = f'(SECURITY_CODE="{stock_code}")'
        if curr_date:
            date_filter += f' AND (REPORT_DATE="{curr_date[:7]}")'

        params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "4" if freq == "quarterly" else "1",
            "pageNumber": "1",
            "reportName": rn,
            "columns": cols,
            "filter": date_filter,
        }
        resp = _SESSION.get(_EM_DATA_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result = data.get("result") or {}
        if not data.get("success"):
            return f"No {report_name} data found for {ticker}."
        rows = result.get("data") or []
        if not rows:
            return f"No {report_name} data found for {ticker}."

        keys = [k for k in rows[0].keys() if not k.startswith("_")]
        lines = [",".join(keys)]
        for row in rows:
            vals = [str(row.get(k, "")) for k in keys]
            lines.append(",".join(vals))
        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to get %s for %s: %s", report_name, ticker, e)
        return f"Error retrieving {report_name} for {ticker}: {e}"


def get_balance_sheet(ticker: str, freq: str = "quarterly",
                      curr_date: str = None) -> str:
    """Get balance sheet from East Money."""
    return _get_financial_table(ticker, "balance", "ALL", freq, curr_date)


def get_cashflow(ticker: str, freq: str = "quarterly",
                 curr_date: str = None) -> str:
    """Get cash flow statement from East Money."""
    return _get_financial_table(ticker, "cashflow", "ALL", freq, curr_date)


def get_income_statement(ticker: str, freq: str = "quarterly",
                         curr_date: str = None) -> str:
    """Get income statement from East Money."""
    return _get_financial_table(ticker, "income", "ALL", freq, curr_date)



def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """Get company-specific news via Sina Finance API (eastmoney module fallback)."""
    stock_code = ticker.split(".")[0]
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get"
        params = {
            "pageid": "153",
            "lid": "2516",
            "k": stock_code,
            "num": "15",
            "page": "1",
        }
        resp = _SESSION.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("result", {}).get("data", []) if data.get("result") else []
        if not items:
            return f"No news found for {ticker}."

        lines = [f"# News for {ticker}", ""]
        for item in items[:15]:
            title = item.get("title", "N/A")
            date = item.get("ctime", "")
            url = item.get("url", "")
            lines.append(f"- {title} ({date})")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to get news for %s: %s", ticker, e)
        return f"Error retrieving news for {ticker}: {e}"


def get_global_news(curr_date: str, look_back_days: int = None, limit: int = None) -> str:
    """Get macro/global news via Sina Finance API (eastmoney module fallback)."""
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get"
        params = {
            "pageid": "153",
            "lid": "2516",
            "k": "A股 宏观经济",
            "num": "15",
            "page": "1",
        }
        resp = _SESSION.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("result", {}).get("data", []) if data.get("result") else []
        if not items:
            return "No global news found."

        lines = ["# Global/Macro News", ""]
        for item in items[:15]:
            title = item.get("title", "N/A")
            date = item.get("ctime", "")
            lines.append(f"- {title} ({date})")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to get global news: %s", e)
        return f"Error retrieving global news: {e}"


def get_insider_transactions(ticker: str) -> str:
    """Get insider transactions from East Money."""
    stock_code = ticker.split(".")[0]
    try:
        params = {
            "sortColumns": "CHANGE_DATE",
            "sortTypes": "-1",
            "pageSize": "20",
            "pageNumber": "1",
            "reportName": "RPT_SHARECHANGE",
            "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_DATE,CHANGE_TYPE,CHANGE_NAME,CHANGE_NUM,HOLD_NUM_AFTER,AVG_PRICE",
            "filter": f'(SECURITY_CODE="{stock_code}")',
        }
        resp = _SESSION.get(_EM_DATA_URL, params=params, timeout=15)
        data = resp.json()
        rows = data.get("result", {}).get("data", []) if data.get("result") else []
        if not rows:
            return f"No insider transactions found for {ticker}."

        lines = [f"# Insider Transactions for {ticker}", ""]
        lines.append("Date,Person,Type,Shares,AvgPrice")
        for r in rows:
            date = str(r.get("CHANGE_DATE", ""))[:10]
            name = r.get("CHANGE_NAME", "")
            ctype = r.get("CHANGE_TYPE", "")
            num = r.get("CHANGE_NUM", "")
            price = r.get("AVG_PRICE", "")
            lines.append(f"{date},{name},{ctype},{num},{price}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Failed to get insider transactions for %s: %s", ticker, e)
        return f"Error retrieving insider transactions for {ticker}: {e}"
