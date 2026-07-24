# TradingAgents A 股智能投研系统

TradingAgents 是一个面向 A 股研究场景的多智能体投研框架。技术面、市场情绪、新闻与基本面信息进入可重复执行的分析、辩论、交易规划和风险决策流程，帮助研究者系统整理证据与观点。

> 本项目仅用于学习与研究，不构成投资建议、交易信号或收益承诺。模型生成内容可能不准确，任何实际投资决策都应由使用者独立核验并自行承担风险。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 多维分析 | 技术、情绪、新闻和基本面分析师从不同角度形成研究报告 |
| 多空研究辩论 | 多头与空头研究员围绕已有证据展开对抗式讨论，由研究主管汇总结论 |
| 风险决策角色 | 激进、保守和中立三类风险角色评估交易计划，投资组合经理作出最终决策 |
| A 股代码支持 | 识别上海、深圳证券交易所代码后缀，例如 `.SH` 与 `.SZ`，用于分析上下文、数据工具参数和基准映射 |
| 多模型供应商 | 支持 OpenAI 兼容接口，以及 Anthropic、Google、Azure 等客户端与多种模型配置 |
| 稳定执行 | 提供数据供应商降级、请求重试、工具调用轮次控制和可选 checkpoint 恢复 |
| 中文输出 | 可通过环境变量、CLI 交互或 Python 配置将分析报告与最终结论设为中文 |

## 决策工作流

```text
股票代码 + 研究日期
        │
        ▼
┌─────────────────────────────────────────────┐
│ LangGraph 并行扇出（按已选择分析师）：         │
│ 技术分析师 │ 情绪分析师 │ 新闻分析师 │ 基本面分析师 │
└────────────────────┬────────────────────────┘
                     │ 汇合
                     ▼
          多头研究员 ⇄ 空头研究员
                     │
                 研究主管
                     │
                   交易员
                     │
      激进风险角色 → 保守风险角色 → 中立风险角色
                     │             ↖ 可按轮次继续讨论
                     ▼
                投资组合经理
```

当前实现由 LangGraph `StateGraph` 编排。默认 Python 配置包含技术、情绪、新闻和基本面四类分析师；实际运行时会根据所选分析师集合从 `START` 扇出并行执行，各自完成工具调用和报告后汇合到多头研究员。后续的多空辩论、交易计划、风险讨论和组合决策按照图中的条件边推进。

## 系统组成

### 分析团队

- **技术分析师**：读取行情和技术指标，分析趋势、动量、波动及关键价位。
- **情绪分析师**：评估与标的相关的信息语气和市场情绪。
- **新闻分析师**：梳理公司、行业与宏观新闻，识别潜在催化因素和风险事件。
- **基本面分析师**：研究财务、估值和经营信息，形成基本面判断。

### 决策团队

- **多头研究员与空头研究员**：分别构建支持和反对交易的论证，通过辩论检验分析结论。
- **研究主管**：综合多空观点，形成研究层面的投资方案。
- **交易员**：把研究结论转化为可执行的交易计划。
- **激进、保守与中立风险角色**：从不同风险偏好审视计划，揭示仓位、回撤与机会成本等问题。
- **投资组合经理**：综合研究、交易和风控信息，输出最终决策。

## 技术实现

| 模块 | 实现 |
| --- | --- |
| 工作流编排 | LangGraph `StateGraph` 定义节点、工具循环、辩论条件边和最终状态 |
| 智能体与工具 | LangChain 消息模型和 tool calling 连接分析节点与行情、新闻、基本面工具 |
| 模型客户端 | OpenAI 兼容客户端，以及 Anthropic、Google、Azure 客户端；按供应商处理认证与参数差异 |
| 数据路由 | 工具级配置优先于类别级配置；根据数据类别配置和供应商可用性执行路由与降级 |
| 工具调用兼容 | 标准工具调用缺失时，可从部分模型返回内容中恢复 XML 格式的工具调用 |
| 执行稳定性 | 请求重试、工具调用轮次限制、数据源 fallback，避免瞬时错误或工具循环长期阻塞 |
| 状态恢复 | 可选 SQLite checkpoint，在相同股票与日期的失败任务中从最近成功节点恢复 |
| 本地记录 | 将完整状态、分节报告、消息和工具调用日志写入本地结果目录 |

配置中的 `quick_think_llm` 用于分析师、研究员、交易员和风险讨论等高频执行节点；`deep_think_llm` 用于研究主管与投资组合经理等综合决策节点。两者可以选用不同模型，在响应速度、成本与推理能力之间做取舍。

## 快速开始

要求 Python 3.10 或更高版本。

```bash
git clone https://github.com/yang1729346/TradingAgents-A-Share.git
cd TradingAgents-A-Share

conda create -n tradingagents python=3.13
conda activate tradingagents
pip install .
```

也可以使用 `uv` 创建和同步项目环境：

```bash
uv sync
```

复制环境变量模板并按需配置：

```bash
cp .env.example .env
```

Windows PowerShell 可使用 `Copy-Item .env.example .env`。下面是最小配置示例，所有密钥均为占位符：

```dotenv
OPENAI_API_KEY=your_api_key
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=gpt-5.4
TRADINGAGENTS_QUICK_THINK_LLM=gpt-5.4-mini
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
TRADINGAGENTS_CHECKPOINT_ENABLED=true
```

不要把包含真实 API 密钥的 `.env` 提交到版本库。其他供应商的密钥名和可选配置请参考 [`.env.example`](.env.example)。

## 使用方式

安装后直接运行 `tradingagents`；当前 CLI 是单命令应用，不需要 `analyze` 子命令。模块方式与安装命令等价：

```bash
tradingagents
python -m cli.main
```

启用崩溃恢复时，将 `--checkpoint` 作为根选项传入：

```bash
tradingagents --checkpoint
python -m cli.main --checkpoint
```

Python 调用示例：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["output_language"] = "Chinese"
config["checkpoint_enabled"] = True

graph = TradingAgentsGraph(debug=True, config=config)
final_state, decision = graph.propagate("600519.SH", "2026-01-15")
print(decision)
```

分析 A 股时建议显式携带交易所后缀，例如上交所 `600519.SH`、深交所 `000001.SZ`，以便数据工具收到完整代码，并使基准映射正确识别市场。

## 项目结构

```text
TradingAgents-A-Share/
├── tradingagents/
│   ├── agents/             # 分析、研究、交易、风控与管理智能体
│   ├── dataflows/          # 行情、新闻、基本面数据工具与供应商路由
│   ├── graph/              # StateGraph 工作流、条件边与 checkpoint
│   ├── llm_clients/        # 多供应商模型客户端与工具调用兼容层
│   └── default_config.py   # 默认配置及环境变量覆盖
├── cli/                    # Typer 命令行界面
├── tests/                  # 单元、集成与冒烟测试
├── main.py                 # Python 使用示例入口
└── pyproject.toml          # 包元数据、依赖与 tradingagents 命令入口
```

## 输出与运行数据

CLI 会在本地结果目录保存分析过程中的分节报告、消息和工具调用日志，并可按提示另存完整 Markdown 报告。Python 工作流还会记录最终状态，默认运行数据位于用户目录下的 `.tradingagents`；具体位置可通过配置调整。

开启 checkpoint 后，未完成的同一股票、同一研究日期任务可以从 SQLite 中最近成功的节点继续；任务成功完成后，对应 checkpoint 会被清理。恢复机制减少重复调用，但不能保证外部数据源或模型响应完全可复现。

报告和最终决策均由模型结合工具数据生成。使用前应核对证券代码、日期、原始数据、引用事实、计算结果和模型推断，尤其不要把未经验证的输出直接用于真实交易。

## 来源与许可

本仓库基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 的开源代码构建，并围绕 A 股数据、中文分析、模型工具调用兼容、数据路由和运行稳定性进行了调整。相关论文见 [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)。

项目按 [Apache License 2.0](LICENSE) 分发；使用、修改和再分发时应遵守许可证中的版权声明、变更说明、许可证副本和归属保留等义务。
