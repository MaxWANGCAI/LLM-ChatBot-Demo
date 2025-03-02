# 示例数据说明

本目录包含了系统使用的示例知识库数据文件，用于演示和测试目的。每个知识库对应一个特定的角色和功能。

## 文件说明

1. `legal_kb.csv` - 法务知识库
   - 角色：法务助手
   - 包含：法律法规、合同审批、知识产权等法律相关信息
   - 字段：content, source_type, source_name, created_at

2. `business_kb.csv` - 业务知识库
   - 角色：业务助手
   - 包含：业务流程、市场分析、运营管理等商业信息
   - 字段：content, metadata

3. `customer_kb.csv` - 客服知识库
   - 角色：客服助手
   - 包含：退货政策、配送说明、售后服务等客服信息
   - 字段：content, source_type, source_name, created_at

## 数据格式要求

### 通用格式要求
- 文件格式：CSV
- 编码：UTF-8
- 分隔符：逗号 (,)
- 文本包含逗号时需要用双引号包围

### 字段说明

1. `content`（必需）
   - 类型：文本
   - 说明：知识条目的具体内容
   - 示例：`"这是一条知识条目的内容"`

2. `source_type`（可选）
   - 类型：文本
   - 说明：知识来源类型
   - 示例：`legal_doc`, `business_doc`, `customer_service`

3. `source_name`（可选）
   - 类型：文本
   - 说明：具体来源名称
   - 示例：`return_policy`, `contract_approval`

4. `created_at`（可选）
   - 类型：日期
   - 格式：YYYY-MM-DD
   - 示例：`2023-01-01`

5. `metadata`（可选，仅用于 business_kb.csv）
   - 类型：JSON 对象
   - 说明：额外的元数据信息
   - 示例：`{"category": "marketing_strategy", "source": "营销手册"}`

## 使用说明

1. 创建新的知识库数据：
   - 在 `data/production/` 目录下创建对应的 CSV 文件
   - 参考本目录下的示例文件格式
   - 文件命名规则：`{type}_kb.csv`

2. 导入数据：
   ```bash
   python app/scripts/manage.py import data/production/*.csv
   ```

3. 注意事项：
   - 确保 CSV 文件的编码为 UTF-8
   - 文本中包含逗号时，需要用双引号包围
   - JSON 格式的 metadata 需要是有效的 JSON 字符串
   - 日期格式需要符合 YYYY-MM-DD 规范 