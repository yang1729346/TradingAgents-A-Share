# TradingAgents（A股增强版）

基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 多智能体金融交易框架的二次开发版本，针对 **A股（中国股市）** 进行了深度优化。

## 原项目简介

原项目 TradingAgents 是一个 LLM 多智能体交易框架，模拟真实交易团队的协作流程：

- **分析师团队**：技术分析师、情绪分析师、新闻分析师、基本面分析师
- **研究员团队**：多头研究员 vs 空头研究员进行辩论
- **交易员**：综合分析结果制定交易计划
- **风控团队**：激进派、保守派、中立派进行风险辩论
- **投资组合经理**：做出最终买卖决策

> 原项目论文：[TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)

## 本版本的主要修改

### 1. 新增东方财富数据源（核心改动）

| 项目 | 原项目 | 本版本 |
|------|--------|--------|
| 默认数据源 | yfinance（Yahoo Finance） | **东方财富（Eastmoney）** |
| A股数据 | 不支持 | **原生支持**（沪深京三市） |
| 数据接口 | 需翻墙，经常被限速 | **国内直连，稳定快速** |

新增文件：`tradingagents/dataflows/eastmoney.py`（约410行）

支持的功能：
- 股票K线数据（日线/周线/月线）
- 技术指标计算（MACD、RSI、布林带等）
- 财务报表（资产负债表、利润表、现金流量表）
- 公司基本面数据
- 个股新闻和全球财经新闻
- 股票代码自动转换（000630.SZ → 东方财富格式）

### 2. 新增小米 MIMO 大模型支持

| 项目 | 说明 |
|------|------|
| 快速模型 | MiMo-v2.5 |
| 深度模型 | MiMo-v2.5-Pro |
| API地址 | `https://token-plan-cn.xiaomimimo.com/v1` |

修改文件：`model_catalog.py`、`openai_client.py`、`api_key_env.py`、`factory.py`

### 3. XML 工具调用解析（提升兼容性）

部分国产大模型返回工具调用时使用XML格式而非标准JSON，原项目无法解析。本版本在 `base_client.py` 中增加了正则表达式解析，自动识别并转换XML格式的工具调用，兼容更多模型。

### 4. 工具调用轮次限制（防止死循环）

在三个分析师节点中增加了 `MAX_TOOL_ROUNDS = 3` 限制：
- `market_analyst.py`
- `news_analyst.py`
- `fundamentals_analyst.py`

当LLM连续3轮都发起工具调用时，强制停止绑定工具，促使其输出分析报告，防止无限循环。

### 5. 请求重试与限速保护

`openai_client.py` 中新增：
- 指数退避重试（最多5次，初始延迟2秒，退避因子2倍）
- 调用间隔1秒限速（避免API限流）
- 连接错误自动识别与重试
- 非OpenAI供应商默认 `max_retries=5`、`timeout=180`

### 6. 数据源容错改进

`interface.py` 中改进了 `route_to_vendor()` 函数：
- 捕获所有异常（原项目只捕获特定异常）
- 检查返回结果是否为空或错误
- 返回错误提示字符串而非直接崩溃
- 记录警告日志便于排查

### 7. 其他修改

- `.gitignore`：增加 `reports/`、`y/` 目录排除
- 默认配置：数据源切换为东方财富，支持中文输出

## 对A股分析的优势

| 优势 | 说明 |
|------|------|
| **数据直连** | 东方财富API国内直连，无需翻墙，无速率限制 |
| **A股原生支持** | 直接输入沪深京股票代码（如 `000630`、`600519`）即可分析 |
| **中文输出** | 支持中文分析报告，更符合国内用户习惯 |
| **国产模型适配** | MIMO等国产模型的XML工具调用格式已兼容 |
| **运行稳定** | 重试机制+限速保护+容错处理，长时间运行不易崩溃 |

## 安装与使用

```bash
# 克隆本仓库
git clone https://github.com/你的用户名/TradingAgents.git
cd TradingAgents

# 创建虚拟环境
conda create -n tradingagents python=3.13
conda activate tradingagents

# 安装依赖
pip install .

# 配置环境变量（复制 .env.example 为 .env，填入API密钥）
cp .env.example .env
```

Python 使用示例：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("600519", "2026-01-15")  # 贵州茅台
print(decision)
```

CLI 使用：

```bash
tradingagents
# 或
python -m cli.main
```

## 致谢

本项目基于 **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** 进行二次开发。感谢原作者 Yijia Xiao、Edward Sun、Di Luo、Wei Wang 的杰出工作。

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework},
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138},
}
```

## 免责声明

本项目仅用于学习和研究目的，不构成任何投资建议。股市有风险，投资需谨慎。
