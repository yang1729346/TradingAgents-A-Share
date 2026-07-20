# TradingAgents - A股增强版

基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 多智能体 LLM 金融交易框架，针对 **A 股市场** 进行了深度适配与工程化改进。

> 原项目论文：[TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)

---

## 系统架构

系统模拟真实投资团队的决策流程，通过 LangGraph StateGraph 编排 5 个阶段的多智能体协作：

```
输入股票代码 + 日期
        │
        ▼
┌─────────────────────────────────┐
│  Phase 1: 分析师团队（并行）       │
│  ├─ 技术分析师（K线、MACD、RSI…）  │
│  ├─ 情绪分析师（新闻、公告…）      │
│  ├─ 新闻分析师（宏观、行业…）      │
│  └─ 基本面分析师（财报、估值…）    │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Phase 2: 研究员辩论              │
│  ├─ 多头研究员（看多论证）         │
│  ├─ 空头研究员（看空论证）         │
│  └─ 研究主管（综合决策）           │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Phase 3: 交易员制定计划           │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Phase 4: 风控团队辩论             │
│  ├─ 激进派                        │
│  ├─ 保守派                        │
│  └─ 中立派                        │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Phase 5: 投资组合经理最终决策     │
└─────────────────────────────────┘
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **框架** | LangGraph (StateGraph)、LangChain |
| **LLM 支持** | OpenAI、DeepSeek、MiMo、GLM、MiniMax、Qwen 等 15+ 供应商 |
| **数据源** | 东方财富（A 股）、Yahoo Finance（美股）、FinnHub |
| **持久化** | SQLite Checkpoint（崩溃恢复） |
| **输出格式** | Pydantic 结构化 Schema + 自由文本 |
| **语言** | Python 3.13 |

---

## 核心技术实现

### 1. 多供应商容错路由

数据获取采用三级供应商解析 + 自动降级机制：

```
tool_vendors（工具指定） → data_vendors_cn（A股专用） → data_vendors（通用）
```

通过 `_is_cn_ticker()` 自动识别 `.SZ`/`.SH` 后缀，路由到国内数据源。当主供应商异常时，自动切换到备选供应商，返回错误信息而非崩溃。

### 2. XML 工具调用解析

部分国产大模型（MiMo、GLM）返回工具调用时使用 XML 格式而非标准 JSON。系统通过正则表达式自动识别并转换：

```python
_FUNC_CALL_RE = re.compile(r'<function_call>(.*?)</function_call>', re.DOTALL)
_PARAM_RE     = re.compile(r'<(\w+)>(.*?)</\1>', re.DOTALL)
```

在 `normalize_content()` 中检测 `response.tool_calls` 为空时，自动从 `content` 中提取 XML 格式的函数调用并转换为标准 ToolCall 对象。

### 3. 双模型架构

| 模型类型 | 用途 | 默认配置 |
|----------|------|----------|
| `deep_think_llm` | 研究主管、投资组合经理（决策节点） | gpt-5.4 |
| `quick_think_llm` | 分析师、研究员、交易员（执行节点） | gpt-5.4-mini |

决策节点使用更强的模型进行综合判断，执行节点使用更快的模型完成具体分析任务。

### 4. 工具调用轮次限制

分析师节点设置 `MAX_TOOL_ROUNDS = 2`，通过 `_count_tool_rounds()` 统计工具调用消息数量。达到上限后自动解绑工具，强制 LLM 输出分析结论，防止无限循环。

### 5. 请求重试与限速保护

- 指数退避重试：2s → 4s → 8s → 16s → 32s，最多 5 次
- 仅对连接错误重试，业务错误直接抛出
- 非 OpenAI 供应商默认 `max_retries=5`、`timeout=180`

### 6. SQLite 崩溃恢复

每个股票代码独立一个 SQLite 数据库文件，通过 SHA256 生成确定性 `thread_id`。系统崩溃后可从最近的 checkpoint 恢复执行，避免重复计算。

---

## 实际分析效果

以下为系统对真实股票的分析输出示例：

### A 股分析：华电辽能（600396.SH）

系统生成了完整的五阶段分析报告，包含：

- **技术分析**：MACD 2.66、RSI 75.32、KDJ K 值 89.11，识别出极端超买状态
- **情绪分析**：宏观流动性宽松与贸易摩擦并存，公司层面"静默"
- **新闻分析**：央行 5000 亿逆回购、地缘局势、能源行业政策
- **研究员辩论**：多头与空头围绕"流动性驱动 vs 基本面脱节"展开 5 轮辩论
- **风控辩论**：激进派、保守派、中立派三方就"卖出时机与仓位管理"激烈交锋
- **最终决策**：投资组合经理综合研判，给出 **卖出** 建议

> 完整报告示例：[`reports/600396.SH_20260604_180515/`](reports/600396.SH_20260604_180515/)

### 美股分析：Marvell Technology（MRVL）

系统同样支持美股分析，已完成对 MRVL、AVGO、GLW 等标的的多轮分析：

> 完整报告示例：[`reports/MRVL_20260620_215103/`](reports/MRVL_20260620_215103/)

---

## A 股适配改进

相比原项目，本版本针对 A 股市场进行了以下改进：

| 改进项 | 说明 |
|--------|------|
| **数据源切换** | 默认使用东方财富 API，国内直连，无需翻墙 |
| **A 股原生支持** | 直接输入沪深京股票代码（如 `000630`、`600519`）即可分析 |
| **中文输出** | 分析报告默认中文，符合国内用户习惯 |
| **国产模型适配** | MiMo、GLM 等模型的 XML 工具调用格式已兼容 |
| **稳定性增强** | 重试机制 + 限速保护 + 容错路由，长时间运行不易崩溃 |

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/yang1729346/TradingAgents-A-Share.git
cd TradingAgents

# 创建虚拟环境
conda create -n tradingagents python=3.13
conda activate tradingagents

# 安装依赖
pip install .

# 配置 API 密钥
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

**Python 调用：**

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("600519", "2026-01-15")  # 贵州茅台
print(decision)
```

**CLI 使用：**

```bash
tradingagents
# 或
python -m cli.main
```

---

## 项目结构

```
TradingAgents/
├── tradingagents/
│   ├── agents/
│   │   ├── analysts/          # 分析师（技术、情绪、新闻、基本面）
│   │   ├── researchers/       # 研究员（多头、空头、主管）
│   │   ├── trader/            # 交易员
│   │   └── risk_mgmt/         # 风控（激进、保守、中立）
│   ├── graph/
│   │   ├── trading_graph.py   # 主编排器
│   │   ├── setup.py           # 图组装
│   │   └── checkpointer.py    # SQLite 崩溃恢复
│   ├── dataflows/
│   │   ├── interface.py       # 供应商路由与容错
│   │   └── eastmoney.py       # 东方财富数据源
│   ├── llm_clients/
│   │   ├── base_client.py     # XML 工具调用解析
│   │   ├── openai_client.py   # 重试与限速
│   │   └── factory.py         # 15+ 供应商工厂
│   └── default_config.py      # 配置（双模型、供应商链）
├── reports/                   # 历史分析报告
└── cli/                       # 命令行界面
```

---

## 致谢

本项目基于 **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** 进行二次开发。感谢原作者 Yijia Xiao、Edward Sun、Di Luo、Wei Wang 的工作。

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
