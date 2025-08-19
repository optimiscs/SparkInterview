/**
 * LangGraph智能面试系统 - 前端集成
 * 使用LangChain + LangGraph接口
 */

document.addEventListener('DOMContentLoaded', async function() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const messagesContainer = document.getElementById('chat-messages-container');
    const newInterviewBtn = document.getElementById('new-interview-btn');

    // 聊天状态管理 - 简化版本
    let isProcessing = false;
    let currentSessionId = localStorage.getItem('current_session_id') || null;

    // 初始化应用
    await initializeApp();

    // ==================== API调用工具函数 ====================
    
    /**
     * 统一的API调用函数
     */
    async function callAPI(endpoint, method = 'GET', data = null, basePrefix = '/api/v1') {
        try {
            const url = `${basePrefix}${endpoint}`;
            console.log('API调用:', method, url, data);
            
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
                }
            };

            if (data && method !== 'GET') {
                options.body = JSON.stringify(data);
            }

            const response = await fetch(url, options);
            console.log('API响应状态:', response.status, response.statusText);
            
            if (!response.ok) {
                let errorData = {};
                try {
                    errorData = await response.json();
                } catch (e) {
                    console.error('解析错误响应失败:', e);
                }
                const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                console.error('API错误:', errorMessage, errorData);
                throw new Error(errorMessage);
            }

            const result = await response.json();
            console.log('API调用成功:', result);
            return result;
        } catch (error) {
            console.error('API调用失败:', error);
            throw error;
        }
    }

    /**
     * 获取简历列表
     */
    async function loadResumesList() {
        try {
            const response = await callAPI('/resume/list');
            
            if (response.success && response.data) {
                return response.data.map(resume => ({
                    id: resume.id,
                    name: resume.version_name || '未命名简历',
                    target_position: resume.target_position || '未指定职位',
                    created_at: resume.created_at,
                    updated_at: resume.updated_at,
                    status: resume.status
                }));
            } else {
                throw new Error('获取简历列表失败');
            }
        } catch (error) {
            console.error('加载简历列表失败:', error);
            throw error;
        }
    }

    // ==================== 核心初始化函数 ====================
    
    async function initializeApp() {
        console.log('🚀 初始化面试系统...');
        
        try {
            // 显示初始加载状态
            showLoadingState('正在验证登录状态...');
            
            // 简化认证检查
            const token = localStorage.getItem('access_token');
            const userData = localStorage.getItem('current_user');
            
            if (!token) {
                handleAuthError('no_token');
                return;
            }
            
            // 验证token有效性
            const isValidToken = await validateToken();
            if (!isValidToken) {
                handleAuthError('invalid_token');
                return;
            }
            
            const user = userData ? JSON.parse(userData) : { name: '用户' };
            console.log('✅ 用户认证成功:', user.name);
            
            // 绑定事件监听器
            bindEventListeners();
            
            // 初始化智能体状态面板
            initializeAgentStatusPanel();
            
            // 渲染用户界面
            renderUserInterface();
            
        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
            renderNetworkErrorPrompt();
        }
    }

    /**
     * 验证Token有效性
     */
    async function validateToken() {
        const token = localStorage.getItem('access_token');
        if (!token) return false;

        try {
            const response = await fetch('/api/v1/profile', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const userInfo = await response.json();
                localStorage.setItem('current_user', JSON.stringify(userInfo));
                return true;
            } else {
                localStorage.removeItem('access_token');
                localStorage.removeItem('current_user');
                return false;
            }
        } catch (error) {
            console.error('❌ Token验证异常:', error);
            return false;
        }
    }

    // ==================== 简化的辅助函数 ====================
    
    /**
     * 显示加载状态
     */
    function showLoadingState(message = '加载中...') {
        if (messagesContainer) {
            messagesContainer.innerHTML = `
                <div class="flex items-center justify-center py-8">
                    <div class="flex items-center space-x-2 text-gray-400">
                        <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                        <span class="text-sm">${message}</span>
                    </div>
                </div>
            `;
        }
    }
    
    /**
     * 处理认证错误
     */
    function handleAuthError(reason) {
        switch (reason) {
            case 'no_token':
                renderLoginPrompt();
                break;
            case 'invalid_token':
                renderTokenExpiredPrompt();
                break;
            case 'auth_error':
                renderNetworkErrorPrompt();
                break;
            default:
                renderLoginPrompt();
        }
    }
    
    /**
     * 渲染用户界面
     */
    async function renderUserInterface() {
        console.log('📋 渲染用户界面...');
        
        try {
            // 获取用户会话列表
            const sessions = await loadUserSessions();
            console.log(`📋 找到 ${sessions.length} 个会话`);
            
            if (sessions.length === 0) {
                // 新用户或没有会话 - 显示欢迎界面
                renderWelcomeInterface();
            } else {
                // 有会话的用户 - 显示会话选择界面
                renderSessionSelection(sessions);
            }
            
            // 渲染左侧会话列表
            renderSessionList(sessions);
        } catch (error) {
            console.error('❌ 渲染用户界面失败:', error);
            // 降级到欢迎界面
            renderWelcomeInterface();
        }
    }

    /**
     * 获取用户会话列表
     */
    async function loadUserSessions() {
        try {
            const response = await callAPI('/langgraph-chat/sessions');
            return response.sessions || [];
        } catch (error) {
            console.error('❌ 获取会话列表失败:', error);
            return [];
        }
    }

    /**
     * 获取用户姓名
     */
    function getUserName() {
        const userData = localStorage.getItem('current_user');
        if (userData) {
            try {
                const user = JSON.parse(userData);
                return user.name || '用户';
            } catch (e) {
                console.warn('解析用户信息失败');
            }
        }
        return '用户';
    }

    function bindEventListeners() {
        // 新建面试按钮
        if (newInterviewBtn) {
            newInterviewBtn.addEventListener('click', createNewLangGraphSession);
        }

        // 发送消息按钮
        if (sendButton) {
            sendButton.addEventListener('click', sendLangGraphMessage);
        }

        // 回车发送消息
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendLangGraphMessage();
                }
            });
        }
    }

    // ==================== 简化的会话管理 ====================

    /**
     * 显示面试配置弹窗
     */
    async function createNewLangGraphSession() {
        // 简化认证检查
        const token = localStorage.getItem('access_token');
        if (!token) {
            handleAuthError('no_token');
            return;
        }

        try {
            console.log('🎛️ 显示面试配置弹窗...');
            await showInterviewConfigModal();
        } catch (error) {
            console.error('❌ 显示配置弹窗失败:', error);
            showSystemMessage(`配置失败: ${error.message}`, 'error');
        }
    }

    /**
     * 实际创建面试会话
     */
    async function doCreateInterviewSession(resumeId, options = {}) {
        try {
            // 显示加载状态
            showLoadingState('正在创建面试会话...');
            
            console.log('🚀 创建新的面试会话...', { resumeId, options });
            
            // 获取当前用户信息
            const userData = localStorage.getItem('current_user');
            const user = userData ? JSON.parse(userData) : { name: '用户' };
            
            // 构建面试请求数据
            const interviewData = {
                user_name: user.name,
                target_position: options.position || '算法工程师',
                target_field: options.field || '人工智能',
                resume_id: resumeId,
                interview_type: options.type || 'technical',
                difficulty: options.difficulty || 'intermediate'
            };
            
            // 直接调用创建会话API
            const result = await callAPI('/langgraph-chat/start', 'POST', interviewData);
            
            if (result.success) {
                // 保存当前会话信息
                currentSessionId = result.session_id;
                localStorage.setItem('current_session_id', currentSessionId);
                
                // 清空消息容器并显示欢迎消息
                messagesContainer.innerHTML = '';
                
                displayLangGraphMessage({
                    role: 'assistant',
                    content: result.message,
                    timestamp: new Date().toISOString(),
                    user_profile: result.user_profile,
                    completeness_score: result.completeness_score,
                    interview_stage: result.interview_stage
                });
                
                // 更新智能体状态面板
                updateAgentStatusPanel({
                    session_active: true,
                    user_profile: result.user_profile,
                    completeness_score: result.completeness_score || 0.2,
                    interview_stage: result.interview_stage || 'introduction'
                });
                
                // 重新加载并更新左侧会话列表
                try {
                    const sessions = await loadUserSessions();
                    renderSessionList(sessions);
                    console.log('✅ 会话列表已更新');
                } catch (error) {
                    console.warn('⚠️ 更新会话列表失败:', error);
                }
                
                // 通知面试完成管理器设置当前会话
                if (window.interviewCompletion) {
                    await window.interviewCompletion.setCurrentSession(currentSessionId);
                }
                
                showSystemMessage('✅ 面试会话创建成功！', 'success');
            } else {
                throw new Error(result.error || '创建会话失败');
            }
            
        } catch (error) {
            console.error('❌ 创建面试会话失败:', error);
            showSystemMessage(`创建失败: ${error.message}`, 'error');
            renderUserInterface(); // 恢复界面
        }
    }

    /**
     * 切换到指定会话
     */
    async function switchToSession(sessionId) {
        try {
            showLoadingState('正在切换会话...');
            
            // 验证会话是否存在
            const response = await callAPI(`/langgraph-chat/sessions/${sessionId}/status`);
            if (!response.success) {
                throw new Error('会话不存在或已过期');
            }
            
            // 更新当前会话ID
            const previousSessionId = currentSessionId;
            currentSessionId = sessionId;
            localStorage.setItem('current_session_id', sessionId);
            
            // 清空消息容器
            messagesContainer.innerHTML = '';
            
            // 加载会话的历史消息
            try {
                showLoadingState('正在加载历史消息...');
                const historyResponse = await callAPI(`/langgraph-chat/sessions/${sessionId}/messages`);
                
                if (historyResponse.success && historyResponse.messages) {
                    // 显示历史消息
                    historyResponse.messages.forEach(message => {
                        displayLangGraphMessage({
                            role: message.role,
                            content: message.content,
                            timestamp: message.timestamp
                        });
                    });
                    
                    logger.info(`📚 已加载${historyResponse.messages.length}条历史消息`);
                    
                    // 显示会话恢复提示
            displayLangGraphMessage({
                role: 'assistant',
                        content: `欢迎回到 ${response.session_info.target_position} 面试！上方是我们之前的对话记录。您可以继续之前的话题，或者开始新的讨论。`,
                        timestamp: new Date().toISOString(),
                        interview_stage: 'resumed'
                    });
                } else {
                    // 如果没有历史消息，显示基本的切换消息
                    displayLangGraphMessage({
                        role: 'assistant',
                        content: `已切换到会话：${response.session_info.target_position} - ${response.session_info.target_field}\n\n这是一个新的会话，让我们开始对话吧！`,
                        timestamp: new Date().toISOString(),
                        interview_stage: 'resumed'
                    });
                }
            } catch (historyError) {
                console.warn('⚠️ 加载历史消息失败:', historyError);
                // 降级显示基本切换消息
                displayLangGraphMessage({
                    role: 'assistant',
                    content: `已切换到会话：${response.session_info.target_position} - ${response.session_info.target_field}\n\n您可以继续之前的面试对话。`,
                    timestamp: new Date().toISOString(),
                    interview_stage: 'resumed'
                });
            }
            
            // 重新渲染会话列表以更新活跃状态
            const sessions = await loadUserSessions();
            renderSessionList(sessions);
            
            // 更新智能体状态面板
            updateAgentStatusPanel({
                session_active: true,
                session_info: response.session_info,
                interview_stage: 'resumed'
            });
            
            // 通知面试完成管理器设置当前会话
            if (window.interviewCompletion) {
                await window.interviewCompletion.setCurrentSession(sessionId);
                
                // 如果面试已结束，显示相应提示
                if (window.interviewCompletion.interviewEnded) {
                    // 显示已完成面试的恢复提示
                    displayLangGraphMessage({
                        role: 'assistant',
                        content: `欢迎回到 ${response.session_info.target_position} 面试！\n\n✅ 这场面试已经结束，您可以查看生成的面试报告。\n\n如需重新面试，请创建新的面试会话。`,
                        timestamp: new Date().toISOString(),
                        interview_stage: 'completed',
                        report_available: true
                    });
                    
                    showSystemMessage(`面试已结束，报告可查看`, 'info');
                } else {
                    showSystemMessage(`已切换到 ${response.session_info.target_position} 面试`, 'success');
                }
            } else {
                showSystemMessage(`已切换到 ${response.session_info.target_position} 面试`, 'success');
            }
            
            console.log(`✅ 成功切换到会话: ${sessionId}`);
            
        } catch (error) {
            console.error('❌ 切换会话失败:', error);
            
            // 恢复之前的会话ID
            if (currentSessionId !== sessionId) {
                currentSessionId = previousSessionId;
                if (previousSessionId) {
                    localStorage.setItem('current_session_id', previousSessionId);
                } else {
                    localStorage.removeItem('current_session_id');
                }
            }
            
            showSystemMessage(`切换失败: ${error.message}`, 'error');
            renderUserInterface(); // 恢复界面
        }
    }

    /**
     * 删除指定会话
     */
    async function deleteSession(sessionId) {
        try {
            // 确认删除
            const confirmed = confirm('确定要删除这个面试会话吗？删除后无法恢复。');
            if (!confirmed) return;
            
            // 调用删除API
            const response = await callAPI(`/langgraph-chat/sessions/${sessionId}`, 'DELETE');
            if (!response.success) {
                throw new Error(response.message || '删除失败');
            }
            
            // 如果删除的是当前会话，清空当前会话状态
            if (currentSessionId === sessionId) {
                currentSessionId = null;
                localStorage.removeItem('current_session_id');
                
                // 清空消息容器
                messagesContainer.innerHTML = '';
                
                // 重新渲染欢迎界面
                renderWelcomeInterface();
            }
            
            // 重新加载并渲染会话列表
            const sessions = await loadUserSessions();
            renderSessionList(sessions);
            
            showSystemMessage('会话已删除', 'success');
            console.log(`✅ 成功删除会话: ${sessionId}`);
            
        } catch (error) {
            console.error('❌ 删除会话失败:', error);
            showSystemMessage(`删除失败: ${error.message}`, 'error');
        }
    }

    /**
     * 更新新建面试按钮状态
     */
    function updateNewInterviewButton(isProcessing) {
        if (!newInterviewBtn) return;
        
        if (isProcessing) {
            newInterviewBtn.disabled = true;
            newInterviewBtn.innerHTML = '<i class="ri-loader-line animate-spin"></i><span>创建中...</span>';
        } else {
            newInterviewBtn.disabled = false;
            newInterviewBtn.innerHTML = '<i class="ri-add-line"></i><span>新建面试</span>';
        }
    }

    /**
     * 发送面试消息 - 简化版本
     */
    async function sendLangGraphMessage() {
        const message = messageInput?.value.trim();
        if (!message || isProcessing) return;

        if (!currentSessionId) {
            showSystemMessage('请先创建面试会话', 'error');
            return;
        }

        try {
            isProcessing = true;
            updateSendButton(true);
            
            // 显示用户消息
            displayLangGraphMessage({
                role: 'user',
                content: message,
                timestamp: new Date().toISOString()
            });
            
            // 清空输入框
            messageInput.value = '';
            
            // 显示智能体思考状态
            const thinkingMessageId = showThinkingMessage();
            
            // 直接调用消息API
            const data = await callAPI('/langgraph-chat/message', 'POST', {
                session_id: currentSessionId,
                message: message
            });

            // 移除思考消息
            removeThinkingMessage(thinkingMessageId);
            
            if (data.success) {
                // 显示智能体回复
                displayLangGraphMessage({
                    role: 'assistant',
                    content: data.message,
                    timestamp: new Date().toISOString(),
                    user_profile: data.user_profile,
                    completeness_score: data.completeness_score,
                    missing_info: data.missing_info,
                    user_emotion: data.user_emotion,
                    decision: data.decision,
                    interview_stage: data.interview_stage
                });
                
                // 更新智能体状态
                updateAgentStatusPanel({
                    user_profile: data.user_profile,
                    completeness_score: data.completeness_score,
                    missing_info: data.missing_info,
                    user_emotion: data.user_emotion,
                    decision: data.decision,
                    interview_stage: data.interview_stage
                });
                
                // 检查是否为end_interview决策
                if (data.decision && data.decision.action_type === 'end_interview') {
                    // 通知面试完成管理器处理结束流程
                    if (window.interviewCompletion) {
                        window.interviewCompletion.handleEndInterviewResponse(data);
                    }
                }
                
            } else {
                // 显示错误消息
                displayLangGraphMessage({
                    role: 'assistant',
                    content: data.message || '抱歉，我遇到了一些问题。',
                    timestamp: new Date().toISOString(),
                    error: data.error
                });
            }
            
        } catch (error) {
            console.error('❌ 发送消息失败:', error);
            
            // 移除思考消息
            if (typeof thinkingMessageId !== 'undefined') {
                removeThinkingMessage(thinkingMessageId);
            }
            
            displayLangGraphMessage({
                role: 'assistant', 
                content: `抱歉，我遇到了技术问题：${error.message}`,
                timestamp: new Date().toISOString(),
                error: error.message
            });
        } finally {
            isProcessing = false;
            updateSendButton(false);
        }
    }

    // ==================== 流式响应处理 ====================

    async function sendLangGraphMessageStream() {
        const message = messageInput?.value.trim();
        if (!message || isProcessing) return;

        if (!currentSessionId) {
            showSystemMessage('请先创建面试会话', 'error');
            return;
        }

        try {
            isProcessing = true;
            updateSendButton(true);
            
            // 显示用户消息
            displayLangGraphMessage({
                role: 'user',
                content: message,
                timestamp: new Date().toISOString()
            });
            
            messageInput.value = '';
            
            // 创建流式响应容器
            const streamMessageId = createStreamMessage();
            
            // 发送流式请求
            const token = localStorage.getItem('access_token');
            const response = await fetch('/api/v1/langgraph-chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    message: message
                })
            });

            if (!response.ok) {
                throw new Error(`流式响应失败: ${response.status}`);
            }

            // 处理流式响应
            await handleStreamResponse(response, streamMessageId);
            
        } catch (error) {
            console.error('❌ 流式消息失败:', error);
            showSystemMessage(`处理失败: ${error.message}`, 'error');
        } finally {
            isProcessing = false;
            updateSendButton(false);
        }
    }

    async function handleStreamResponse(response, messageId) {
        const reader = response.body.getReader();
        let accumulatedText = '';
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = new TextDecoder().decode(value);
                const lines = chunk.split('\\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            switch (data.type) {
                                case 'start':
                                    updateStreamMessage(messageId, '🧠 智能体开始思考...', true);
                                    break;
                                    
                                case 'progress':
                                    updateStreamMessage(messageId, `${data.message} (${data.step}/${data.total})`, true);
                                    break;
                                    
                                case 'chunk':
                                    accumulatedText += data.content;
                                    updateStreamMessage(messageId, accumulatedText, false);
                                    break;
                                    
                                case 'complete':
                                    updateStreamMessage(messageId, accumulatedText, false);
                                    
                                    // 更新智能体状态
                                    updateAgentStatusPanel({
                                        user_profile: data.user_profile,
                                        completeness_score: data.completeness_score,
                                        user_emotion: data.user_emotion,
                                        decision: data.decision,
                                        missing_info: data.missing_info
                                    });
                                    break;
                                    
                                case 'error':
                                    updateStreamMessage(messageId, `错误: ${data.error}`, false, true);
                                    break;
                                    
                                case 'end':
                                    return;
                            }
                        } catch (error) {
                            console.error('解析流式数据失败:', error);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('读取流式响应失败:', error);
            updateStreamMessage(messageId, '处理响应时出错', false, true);
        }
    }

    // ==================== UI更新函数 ====================

    function displayLangGraphMessage(messageData) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message-slide-in mb-6';
        
        const isUser = messageData.role === 'user';
        const isError = messageData.error;
        const alignmentClass = isUser ? 'justify-end' : 'justify-start';
        const bgColor = isError ? 'bg-red-100 border border-red-300' : 
                       isUser ? 'bg-primary text-white' : 'bg-gray-100 text-gray-900';
        
        let roleDisplay = '';
        if (!isUser) {
            const statusIcon = messageData.decision ? getDecisionIcon(messageData.decision.action_type) : '🤖';
            roleDisplay = `
                <div class="flex items-center space-x-2 mb-2">
                    <span class="text-lg">${statusIcon}</span>
                    <span class="text-sm font-medium">LangGraph智能体</span>
                    ${messageData.user_emotion ? `<span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">${getEmotionDisplay(messageData.user_emotion)}</span>` : ''}
                    ${messageData.completeness_score !== undefined ? `<span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">完整度${Math.round(messageData.completeness_score * 100)}%</span>` : ''}
                </div>
            `;
        }
        
        messageDiv.innerHTML = `
            <div class="flex ${alignmentClass}">
                <div class="max-w-3xl ${bgColor} rounded-lg p-4 shadow-sm">
                    ${roleDisplay}
                    <div class="message-content whitespace-pre-wrap">${messageData.content}</div>
                    ${messageData.timestamp ? `<div class="text-xs opacity-70 mt-2">${new Date(messageData.timestamp).toLocaleTimeString()}</div>` : ''}
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        scrollToBottom();
    }

    function showThinkingMessage() {
        const messageId = 'thinking-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.id = messageId;
        messageDiv.className = 'message-slide-in mb-6';
        messageDiv.innerHTML = `
            <div class="flex justify-start">
                <div class="max-w-3xl bg-gray-100 text-gray-900 rounded-lg p-4 shadow-sm">
                    <div class="flex items-center space-x-2 mb-2">
                        <i class="ri-robot-line text-blue-600"></i>
                        <span class="text-sm font-medium">LangGraph智能体</span>
                    </div>
                    <div class="flex items-center space-x-2">
                        <div class="loading-dots">
                            <div class="dot"></div>
                            <div class="dot"></div>
                            <div class="dot"></div>
                        </div>
                        <span class="text-sm text-gray-600">正在感知和决策...</span>
                    </div>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        scrollToBottom();
        return messageId;
    }

    function removeThinkingMessage(messageId) {
        const element = document.getElementById(messageId);
        if (element) {
            element.remove();
        }
    }

    function createStreamMessage() {
        const messageId = 'stream-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.id = messageId;
        messageDiv.className = 'message-slide-in mb-6';
        messageDiv.innerHTML = `
            <div class="flex justify-start">
                <div class="max-w-3xl bg-gray-100 text-gray-900 rounded-lg p-4 shadow-sm">
                    <div class="flex items-center space-x-2 mb-2">
                        <i class="ri-robot-line text-blue-600"></i>
                        <span class="text-sm font-medium">LangGraph智能体</span>
                    </div>
                    <div class="message-content"></div>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        scrollToBottom();
        return messageId;
    }

    function updateStreamMessage(messageId, content, isThinking = false, isError = false) {
        const element = document.getElementById(messageId);
        if (element) {
            const contentDiv = element.querySelector('.message-content');
            if (contentDiv) {
                if (isThinking) {
                    contentDiv.innerHTML = `
                        <div class="flex items-center space-x-2">
                            <div class="loading-dots">
                                <div class="dot"></div>
                                <div class="dot"></div>  
                                <div class="dot"></div>
                            </div>
                            <span class="text-sm text-gray-600">${content}</span>
                        </div>
                    `;
                } else {
                    contentDiv.className = `message-content whitespace-pre-wrap ${isError ? 'text-red-600' : ''}`;
                    contentDiv.textContent = content;
                }
            }
            scrollToBottom();
        }
    }

    function showSystemMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        const typeClasses = {
            'info': 'bg-blue-50 border-blue-200 text-blue-800',
            'success': 'bg-green-50 border-green-200 text-green-800', 
            'error': 'bg-red-50 border-red-200 text-red-800',
            'warning': 'bg-yellow-50 border-yellow-200 text-yellow-800'
        };
        
        messageDiv.className = `message-slide-in mb-4 p-3 border rounded-lg ${typeClasses[type] || typeClasses.info}`;
        messageDiv.innerHTML = `
            <div class="flex items-center space-x-2">
                <i class="ri-information-line"></i>
                <span>${message}</span>
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        scrollToBottom();
        
        // 3秒后自动移除
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 3000);
    }

    function updateSendButton(isProcessing) {
        if (!sendButton) return;
        
        if (isProcessing) {
            sendButton.disabled = true;
            sendButton.innerHTML = '<i class="ri-loader-line animate-spin"></i>';
        } else {
            sendButton.disabled = false;
            sendButton.textContent = '发送';
        }
    }

    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    // ==================== 智能体状态面板 ====================

    function initializeAgentStatusPanel() {
        // 更新右侧分析面板为智能体状态
        const analysisPanel = document.getElementById('analysisPanel');
        if (analysisPanel) {
            // 保持原有的折叠功能
            const collapseToggle = analysisPanel.querySelector('#collapseToggle');
            
            // 替换内容为智能体状态面板
            analysisPanel.innerHTML = `
                <div class="relative">
                    <button id="collapseToggle" class="absolute -left-8 top-1/2 -translate-y-1/2 w-8 h-16 bg-gray-50 border border-l-0 border-gray-100 rounded-l-lg flex items-center justify-center transition-colors hover:bg-gray-100 !rounded-none">
                        <i class="ri-arrow-right-s-line text-gray-600 transition-transform duration-300"></i>
                    </button>
                    <div class="p-4 border-b border-gray-100">
                        <h3 class="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                            <i class="ri-robot-line text-blue-600"></i>
                            <span>LangGraph智能体</span>
                        </h3>
                    </div>
                </div>
                <div class="flex-1 overflow-y-auto p-4 space-y-4">
                    <!-- 感知状态 -->
                    <div class="bg-white rounded-lg p-4 border border-gray-200">
                        <div class="flex items-center space-x-2 mb-3">
                            <div class="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
                                <i class="ri-eye-line text-blue-600 text-sm"></i>
                            </div>
                            <h4 class="text-sm font-medium text-gray-900">🧠 感知层</h4>
                        </div>
                        <div id="perception-status" class="space-y-2 text-xs">
                            <div class="flex justify-between">
                                <span class="text-gray-600">信息完整度:</span>
                                <span id="completeness-score" class="font-medium text-blue-600">0%</span>
                            </div>
                            <div class="w-full bg-gray-200 rounded-full h-2">
                                <div id="completeness-bar" class="bg-gradient-to-r from-red-400 via-yellow-400 to-green-500 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                            </div>
                            <div id="user-emotion" class="text-gray-600">
                                <span>用户情绪:</span>
                                <span id="emotion-display" class="ml-1 px-2 py-0.5 bg-gray-100 rounded text-gray-700">未知</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 决策状态 -->
                    <div class="bg-white rounded-lg p-4 border border-gray-200">
                        <div class="flex items-center space-x-2 mb-3">
                            <div class="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center">
                                <i class="ri-brain-line text-purple-600 text-sm"></i>
                            </div>
                            <h4 class="text-sm font-medium text-gray-900">🤖 决策层</h4>
                        </div>
                        <div id="decision-status" class="space-y-2 text-xs">
                            <div>
                                <span class="text-gray-600">当前策略:</span>
                                <span id="decision-action" class="ml-1 px-2 py-0.5 bg-purple-100 text-purple-800 rounded">等待中</span>
                            </div>
                            <div id="decision-reasoning" class="text-gray-600 text-xs">
                                <span class="font-medium">推理:</span>
                                <div id="reasoning-text" class="mt-1 text-gray-500">等待用户输入...</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 行动状态 -->
                    <div class="bg-white rounded-lg p-4 border border-gray-200">
                        <div class="flex items-center space-x-2 mb-3">
                            <div class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
                                <i class="ri-flashlight-line text-green-600 text-sm"></i>
                            </div>
                            <h4 class="text-sm font-medium text-gray-900">⚡ 行动层</h4>
                        </div>
                        <div id="action-status" class="space-y-2 text-xs">
                            <div id="recent-actions" class="text-gray-600">
                                <span class="font-medium">最近行动:</span>
                                <div id="action-timeline" class="mt-1 space-y-1 text-gray-500">
                                    <div class="text-center py-2">暂无行动记录</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // 重新绑定折叠功能
            bindCollapsePanelToggle();
        }
    }

    function updateAgentStatusPanel(statusData) {
        // 更新感知状态
        if (statusData.completeness_score !== undefined) {
            const completenessScore = document.getElementById('completeness-score');
            const completenessBar = document.getElementById('completeness-bar');
            
            const percentage = Math.round(statusData.completeness_score * 100);
            if (completenessScore) completenessScore.textContent = percentage + '%';
            if (completenessBar) completenessBar.style.width = percentage + '%';
        }
        
        // 更新用户情绪
        if (statusData.user_emotion) {
            const emotionDisplay = document.getElementById('emotion-display');
            if (emotionDisplay) {
                emotionDisplay.textContent = getEmotionDisplay(statusData.user_emotion);
                emotionDisplay.className = `ml-1 px-2 py-0.5 rounded text-xs ${getEmotionClass(statusData.user_emotion)}`;
            }
        }
        
        // 更新决策状态
        if (statusData.decision) {
            const decisionAction = document.getElementById('decision-action');
            const reasoningText = document.getElementById('reasoning-text');
            
            if (decisionAction) {
                decisionAction.textContent = getActionDisplay(statusData.decision.action_type);
                decisionAction.className = `ml-1 px-2 py-0.5 rounded text-xs ${getActionClass(statusData.decision.action_type)}`;
            }
            
            if (reasoningText) {
                reasoningText.textContent = statusData.decision.reasoning || '智能决策中...';
            }
        }
        
        // 更新行动记录
        if (statusData.decision && statusData.decision.action_type) {
            addActionToTimeline(statusData.decision.action_type, getActionDisplay(statusData.decision.action_type));
        }
    }

    function addActionToTimeline(actionType, description) {
        const timeline = document.getElementById('action-timeline');
        if (!timeline) return;
        
        const time = new Date().toLocaleTimeString('zh-CN', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit' 
        });
        
        // 如果是首次添加，清除"暂无行动记录"
        if (timeline.querySelector('.text-center')) {
            timeline.innerHTML = '';
        }
        
        const actionItem = document.createElement('div');
        actionItem.className = 'flex items-center space-x-2 text-xs text-gray-600';
        actionItem.innerHTML = `
            <span class="text-gray-400">${time}</span>
            <span class="w-1 h-1 bg-green-500 rounded-full"></span>
            <span>${description}</span>
        `;
        
        timeline.insertBefore(actionItem, timeline.firstChild);
        
        // 保持最多5个记录
        while (timeline.children.length > 5) {
            timeline.removeChild(timeline.lastChild);
        }
    }

    // ==================== 工具函数 ====================

    function getDecisionIcon(actionType) {
        const icons = {
            'ask_question': '❓',
            'provide_comfort': '🤗',
            'generate_question': '📝',
            'update_database': '💾'
        };
        return icons[actionType] || '🤖';
    }

    function getEmotionDisplay(emotion) {
        const emotions = {
            'neutral': '中性',
            'anxious': '紧张', 
            'confident': '自信',
            'confused': '困惑'
        };
        return emotions[emotion] || emotion;
    }

    function getEmotionClass(emotion) {
        const classes = {
            'neutral': 'bg-gray-100 text-gray-700',
            'anxious': 'bg-yellow-100 text-yellow-700',
            'confident': 'bg-green-100 text-green-700',
            'confused': 'bg-blue-100 text-blue-700'
        };
        return classes[emotion] || 'bg-gray-100 text-gray-700';
    }

    function getActionDisplay(actionType) {
        const actions = {
            'ask_question': '询问信息',
            'provide_comfort': '情感支持',
            'generate_question': '生成问题',
            'update_database': '更新数据'
        };
        return actions[actionType] || actionType;
    }

    function getActionClass(actionType) {
        const classes = {
            'ask_question': 'bg-blue-100 text-blue-800',
            'provide_comfort': 'bg-green-100 text-green-800',
            'generate_question': 'bg-purple-100 text-purple-800',
            'update_database': 'bg-orange-100 text-orange-800'
        };
        return classes[actionType] || 'bg-gray-100 text-gray-800';
    }

    function bindCollapsePanelToggle() {
        const collapseToggle = document.getElementById('collapseToggle');
        if (collapseToggle) {
            collapseToggle.addEventListener('click', function() {
                // 简化的折叠功能
                const panel = document.getElementById('analysisPanel');
                if (panel) {
                    panel.classList.toggle('collapsed');
                }
            });
        }
    }

    // ==================== UI渲染函数 ====================

    /**
     * 渲染会话选择界面（有会话的用户）
     */
    function renderSessionSelection(sessions) {
        console.log('🎨 渲染会话选择界面');
        
        const messagesContainer = document.getElementById('chat-messages-container');
        if (!messagesContainer) return;
        
        messagesContainer.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full py-12 px-6">
                <div class="max-w-2xl w-full text-center space-y-8">
                    <!-- 欢迎回来 -->
                    <div class="space-y-3">
                        <h1 class="text-3xl font-bold text-gray-900">
                            欢迎回来，${getUserName()}！
                        </h1>
                        <p class="text-gray-600 text-lg">
                            选择一个会话继续面试，或创建新的面试会话
                        </p>
                    </div>
                    
                    <!-- 最近会话 -->
                    <div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
                        <div class="bg-gray-50 px-6 py-4 border-b border-gray-200">
                            <h2 class="text-lg font-semibold text-gray-900 flex items-center">
                                <i class="ri-history-line text-blue-600 mr-2"></i>
                                最近的面试会话
                            </h2>
                        </div>
                        <div class="divide-y divide-gray-200 max-h-80 overflow-y-auto">
                            ${sessions.slice(0, 5).map(session => `
                                <div class="p-6 hover:bg-gray-50 cursor-pointer transition-colors session-item" 
                                     onclick="switchToSession('${session.session_id}')">
                                    <div class="flex items-center justify-between">
                                        <div class="flex-1">
                                            <h3 class="font-medium text-gray-900 mb-1">
                                                ${session.target_position || '面试会话'} - ${session.target_field || '技术面试'}
                                            </h3>
                                            <p class="text-sm text-gray-600 mb-2">
                                                创建时间: ${new Date(session.created_at).toLocaleString('zh-CN')}
                                            </p>
                                            ${session.last_activity ? `
                                                <p class="text-xs text-gray-500">
                                                    最后活跃: ${new Date(session.last_activity).toLocaleString('zh-CN')}
                                                </p>
                                            ` : ''}
                                        </div>
                                        <div class="flex items-center space-x-2 ml-4">
                                            <span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">
                                                活跃
                                            </span>
                                            <i class="ri-arrow-right-s-line text-gray-400"></i>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div class="flex justify-center space-x-4">
                        <button id="continue-last-session" 
                                class="bg-blue-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
                            <i class="ri-play-line mr-2"></i>
                            继续最近的会话
                        </button>
                        <button onclick="createNewLangGraphSession()" 
                                class="border border-gray-300 text-gray-700 px-8 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors">
                            <i class="ri-add-line mr-2"></i>
                            创建新面试
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // 绑定继续最近会话的事件
        const continueBtn = document.getElementById('continue-last-session');
        if (continueBtn && sessions.length > 0) {
            continueBtn.addEventListener('click', () => {
                switchToSession(sessions[0].session_id);
            });
        }
    }

    /**
     * 渲染左侧会话列表
     */
    function renderSessionList(sessions) {
        console.log(`📋 渲染会话列表: ${sessions.length} 个会话`);
        
        // 找到左侧会话列表容器
        const sessionListContainer = document.querySelector('.w-80 .flex-1.overflow-y-auto');
        if (!sessionListContainer) {
            console.warn('未找到会话列表容器');
            return;
        }
        
        // 清空现有内容
        sessionListContainer.innerHTML = '';
        
        if (sessions.length === 0) {
            // 显示空状态
            sessionListContainer.innerHTML = `
                <div class="flex flex-col items-center justify-center py-8 text-center">
                    <div class="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                        <i class="ri-chat-3-line text-gray-400 text-xl"></i>
                    </div>
                    <p class="text-sm text-gray-500 mb-1">暂无面试记录</p>
                    <p class="text-xs text-gray-400">点击上方按钮开始新面试</p>
                </div>
            `;
            return;
        }
        
        // 渲染会话列表
        sessions.forEach((session, index) => {
            const isActive = session.session_id === currentSessionId;
            const sessionItem = document.createElement('div');
            sessionItem.className = `
                session-item cursor-pointer p-3 rounded-lg border transition-all duration-200 hover:shadow-sm
                ${isActive ? 
                    'bg-blue-50 border-blue-200 shadow-sm' : 
                    'bg-white border-gray-200 hover:bg-gray-50'
                }
            `;
            
            // 计算时间差
            const createdTime = new Date(session.created_at);
            const now = new Date();
            const diffHours = Math.floor((now - createdTime) / (1000 * 60 * 60));
            let timeDisplay = '';
            
            if (diffHours < 1) {
                timeDisplay = '刚刚创建';
            } else if (diffHours < 24) {
                timeDisplay = `${diffHours}小时前`;
            } else {
                const diffDays = Math.floor(diffHours / 24);
                if (diffDays === 1) {
                    timeDisplay = '昨天';
                } else if (diffDays < 7) {
                    timeDisplay = `${diffDays}天前`;
                } else {
                    timeDisplay = createdTime.toLocaleDateString('zh-CN', { 
                        month: 'short', 
                        day: 'numeric' 
                    });
                }
            }
            
            sessionItem.innerHTML = `
                <div class="flex items-start space-x-3">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center ${
                            isActive ? 'bg-blue-100' : 'bg-gray-100'
                        }">
                            <i class="ri-briefcase-line text-sm ${
                                isActive ? 'text-blue-600' : 'text-gray-600'
                            }"></i>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-1">
                            <h4 class="text-sm font-medium text-gray-900 truncate">
                                ${session.target_position || '面试会话'}
                            </h4>
                            ${isActive ? '<i class="ri-checkbox-circle-fill text-blue-600 text-sm flex-shrink-0"></i>' : ''}
                        </div>
                        <p class="text-xs text-gray-600 mb-1">
                            ${session.target_field || '技术面试'}
                        </p>
                        <div class="flex items-center justify-between">
                            <span class="text-xs text-gray-500">${timeDisplay}</span>
                            <div class="flex space-x-1">
                                ${session.interview_ended ? `
                                    <span class="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                                        已完成
                                    </span>
                                ` : ''}
                                ${isActive ? `
                                    <span class="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                                        当前
                                    </span>
                                ` : `
                                    <button class="session-switch-btn p-1 hover:bg-gray-200 rounded transition-colors" 
                                            data-session-id="${session.session_id}"
                                            title="切换到此会话">
                                        <i class="ri-arrow-right-s-line text-gray-400 text-xs"></i>
                                    </button>
                                `}
                                ${session.report_id ? `
                                    <button class="session-report-btn p-1 hover:bg-green-100 rounded transition-colors" 
                                            data-session-id="${session.session_id}"
                                            data-report-id="${session.report_id}"
                                            title="查看报告">
                                        <i class="ri-file-text-line text-gray-400 hover:text-green-600 text-xs"></i>
                                    </button>
                                ` : ''}
                                <button class="session-delete-btn p-1 hover:bg-red-100 rounded transition-colors" 
                                        data-session-id="${session.session_id}"
                                        title="删除会话">
                                    <i class="ri-delete-bin-line text-gray-400 hover:text-red-600 text-xs"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // 绑定点击切换事件
            if (!isActive) {
                sessionItem.addEventListener('click', (e) => {
                    // 排除按钮点击
                    if (!e.target.closest('button')) {
                        switchToSession(session.session_id);
                    }
                });
            }
            
            sessionListContainer.appendChild(sessionItem);
        });
        
        // 绑定切换和删除按钮事件
        bindSessionListEvents();
    }

    /**
     * 绑定会话列表事件
     */
    function bindSessionListEvents() {
        // 切换会话按钮事件
        document.querySelectorAll('.session-switch-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // 防止触发父级点击事件
                const sessionId = button.dataset.sessionId;
                switchToSession(sessionId);
            });
        });
        
        // 查看报告按钮事件
        document.querySelectorAll('.session-report-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // 防止触发父级点击事件
                const sessionId = button.dataset.sessionId;
                const reportId = button.dataset.reportId;
                
                if (reportId) {
                    // 直接跳转到报告页面
                    const reportUrl = `./interview_report.html?session_id=${sessionId}&report_id=${reportId}`;
                    window.open(reportUrl, '_blank');
                } else {
                    console.warn('⚠️ 报告ID缺失');
                }
            });
        });
        
        // 删除会话按钮事件
        document.querySelectorAll('.session-delete-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // 防止触发父级点击事件
                const sessionId = button.dataset.sessionId;
                deleteSession(sessionId);
            });
        });
    }
    
    /**
     * 渲染新用户欢迎界面
     */
    function renderWelcomeInterface() {
        console.log('🎨 渲染新用户欢迎界面');
        
        const messagesContainer = document.getElementById('chat-messages-container');
        if (!messagesContainer) return;
        
        // 清空加载状态
        messagesContainer.innerHTML = '';
        
        // 渲染欢迎界面
        const welcomeHTML = `
            <div class="flex flex-col items-center justify-center h-full py-12 px-6">
                <div class="max-w-md text-center space-y-6">
                    <!-- 欢迎图标 -->
                    <div class="w-24 h-24 mx-auto bg-gradient-to-br from-blue-100 to-purple-100 rounded-full flex items-center justify-center">
                        <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                            <i class="ri-robot-line text-white text-2xl"></i>
                        </div>
                    </div>
                    
                    <!-- 欢迎标题 -->
                    <div class="space-y-3">
                        <h1 class="text-2xl font-bold text-gray-900">
                            欢迎来到 <span class="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">职面星火</span>
                        </h1>
                        <p class="text-gray-600 text-lg">
                            AI智能面试官，助力您的求职之路
                        </p>
                    </div>
                    
                    <!-- 功能介绍 -->
                    <div class="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 space-y-4">
                        <h2 class="text-lg font-semibold text-gray-900 flex items-center justify-center">
                            <i class="ri-lightbulb-line text-blue-600 mr-2"></i>
                            AI面试官能为您做什么
                        </h2>
                        <div class="grid gap-3 text-sm text-gray-700">
                            <div class="flex items-start space-x-2">
                                <i class="ri-check-line text-green-500 mt-0.5 flex-shrink-0"></i>
                                <span><strong>智能提问</strong> - 根据您的简历和目标岗位个性化面试问题</span>
                            </div>
                            <div class="flex items-start space-x-2">
                                <i class="ri-check-line text-green-500 mt-0.5 flex-shrink-0"></i>
                                <span><strong>实时分析</strong> - 微表情、语音语调、回答质量全方位评估</span>
                            </div>
                            <div class="flex items-start space-x-2">
                                <i class="ri-check-line text-green-500 mt-0.5 flex-shrink-0"></i>
                                <span><strong>STAR指导</strong> - 帮助您结构化表达，提升面试表现</span>
                            </div>
                            <div class="flex items-start space-x-2">
                                <i class="ri-check-line text-green-500 mt-0.5 flex-shrink-0"></i>
                                <span><strong>专业复盘</strong> - 详细的面试报告和改进建议</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 开始按钮 -->
                    <div class="space-y-4">
                        <button id="welcome-start-btn" class="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white px-8 py-4 rounded-xl font-medium text-lg hover:from-blue-700 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5">
                            <i class="ri-play-circle-line mr-2"></i>
                            开始我的第一次AI面试
                        </button>
                        
                        <div class="flex items-center justify-center space-x-4 text-sm text-gray-500">
                            <div class="flex items-center space-x-1">
                                <i class="ri-shield-check-line text-green-500"></i>
                                <span>隐私安全</span>
                            </div>
                            <div class="w-px h-4 bg-gray-300"></div>
                            <div class="flex items-center space-x-1">
                                <i class="ri-time-line text-blue-500"></i>
                                <span>随时开始</span>
                            </div>
                            <div class="w-px h-4 bg-gray-300"></div>
                            <div class="flex items-center space-x-1">
                                <i class="ri-star-line text-yellow-500"></i>
                                <span>专业指导</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 温馨提示 -->
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left">
                        <div class="flex items-start space-x-2">
                            <i class="ri-information-line text-blue-600 mt-0.5 flex-shrink-0"></i>
                            <div class="text-sm text-blue-800">
                                <p class="font-medium mb-1">开始前的小提示：</p>
                                <ul class="space-y-1 text-blue-700">
                                    <li>• 请确保网络连接稳定</li>
                                    <li>• 建议在安静的环境中进行</li>
                                    <li>• 准备好您的简历信息</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        messagesContainer.innerHTML = welcomeHTML;
        
        // 绑定开始按钮事件
        const welcomeStartBtn = document.getElementById('welcome-start-btn');
        if (welcomeStartBtn) {
            welcomeStartBtn.addEventListener('click', handleWelcomeStart);
        }
        
        // 添加欢迎动画
        const welcomeContainer = messagesContainer.querySelector('.flex.flex-col');
        if (welcomeContainer) {
            welcomeContainer.style.opacity = '0';
            welcomeContainer.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                welcomeContainer.style.transition = 'all 0.6s ease-out';
                welcomeContainer.style.opacity = '1';
                welcomeContainer.style.transform = 'translateY(0)';
            }, 100);
        }
    }
    

    
    /**
     * 渲染登录提示界面
     */
    function renderLoginPrompt() {
        console.log('🔐 渲染登录提示界面');
        
        const messagesContainer = document.getElementById('chat-messages-container');
        if (!messagesContainer) return;
        
        // 清空现有内容
        messagesContainer.innerHTML = '';
        
        const loginPromptHTML = `
            <div class="flex flex-col items-center justify-center h-full py-12 px-6">
                <div class="max-w-md text-center space-y-6">
                    <!-- 登录图标 -->
                    <div class="w-20 h-20 mx-auto bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full flex items-center justify-center">
                        <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center">
                            <i class="ri-lock-line text-white text-xl"></i>
                        </div>
                    </div>
                    
                    <!-- 提示内容 -->
                    <div class="space-y-3">
                        <h1 class="text-2xl font-bold text-gray-900">
                            需要登录才能使用
                        </h1>
                        <p class="text-gray-600">
                            请先登录您的账户，然后开始AI面试体验
                        </p>
                    </div>
                    
                    <!-- 功能预览 -->
                    <div class="bg-gray-50 rounded-lg p-6 space-y-3">
                        <h3 class="font-medium text-gray-900 flex items-center justify-center">
                            <i class="ri-star-line text-yellow-500 mr-2"></i>
                            登录后您可以体验
                        </h3>
                        <div class="grid gap-2 text-sm text-gray-600">
                            <div class="flex items-center space-x-2">
                                <i class="ri-checkbox-circle-line text-green-500"></i>
                                <span>个性化AI面试问题</span>
                            </div>
                            <div class="flex items-center space-x-2">
                                <i class="ri-checkbox-circle-line text-green-500"></i>
                                <span>实时面试表现分析</span>
                            </div>
                            <div class="flex items-center space-x-2">
                                <i class="ri-checkbox-circle-line text-green-500"></i>
                                <span>面试历史记录保存</span>
                            </div>
                            <div class="flex items-center space-x-2">
                                <i class="ri-checkbox-circle-line text-green-500"></i>
                                <span>专业面试报告生成</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div class="space-y-3">
                        <button id="goto-login-btn" class="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
                            <i class="ri-login-circle-line mr-2"></i>
                            前往登录
                        </button>
                        
                        <button id="goto-register-btn" class="w-full border border-gray-300 text-gray-700 px-6 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors">
                            <i class="ri-user-add-line mr-2"></i>
                            还没有账户？立即注册
                        </button>
                        
                        <div class="flex items-center justify-center pt-4">
                            <button id="refresh-auth-btn" class="text-sm text-blue-600 hover:text-blue-800 hover:underline">
                                <i class="ri-refresh-line mr-1"></i>
                                已登录？刷新页面
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        messagesContainer.innerHTML = loginPromptHTML;
        
        // 绑定按钮事件
        const gotoLoginBtn = document.getElementById('goto-login-btn');
        const gotoRegisterBtn = document.getElementById('goto-register-btn');
        const refreshAuthBtn = document.getElementById('refresh-auth-btn');
        
        if (gotoLoginBtn) {
            gotoLoginBtn.addEventListener('click', () => {
                console.log('🔄 跳转到登录页面');
                window.location.href = '/frontend/login.html';
            });
        }
        
        if (gotoRegisterBtn) {
            gotoRegisterBtn.addEventListener('click', () => {
                console.log('🔄 跳转到注册页面');
                window.location.href = '/frontend/register.html';
            });
        }
        
        if (refreshAuthBtn) {
            refreshAuthBtn.addEventListener('click', () => {
                console.log('🔄 刷新认证状态');
                location.reload();
            });
        }
        
        // 添加进入动画
        const loginContainer = messagesContainer.querySelector('.flex.flex-col');
        if (loginContainer) {
            loginContainer.style.opacity = '0';
            loginContainer.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                loginContainer.style.transition = 'all 0.5s ease-out';
                loginContainer.style.opacity = '1';
                loginContainer.style.transform = 'translateY(0)';
            }, 100);
        }
    }
    
    /**
     * 渲染Token过期提示界面
     */
    function renderTokenExpiredPrompt() {
        console.log('⏰ 渲染Token过期提示界面');
        
        const messagesContainer = document.getElementById('chat-messages-container');
        if (!messagesContainer) return;
        
        messagesContainer.innerHTML = '';
        
        const expiredPromptHTML = `
            <div class="flex flex-col items-center justify-center h-full py-12 px-6">
                <div class="max-w-md text-center space-y-6">
                    <!-- 过期图标 -->
                    <div class="w-20 h-20 mx-auto bg-gradient-to-br from-orange-100 to-red-100 rounded-full flex items-center justify-center">
                        <div class="w-12 h-12 bg-gradient-to-br from-orange-500 to-red-600 rounded-full flex items-center justify-center">
                            <i class="ri-time-line text-white text-xl"></i>
                        </div>
                    </div>
                    
                    <!-- 提示内容 -->
                    <div class="space-y-3">
                        <h1 class="text-2xl font-bold text-gray-900">
                            登录状态已过期
                        </h1>
                        <p class="text-gray-600">
                            为了保护您的账户安全，登录状态已过期<br/>
                            请重新登录继续使用
                        </p>
                    </div>
                    
                    <!-- 安全提示 -->
                    <div class="bg-orange-50 border border-orange-200 rounded-lg p-4">
                        <div class="flex items-start space-x-2">
                            <i class="ri-shield-check-line text-orange-600 mt-0.5 flex-shrink-0"></i>
                            <div class="text-sm text-orange-800">
                                <p class="font-medium mb-1">安全保护</p>
                                <p>系统会定期清理过期的登录状态，确保您的账户安全。</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div class="space-y-3">
                        <button id="relogin-btn" class="w-full bg-orange-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-orange-700 transition-colors">
                            <i class="ri-login-circle-line mr-2"></i>
                            重新登录
                        </button>
                        
                        <button id="back-home-btn" class="w-full border border-gray-300 text-gray-700 px-6 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors">
                            <i class="ri-home-line mr-2"></i>
                            返回首页
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        messagesContainer.innerHTML = expiredPromptHTML;
        
        // 绑定按钮事件
        const reloginBtn = document.getElementById('relogin-btn');
        const backHomeBtn = document.getElementById('back-home-btn');
        
        if (reloginBtn) {
            reloginBtn.addEventListener('click', () => {
                window.location.href = '/frontend/login.html';
            });
        }
        
        if (backHomeBtn) {
            backHomeBtn.addEventListener('click', () => {
                window.location.href = '/index.html';
            });
        }
        
        // 添加动画
        const expiredContainer = messagesContainer.querySelector('.flex.flex-col');
        if (expiredContainer) {
            expiredContainer.style.opacity = '0';
            expiredContainer.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                expiredContainer.style.transition = 'all 0.5s ease-out';
                expiredContainer.style.opacity = '1';
                expiredContainer.style.transform = 'translateY(0)';
            }, 100);
        }
    }
    
    /**
     * 渲染网络错误提示界面
     */
    function renderNetworkErrorPrompt() {
        console.log('🌐 渲染网络错误提示界面');
        
        const messagesContainer = document.getElementById('chat-messages-container');
        if (!messagesContainer) return;
        
        messagesContainer.innerHTML = '';
        
        const networkErrorHTML = `
            <div class="flex flex-col items-center justify-center h-full py-12 px-6">
                <div class="max-w-md text-center space-y-6">
                    <!-- 网络错误图标 -->
                    <div class="w-20 h-20 mx-auto bg-gradient-to-br from-red-100 to-pink-100 rounded-full flex items-center justify-center">
                        <div class="w-12 h-12 bg-gradient-to-br from-red-500 to-pink-600 rounded-full flex items-center justify-center">
                            <i class="ri-wifi-off-line text-white text-xl"></i>
                        </div>
                    </div>
                    
                    <!-- 提示内容 -->
                    <div class="space-y-3">
                        <h1 class="text-2xl font-bold text-gray-900">
                            网络连接异常
                        </h1>
                        <p class="text-gray-600">
                            无法连接到服务器，请检查网络连接<br/>
                            或稍后重试
                        </p>
                    </div>
                    
                    <!-- 故障排除 -->
                    <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-left">
                        <div class="flex items-start space-x-2">
                            <i class="ri-question-line text-red-600 mt-0.5 flex-shrink-0"></i>
                            <div class="text-sm text-red-800">
                                <p class="font-medium mb-2">可能的解决方案：</p>
                                <ul class="space-y-1 text-red-700">
                                    <li>• 检查您的网络连接</li>
                                    <li>• 刷新页面重试</li>
                                    <li>• 稍后再试</li>
                                    <li>• 联系技术支持</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div class="space-y-3">
                        <button id="retry-connection-btn" class="w-full bg-red-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-red-700 transition-colors">
                            <i class="ri-refresh-line mr-2"></i>
                            重新尝试
                        </button>
                        
                        <button id="goto-home-btn" class="w-full border border-gray-300 text-gray-700 px-6 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors">
                            <i class="ri-home-line mr-2"></i>
                            返回首页
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        messagesContainer.innerHTML = networkErrorHTML;
        
        // 绑定按钮事件
        const retryBtn = document.getElementById('retry-connection-btn');
        const gotoHomeBtn = document.getElementById('goto-home-btn');
        
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                location.reload();
            });
        }
        
        if (gotoHomeBtn) {
            gotoHomeBtn.addEventListener('click', () => {
                window.location.href = '/index.html';
            });
        }
        
        // 添加动画
        const errorContainer = messagesContainer.querySelector('.flex.flex-col');
        if (errorContainer) {
            errorContainer.style.opacity = '0';
            errorContainer.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                errorContainer.style.transition = 'all 0.5s ease-out';
                errorContainer.style.opacity = '1';
                errorContainer.style.transform = 'translateY(0)';
            }, 100);
        }
    }

    /**
     * 显示面试配置弹窗
     */
    async function showInterviewConfigModal() {
        try {
            console.log('📋 直接获取简历列表...');
            
            // 显示加载状态
            showLoadingState('正在加载简历列表...');
            
            // 直接调用API获取简历列表
            const resumes = await loadResumesList();
            
            console.log(`📄 找到 ${resumes.length} 个简历`);
            
            // 如果没有简历，提示用户创建
            if (resumes.length === 0) {
                showNoResumeModal();
                return;
            }
            
            // 创建配置弹窗
            const modalHTML = `
                <div id="interview-config-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div class="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                        <!-- 弹窗头部 -->
                        <div class="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 rounded-t-xl">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-3">
                                    <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                                        <i class="ri-settings-4-line text-blue-600"></i>
                                    </div>
                                    <h2 class="text-xl font-semibold text-gray-900">配置新面试</h2>
                                </div>
                                <button id="close-config-modal" class="text-gray-400 hover:text-gray-600 transition-colors">
                                    <i class="ri-close-line text-xl"></i>
                                </button>
                            </div>
                        </div>
                        
                        <!-- 弹窗内容 -->
                        <div class="p-6 space-y-6">
                            <!-- 简历选择 -->
                            <div class="space-y-3">
                                <label class="block text-sm font-medium text-gray-900">
                                    <i class="ri-file-text-line mr-2 text-blue-600"></i>
                                    选择简历版本
                                </label>
                                <div class="grid gap-3 max-h-60 overflow-y-auto">
                                    ${resumes.map(resume => `
                                        <label class="relative">
                                            <input type="radio" name="resume-selection" value="${resume.id}" 
                                                   class="peer sr-only" ${resumes.length === 1 ? 'checked' : ''}>
                                            <div class="peer-checked:ring-2 peer-checked:ring-blue-500 peer-checked:bg-blue-50 
                                                        border border-gray-200 rounded-lg p-4 cursor-pointer hover:bg-gray-50 transition-all">
                                                <div class="flex items-start justify-between">
                                                    <div class="flex-1">
                                                        <h3 class="font-medium text-gray-900 mb-1">${resume.name}</h3>
                                                        <p class="text-sm text-gray-600 mb-2">目标职位: ${resume.target_position}</p>
                                                        <div class="flex items-center space-x-4 text-xs text-gray-500">
                                                            <span>创建: ${new Date(resume.created_at).toLocaleDateString('zh-CN')}</span>
                                                            <span class="px-2 py-1 bg-gray-100 rounded">${resume.status === 'active' ? '活跃' : '草稿'}</span>
                                                        </div>
                                                    </div>
                                                    <div class="peer-checked:text-blue-600 text-gray-400">
                                                        <i class="ri-checkbox-circle-line text-lg"></i>
                                                    </div>
                                                </div>
                                            </div>
                                        </label>
                                    `).join('')}
                                </div>
                            </div>
                            
                            <!-- 面试配置 -->
                            <div class="grid md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-900 mb-2">
                                        <i class="ri-briefcase-line mr-2 text-green-600"></i>
                                        目标职位
                                    </label>
                                    <input id="target-position" type="text" value="算法工程师" 
                                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-900 mb-2">
                                        <i class="ri-globe-line mr-2 text-purple-600"></i>
                                        技术领域
                                    </label>
                                    <select id="target-field" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                                        <option value="人工智能">人工智能</option>
                                        <option value="后端开发">后端开发</option>
                                        <option value="前端开发">前端开发</option>
                                        <option value="全栈开发">全栈开发</option>
                                        <option value="数据科学">数据科学</option>
                                        <option value="机器学习">机器学习</option>
                                        <option value="计算机视觉">计算机视觉</option>
                                        <option value="自然语言处理">自然语言处理</option>
                                    </select>
                                </div>
                            </div>
                            
                            <!-- 面试类型 -->
                            <div>
                                <label class="block text-sm font-medium text-gray-900 mb-3">
                                    <i class="ri-chat-3-line mr-2 text-orange-600"></i>
                                    面试类型
                                </label>
                                <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                                    <label class="relative">
                                        <input type="radio" name="interview-type" value="technical" class="peer sr-only" checked>
                                        <div class="peer-checked:ring-2 peer-checked:ring-blue-500 peer-checked:bg-blue-50 
                                                    border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-all text-center">
                                            <i class="ri-code-line text-blue-600 text-xl mb-1 block"></i>
                                            <span class="text-sm font-medium">技术面试</span>
                                        </div>
                                    </label>
                                    <label class="relative">
                                        <input type="radio" name="interview-type" value="behavioral" class="peer sr-only">
                                        <div class="peer-checked:ring-2 peer-checked:ring-green-500 peer-checked:bg-green-50 
                                                    border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-all text-center">
                                            <i class="ri-user-heart-line text-green-600 text-xl mb-1 block"></i>
                                            <span class="text-sm font-medium">行为面试</span>
                                        </div>
                                    </label>
                                    <label class="relative">
                                        <input type="radio" name="interview-type" value="comprehensive" class="peer sr-only">
                                        <div class="peer-checked:ring-2 peer-checked:ring-purple-500 peer-checked:bg-purple-50 
                                                    border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-all text-center">
                                            <i class="ri-stack-line text-purple-600 text-xl mb-1 block"></i>
                                            <span class="text-sm font-medium">综合面试</span>
                                        </div>
                                    </label>
                                </div>
                            </div>
                            
                            <!-- 面试难度 -->
                            <div>
                                <label class="block text-sm font-medium text-gray-900 mb-3">
                                    <i class="ri-speed-line mr-2 text-red-600"></i>
                                    面试难度
                                </label>
                                <div class="flex space-x-2">
                                    <label class="flex-1 relative">
                                        <input type="radio" name="difficulty" value="junior" class="peer sr-only">
                                        <div class="peer-checked:ring-2 peer-checked:ring-green-500 peer-checked:bg-green-50 
                                                    border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-all text-center">
                                            <span class="text-sm font-medium">初级</span>
                                        </div>
                                    </label>
                                    <label class="flex-1 relative">
                                        <input type="radio" name="difficulty" value="intermediate" class="peer sr-only" checked>
                                        <div class="peer-checked:ring-2 peer-checked:ring-yellow-500 peer-checked:bg-yellow-50 
                                                    border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-all text-center">
                                            <span class="text-sm font-medium">中级</span>
                                        </div>
                                    </label>
                                    <label class="flex-1 relative">
                                        <input type="radio" name="difficulty" value="senior" class="peer sr-only">
                                        <div class="peer-checked:ring-2 peer-checked:ring-red-500 peer-checked:bg-red-50 
                                                    border border-gray-200 rounded-lg p-3 cursor-pointer hover:bg-gray-50 transition-all text-center">
                                            <span class="text-sm font-medium">高级</span>
                                        </div>
                                    </label>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 弹窗底部 -->
                        <div class="sticky bottom-0 bg-gray-50 px-6 py-4 rounded-b-xl border-t border-gray-200">
                            <div class="flex justify-end space-x-3">
                                <button id="cancel-config" class="px-6 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors">
                                    取消
                                </button>
                                <button id="start-interview" class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                                    <i class="ri-play-circle-line mr-2"></i>
                                    开始面试
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // 添加到页面
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            // 绑定事件
            bindConfigModalEvents();
            
            // 添加进入动画
            const modal = document.getElementById('interview-config-modal');
            const modalContent = modal.querySelector('.bg-white');
            modalContent.style.opacity = '0';
            modalContent.style.transform = 'scale(0.9) translateY(-20px)';
            
            setTimeout(() => {
                modalContent.style.transition = 'all 0.3s ease-out';
                modalContent.style.opacity = '1';
                modalContent.style.transform = 'scale(1) translateY(0)';
            }, 50);
            
        } catch (error) {
            console.error('❌ 创建配置弹窗失败:', error);
            throw error;
        }
    }

    /**
     * 显示无简历提示弹窗
     */
    function showNoResumeModal() {
        const modalHTML = `
            <div id="no-resume-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                <div class="bg-white rounded-xl shadow-2xl max-w-md w-full">
                    <div class="p-6 text-center space-y-4">
                        <div class="w-16 h-16 mx-auto bg-yellow-100 rounded-full flex items-center justify-center">
                            <i class="ri-file-add-line text-yellow-600 text-2xl"></i>
                        </div>
                        
                        <div class="space-y-2">
                            <h3 class="text-xl font-semibold text-gray-900">暂无简历</h3>
                            <p class="text-gray-600">您还没有创建简历，请先创建简历后再开始面试</p>
                        </div>
                        
                        <div class="space-y-3">
                            <button id="goto-create-resume" class="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
                                <i class="ri-add-line mr-2"></i>
                                创建简历
                            </button>
                            <button id="close-no-resume-modal" class="w-full border border-gray-300 text-gray-700 px-6 py-3 rounded-lg font-medium hover:bg-gray-50 transition-colors">
                                暂不创建
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // 绑定事件
        document.getElementById('goto-create-resume').addEventListener('click', () => {
            window.location.href = '/frontend/Resume_create.html';
        });
        
        document.getElementById('close-no-resume-modal').addEventListener('click', () => {
            document.getElementById('no-resume-modal').remove();
        });
    }

    /**
     * 绑定配置弹窗事件
     */
    function bindConfigModalEvents() {
        const modal = document.getElementById('interview-config-modal');
        const closeBtn = document.getElementById('close-config-modal');
        const cancelBtn = document.getElementById('cancel-config');
        const startBtn = document.getElementById('start-interview');
        
        // 关闭弹窗
        const closeModal = () => {
            const modalContent = modal.querySelector('.bg-white');
            modalContent.style.transition = 'all 0.2s ease-in';
            modalContent.style.opacity = '0';
            modalContent.style.transform = 'scale(0.9) translateY(-20px)';
            
            setTimeout(() => {
                modal.remove();
            }, 200);
        };
        
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        // 开始面试
        startBtn.addEventListener('click', async () => {
            try {
                startBtn.disabled = true;
                startBtn.innerHTML = '<i class="ri-loader-line animate-spin mr-2"></i>创建中...';
                
                // 获取选择的简历
                const selectedResume = document.querySelector('input[name="resume-selection"]:checked');
                if (!selectedResume) {
                    showSystemMessage('请选择一个简历', 'warning');
                    return;
                }
                
                // 获取配置信息
                const config = {
                    position: document.getElementById('target-position').value,
                    field: document.getElementById('target-field').value,
                    type: document.querySelector('input[name="interview-type"]:checked').value,
                    difficulty: document.querySelector('input[name="difficulty"]:checked').value
                };
                
                console.log('🎯 面试配置:', { resumeId: selectedResume.value, config });
                
                // 关闭弹窗
                closeModal();
                
                // 创建面试会话
                await doCreateInterviewSession(selectedResume.value, config);
                
            } catch (error) {
                console.error('❌ 创建面试失败:', error);
                showSystemMessage(`创建失败: ${error.message}`, 'error');
            } finally {
                startBtn.disabled = false;
                startBtn.innerHTML = '<i class="ri-play-circle-line mr-2"></i>开始面试';
            }
        });
    }

    /**
     * 欢迎页面的开始按钮处理
     */
    function handleWelcomeStart() {
        console.log('🚀 用户点击开始第一次面试');
        createNewLangGraphSession();
    }

    // 暴露给全局作用域的函数
    window.createNewLangGraphSession = createNewLangGraphSession;
    window.sendLangGraphMessage = sendLangGraphMessage;
    window.sendLangGraphMessageStream = sendLangGraphMessageStream;
    window.switchToSession = switchToSession;
    window.handleWelcomeStart = handleWelcomeStart;

    console.log('✅ LangGraph智能面试系统初始化完成');
});
