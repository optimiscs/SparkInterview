document.addEventListener('DOMContentLoaded', function() {
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const messagesContainer = document.getElementById('chat-messages-container');

// 聊天状态管理
let currentSessionId = null;
let websocket = null;
let isProcessing = false;
let userSessions = []; // 存储用户的所有会话

// 获取用户真实信息
function getRealUserInfo() {
    // 从URL参数获取
    const urlParams = new URLSearchParams(window.location.search);
    
    // 从localStorage获取用户配置信息
    const savedUserInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    const savedConfig = JSON.parse(localStorage.getItem('interviewConfig') || '{}');
    
    return {
        user_name: urlParams.get('username') || savedUserInfo.name || '面试用户',
        target_position: urlParams.get('position') || savedConfig.position || '前端开发工程师',
        target_field: urlParams.get('field') || savedConfig.domain || '前端开发',
        resume_text: savedConfig.resumeSummary || '具有丰富的技术经验，渴望在新的职位上发挥所长'
    };
}

// 从后端获取用户的所有会话
async function fetchUserSessions() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.warn('未找到访问令牌，无法获取用户会话');
            return [];
        }
        
        const response = await fetch('/api/v1/chat/sessions', {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            userSessions = data.sessions || [];
            console.log('获取到用户会话:', userSessions.length, '个');
            return userSessions;
        } else {
            console.error('获取用户会话失败:', response.status, response.statusText);
            return [];
        }
    } catch (error) {
        console.error('获取用户会话异常:', error);
        return [];
    }
}

// 渲染会话列表
function renderSessionList(sessions) {
    const sessionContainer = document.querySelector('.flex-1.overflow-y-auto.p-4.space-y-3');
    if (!sessionContainer) return;
    
    // 清空现有内容
    sessionContainer.innerHTML = '';
    
    if (sessions.length === 0) {
        // 没有会话时显示提示
        sessionContainer.innerHTML = `
            <div class="text-center py-8">
                <div class="w-16 h-16 mx-auto mb-4 text-gray-300">
                    <i class="ri-chat-1-line text-4xl"></i>
                </div>
                <p class="text-gray-500 text-sm">暂无面试记录</p>
                <p class="text-gray-400 text-xs mt-1">点击"新建面试"开始您的第一次面试</p>
            </div>
        `;
        return;
    }
    
    // 渲染每个会话
    sessions.forEach((session, index) => {
        const sessionDiv = document.createElement('div');
        const isActive = session.session_id === currentSessionId;
        sessionDiv.className = `bg-white rounded-lg p-4 border ${isActive ? 'border-primary shadow-sm' : 'border-gray-200'} group cursor-pointer hover:shadow-sm transition-all`;
        
        // 计算面试时长（如果有的话）
        const createdTime = new Date(session.created_at);
        const lastActivity = new Date(session.last_activity);
        const durationMinutes = Math.round((lastActivity - createdTime) / (1000 * 60));
        
        // 根据消息数量判断状态
        let statusBadge = '';
        let statusText = '';
        if (session.message_count <= 2) {
            statusBadge = 'bg-yellow-100 text-yellow-800';
            statusText = '刚开始';
        } else if (session.message_count < 10) {
            statusBadge = 'bg-blue-100 text-blue-800';
            statusText = '进行中';
        } else {
            statusBadge = 'bg-green-100 text-green-800';
            statusText = '已完成';
        }
        
        // 获取技能领域对应的图标
        const fieldIcons = {
            '前端开发': 'ri-code-line',
            '后端开发': 'ri-server-line',
            '全栈开发': 'ri-stack-line',
            '数据分析': 'ri-bar-chart-line',
            '产品管理': 'ri-product-hunt-line',
            '设计相关': 'ri-palette-line',
            '人工智能': 'ri-robot-line',
            '测试工程': 'ri-bug-line',
            '运维工程': 'ri-settings-line'
        };
        const iconClass = fieldIcons[session.target_field] || 'ri-briefcase-line';
        
        sessionDiv.innerHTML = `
            <div class="flex items-center space-x-3 mb-2">
                <div class="w-8 h-8 ${isActive ? 'bg-primary' : 'bg-blue-500'} rounded-full flex items-center justify-center">
                    <i class="${iconClass} text-white text-sm"></i>
                </div>
                <div class="flex-1">
                    <h3 class="text-sm font-medium text-gray-900">${session.target_position}</h3>
                    <p class="text-xs text-gray-500">${formatDateTime(session.created_at)}</p>
                </div>
                <button class="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity delete-session" data-session-id="${session.session_id}">
                    <i class="ri-delete-bin-line text-gray-400 hover:text-red-500"></i>
                </button>
            </div>
            <div class="text-xs text-gray-600">
                <span class="inline-block ${statusBadge} px-2 py-1 rounded-full mr-2">${statusText}</span>
                <span class="text-gray-500">
                    ${session.message_count}条消息${durationMinutes > 0 ? ` • ${durationMinutes}分钟` : ''}
                </span>
            </div>
        `;
        
        // 点击切换会话
        sessionDiv.addEventListener('click', (e) => {
            if (!e.target.closest('.delete-session')) {
                switchToSession(session.session_id);
            }
        });
        
        // 删除会话事件
        const deleteBtn = sessionDiv.querySelector('.delete-session');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showDeleteSessionModal(session.session_id, session.target_position);
        });
        
        sessionContainer.appendChild(sessionDiv);
    });
}

// 格式化日期时间
function formatDateTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMinutes = Math.round((now - date) / (1000 * 60));
    
    if (diffMinutes < 60) {
        return `${diffMinutes}分钟前`;
    } else if (diffMinutes < 24 * 60) {
        return `${Math.round(diffMinutes / 60)}小时前`;
    } else {
        return date.toLocaleDateString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

// 切换到指定会话
async function switchToSession(sessionId) {
    if (sessionId === currentSessionId) return;
    
    try {
        // 关闭当前WebSocket连接
        if (websocket) {
            websocket.close(1000, 'Switching session');
        }
        
        currentSessionId = sessionId;
        localStorage.setItem('currentChatSession', sessionId);
        
        // 清空消息容器
        messagesContainer.innerHTML = `
            <div class="flex items-center justify-center py-8">
                <div class="flex items-center space-x-2 text-gray-500">
                    <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    <span class="text-sm">加载会话历史...</span>
                </div>
            </div>
        `;
        
        // 获取会话历史
        const history = await fetchChatHistory(sessionId);
        if (history) {
            displayChatHistory(history);
        }
        
        // 重新建立WebSocket连接
        connectWebSocket();
        
        // 更新会话列表显示
        renderSessionList(userSessions);
        
        addSystemMessage(`已切换到会话: ${sessionId.substring(0, 8)}...`, 'info');
        
    } catch (error) {
        console.error('切换会话失败:', error);
        showError('切换会话失败: ' + error.message, true);
    }
}

// 获取会话历史
async function fetchChatHistory(sessionId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/v1/chat/history/${sessionId}`, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
        
        if (response.ok) {
            return await response.json();
        } else {
            console.error('获取会话历史失败:', response.status);
            return null;
        }
    } catch (error) {
        console.error('获取会话历史异常:', error);
        return null;
    }
}

// 显示会话历史
function displayChatHistory(history) {
    messagesContainer.innerHTML = '';
    
    if (history.messages && history.messages.length > 0) {
        history.messages.forEach(msg => {
            addMessageToUI(msg.content, msg.role);
        });
        scrollToBottom();
    } else {
        messagesContainer.innerHTML = `
            <div class="flex items-center justify-center py-8 text-gray-500">
                <span class="text-sm">会话历史为空</span>
            </div>
        `;
    }
}

// 显示删除会话确认模态框
function showDeleteSessionModal(sessionId, positionName) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
<div class="bg-white rounded-lg p-6 max-w-sm w-full mx-4 shadow-xl">
<div class="flex items-center space-x-3 mb-4">
<div class="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
<i class="ri-delete-bin-line text-red-500 text-lg"></i>
</div>
<h3 class="text-lg font-medium text-gray-900">删除面试记录</h3>
</div>
            <p class="text-gray-600 mb-6">确定要删除"${positionName}"的面试记录吗？删除后将无法恢复。</p>
<div class="flex justify-end space-x-3">
                <button class="px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors" onclick="this.closest('.fixed').remove()">取消</button>
                <button class="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors" onclick="deleteSession('${sessionId}')">删除</button>
</div>
</div>
`;
    document.body.appendChild(modal);
}

// 删除会话
async function deleteSession(sessionId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/v1/chat/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
        
        if (response.ok) {
            // 从本地列表移除
            userSessions = userSessions.filter(s => s.session_id !== sessionId);
            
            // 如果删除的是当前会话，需要切换到其他会话或创建新会话
            if (sessionId === currentSessionId) {
                if (userSessions.length > 0) {
                    await switchToSession(userSessions[0].session_id);
                } else {
                    await initializeChatSession();
                }
            }
            
            // 更新会话列表显示
            renderSessionList(userSessions);
            
            addSystemMessage('面试记录已删除', 'success');
        } else {
            throw new Error('删除会话失败');
        }
    } catch (error) {
        console.error('删除会话失败:', error);
        showError('删除会话失败: ' + error.message);
    } finally {
        // 关闭模态框
        document.querySelector('.fixed.inset-0.bg-black').remove();
    }
}

// 应用初始化
async function initializeApp() {
    try {
        // 检查认证状态
        const token = localStorage.getItem('access_token');
        if (!token) {
            showError('请先登录后再开始面试');
            return;
        }
        
        // 先获取用户现有会话
        await fetchUserSessions();
        renderSessionList(userSessions);
        
        // 检查是否有保存的会话ID或URL参数中的会话ID
        const urlParams = new URLSearchParams(window.location.search);
        let targetSessionId = urlParams.get('sessionId') || localStorage.getItem('currentChatSession');
        
        // 如果有指定会话ID且该会话存在，恢复该会话
        if (targetSessionId && userSessions.some(s => s.session_id === targetSessionId)) {
            await switchToSession(targetSessionId);
            return;
        }
        
        // 如果有现有会话，恢复最新的会话
        if (userSessions.length > 0) {
            await switchToSession(userSessions[0].session_id);
            return;
        }
        
        // 没有现有会话，创建新会话
        await createNewChatSession();
        
    } catch (error) {
        console.error('应用初始化失败:', error);
        showError('应用初始化失败: ' + error.message, true);
    }
}

// 创建新的聊天会话
async function createNewChatSession() {
    try {
        // 检查认证状态
        const token = localStorage.getItem('access_token');
        if (!token) {
            showError('请先登录后再开始面试');
            return;
        }

        // 获取真实用户信息
        const userInfo = getRealUserInfo();
        console.log('创建新会话，用户信息:', userInfo);
        
        const response = await fetch('/api/v1/chat/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(userInfo)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`创建聊天会话失败: ${response.status} ${errorText}`);
        }

        const data = await response.json();
        currentSessionId = data.session_id;
        
        // 保存会话信息
        localStorage.setItem('currentChatSession', currentSessionId);
        
        // 清除加载指示器
        messagesContainer.innerHTML = '';
        
        // 显示欢迎消息
        addMessageToUI(data.message.content, 'assistant');
        
        // 更新页面标题显示用户信息
        updatePageHeader(userInfo);
        
        // 重新获取会话列表（包含新创建的会话）
        await fetchUserSessions();
        renderSessionList(userSessions);
        
        // 建立WebSocket连接
        connectWebSocket();
        
        addSystemMessage('新面试会话已创建', 'success');
        
    } catch (error) {
        console.error('创建聊天会话失败:', error);
        showError(`无法创建新的面试会话: ${error.message}`, true);
        
        // 清除加载指示器，显示连接失败状态
        messagesContainer.innerHTML = `
            <div class="flex items-center justify-center py-12">
                <div class="text-center">
                    <div class="w-16 h-16 mx-auto mb-4 text-red-500">
                        <i class="ri-wifi-off-line text-4xl"></i>
                    </div>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">连接失败</h3>
                    <p class="text-gray-600 mb-4">无法连接到AI面试官，请检查网络后重试</p>
                    <button onclick="createNewChatSession()" class="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors">
                        重新连接
                    </button>
                </div>
            </div>
        `;
    }
}

// 向后兼容的初始化函数
async function initializeChatSession() {
    await createNewChatSession();
}

// 更新页面头部信息
function updatePageHeader(userInfo) {
    const progressItems = document.querySelectorAll('.text-sm.font-medium.text-primary, .text-sm.text-gray-400');
    if (progressItems.length > 0) {
        // 更新进度条显示当前用户的目标职位
        const targetElement = document.querySelector('.text-sm.font-medium.text-primary');
        if (targetElement && targetElement.textContent.includes('岗位确认')) {
            targetElement.textContent = `${userInfo.target_position} 面试`;
        }
    }
}

// WebSocket连接
function connectWebSocket() {
    if (!currentSessionId) return;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/chat/ws/${currentSessionId}`;
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function(event) {
        console.log('WebSocket连接已建立');
        updateConnectionStatus('connected');
        addSystemMessage('AI面试官已连接，可以开始对话', 'success');
    };
    
    websocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    websocket.onclose = function(event) {
        console.log('WebSocket连接已关闭');
        if (event.code !== 1000) {
            updateConnectionStatus('disconnected');
            setTimeout(() => {
                if (currentSessionId) {
                    updateConnectionStatus('connecting');
                    connectWebSocket();
                }
            }, 3000);
        }
    };
    
    websocket.onerror = function(error) {
        console.error('WebSocket错误:', error);
        updateConnectionStatus('disconnected');
        showError('WebSocket连接错误，正在尝试重新连接...', true);
    };
}

// 处理WebSocket消息
let currentAIMessage = null;
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'connected':
            console.log('WebSocket连接确认:', data.message);
            break;
            
        case 'processing_start':
            isProcessing = true;
            updateSendButton();
            // 创建AI消息占位符
            currentAIMessage = addMessageToUI('', 'assistant', true);
            showTypingIndicator();
            break;
            
        case 'chunk':
            if (currentAIMessage) {
                appendToAIMessage(data.content);
            }
            break;
            
        case 'complete':
            isProcessing = false;
            updateSendButton();
            hideTypingIndicator();
            if (currentAIMessage) {
                finalizeAIMessage();
                currentAIMessage = null;
            }
            scrollToBottom();
            break;
            
        case 'error':
            isProcessing = false;
            updateSendButton();
            hideTypingIndicator();
            showError(data.message || '处理消息时发生错误', true);
            // 添加系统消息说明错误
            addSystemMessage(`系统错误: ${data.message || '未知错误'}`, 'error');
            break;
    }
}

// 添加消息到UI
function addMessageToUI(content, role, isStreaming = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = role === 'user' ? 
        'flex items-start space-x-4 justify-end message-slide-in' : 
        'flex items-start space-x-4 message-slide-in';
    
    const currentTime = new Date().toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    if (role === 'user') {
        messageDiv.innerHTML = `
            <div class="flex-1 flex justify-end">
                <div class="max-w-2xl">
                    <div class="flex items-center space-x-2 mb-2 justify-end">
                        <span class="text-xs text-gray-500">${currentTime}</span>
                        <span class="text-sm font-medium text-gray-900">我</span>
                    </div>
                    <div class="bg-primary text-white rounded-lg rounded-tr-none p-4">
                        <p class="leading-relaxed message-content">${content}</p>
                    </div>
                </div>
            </div>
            <div class="w-12 h-12 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                <i class="ri-user-line text-white"></i>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="w-12 h-12 rounded-full overflow-hidden flex-shrink-0">
                <img src="https://readdy.ai/api/search-image?query=professional%20friendly%20AI%20interviewer%20avatar%2C%20business%20attire%2C%20warm%20smile%2C%20clean%20background%2C%20professional%20headshot%20style%2C%20modern%20corporate%20setting&width=100&height=100&seq=ai-interviewer-1&orientation=squarish" alt="AI 面试官" class="w-full h-full object-cover">
</div>
<div class="flex-1">
                <div class="flex items-center space-x-2 mb-2">
                    <span class="text-sm font-medium text-gray-900">AI 面试官 - 李诚</span>
                    <span class="text-xs text-gray-500">${currentTime}</span>
</div>
                <div class="bg-gray-50 rounded-lg rounded-tl-none p-4 max-w-2xl">
                    <p class="text-gray-800 leading-relaxed message-content">${content}</p>
                    ${isStreaming ? '<div class="typing-cursor">|</div>' : ''}
</div>
</div>
`;
    }
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    
    return messageDiv;
}

// 追加内容到AI消息
function appendToAIMessage(content) {
    if (currentAIMessage && content) {
        const messageContent = currentAIMessage.querySelector('.message-content');
        if (messageContent) {
            // 获取当前内容
            let currentContent = messageContent.textContent || '';
            currentContent += content;
            
            // 格式化内容并更新显示
            messageContent.innerHTML = formatAIMessage(currentContent);
        }
    }
}

// 格式化AI消息内容
function formatAIMessage(content) {
    if (!content) return '';
    
    // 处理换行符
    let formatted = content
        .replace(/\n\n/g, '</p><p class="text-gray-800 leading-relaxed mb-2">')
        .replace(/\n/g, '<br>');
    
    // 处理加粗文本 **text**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
    
    // 处理代码片段 `code`
    formatted = formatted.replace(/`([^`]+)`/g, '<code class="bg-gray-200 px-1 py-0.5 rounded text-sm font-mono">$1</code>');
    
    // 处理列表项
    formatted = formatted.replace(/^[\-\*\+] (.+)$/gm, '<li class="ml-4 mb-1">• $1</li>');
    
    // 处理数字列表
    formatted = formatted.replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 mb-1">$1. $2</li>');
    
    // 包装段落
    if (!formatted.includes('<p')) {
        formatted = `<p class="text-gray-800 leading-relaxed">${formatted}</p>`;
    }
    
    return formatted;
}

// 完成AI消息的格式化
function finalizeAIMessage() {
    if (currentAIMessage) {
        const cursor = currentAIMessage.querySelector('.typing-cursor');
        if (cursor) {
            cursor.remove();
        }
        
        // 最终格式化消息内容
        const messageContent = currentAIMessage.querySelector('.message-content');
        if (messageContent) {
            const rawContent = messageContent.textContent || '';
            messageContent.innerHTML = formatAIMessage(rawContent);
        }
    }
}



// 显示/隐藏输入指示器
function showTypingIndicator() {
    // 先移除已存在的指示器
    hideTypingIndicator();
    
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'flex items-center space-x-3 text-sm text-gray-500 p-4 message-slide-in';
    indicator.innerHTML = `
        <div class="w-10 h-10 rounded-full overflow-hidden flex-shrink-0">
            <img src="https://readdy.ai/api/search-image?query=professional%20friendly%20AI%20interviewer%20avatar%2C%20business%20attire%2C%20warm%20smile%2C%20clean%20background%2C%20professional%20headshot%20style%2C%20modern%20corporate%20setting&width=100&height=100&seq=ai-interviewer-1&orientation=squarish" alt="AI 面试官" class="w-full h-full object-cover">
        </div>
        <div class="flex items-center space-x-2">
            <div class="loading-dots">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
            <span class="text-gray-600">AI面试官正在思考...</span>
        </div>
    `;
    messagesContainer.appendChild(indicator);
    scrollToBottom();
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// 发送消息
function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isProcessing) {
        return;
    }
    
    // 检查WebSocket连接状态
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
        showError('连接已断开，正在尝试重新连接...');
        connectWebSocket();
        return;
    }
    
    // 显示用户消息
    addMessageToUI(message, 'user');
    
    try {
        // 通过WebSocket发送消息
        websocket.send(JSON.stringify({
            type: 'message',
            message: message
        }));
        
        // 清空输入框
        messageInput.value = '';
        messageInput.style.height = 'auto';
        updateSendButton();
        
    } catch (error) {
        console.error('发送消息失败:', error);
        showError('发送消息失败，请重试');
        isProcessing = false;
        updateSendButton();
    }
}

// 添加消息重发功能
function resendMessage(messageText) {
    if (messageText) {
        messageInput.value = messageText;
        updateSendButton();
        sendMessage();
    }
}

// 更新发送按钮状态
function updateSendButton() {
    if (messageInput.value.trim() && !isProcessing) {
sendButton.disabled = false;
sendButton.classList.remove('opacity-50', 'cursor-not-allowed');
        sendButton.textContent = '发送';
} else {
sendButton.disabled = true;
sendButton.classList.add('opacity-50', 'cursor-not-allowed');
        sendButton.textContent = isProcessing ? '处理中...' : '发送';
    }
}

// 滚动到底部
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// 显示错误
function showError(message, canRetry = false) {
    // 移除之前的错误消息
    const existingError = messagesContainer.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message bg-red-50 border-l-4 border-red-400 p-4 mb-4 message-slide-in';
    
    let retryButton = '';
    if (canRetry) {
        retryButton = `
            <button onclick="retryLastAction()" class="ml-4 px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600 transition-colors">
                重试
            </button>
        `;
    }
    
    errorDiv.innerHTML = `
        <div class="flex items-center">
            <div class="w-6 h-6 mr-3">
                <i class="ri-error-warning-line text-red-500 text-lg"></i>
            </div>
            <div class="flex-1">
                <h4 class="text-red-800 font-medium text-sm">连接问题</h4>
                <p class="text-red-700 text-sm mt-1">${message}</p>
            </div>
            <div class="flex items-center">
                ${retryButton}
                <button onclick="this.closest('.error-message').remove()" class="ml-2 w-6 h-6 text-red-500 hover:text-red-700">
                    <i class="ri-close-line text-sm"></i>
                </button>
            </div>
        </div>
    `;
    messagesContainer.appendChild(errorDiv);
    scrollToBottom();
    
    // 5秒后自动消失
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

// 重试最后一个操作
function retryLastAction() {
    if (!currentSessionId) {
        initializeChatSession();
    } else if (websocket && websocket.readyState !== WebSocket.OPEN) {
        connectWebSocket();
    }
}

// 添加系统消息
function addSystemMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'flex justify-center mb-4 message-slide-in';
    
    let bgColor = 'bg-blue-100';
    let textColor = 'text-blue-800';
    let iconClass = 'ri-information-line';
    
    switch (type) {
        case 'error':
            bgColor = 'bg-red-100';
            textColor = 'text-red-800';
            iconClass = 'ri-error-warning-line';
            break;
        case 'success':
            bgColor = 'bg-green-100';
            textColor = 'text-green-800';
            iconClass = 'ri-check-line';
            break;
        case 'warning':
            bgColor = 'bg-yellow-100';
            textColor = 'text-yellow-800';
            iconClass = 'ri-alert-line';
            break;
    }
    
    const currentTime = new Date().toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    messageDiv.innerHTML = `
        <div class="px-4 py-2 ${bgColor} ${textColor} rounded-full text-sm flex items-center space-x-2 max-w-md">
            <i class="${iconClass}"></i>
            <span>${message}</span>
            <span class="text-xs opacity-70">${currentTime}</span>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

// 连接状态指示器
function createConnectionIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'connection-indicator';
    indicator.className = 'connection-indicator connecting';
    indicator.textContent = '连接中...';
    document.body.appendChild(indicator);
    return indicator;
}

function updateConnectionStatus(status) {
    let indicator = document.getElementById('connection-indicator');
    if (!indicator) {
        indicator = createConnectionIndicator();
    }
    
    indicator.className = `connection-indicator ${status}`;
    
    switch (status) {
        case 'connected':
            indicator.textContent = '已连接';
            setTimeout(() => {
                if (indicator.classList.contains('connected')) {
                    indicator.style.opacity = '0';
                    setTimeout(() => {
                        if (indicator.parentNode) {
                            indicator.parentNode.removeChild(indicator);
                        }
                    }, 300);
                }
            }, 2000);
            break;
        case 'disconnected':
            indicator.textContent = '连接断开';
            break;
        case 'connecting':
            indicator.textContent = '重新连接中...';
            break;
    }
}

// 事件监听器
messageInput.addEventListener('input', function() {
this.style.height = 'auto';
this.style.height = Math.min(this.scrollHeight, 120) + 'px';
updateSendButton();
});

messageInput.addEventListener('keydown', function(e) {
if (e.key === 'Enter' && !e.shiftKey) {
e.preventDefault();
sendMessage();
}
});

sendButton.addEventListener('click', sendMessage);

// 页面加载时初始化
updateSendButton();
initializeApp();

// 页面卸载时关闭WebSocket连接
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close(1000, 'Page unloading');
    }
});
});
