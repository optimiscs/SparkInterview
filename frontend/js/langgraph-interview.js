/**
 * LangGraph智能面试系统 - 前端集成
 * 使用LangChain + LangGraph接口
 */

document.addEventListener('DOMContentLoaded', async function() {
    // 获取页面UI元素
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const messagesContainer = document.getElementById('chat-messages-container');
    const newInterviewBtn = document.getElementById('new-interview-btn');
    const sessionsListContainer = document.getElementById('sessions-list-container');
    const sessionSearchInput = document.getElementById('session-search-input');
    const aiSubtitleText = document.getElementById('ai-subtitle-text');

    // 录音相关元素
    const voiceRecordBtn = document.querySelector('.mic-pulse');
    
    // 聊天状态管理
    let isProcessing = false;
    let currentSessionId = localStorage.getItem('current_session_id') || null;
    let isRecording = false;
    let allSessions = []; // 存储所有会话数据用于搜索
    
    // 音频发送策略 - 实时小包模式（优化识别实时性）
    let audioBuffer = [];           // 累积音频数据
    let bufferCount = 0;           // 当前缓冲区计数
    const BUFFERS_PER_PACKET = 1;  // 1个缓冲区立即发送 (约0.5秒，提高实时性)

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
            
            // 存储会话数据用于搜索
            allSessions = sessions;
            
            if (sessions.length === 0) {
                // 新用户或没有会话 - 显示欢迎界面
                renderWelcomeInterface();
            } else {
                // 有会话的用户 - 显示会话选择界面
                renderSessionSelection(sessions);
            }
            
            // 渲染左侧会话列表
            renderSessionsList(sessions);
        } catch (error) {
            console.error('❌ 渲染用户界面失败:', error);
            // 降级到欢迎界面
            renderWelcomeInterface();
        }
    }
    
    /**
     * 渲染会话列表到左侧容器
     */
    function renderSessionsList(sessions) {
        if (!sessionsListContainer) {
            console.warn('未找到会话列表容器');
            return;
        }

        if (sessions.length === 0) {
            sessionsListContainer.innerHTML = `
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

        // 清空容器
        sessionsListContainer.innerHTML = '';

        // 渲染每个会话
        sessions.forEach((session, index) => {
            const isActive = session.session_id === currentSessionId;
            const createdTime = new Date(session.created_at);
            const timeDisplay = formatTimeAgo(createdTime);
            
            // 计算面试时长
            const durationMinutes = session.duration ? Math.ceil(session.duration / 60) : 0;
            
            // 根据会话状态确定状态显示
            let statusBadge = 'bg-green-100 text-green-600';
            let statusText = '已完成';
            
            if (!session.interview_ended) {
                if (isActive) {
                    statusBadge = 'bg-blue-100 text-blue-600';
                    statusText = '进行中';
                } else {
                    statusBadge = 'bg-gray-100 text-gray-600';
                    statusText = '待继续';
                }
            }

            // 技术领域图标映射
            const fieldIcons = {
                '人工智能': 'ri-robot-line',
                '后端开发': 'ri-server-line',
                '前端开发': 'ri-layout-line',
                '全栈开发': 'ri-stack-line',
                '数据科学': 'ri-bar-chart-line',
                '机器学习': 'ri-brain-line',
                '计算机视觉': 'ri-eye-line',
                '自然语言处理': 'ri-chat-3-line'
            };
            const iconClass = fieldIcons[session.target_field] || 'ri-briefcase-line';

            const sessionDiv = document.createElement('div');
            sessionDiv.className = `session-item bg-white rounded-lg p-3 border border-gray-200 cursor-pointer hover:shadow-md transition-all duration-200 group ${
                isActive ? 'ring-2 ring-primary bg-blue-50 border-primary' : ''
            }`;
            
            sessionDiv.innerHTML = `
                <div class="flex items-center space-x-3 mb-2">
                    <div class="w-8 h-8 ${isActive ? 'bg-primary' : 'bg-blue-500'} rounded-full flex items-center justify-center">
                        <i class="${iconClass} text-white text-sm"></i>
                    </div>
                    <div class="flex-1">
                        <h3 class="text-sm font-medium text-gray-900">${session.target_position || '面试会话'}</h3>
                        <p class="text-xs text-gray-500">${timeDisplay}</p>
                    </div>
                    <button class="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity delete-session" data-session-id="${session.session_id}">
                        <i class="ri-delete-bin-line text-gray-400 hover:text-red-500"></i>
                    </button>
                </div>
                <div class="text-xs text-gray-600">
                    <span class="inline-block ${statusBadge} px-2 py-1 rounded-full mr-2">${statusText}</span>
                    <span class="text-gray-500">
                        ${session.message_count || 0}条消息${durationMinutes > 0 ? ` • ${durationMinutes}分钟` : ''}
                    </span>
                </div>
                <div class="text-xs text-gray-500 mt-1">
                    ${session.target_field || '技术面试'}
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
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    showDeleteSessionModal(session.session_id, session.target_position);
                });
            }
            
            sessionsListContainer.appendChild(sessionDiv);
        });
    }
    
    /**
     * 显示删除会话确认模态框
     */
    function showDeleteSessionModal(sessionId, sessionName) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
                <div class="p-6">
                    <div class="flex items-center space-x-3 mb-4">
                        <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                            <i class="ri-delete-bin-line text-red-600 text-xl"></i>
                        </div>
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900">删除会话</h3>
                            <p class="text-sm text-gray-600">此操作无法撤销</p>
                        </div>
                    </div>
                    
                    <p class="text-gray-700 mb-6">
                        确定要删除面试会话 <span class="font-medium">"${sessionName || '未命名会话'}"</span> 吗？
                        这将永久删除所有相关的对话记录和数据。
                    </p>
                    
                    <div class="flex justify-end space-x-3">
                        <button class="cancel-delete px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                            取消
                        </button>
                        <button class="confirm-delete px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
                            确认删除
                        </button>
                    </div>
                </div>
            </div>
        `;

        // 绑定事件
        modal.querySelector('.cancel-delete').addEventListener('click', () => {
            modal.remove();
        });

        modal.querySelector('.confirm-delete').addEventListener('click', async () => {
            try {
                await deleteSession(sessionId);
                modal.remove();
            } catch (error) {
                console.error('删除会话失败:', error);
                showSystemMessage('删除会话失败: ' + error.message, 'error');
            }
        });

        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        document.body.appendChild(modal);
    }
    
    /**
     * 格式化时间显示
     */
    function formatTimeAgo(date) {
        const now = new Date();
        const diffHours = Math.floor((now - date) / (1000 * 60 * 60));
        
        if (diffHours < 1) return '刚刚创建';
        if (diffHours < 24) return `${diffHours}小时前`;
        
        const diffDays = Math.floor(diffHours / 24);
        if (diffDays === 1) return '昨天';
        if (diffDays < 7) return `${diffDays}天前`;
        
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
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
        
        // 录音按钮
        if (voiceRecordBtn) {
            voiceRecordBtn.addEventListener('click', toggleRecording);
        }
        
        // 会话搜索功能
        if (sessionSearchInput) {
            sessionSearchInput.addEventListener('input', (e) => {
                searchSessions(e.target.value);
            });
        }
    }
    
    // ==================== 语音识别集成 ====================
    
    // 语音识别相关变量
    let voiceSession = null;
    let voiceWebSocket = null;
    let isVoiceConnected = false;
    let currentThinkingMessageId = null;
    
    /**
     * 切换录音状态
     */
    async function toggleRecording() {
        if (isRecording) {
            await stopRecording();
        } else {
            await startRecording();
        }
    }
    
    /**
     * 开始录音
     */
    async function startRecording() {
        if (!currentSessionId) {
            showSystemMessage('请先创建面试会话', 'error');
            return;
        }
        
        try {
            console.log('🎤 开始录音...');
            
            // 🤖 中断数字人播放 - 避免录音时的声音冲突
            if (typeof window.interruptAvatar === 'function') {
                try {
                    await window.interruptAvatar();
                    console.log('⏸️ 已中断数字人播放，准备开始录音');
                } catch (error) {
                    console.warn('⚠️ 中断数字人播放失败，继续录音:', error);
                }
            }
            
            // 创建语音识别会话
            await createVoiceSession();
            
            // 请求麦克风权限
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            // 使用AudioContext获取PCM数据而不是MediaRecorder
            // 创建AudioContext进行实时音频处理
            const audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            
            const source = audioContext.createMediaStreamSource(stream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            processor.onaudioprocess = (event) => {
                if (!isRecording) return;
                
                const inputData = event.inputBuffer.getChannelData(0);
                
                // 转换为16位PCM并添加到缓冲区
                const pcmData = convertToPCM16(inputData);
                audioBuffer.push(pcmData);
                bufferCount++;
                
                // 累积4个缓冲区后发送 (约2秒的音频)
                if (bufferCount >= BUFFERS_PER_PACKET) {
                    // 合并所有缓冲区数据
                    const totalLength = audioBuffer.reduce((sum, arr) => sum + arr.length, 0);
                    const mergedBuffer = new Uint8Array(totalLength);
                    
                    let offset = 0;
                    for (const buffer of audioBuffer) {
                        mergedBuffer.set(buffer, offset);
                        offset += buffer.length;
                    }
                    
                    // 发送大包数据
                    if (voiceWebSocket && isVoiceConnected) {
                        voiceWebSocket.send(mergedBuffer.buffer);
                        console.log(`📤 发送2秒音频包: ${mergedBuffer.length} bytes (${BUFFERS_PER_PACKET}个缓冲区)`);
                    }
                    
                    // 重置缓冲区
                    audioBuffer = [];
                    bufferCount = 0;
                }
            };
            
            source.connect(processor);
            processor.connect(audioContext.destination);
            
            // 保存引用以便停止时断开
            window.currentAudioContext = audioContext;
            window.currentProcessor = processor;
            
            isRecording = true;
            console.log('✅ PCM音频处理器已启动');
            
            // 更新UI
            updateRecordingUI(true);
            
            // 连接语音识别WebSocket
            await connectVoiceWebSocket();
            
            // 启动语调分析
            if (typeof startVoiceToneAnalysis === 'function' && voiceSession) {
                startVoiceToneAnalysis(voiceSession.session_id);
            }
            
        } catch (error) {
            console.error('❌ 开始录音失败:', error);
            showSystemMessage(`录音失败: ${error.message}`, 'error');
            isRecording = false;
            updateRecordingUI(false);
        }
    }
    
    /**
     * 停止录音 - 触发LangGraph感知节点
     */
    async function stopRecording() {
        try {
            console.log('🎤 前端主动停止录音 - 将触发LangGraph感知节点');
            isRecording = false;
            
            // 发送剩余的缓冲区数据 (如果有的话)
            if (audioBuffer.length > 0 && voiceWebSocket && isVoiceConnected) {
                const totalLength = audioBuffer.reduce((sum, arr) => sum + arr.length, 0);
                const mergedBuffer = new Uint8Array(totalLength);
                
                let offset = 0;
                for (const buffer of audioBuffer) {
                    mergedBuffer.set(buffer, offset);
                    offset += buffer.length;
                }
                
                voiceWebSocket.send(mergedBuffer.buffer);
                console.log(`📤 发送剩余音频数据: ${mergedBuffer.length} bytes (${audioBuffer.length}个缓冲区)`);
            }
            
            // 清理音频缓冲区
            audioBuffer = [];
            bufferCount = 0;
            
            // 断开AudioContext连接
            if (window.currentProcessor) {
                window.currentProcessor.disconnect();
                window.currentProcessor = null;
            }
            
            if (window.currentAudioContext) {
                await window.currentAudioContext.close();
                window.currentAudioContext = null;
            }
            
            // 🎯 关键修改：发送stop命令现在将触发后端LangGraph感知节点
            if (voiceWebSocket && isVoiceConnected) {
                console.log('📤 发送停止录音命令 - 后端将触发LangGraph感知节点');
                voiceWebSocket.send(JSON.stringify({ command: 'stop' }));
                
                // 更新UI状态，显示AI正在分析
                updateAISubtitle('🤖 录音已停止，AI正在进行语音分析和情感感知...');
            }
            
            // 更新录音UI状态
            updateRecordingUI(false);
            
            // 停止语调分析
            if (typeof stopVoiceToneAnalysis === 'function') {
                stopVoiceToneAnalysis();
            }
            
        } catch (error) {
            console.error('❌ 停止录音失败:', error);
        }
    }
    
    /**
     * 创建语音识别会话
     */
    async function createVoiceSession() {
        try {
            const userData = localStorage.getItem('current_user');
            const user = userData ? JSON.parse(userData) : { id: 'unknown' };
            
            const response = await callAPI('/voice/create-session', 'POST', {
                user_id: user.id,
                interview_session_id: currentSessionId,
                session_id: `voice_${currentSessionId}_${Date.now()}`
            });
            
            if (response.success) {
                voiceSession = response;
                console.log('✅ 语音会话创建成功:', voiceSession.session_id);
            } else {
                throw new Error(response.message || '创建语音会话失败');
            }
            
        } catch (error) {
            console.error('❌ 创建语音会话失败:', error);
            throw error;
        }
    }
    
    /**
     * 连接语音识别WebSocket
     */
    async function connectVoiceWebSocket() {
        try {
            if (!voiceSession) {
                throw new Error('语音会话未创建');
            }
            
            const wsUrl = `ws://localhost:8000/api/v1/voice/recognition/${voiceSession.session_id}`;
            voiceWebSocket = new WebSocket(wsUrl);
            
            voiceWebSocket.onopen = () => {
                console.log('🔗 语音识别WebSocket连接成功');
                isVoiceConnected = true;
                
                // 发送开始录音命令
                voiceWebSocket.send(JSON.stringify({ command: 'start' }));
            };
            
            voiceWebSocket.onmessage = (event) => {
                handleVoiceMessage(JSON.parse(event.data));
            };
            
            voiceWebSocket.onclose = () => {
                console.log('🔌 语音识别WebSocket连接关闭');
                isVoiceConnected = false;
            };
            
            voiceWebSocket.onerror = (error) => {
                console.error('❌ 语音识别WebSocket错误:', error);
                isVoiceConnected = false;
            };
            
        } catch (error) {
            console.error('❌ 连接语音WebSocket失败:', error);
            throw error;
        }
    }
    
    /**
     * 将Float32Array转换为16位PCM数据
     */
    function convertToPCM16(float32Array) {
        const buffer = new ArrayBuffer(float32Array.length * 2);
        const view = new DataView(buffer);
        let offset = 0;
        
        for (let i = 0; i < float32Array.length; i++, offset += 2) {
            const sample = Math.max(-1, Math.min(1, float32Array[i]));
            view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
        }
        
        return new Uint8Array(buffer);
    }
    
    /**
     * 处理语音识别消息
     */
    function handleVoiceMessage(message) {
        console.log('🎯 语音识别消息:', message);
        
        switch (message.type) {
            case 'result':
                if (message.is_final) {
                    // 最终识别结果
                    console.log('📝 最终识别文本:', message.text);
                    updateAISubtitle(`识别完成: ${message.text}`);
                    updateUserSubtitle(`识别完成: ${message.text}`);
                    
                    // 显示用户语音消息到聊天界面
                    displayLangGraphMessage({
                        role: 'user',
                        content: message.text,
                        timestamp: new Date().toISOString(),
                        source: 'voice'
                    });
                    
                    // 显示AI思考状态
                    currentThinkingMessageId = showThinkingMessage();
                } else {
                    // 实时识别结果 - 同时在AI区域和用户区域显示
                    const recognitionText = message.text || '正在识别...';
                    updateAISubtitle(`🎤 ${recognitionText}`);
                    updateUserSubtitle(recognitionText, true); // 表示用户正在说话
                }
                break;
                
            case 'final_result':
                // 讯飞识别的最终结果（但不触发LangGraph）
                console.log('✅ 讯飞识别结果:', message.text);
                const finalText = message.text || '等待识别完成...';
                updateAISubtitle(`识别: ${finalText}`);
                updateUserSubtitle(`识别: ${finalText}`);
                // 注意：不再在这里触发LangGraph，等待前端停止录音时触发
                break;
                
            case 'recording_stopped':
                // 🎯 新增：前端停止录音触发的消息类型
                console.log('🛑 录音已停止，完整识别文本:', message.text);
                const stoppedText = message.text || '未识别到内容';
                updateAISubtitle(`录音完成: ${stoppedText}`);
                updateUserSubtitle(`录音完成: ${stoppedText}`);
                
                if (message.text && message.text.trim()) {
                    // 显示用户语音消息到聊天界面
                    displayLangGraphMessage({
                        role: 'user',
                        content: message.text,
                        timestamp: new Date().toISOString(),
                        source: 'voice'
                    });
                    
                    // 显示AI思考状态
                    currentThinkingMessageId = showThinkingMessage();
                    updateAISubtitle('🧠 AI正在进行深度分析和情感感知...');
                    updateUserSubtitle('AI正在分析您的回答...');
                    
                    console.log('🚀 录音停止已触发LangGraph感知节点处理');
                } else {
                    updateAISubtitle('未识别到有效语音内容');
                    updateUserSubtitle('未识别到有效语音内容');
                }
                break;
                
            case 'voice_analysis':
                // 接收到语调分析数据
                console.log('🎼 接收到语调分析数据:', message.data);
                
                // 转发给语调分析器处理
                if (typeof handleVoiceToneAnalysis === 'function') {
                    handleVoiceToneAnalysis(message);
                } else {
                    console.warn('⚠️ handleVoiceToneAnalysis函数未找到');
                }
                break;
                
            case 'ai_response':
                // 接收到AI回复 (如果后端直接集成了LangGraph)
                console.log('🤖 接收到AI回复:', message.message);
                
                // 移除思考消息
                if (currentThinkingMessageId) {
                    removeThinkingMessage(currentThinkingMessageId);
                    currentThinkingMessageId = null;
                }
                
                // 显示AI回复消息
                displayLangGraphMessage({
                    role: 'assistant',
                    content: message.message,
                    timestamp: new Date().toISOString(),
                    user_profile: message.user_profile,
                    completeness_score: message.completeness_score,
                    missing_info: message.missing_info,
                    user_emotion: message.user_emotion,
                    decision: message.decision,
                    interview_stage: message.interview_stage
                });
                
                // 更新字幕显示AI回复 - 同时显示在所有字幕区域
                updateAllSubtitles(message.message, true);
                
                // 更新智能体状态面板
                updateAgentStatusPanel({
                    user_profile: message.user_profile,
                    completeness_score: message.completeness_score,
                    missing_info: message.missing_info,
                    user_emotion: message.user_emotion,
                    decision: message.decision,
                    interview_stage: message.interview_stage
                });
                break;
                
            case 'error':
                console.error('❌ 语音识别错误:', message.message);
                showSystemMessage(`语音识别错误: ${message.message}`, 'error');
                updateAISubtitle('语音识别出错');
                
                // 移除思考消息
                if (currentThinkingMessageId) {
                    removeThinkingMessage(currentThinkingMessageId);
                    currentThinkingMessageId = null;
                }
                break;
                
            case 'status':
                console.log('📊 语音识别状态:', message.status);
                if (message.status === 'recording') {
                    updateAISubtitle('🎤 开始录音...');
                }
                break;
        }
    }
    
    /**
     * 将语音识别文本发送到LangGraph
     */
    async function sendVoiceTextToLangGraph(text) {
        try {
            console.log('🤖 发送语音文本到LangGraph:', text);
            
            // 调用LangGraph消息API
            const data = await callAPI('/langgraph-chat/message', 'POST', {
                session_id: currentSessionId,
                message: text
            });
            
            // 移除思考消息
            if (currentThinkingMessageId) {
                removeThinkingMessage(currentThinkingMessageId);
                currentThinkingMessageId = null;
            }
            
            if (data.success) {
                // 显示AI回复
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
                
                // 更新字幕显示AI回复 - 同时显示在所有字幕区域
                updateAllSubtitles(data.message, true);
                
                // 更新智能体状态
                updateAgentStatusPanel({
                    user_profile: data.user_profile,
                    completeness_score: data.completeness_score,
                    missing_info: data.missing_info,
                    user_emotion: data.user_emotion,
                    decision: data.decision,
                    interview_stage: data.interview_stage
                });
                
            } else {
                showSystemMessage(`处理语音消息失败: ${data.message}`, 'error');
                updateAISubtitle('处理失败');
            }
            
        } catch (error) {
            console.error('❌ 发送语音文本到LangGraph失败:', error);
            showSystemMessage(`处理语音消息失败: ${error.message}`, 'error');
            updateAISubtitle('处理出错');
            
            // 移除思考消息
            if (currentThinkingMessageId) {
                removeThinkingMessage(currentThinkingMessageId);
                currentThinkingMessageId = null;
            }
        }
    }
    
    /**
     * 更新录音UI状态
     */
    function updateRecordingUI(recording) {
        if (!voiceRecordBtn) return;
        
        if (recording) {
            voiceRecordBtn.classList.add('mic-pulse');
            voiceRecordBtn.classList.add('bg-red-500');
            voiceRecordBtn.classList.remove('bg-primary');
            voiceRecordBtn.innerHTML = '<i class="ri-stop-line text-white text-xl"></i>';
            
            // 更新字幕显示录音状态
            updateAISubtitle('🎤 正在录音(实时模式)...');
            updateUserSubtitle('正在录音...', true);
            
            // 🎯 新增：根据录音状态切换视频主次位置
            if (typeof window.updateMainViewByRecording === 'function') {
                window.updateMainViewByRecording(true);
                console.log('📹 录音开始 - 用户切换到主位置');
            }
        } else {
            voiceRecordBtn.classList.remove('mic-pulse');
            voiceRecordBtn.classList.remove('bg-red-500');
            voiceRecordBtn.classList.add('bg-primary');
            voiceRecordBtn.innerHTML = '<i class="ri-mic-line text-white text-xl"></i>';
            
            updateAISubtitle('录音已停止，等待AI回复...');
            updateUserSubtitle('录音已停止，等待AI回复...');
            
            // 🎯 新增：录音停止后延迟切换到AI主位置
            if (typeof window.updateMainViewByRecording === 'function') {
                // 延迟2秒切换，给用户一点反应时间
                setTimeout(() => {
                    window.updateMainViewByRecording(false);
                    console.log('📹 录音结束 - AI切换到主位置');
                }, 2000);
            }
        }
    }
    
    /**
     * 搜索会话
     */
    function searchSessions(searchTerm) {
        if (!searchTerm.trim()) {
            // 如果搜索词为空，显示所有会话
            renderSessionsList(allSessions);
            return;
        }

        const filteredSessions = allSessions.filter(session => {
            const searchString = searchTerm.toLowerCase();
            return (
                (session.target_position || '').toLowerCase().includes(searchString) ||
                (session.target_field || '').toLowerCase().includes(searchString) ||
                (session.session_id || '').toLowerCase().includes(searchString)
            );
        });

        renderSessionsList(filteredSessions);
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
                const previousSessionId = currentSessionId;
                currentSessionId = result.session_id;
                localStorage.setItem('current_session_id', currentSessionId);
                
                // 触发会话切换事件，通知状态管理器
                const sessionSwitchedEvent = new CustomEvent('sessionSwitched', {
                    detail: {
                        sessionId: currentSessionId,
                        previousSessionId: previousSessionId,
                        timestamp: Date.now(),
                        isNewSession: true
                    }
                });
                document.dispatchEvent(sessionSwitchedEvent);
                
                // 触发新会话创建事件，通知欢迎界面管理器
                const newSessionEvent = new CustomEvent('newSessionCreated', {
                    detail: {
                        sessionId: currentSessionId,
                        timestamp: Date.now()
                    }
                });
                document.dispatchEvent(newSessionEvent);
                
                console.log('📡 新会话创建事件已触发:', { sessionId: currentSessionId });
                
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
                    allSessions = sessions; // 更新会话数据
                    renderSessionsList(sessions);
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
            
            // 触发会话切换事件，通知状态管理器
            const event = new CustomEvent('sessionSwitched', {
                detail: {
                    sessionId: sessionId,
                    previousSessionId: previousSessionId,
                    timestamp: Date.now()
                }
            });
            document.dispatchEvent(event);
            console.log('📡 会话切换事件已触发:', { from: previousSessionId, to: sessionId });
            
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
            allSessions = sessions; // 更新会话数据
            renderSessionsList(sessions);
            
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
            allSessions = sessions; // 更新会话数据
            renderSessionsList(sessions);
            
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
            
            // 更新AI字幕 - 如果是AI消息则同时显示在所有字幕区域
            updateAllSubtitles(messageData.content, true);
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
    
    /**
     * 更新AI字幕 - 同时更新主位置和次位置的AI字幕
     */
    function updateAISubtitle(text) {
        // 更新AI数字人主位置字幕
        if (aiSubtitleText) {
            aiSubtitleText.textContent = text;
        }
        
        // 更新AI数字人次位置字幕
        const aiSubtitleSecondary = document.getElementById('ai-subtitle-secondary');
        if (aiSubtitleSecondary) {
            aiSubtitleSecondary.textContent = text;
        }
        
        console.log('📺 AI字幕已更新:', text.substring(0, 50) + '...');
    }
    
    /**
     * 更新所有字幕区域 - AI回复时同时更新所有字幕显示
     */
    function updateAllSubtitles(text, isAIResponse = false) {
        if (isAIResponse) {
            // AI回复时，更新所有位置的字幕
            updateAISubtitle(text);
            
            // 同时在用户字幕区域显示AI回复（带AI前缀）
            const userSubtitleText = document.getElementById('user-subtitle-text');
            if (userSubtitleText) {
                userSubtitleText.textContent = `🤖 AI: ${text}`;
            }
            
            console.log('🗣️ AI回复同时显示在所有字幕区域');
            
            // 🤖 数字人朗读功能 - AI回复时触发数字人播放
            if (text && text.trim() && typeof window.speakText === 'function') {
                try {
                    console.log('🎤 触发数字人朗读:', text.substring(0, 50) + (text.length > 50 ? '...' : ''));
                    
                    // 清理文本，移除特殊标记
                    const cleanText = cleanTextForSpeech(text);
                    
                    if (cleanText && cleanText.trim()) {
                        // 调用数字人朗读
                        window.speakText(cleanText, {
                            interruptible: true, // 允许中断
                            voice: 'x4_yuexiaoni_assist', // 悦小妮助手
                            speed: 50,
                            volume: 80
                        }).then(requestId => {
                            console.log('✅ 数字人朗读请求已发送:', requestId);
                        }).catch(error => {
                            console.error('❌ 数字人朗读失败:', error);
                        });
                    }
                } catch (error) {
                    console.error('❌ 调用数字人朗读功能失败:', error);
                }
            }
        } else {
            // 用户语音识别结果只显示在AI字幕区域
            updateAISubtitle(text);
        }
    }
    
    /**
     * 清理文本用于语音播放
     */
    function cleanTextForSpeech(text) {
        if (!text) return '';
        
        return text
            // 移除HTML标签
            .replace(/<[^>]*>/g, '')
            // 移除Markdown标记
            .replace(/\*\*(.*?)\*\*/g, '$1')
            .replace(/\*(.*?)\*/g, '$1')
            .replace(/`(.*?)`/g, '$1')
            // 移除特殊符号
            .replace(/[#*`\[\]]/g, '')
            // 替换多个空格为单个空格
            .replace(/\s+/g, ' ')
            // 去除首尾空格
            .trim();
    }
    
    /**
     * 更新用户字幕 - 用户录音和语音识别时的状态显示
     */
    function updateUserSubtitle(text, isUserSpeaking = false) {
        const userSubtitleText = document.getElementById('user-subtitle-text');
        if (userSubtitleText) {
            if (isUserSpeaking) {
                userSubtitleText.textContent = `🎤 ${text}`;
            } else {
                userSubtitleText.textContent = text;
            }
        }
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
        // 纯JS逻辑初始化，HTML结构已在interview.html中定义
        console.log('🤖 初始化智能体状态面板（纯JS逻辑）');
        
        // 绑定面板模式切换事件
        bindPanelModeToggle();
        
        // 绑定展开面板按钮事件
        bindExpandPanelButton();
        
        // 绑定右侧边缘鼠标感应事件
        bindRightEdgeHover();
        
        console.log('✅ 智能体状态面板初始化完成');
    }
    
    /**
     * 绑定展开面板按钮功能
     */
    function bindExpandPanelButton() {
        const expandPanelButton = document.getElementById('expandPanelButton');
        if (expandPanelButton) {
            // 如果有展开按钮，为其绑定点击事件
            const expandBtn = expandPanelButton.querySelector('button');
            if (expandBtn) {
                expandBtn.addEventListener('click', function() {
                    const panel = document.getElementById('analysisPanel');
                    const expandButton = document.getElementById('expandPanelButton');
                    
                    if (panel && expandButton) {
                        // 显示面板
                        panel.style.width = '24rem';
                        panel.style.opacity = '1';
                        panel.style.display = 'block';
                        
                        // 隐藏展开按钮
                        expandButton.style.opacity = '0';
                        expandButton.style.transform = 'translateY(-50%) translateX(100%)';
                        
                        // 更新折叠按钮图标
                        const toggleIcon = document.querySelector('#togglePanel i');
                        if (toggleIcon) {
                            toggleIcon.className = 'ri-arrow-right-line text-gray-600';
                        }
                        
                        console.log('🔄 面板已通过展开按钮打开');
                    }
                });
            }
        }
    }
    
    /**
     * 绑定右侧边缘鼠标感应功能
     */
    function bindRightEdgeHover() {
        const rightEdgeHover = document.getElementById('rightEdgeHover');
        const expandPanelButton = document.getElementById('expandPanelButton');
        let hoverTimeout = null;
        
        if (rightEdgeHover && expandPanelButton) {
            console.log('🖱️ 绑定右侧边缘鼠标感应事件');
            
            // 鼠标进入右边缘区域
            rightEdgeHover.addEventListener('mouseenter', function() {
                const panel = document.getElementById('analysisPanel');
                const isPanelVisible = panel && !panel.classList.contains('hidden') && 
                                     panel.style.width !== '0px' && panel.style.display !== 'none';
                
                if (!isPanelVisible) {
                    clearTimeout(hoverTimeout);
                    showExpandButton();
                    console.log('👆 鼠标进入右边缘，显示展开按钮');
                }
            });
            
            // 鼠标离开右边缘区域
            rightEdgeHover.addEventListener('mouseleave', function() {
                const panel = document.getElementById('analysisPanel');
                const isPanelVisible = panel && !panel.classList.contains('hidden') && 
                                     panel.style.width !== '0px' && panel.style.display !== 'none';
                
                if (!isPanelVisible) {
                    hoverTimeout = setTimeout(() => {
                        hideExpandButton();
                        console.log('👈 鼠标离开右边缘，隐藏展开按钮');
                    }, 500); // 500ms延迟隐藏，给用户时间点击
                }
            });
            
            // 鼠标进入展开按钮区域时取消隐藏
            expandPanelButton.addEventListener('mouseenter', function() {
                const panel = document.getElementById('analysisPanel');
                const isPanelVisible = panel && !panel.classList.contains('hidden') && 
                                     panel.style.width !== '0px' && panel.style.display !== 'none';
                
                if (!isPanelVisible) {
                    clearTimeout(hoverTimeout);
                    console.log('👆 鼠标进入展开按钮，保持显示');
                }
            });
            
            // 鼠标离开展开按钮区域时延迟隐藏
            expandPanelButton.addEventListener('mouseleave', function() {
                const panel = document.getElementById('analysisPanel');
                const isPanelVisible = panel && !panel.classList.contains('hidden') && 
                                     panel.style.width !== '0px' && panel.style.display !== 'none';
                
                if (!isPanelVisible) {
                    hoverTimeout = setTimeout(() => {
                        hideExpandButton();
                        console.log('👈 鼠标离开展开按钮，隐藏');
                    }, 300);
                }
            });
        }
        
        /**
         * 显示展开按钮
         */
        function showExpandButton() {
            if (expandPanelButton) {
                expandPanelButton.style.opacity = '1';
                expandPanelButton.style.transform = 'translateY(-50%) translateX(0)';
            }
        }
        
        /**
         * 隐藏展开按钮
         */
        function hideExpandButton() {
            if (expandPanelButton) {
                expandPanelButton.style.opacity = '0';
                expandPanelButton.style.transform = 'translateY(-50%) translateX(100%)';
            }
        }
    }
    
    /**
     * 绑定面板模式切换功能
     */
    function bindPanelModeToggle() {
        // 使用事件委托来确保新创建的按钮也能响应事件
        const analysisPanel = document.getElementById('analysisPanel');
        
        if (analysisPanel) {
            console.log('🔗 使用事件委托绑定面板模式切换');
            
            // 移除之前可能存在的事件监听器，避免重复绑定
            const existingHandler = analysisPanel._panelModeHandler;
            if (existingHandler) {
                analysisPanel.removeEventListener('click', existingHandler);
            }
            
            // 定义事件处理函数
            const handlePanelModeClick = (event) => {
                const target = event.target;
                
                // 检查点击的是否是模式切换按钮
                if (target.id === 'mode-analysis' || target.closest('#mode-analysis')) {
                    switchToAnalysisMode();
                    event.stopPropagation(); // 阻止事件冒泡
                } else if (target.id === 'mode-agent' || target.closest('#mode-agent')) {
                    switchToAgentMode();
                    event.stopPropagation(); // 阻止事件冒泡
                }
            };
            
            // 保存处理函数引用，便于后续移除
            analysisPanel._panelModeHandler = handlePanelModeClick;
            
            // 添加事件委托
            analysisPanel.addEventListener('click', handlePanelModeClick);
        }
        
        /**
         * 切换到教练分析模式
         */
        function switchToAnalysisMode() {
            const modeAnalysisBtn = document.getElementById('mode-analysis');
            const modeAgentBtn = document.getElementById('mode-agent');
            const analysisContent = document.getElementById('analysis-content');
            const agentContent = document.getElementById('agent-content');
            const panelModeIcon = document.getElementById('panel-mode-icon');
            const panelModeTitle = document.getElementById('panel-mode-title');
            
            console.log('🎯 正在切换到教练分析模式...');
            
            // 更新按钮状态
            if (modeAnalysisBtn) {
                modeAnalysisBtn.className = 'px-3 py-1 text-xs rounded-md bg-white text-gray-900 shadow-sm transition-all';
            }
            if (modeAgentBtn) {
                modeAgentBtn.className = 'px-3 py-1 text-xs rounded-md text-gray-600 hover:text-gray-900 transition-all';
            }
            
            // 切换内容显示
            if (analysisContent) {
                analysisContent.classList.remove('hidden');
                console.log('✅ 教练分析内容已显示');
            }
            if (agentContent) {
                agentContent.classList.add('hidden');
                console.log('✅ 智能体内容已隐藏');
            }
            
            // 更新标题和图标
            if (panelModeIcon) panelModeIcon.className = 'ri-brain-line text-primary';
            if (panelModeTitle) panelModeTitle.textContent = 'AI 教练分析';
            
            console.log('🎯 已切换到教练分析模式');
        }
        
        /**
         * 切换到智能体模式
         */
        function switchToAgentMode() {
            const modeAnalysisBtn = document.getElementById('mode-analysis');
            const modeAgentBtn = document.getElementById('mode-agent');
            const analysisContent = document.getElementById('analysis-content');
            const agentContent = document.getElementById('agent-content');
            const panelModeIcon = document.getElementById('panel-mode-icon');
            const panelModeTitle = document.getElementById('panel-mode-title');
            
            console.log('🤖 正在切换到智能体模式...');
            
            // 更新按钮状态
            if (modeAgentBtn) {
                modeAgentBtn.className = 'px-3 py-1 text-xs rounded-md bg-white text-gray-900 shadow-sm transition-all';
            }
            if (modeAnalysisBtn) {
                modeAnalysisBtn.className = 'px-3 py-1 text-xs rounded-md text-gray-600 hover:text-gray-900 transition-all';
            }
            
            // 切换内容显示
            if (agentContent) {
                agentContent.classList.remove('hidden');
                console.log('✅ 智能体内容已显示');
            }
            if (analysisContent) {
                analysisContent.classList.add('hidden');
                console.log('✅ 教练分析内容已隐藏');
            }
            
            // 更新标题和图标
            if (panelModeIcon) panelModeIcon.className = 'ri-robot-line text-blue-600';
            if (panelModeTitle) panelModeTitle.textContent = 'LangGraph智能体';
            
            console.log('🤖 已切换到智能体模式');
        }
        
        // 使用事件委托来绑定面板折叠按钮，确保DOM更新后仍能工作
        if (analysisPanel) {
            // 移除之前可能存在的面板切换事件监听器
            const existingToggleHandler = analysisPanel._panelToggleHandler;
            if (existingToggleHandler) {
                analysisPanel.removeEventListener('click', existingToggleHandler);
            }
            
            // 定义面板切换事件处理函数
            const handleTogglePanelClick = (event) => {
                const target = event.target;
                
                // 检查点击的是否是面板切换按钮
                if (target.id === 'togglePanel' || target.closest('#togglePanel')) {
                    togglePanelVisibility();
                    event.stopPropagation(); // 阻止事件冒泡
                }
            };
            
            // 保存处理函数引用
            analysisPanel._panelToggleHandler = handleTogglePanelClick;
            
            // 添加事件委托
            analysisPanel.addEventListener('click', handleTogglePanelClick);
            
            console.log('🔄 使用事件委托绑定面板切换按钮');
        }
        
        /**
         * 切换面板显示/隐藏状态
         */
        function togglePanelVisibility() {
            const panel = document.getElementById('analysisPanel');
            const expandButton = document.getElementById('expandPanelButton');
            const toggleBtn = document.getElementById('togglePanel');
            const icon = toggleBtn?.querySelector('i');
            
            if (panel && expandButton) {
                // 判断面板当前是否可见
                const isVisible = panel.style.width !== '0px' && 
                                panel.style.display !== 'none' && 
                                !panel.classList.contains('hidden');
                
                if (isVisible) {
                    // 隐藏面板
                    panel.style.width = '0px';
                    panel.style.opacity = '0';
                    panel.style.display = 'none';
                    if (icon) icon.className = 'ri-arrow-left-line text-gray-600';
                    
                    // 确保展开按钮初始状态为隐藏
                    expandButton.style.opacity = '0';
                    expandButton.style.transform = 'translateY(-50%) translateX(100%)';
                    
                    console.log('🔄 面板已收起，展开按钮待激活');
                } else {
                    // 显示面板
                    panel.style.width = '24rem';
                    panel.style.opacity = '1';
                    panel.style.display = 'block';
                    if (icon) icon.className = 'ri-arrow-right-line text-gray-600';
                    
                    // 面板展开时隐藏展开按钮
                    expandButton.style.opacity = '0';
                    expandButton.style.transform = 'translateY(-50%) translateX(100%)';
                    
                    console.log('🔄 面板已展开');
                }
            }
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
