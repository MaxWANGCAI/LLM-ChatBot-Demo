document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.querySelector('.chat-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const loadingIndicator = document.querySelector('.loading');

    // 发送消息
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // 显示用户消息
        appendMessage('user', message);
        userInput.value = '';

        // 显示加载指示器
        loadingIndicator.style.display = 'inline-block';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            if (!response.ok) {
                throw new Error('网络响应异常');
            }

            const data = await response.json();
            appendMessage('assistant', data.response);
        } catch (error) {
            showError('发送消息失败：' + error.message);
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    // 添加消息到聊天界面
    function appendMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        messageDiv.textContent = content;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // 显示错误消息
    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        chatContainer.appendChild(errorDiv);
        setTimeout(() => errorDiv.remove(), 5000);
    }

    // 事件监听器
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});