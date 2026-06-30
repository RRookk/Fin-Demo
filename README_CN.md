# Fin Demo 中文文档

**Fin-train**（金融大模型微调框架）和 **Finogrid**（B2B 稳定币支付 + AI Agent 微交易平台）的轻量级 API 演示项目。

> 零配置、无需 GPU — 使用 SQLite + 模拟 AI 推理即可本地运行。

[English Docs](README.md)

---

## 项目背景

Fin 项目包含两个核心模块：

### Fin-train — 金融大模型微调框架

让你能在**消费级 GPU**（如 RTX 3090 24GB）上微调 7B-13B 参数的大模型来做金融 NLP 任务。核心技术：

- **LoRA（低秩适配）**：只更新 0.1% 的参数，训练出的 adapter 只有几十 MB
- **指令微调**：统一 9 种金融 NLP 任务（情感分析、股票预测、NER、关系抽取、多轮 QA 等）到一种 prompt 格式
- **多模型兼容**：支持 ChatGLM2、Llama-2、Falcon、InternLM、Qwen、MPT、BLOOM、Baichuan 等 10 种基座模型

### Finogrid — B2B 稳定币支付 + A2A Agent 微交易平台

面向 AI Agent 经济的支付基础设施：

- **V1 支付引擎**：通过 Bridge + 受监管的走廊适配器进行跨境 B2B 支付（USDT/USDC），覆盖 8 个国家
- **Agent 账本**：Agent 到 Agent 的稳定币微交易，含 KYA（了解你的 Agent）、闭环/开环钱包、x402 协议、委派访问控制
- **5 个 AI 监督 Agent**：OpsOversight、AuditGovernance、ProcessImprovement、InternalSupport、TreasuryStrategy — 全部只读，不直接放款

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（单端口模式）
python run.py

# 3. 打开 API 文档
# 浏览器访问 http://localhost:8000/docs
```

数据库自动创建（SQLite），AI 推理全部模拟，不需要 GPU。

---

## API 端点

### Fin-train 模块

```bash
# 金融情感分析
curl -X POST http://localhost:8000/api/fin-train/sentiment \
  -H "Content-Type: application/json" \
  -d '{"text": "苹果公司第四季度营收达949亿美元，同比增长6%。"}'

# 股票预测（使用 yfinance 获取真实价格数据！）
curl -X POST http://localhost:8000/api/fin-train/forecast \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "n_weeks": 2}'

# 金融 RAG 问答
curl -X POST http://localhost:8000/api/fin-train/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "Apple Q4 revenue growth drivers?", "top_k": 3}'
```

### Finogrid 模块 — Agent 微支付完整流程

```bash
# 1. 注册 B2B 客户
curl -X POST "http://localhost:8000/api/finogrid/clients?name=DemoCorp&email=demo@test.com"

# 2. 注册 AI Agent（获取 API Key）
curl -X POST http://localhost:8000/api/finogrid/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "my-bot", "owner_client_id": "<client_id>"}'

# 3. 提交 KYA
curl -X POST http://localhost:8000/api/finogrid/agents/<agent_id>/kya \
  -H "Content-Type: application/json" \
  -d '{"agent_purpose": "AI推理支付", "declared_use_case": "content_generation", "agent_owner_attestation": "我控制此Agent"}'

# 4. 查询 KYA（demo 模式自动通过）
curl http://localhost:8000/api/finogrid/agents/<agent_id>/kya

# 5. 充值 USDC
curl -X POST http://localhost:8000/api/finogrid/agents/<agent_id>/topup \
  -H "Content-Type: application/json" \
  -d '{"amount_usdc": 100, "deposit_tx_hash": "0xdemo"}'

# 6. 创建闭环钱包
curl -X POST http://localhost:8000/api/finogrid/agents/<agent_id>/wallets \
  -H "Content-Type: application/json" \
  -d '{"label": "AI推理支付钱包", "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f7bD18", "loop_type": "closed", "max_per_tx_usdc": 1.0, "max_daily_usdc": 10.0}'

# 7. 创建支付意图
curl -X POST http://localhost:8000/api/finogrid/payment-intents \
  -H "Content-Type: application/json" \
  -d '{"payer_wallet_id": "<wallet_id>", "amount_usdc": 0.05, "intent_description": "GPT-4推理费用", "intent_category": "compute", "expires_at": "2026-06-30T23:59:59Z"}'

# 8. 执行微支付（通过 10 道合规门！）
curl -X POST http://localhost:8000/api/finogrid/micropay \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "unique-key-123", "payer_wallet_id": "<wallet_id>", "payee_address": "0xPayee0000000000000000000000000000000000", "amount_usdc": 0.05, "payment_intent_id": "<intent_id>"}'

# 9. 查看余额和账本
curl http://localhost:8000/api/finogrid/agents/<agent_id>/balance

# B2B 批量支付
curl -X POST http://localhost:8000/api/finogrid/batches \
  -H "Content-Type: application/json" \
  -d '{"client_id": "<client_id>", "reference": "6月工资", "tasks": [{"corridor_code": "BR", "recipient_name": "João", "amount_usdc": 500, "preferred_asset": "USDC", "preferred_mode": "wallet", "beneficiary_data": {"cpf_cnpj": "123.456.789-00"}}]}'
```

---

## Python SDK 用法

```python
from demo.sdk import FinogridClient
import uuid

client = FinogridClient(base_url="http://localhost:8000")

# 注册 Agent
result = client.agents.create("my-agent", owner_client_id="...")
agent_id = result["agent_account_id"]

# KYA（demo 模式下自动通过）
client.kya.submit(agent_id, "AI推理支付", "content_generation", "我控制此Agent")
client.kya.poll_until(agent_id, "basic")

# 充值 + 创建钱包
client.agents.topup(agent_id, 100.0)
wallet = client.wallets.create(agent_id, "钱包", "0x742d...", loop_type="closed")

# 创建支付意图 → 执行支付
intent = client.payment_intents.create(wallet["wallet_id"], 0.05, "AI推理费用")
tx = client.micropay.pay(
    idempotency_key=str(uuid.uuid4()),
    payer_wallet_id=wallet["wallet_id"],
    payee_address="0xPayee...",
    amount_usdc=0.05,
    payment_intent_id=intent["payment_intent_id"],
)
print(f"状态: {tx['status']}")       # settled_offchain
print(f"通过门数: {len(tx['gates_passed'])}")  # 10
```

---

## 10 道合规门

每次微支付都必须通过以下 10 道检查：

1. **幂等性** — 调用方提供的 key 防止重复支付
2. **KYA + 钱包所有权** — Agent 必须通过 KYA，钱包必须活跃
3. **闭环/开环 + 支付意图** — 闭环钱包需要有效的 PaymentIntent
4. **交易对手白名单** — 可选，按钱包配置
5. **单笔限额** — `max_per_tx_usdc`
6. **钱包日限额** — `max_daily_usdc`，每日自动重置
7. **KYA 级别日限额** — basic $1/天，enhanced $100/天（跨所有钱包汇总）
8. **钱包过期/使用次数** — 自动过期和使用次数限制
9. **余额充足性** — 可用余额检查
10. **链下结算** — 原子性余额更新 + 复式记账

---

## 8 国支付走廊

| 代码 | 国家 | 支付通道 | 钱包 SLA |
|------|------|---------|---------|
| BR | 🇧🇷 巴西 | PIX | 60 分钟 |
| NG | 🇳🇬 尼日利亚 | NIBSS | 45 分钟 |
| IN | 🇮🇳 印度 | UPI, IMPS | 30 分钟 |
| AR | 🇦🇷 阿根廷 | CBU | 90 分钟 |
| VN | 🇻🇳 越南 | Napas, VietQR | 60 分钟 |
| AE | 🇦🇪 阿联酋 | IBAN, SWIFT | 120 分钟 |
| ID | 🇮🇩 印尼 | BI-FAST | 45 分钟 |
| PH | 🇵🇭 菲律宾 | InstaPay, PESONet | 30 分钟 |

---

## 哪些是真的 vs Demo 模拟

| 组件 | 生产环境 | Demo |
|------|---------|------|
| Fin-train LoRA 模型 | GPU + 13GB 模型文件 | 关键字模拟分析 |
| 股票价格数据 | yfinance API | ✅ 相同（真实 yfinance） |
| 市场情绪 | Adanos API (Reddit/X/Polymarket) | 模拟 |
| 新闻检索 | 多源爬虫（Reuters, Bloomberg 等） | 模拟知识库 |
| 数据库 | AlloyDB (PostgreSQL) | SQLite |
| 链上结算 | Base L2 (USDC) | 模拟 |
| KYA 验证 | Sardine / Persona / Chainalysis | 自动通过（demo） |
| 合规筛查 | Chainalysis KYT | 模拟 |
| 消息队列 | GCP Pub/Sub | 直接调用 |
| **10 道合规门** | ✅ 相同逻辑 | ✅ **相同逻辑！** |
| **走廊适配器模式** | ✅ 相同模式 | ✅ **相同模式！** |
| **复式记账** | ✅ 相同 | ✅ **相同！** |
| **x402 协议** | ✅ 相同 | ✅ **相同中间件！** |

---

## 技术栈

- **FastAPI** — 现代异步 Python Web 框架
- **SQLAlchemy 2.0** — 异步 ORM + SQLite
- **Pydantic v2** — 类型安全的请求/响应验证
- **yfinance** — 实时股票数据
- **httpx** — 异步 HTTP 客户端

---

## 许可证

MIT — 参见原始 Fin 项目的 [LICENSE](../Fin/LICENSE)。

---

*此 demo 作为 Fin 项目的配套演示而构建。生产环境部署请参见完整的 Fin 代码仓库。*
