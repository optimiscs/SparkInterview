/**
 * 增强面试系统 - 集成智能体的感知-决策-行动架构
 * 与enhanced_chat.py后端配合使用
 */

class EnhancedInterviewSystem {
    constructor() {
        this.sessionId = null;
        this.websocket = null;
        this.agentStatus = null;
        this.userProfile = {};
        this.isProcessing = false;
        
        this.initializeSystem();
    }
    
    initializeSystem() {
        // 初始化DOM元素
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.messagesContainer = document.getElementById('chat-messages-container');
        
        // 初始化智能体状态显示
        this.initializeAgentStatus();
        
        // 绑定事件
        this.bindEvents();
        
        console.log('✅ 增强面试系统初始化完成');
    }
    
    initializeAgentStatus() {
        // 创建智能体状态显示面板
        const analysisPanel = document.getElementById('analysisPanel');
        if (analysisPanel) {
            // 替换右侧分析面板为智能体状态面板
            analysisPanel.innerHTML = this.createAgentStatusPanel();
            
            // 初始化状态显示组件
            if (typeof AgentStatusDisplay !== 'undefined') {
                this.agentStatus = new AgentStatusDisplay('agent-status-container');
            }
        }
    }
    
    createAgentStatusPanel() {
        return `
            <div class="relative">
                <button id="collapseToggle" class="absolute -left-8 top-1/2 -translate-y-1/2 w-8 h-16 bg-gray-50 border border-l-0 border-gray-100 rounded-l-lg flex items-center justify-center transition-colors hover:bg-gray-100">
                    <i class="ri-arrow-right-s-line text-gray-600 transition-transform duration-300"></i>
                </button>
                <div class="p-4 border-b border-gray-100">
                    <h3 class="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                        <i class="ri-robot-line text-blue-600"></i>
                        <span>AI智能体</span>
                    </h3>
                </div>
            </div>
            <div id="agent-status-container" class="flex-1 overflow-y-auto"></div>
            
            <!-- 用户画像显示 -->
            <div class="profile-section p-4 border-t bg-gray-50">
                <h4 class="text-sm font-medium text-gray-800 mb-2 flex items-center">
                    <i class="ri-user-line text-gray-600 mr-2"></i>
                    用户画像
                </h4>
                <div id="user-profile-display" class="space-y-2 text-xs">
                    <div class="profile-item">
                        <span class="text-gray-600">完整度：</span>
                        <span id="profile-completeness" class="font-medium text-blue-600">0%</span>
                    </div>
                    <div class="profile-details"></div>
                </div>
            </div>
        `;
    }
    
    bindEvents() {
        // 新建面试按钮
        const newInterviewBtn = document.getElementById('new-interview-btn');
        if (newInterviewBtn) {
            newInterviewBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.startEnhancedInterview();
            });
        }
        
        // 发送消息按钮
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => {
                this.sendMessage();
            });
        }
        
        // 回车发送消息
        if (this.messageInput) {
            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
    }
    
    async startEnhancedInterview() {
        try {
            // 禁用按钮
            const newInterviewBtn = document.getElementById('new-interview-btn');
            if (newInterviewBtn) {
                newInterviewBtn.disabled = true;
                newInterviewBtn.innerHTML = '<i class="ri-loader-line animate-spin"></i><span>启动智能体...</span>';
            }
            
            // 获取用户信息
            const userInfo = this.getUserInfo();
            console.log('🚀 启动增强面试，用户信息:', userInfo);
            
            // 调用增强的聊天API
            const token = localStorage.getItem('access_token');
            if (!token) {
                throw new Error('请先登录');
            }
            
            const response = await fetch('/api/v1/enhanced-chat/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(userInfo)
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`启动失败: ${response.status} ${errorText}`);
            }
            
            const data = await response.json();
            this.sessionId = data.session_id;
            this.userProfile = data.user_profile || {};
            
            console.log('✅ 智能体会话创建成功:', data.session_id);
            
            // 清空消息容器
            this.messagesContainer.innerHTML = '';
            
            // 显示欢迎消息及智能体状态
            this.displayEnhancedMessage(data.message);
            
            // 更新用户画像显示
            this.updateUserProfileDisplay(this.userProfile);
            
            // 建立WebSocket连接
            this.connectWebSocket();
            
            // 显示成功提示
            this.showSystemMessage('🤖 AI智能体已启动，开始感知-决策-行动循环', 'success');
            
        } catch (error) {
            console.error('启动增强面试失败:', error);
            this.showSystemMessage(`启动失败: ${error.message}`, 'error');
        } finally {
            // 恢复按钮状态
            const newInterviewBtn = document.getElementById('new-interview-btn');
            if (newInterviewBtn) {
                newInterviewBtn.disabled = false;
                newInterviewBtn.innerHTML = '<i class="ri-add-line"></i><span>新建面试</span>';
            }
        }
    }
    
    getUserInfo() {
        // 从多个来源获取用户信息
        const urlParams = new URLSearchParams(window.location.search);
        const savedConfig = JSON.parse(localStorage.getItem('interviewConfig') || '{}');
        const resumeData = JSON.parse(localStorage.getItem('resumeData') || '{}');
        
        return {
            user_name: urlParams.get('username') || savedConfig.userName || '面试用户',
            target_position: urlParams.get('position') || savedConfig.position || '算法工程师',
            target_field: urlParams.get('field') || savedConfig.domain || '人工智能',
            resume_text: this.buildResumeText(resumeData) || savedConfig.resumeSummary || ''
        };
    }
    
    buildResumeText(resumeData) {
        if (!resumeData || !resumeData.basic_info) return '';
        
        const { basic_info, skills, projects, experience, education } = resumeData;
        
        let resumeText = `姓名：${basic_info.name || '未知'}\\n`;
        resumeText += `联系方式：${basic_info.email || ''} ${basic_info.phone || ''}\\n`;
        
        if (education) {
            resumeText += `教育背景：${education.school || ''} ${education.major || ''} ${education.degree || ''}\\n`;
        }
        
        if (skills && skills.length > 0) {
            resumeText += `技能：${skills.join(', ')}\\n`;
        }
        
        if (projects && projects.length > 0) {
            resumeText += '项目经验：\\n';
            projects.forEach(project => {
                resumeText += `- ${project.name || ''}: ${project.description || ''}\\n`;
            });
        }
        
        return resumeText;
    }
    
    displayEnhancedMessage(messageData) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-slide-in mb-6`;
        
        // 根据角色设置样式
        const isUser = messageData.role === 'user';
        const alignmentClass = isUser ? 'justify-end' : 'justify-start';
        const bgColor = isUser ? 'bg-primary text-white' : 'bg-gray-100 text-gray-900';
        
        messageDiv.innerHTML = `
            <div class="flex ${alignmentClass}">
                <div class="max-w-3xl ${bgColor} rounded-lg p-4 shadow-sm">
                    ${!isUser ? '<div class="flex items-center space-x-2 mb-2"><i class="ri-robot-line"></i><span class="text-sm font-medium">AI智能体</span></div>' : ''}
                    <div class="message-content">${messageData.content}</div>
                    ${messageData.timestamp ? `<div class="text-xs opacity-70 mt-2">${new Date(messageData.timestamp).toLocaleTimeString()}</div>` : ''}
                </div>
            </div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        // 如果有感知和决策数据，更新智能体状态
        if (messageData.perception_data && this.agentStatus) {
            this.agentStatus.updatePerceptionStatus(messageData.perception_data);
        }
        
        if (messageData.decision_data && this.agentStatus) {
            this.agentStatus.updateDecisionStatus(messageData.decision_data);
        }
    }
    
    async sendMessage() {
        const message = this.messageInput?.value.trim();
        if (!message || this.isProcessing) return;
        
        if (!this.sessionId) {
            this.showSystemMessage('请先创建面试会话', 'error');
            return;
        }
        
        try {
            this.isProcessing = true;
            this.updateSendButton(true);
            
            // 显示用户消息
            this.displayEnhancedMessage({
                role: 'user',
                content: message,
                timestamp: new Date().toISOString()
            });
            
            // 清空输入框
            this.messageInput.value = '';
            
            // 发送到增强的聊天API
            const token = localStorage.getItem('access_token');
            const response = await fetch('/api/v1/enhanced-chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message
                })
            });
            
            if (!response.ok) {
                throw new Error(`发送消息失败: ${response.status}`);
            }
            
            // 处理流式响应
            await this.handleStreamingResponse(response);
            
        } catch (error) {
            console.error('发送消息失败:', error);
            this.showSystemMessage(`发送失败: ${error.message}`, 'error');
        } finally {
            this.isProcessing = false;
            this.updateSendButton(false);
        }
    }
    
    async handleStreamingResponse(response) {
        const reader = response.body.getReader();
        let assistantMessage = '';
        let messageDiv = null;
        
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
                                    // 开始接收消息，创建消息容器
                                    messageDiv = this.createAssistantMessageContainer();
                                    if (this.agentStatus) {
                                        this.agentStatus.addActionToTimeline('start_response', '开始生成回应');
                                    }
                                    break;
                                    
                                case 'chunk':
                                    // 接收消息块
                                    assistantMessage += data.content;
                                    if (messageDiv) {
                                        this.updateMessageContent(messageDiv, assistantMessage);
                                    }
                                    break;
                                    
                                case 'profile_update':
                                    // 用户画像更新
                                    this.userProfile = data.profile;
                                    this.updateUserProfileDisplay(this.userProfile);
                                    if (this.agentStatus) {
                                        this.agentStatus.updateUserProfile(data.profile);
                                        this.agentStatus.updateActionStatus('database_update', '用户画像已更新');
                                    }
                                    break;
                                    
                                case 'complete':
                                    // 消息完成
                                    if (this.agentStatus) {
                                        this.agentStatus.addActionToTimeline('complete', '回应生成完成');
                                        this.agentStatus.resetStatusIndicators();
                                    }
                                    break;
                                    
                                case 'end':
                                    // 流结束
                                    console.log('✅ 消息处理完成');
                                    return;
                            }
                        } catch (error) {
                            console.error('解析消息数据失败:', error);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('读取流式响应失败:', error);
        }
    }
    
    createAssistantMessageContainer() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message-slide-in mb-6';
        messageDiv.innerHTML = `
            <div class="flex justify-start">
                <div class="max-w-3xl bg-gray-100 text-gray-900 rounded-lg p-4 shadow-sm">
                    <div class="flex items-center space-x-2 mb-2">
                        <i class="ri-robot-line text-blue-600"></i>
                        <span class="text-sm font-medium">AI智能体</span>
                        <div class="flex items-center space-x-1 text-xs text-gray-500">
                            <div class="w-1 h-1 bg-gray-400 rounded-full animate-pulse"></div>
                            <span>思考中</span>
                        </div>
                    </div>
                    <div class="message-content"></div>
                </div>
            </div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        return messageDiv;
    }
    
    updateMessageContent(messageDiv, content) {
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv) {
            contentDiv.textContent = content;
            
            // 移除"思考中"标识
            const thinkingIndicator = messageDiv.querySelector('.text-gray-500');
            if (thinkingIndicator) {
                thinkingIndicator.remove();
            }
        }
        this.scrollToBottom();
    }
    
    updateUserProfileDisplay(profile) {
        const completenessSpan = document.getElementById('profile-completeness');
        const detailsDiv = document.querySelector('.profile-details');
        
        if (!profile || !profile.basic_info) return;
        
        // 更新完整度
        const completeness = Math.round((profile.completeness_score || 0) * 100);
        if (completenessSpan) {
            completenessSpan.textContent = `${completeness}%`;
            completenessSpan.className = `font-medium ${completeness > 70 ? 'text-green-600' : completeness > 40 ? 'text-yellow-600' : 'text-red-600'}`;
        }
        
        // 更新详细信息
        if (detailsDiv) {
            const basicInfo = profile.basic_info;
            const infoItems = [
                { label: '工作年限', value: basicInfo.work_years, key: 'work_years' },
                { label: '当前公司', value: basicInfo.current_company, key: 'current_company' },
                { label: '学历水平', value: basicInfo.education_level, key: 'education_level' },
                { label: '毕业年份', value: basicInfo.graduation_year, key: 'graduation_year' }
            ];
            
            detailsDiv.innerHTML = infoItems.map(item => {
                const status = item.value ? '✅' : '❌';
                const value = item.value || '未知';
                return `
                    <div class="flex justify-between items-center">
                        <span class="text-gray-600">${item.label}:</span>
                        <span class="flex items-center space-x-1">
                            <span>${value}</span>
                            <span class="text-xs">${status}</span>
                        </span>
                    </div>
                `;
            }).join('');
        }
    }
    
    connectWebSocket() {
        if (!this.sessionId) return;
        
        // WebSocket连接逻辑（如果需要实时更新）
        console.log('🔌 WebSocket连接功能待实现');
    }
    
    updateSendButton(isProcessing) {
        if (!this.sendButton) return;
        
        if (isProcessing) {
            this.sendButton.disabled = true;
            this.sendButton.innerHTML = '<i class="ri-loader-line animate-spin"></i>';
        } else {
            this.sendButton.disabled = false;
            this.sendButton.textContent = '发送';
        }
    }
    
    showSystemMessage(message, type = 'info') {
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
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        // 3秒后自动移除系统消息
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 3000);
    }
    
    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
}

// 初始化增强面试系统
let enhancedInterviewSystem = null;

document.addEventListener('DOMContentLoaded', function() {
    // 检查是否在面试页面
    if (document.getElementById('chat-messages-container')) {
        enhancedInterviewSystem = new EnhancedInterviewSystem();
        console.log('🤖 增强面试系统已加载');
    }
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EnhancedInterviewSystem };
} else {
    window.EnhancedInterviewSystem = EnhancedInterviewSystem;
}
