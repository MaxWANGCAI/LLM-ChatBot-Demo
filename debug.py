import asyncio
import pytest
import pytest_asyncio
from app.core.chains.conversation_chain import ConversationChain
from app.utils.logger import qa_logger

@pytest.mark.asyncio
async def test_conversation_chain():
    # 初始化对话链
    chain = ConversationChain(kb_type="business")
    qa_logger.log_info("初始化对话链完成")
    
    # 测试问题列表
    test_questions = [
        "怎么管理渠道?",
        "调整价格的流程是什么?",
    ]
    
    try:
        for question in test_questions:
            print(f"\n测试问题: {question}")
            qa_logger.log_info(f"开始处理问题: {question}")
            
            # 获取响应
            response = await chain.get_response(question)
            
            # 打印结果
            print(f"回答: {response['answer']}")
            print("\n参考来源:")
            for source in response['sources']:
                print(f"- {source}")
            
            # 等待一段时间，避免请求过于频繁
            await asyncio.sleep(2)
        
        # 测试清除对话历史
        print("\n测试清除对话历史")
        chain.clear_memory()
        qa_logger.log_info("对话历史已清除")
        
    except Exception as e:
        qa_logger.log_error(f"测试过程中出错: {str(e)}")
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    # 设置日志级别为DEBUG以查看更多信息
    qa_logger.setLevel("DEBUG")
    
    print("开始测试对话链...\n")
    asyncio.run(test_conversation_chain())
    print("\n测试完成")