from es_utils import ESManager
import os
import pandas as pd
import json
from tqdm import tqdm

def import_knowledge(es_manager, file_path, role=None):
    """导入知识库"""
    if os.path.exists(file_path):
        print(f"开始导入知识库: {file_path}")
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path)
            total_docs = len(df)
            print(f"总共需要导入 {total_docs} 条数据")
            
            documents = []
            
            for _, row in tqdm(df.iterrows(), total=total_docs, desc="处理数据"):
                content = str(row['content'])
                
                # 解析metadata JSON字符串
                try:
                    metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                except:
                    metadata = {}
                
                # 添加角色信息
                if role:
                    metadata['role'] = role
                
                documents.append({
                    "content": content,
                    "metadata": metadata
                })
            
            # 批量导入所有数据
            if documents:
                print("开始批量导入数据...")
                es_manager.bulk_add_documents(documents)
            
            print(f"知识库导入完成: {file_path}")
        except Exception as e:
            print(f"导入文件时出错 {file_path}: {str(e)}")
    else:
        print(f"找不到知识库文件: {file_path}")

def main():
    # 初始化ES管理器
    es_manager = ESManager()
    
    # 创建索引
    print("创建/更新索引配置...")
    es_manager.create_index()
    
    # 定义文件映射
    file_role_mapping = {
        "business_kb.csv": "business",
        "customer_kb.csv": "customer_service",
        "legal_kb.csv": "legal"
    }
    
    # 导入每个文件
    for file_name, role in file_role_mapping.items():
        file_path = os.path.join("app/data", file_name)
        import_knowledge(es_manager, file_path, role)

if __name__ == "__main__":
    main() 