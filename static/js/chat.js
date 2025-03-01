document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const assistantType = document.getElementById('assistant-type');
    const clearButton = document.getElementById('clear-button');

    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        // 添加用户消息到聊天界面
        addMessage('user', message);
        messageInput.value = '';

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    assistant_type: assistantType.value,
                    message: message
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                // 添加助手回复到聊天界面
                addMessage('assistant', data.answer, data.sources);
            } else {
                throw new Error(data.detail || '发送消息时出错');
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('assistant', '抱歉，处理您的请求时出现错误。');
        }

        // 滚动到底部
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function addMessage(type, content, sources = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const textDiv = document.createElement('div');
        textDiv.textContent = content;
        messageDiv.appendChild(textDiv);

        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'sources';
            sourcesDiv.textContent = '来源: ' + sources.map(s => s.title || s.filename).join(', ');
            messageDiv.appendChild(sourcesDiv);
        }

        chatContainer.appendChild(messageDiv);
    }

    async function clearContext() {
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    assistant_type: assistantType.value,
                    message: '',
                    clear_context: true
                })
            });

            if (response.ok) {
                // 清空聊天界面
                chatContainer.innerHTML = '';
                addMessage('assistant', '对话历史已清除');
            } else {
                throw new Error('清除对话历史时出错');
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('assistant', '抱歉，清除对话历史时出现错误。');
        }
    }

    // 事件监听器
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    clearButton.addEventListener('click', clearContext);
}); 