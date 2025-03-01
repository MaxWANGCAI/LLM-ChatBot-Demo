# LangChain 知识库助手

基于 LangChain 和 FastAPI 开发的智能知识库助手系统，集成了法务知识库、业务流程及品类知识库、智能客服三个角色。

## 功能特点

- 多角色知识库助手
- 基于 Elasticsearch 的向量检索
- 支持多轮对话
- 现代化的 Web 界面
- 灵活的大模型 API 调用

## 技术栈

- 后端：FastAPI + LangChain + Elasticsearch
- 前端：HTML + TailwindCSS
- 向量数据库：Elasticsearch

## 环境要求

- Python 3.8+
- Elasticsearch 8.x
- OpenAI API Key

## 安装步骤

1. 克隆项目：
```bash
git clone <repository_url>
cd langchain-kb-assistant
```

2. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
创建 `.env` 文件并添加以下配置：
```
OPENAI_API_KEY=your_api_key_here
```

5. 启动 Elasticsearch：
确保 Elasticsearch 服务已经启动并运行在默认端口 (9200)。

6. 运行应用：
```bash
uvicorn app.main:app --reload
```

访问 http://localhost:8000 即可使用系统。

## 项目结构

```
app/
├── api/
│   └── routers/
│       └── chat.py
├── core/
│   ├── agents/
│   │   └── assistant.py
│   └── chains/
│       └── conversation_chain.py
├── data/
│   ├── legal_kb.csv
│   ├── business_kb.csv
│   └── customer_kb.csv
├── utils/
│   ├── es_client.py
│   └── knowledge_base.py
├── config/
│   └── settings.py
└── main.py
templates/
└── index.html
```

## 使用说明

1. 选择助手类型（法务/业务/客服）
2. 输入问题并发送
3. 系统会从相应知识库中检索相关信息并生成回答
4. 支持多轮对话，可以通过"清除上下文"按钮开始新的对话

## 注意事项

- 首次运行时，系统会自动初始化知识库
- 请确保 OpenAI API Key 配置正确
- 建议在生产环境中适当调整配置参数

## License

MIT
