# LLM 智能问答系统

一个基于大型语言模型（LLM）的智能问答系统，集成了混合检索、重排序和多知识库查询能力，可以根据用户的问题从多个知识库中检索相关信息并生成准确的回答。

## 系统架构

![系统架构图](docs/images/architecture.png)

本系统主要包含以下几个核心组件：

1. **API服务层**：基于FastAPI构建的REST API服务，提供问答接口和管理接口
2. **检索层**：混合检索和重排序系统，包括：
   - 向量检索：使用DashScope的text-embedding-v2模型进行语义检索
   - 关键词检索：使用Elasticsearch进行关键词匹配
   - 重排序：使用DashScope重排序API对检索结果进行精确排序
3. **对话处理层**：基于LangChain的对话处理系统，包括：
   - 对话链：管理对话流程和上下文
   - 提示模板：为不同场景定制LLM提示
   - 对话记忆：管理对话历史
4. **大语言模型层**：支持多种LLM，包括：
   - 通义千问/灵积：阿里云DashScope API
   - OpenAI GPT系列：GPT-3.5/GPT-4
   - Anthropic Claude系列：Claude 3 Opus/Sonnet/Haiku
5. **存储层**：
   - Elasticsearch：存储文档和向量

## 特性与优势

- **混合检索**：结合向量检索和关键词检索的优势，提高检索准确性
- **重排序**：使用DashScope重排序API对检索结果进行精确排序，减少噪声
- **多知识库查询**：支持跨知识库查询和结果合并
- **对话上下文管理**：智能管理对话历史，提供连贯的对话体验
- **可扩展性**：模块化设计，易于扩展和定制

## 技术栈

- **FastAPI**：高性能异步API框架
- **LangChain**：大语言模型应用开发框架
- **Elasticsearch**：全文搜索引擎和向量数据库
- **DashScope**：阿里云AI大模型服务
- **Python 3.9+**：编程语言

## 安装与配置

### 环境要求

- Python 3.9 或更高版本
- Conda 或 virtualenv 用于环境管理
- Elasticsearch 8.x

### 使用Conda安装

```bash
# 克隆代码库
git clone https://github.com/yourusername/llm-qa-system.git
cd llm-qa-system

# 创建并激活conda环境
conda env create -f environment.yml
conda activate env4LLM

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入API密钥和配置信息
```

### 手动安装

```bash
# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入API密钥和配置信息
```

## 快速开始

### 启动服务

```bash
# 开发模式启动
uvicorn app.main:app --reload --port 8000

# 生产模式启动
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 --bind 0.0.0.0:8000
```

### API文档

启动服务后，访问以下URL查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 使用示例

### 问答API

```python
import requests
import json

url = "http://localhost:8000/api/v1/qa"

payload = json.dumps({
  "query": "什么是智能检索系统?",
  "conversation_id": "conv_123",
  "knowledge_base_ids": ["kb_general", "kb_tech"],
  "streaming": True
})

headers = {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer YOUR_API_KEY'
}

response = requests.post(url, headers=headers, data=payload)
print(response.json())
```

### 混合检索与重排序

```python
from elasticsearch import AsyncElasticsearch
from app.core.retrievers.hybrid_retriever import HybridRetriever
from app.core.embeddings.dashscope_embeddings import DashScopeEmbeddings
from app.core.retrievers.reranker import DashScopeReranker

# 初始化组件
es_client = AsyncElasticsearch([{"host": "localhost", "port": 9200}])
embeddings = DashScopeEmbeddings(model="text-embedding-v2")
reranker = DashScopeReranker(model="rerank-v1")

# 创建混合检索器
retriever = HybridRetriever(
    es_client=es_client,
    index_name="my_knowledge_base",
    embedding_model=embeddings,
    reranker=reranker
)

# 执行检索
async def search():
    results = await retriever.retrieve(
        query="什么是向量数据库?", 
        top_k=5
    )
    for doc in results:
        print(f"Score: {doc['score']}, Title: {doc['title']}")
```

### 使用LangChain的对话链

```python
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.llms import DashScope
from app.core.retrievers.hybrid_retriever import HybridRetriever

# 初始化LLM
llm = DashScope(model_name="qwen-turbo")

# 初始化检索器
retriever = HybridRetriever(...)

# 创建对话内存
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

# 创建对话链
qa_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory
)

# 执行问答
response = qa_chain({"question": "什么是向量数据库?"})
print(response["answer"])
```

## 测试

```bash
# 运行所有测试
python -m pytest

# 运行特定测试
python -m pytest app/tests/test_qa.py -v

# 运行测试并生成覆盖率报告
python -m pytest --cov=app
```

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件
