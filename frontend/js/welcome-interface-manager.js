/**
 * 欢迎界面管理器
 * 负责管理主界面的欢迎页面显示、隐藏和交互逻辑
 * 与面试状态管理器和会话管理器协同工作
 */

class WelcomeInterfaceManager {
    constructor() {
        this.isWelcomeVisible = true;  // 默认显示欢迎界面
        this.currentSessionId = null;
        
        // UI 元素引用
        this.welcomeContainer = null;
        this.aiVideoMain = null;
        this.userVideoMain = null;
        this.codeEditorMain = null;
        this.startInterviewBtn = null;
        
        this.init();
    }
    
    init() {
        // 获取UI元素引用
        this.initializeUIElements();
        
        // 绑定事件监听器
        this.bindEvents();
        
        // 检查初始状态
        this.checkInitialState();
        
        console.log('✅ 欢迎界面管理器初始化完成');
    }
    
    /**
     * 初始化UI元素引用
     */
    initializeUIElements() {
        this.welcomeContainer = document.getElementById('welcome-interface');
        this.aiVideoMain = document.getElementById('ai-video-main');
        this.userVideoMain = document.getElementById('user-video-main');
        this.codeEditorMain = document.getElementById('code-editor-main');
        this.startInterviewBtn = document.getElementById('welcome-start-interview');
        
        if (!this.welcomeContainer) {
            console.error('❌ 未找到欢迎界面容器元素');
            return;
        }
        
        console.log('🎯 UI元素初始化完成');
    }
    
    /**
     * 绑定事件监听器
     */
    bindEvents() {
        // 开始面试按钮点击事件
        if (this.startInterviewBtn) {
            this.startInterviewBtn.addEventListener('click', () => {
                this.handleStartInterview();
            });
        }
        
        // 监听会话状态变化
        document.addEventListener('sessionSwitched', (event) => {
            this.handleSessionSwitch(event.detail);
        });
        
        // 监听面试状态变化
        document.addEventListener('interviewStateChanged', (event) => {
            this.handleInterviewStateChange(event.detail);
        });
        
        // 监听面试结束事件
        document.addEventListener('interviewEnded', (event) => {
            this.handleInterviewEnd(event.detail);
        });
        
        // 监听新会话创建
        document.addEventListener('newSessionCreated', (event) => {
            this.handleNewSessionCreated(event.detail);
        });
        
        // 监听页面加载和存储变化
        window.addEventListener('load', () => {
            setTimeout(() => this.checkInitialState(), 1000);
        });
        
        window.addEventListener('storage', (event) => {
            if (event.key === 'current_session_id') {
                this.handleStorageChange(event.newValue);
            }
        });
        
        console.log('🎯 事件监听器绑定完成');
    }
    
    /**
     * 检查初始状态并决定是否显示欢迎界面
     */
    async checkInitialState() {
        try {
            // 获取当前会话信息
            this.currentSessionId = localStorage.getItem('current_session_id');
            
            console.log('🔍 检查初始状态:', {
                currentSessionId: this.currentSessionId,
                isWelcomeVisible: this.isWelcomeVisible
            });
            
            if (!this.currentSessionId) {
                // 没有活跃会话，显示欢迎界面
                this.showWelcome();
            } else {
                // 有活跃会话，检查会话状态
                await this.checkSessionStatus();
            }
            
        } catch (error) {
            console.warn('⚠️ 检查初始状态失败:', error);
            // 出错时默认显示欢迎界面
            this.showWelcome();
        }
    }
    
    /**
     * 检查会话状态
     */
    async checkSessionStatus() {
        try {
            // 检查会话是否已结束
            const sessions = await this.loadUserSessions();
            const currentSession = sessions.find(s => s.session_id === this.currentSessionId);
            
            if (currentSession) {
                const isEnded = currentSession.interview_ended || currentSession.status === 'completed';
                
                if (isEnded) {
                    // 会话已结束，显示欢迎界面
                    console.log('📝 当前会话已结束，显示欢迎界面');
                    this.showWelcome();
                } else {
                    // 会话活跃，隐藏欢迎界面
                    console.log('▶️ 当前会话活跃，隐藏欢迎界面');
                    this.hideWelcome();
                }
            } else {
                // 会话不存在，显示欢迎界面
                console.log('❓ 当前会话不存在，显示欢迎界面');
                this.showWelcome();
            }
            
        } catch (error) {
            console.warn('⚠️ 检查会话状态失败:', error);
            // 出错时显示欢迎界面
            this.showWelcome();
        }
    }
    
    /**
     * 处理开始面试按钮点击
     */
    handleStartInterview() {
        console.log('🚀 用户点击开始面试');
        
        try {
            // 调用全局的创建新面试函数
            if (typeof window.createNewLangGraphSession === 'function') {
                window.createNewLangGraphSession();
            } else if (typeof createNewLangGraphSession === 'function') {
                createNewLangGraphSession();
            } else {
                // 如果全局函数不可用，模拟点击新建面试按钮
                const newInterviewBtn = document.getElementById('new-interview-btn');
                if (newInterviewBtn) {
                    newInterviewBtn.click();
                } else {
                    this.showMessage('无法启动新面试，请刷新页面重试', 'error');
                }
            }
            
        } catch (error) {
            console.error('❌ 启动新面试失败:', error);
            this.showMessage('启动新面试失败，请重试', 'error');
        }
    }
    
    /**
     * 处理会话切换事件
     */
    handleSessionSwitch(eventData) {
        console.log('🔄 处理会话切换:', eventData);
        
        const { sessionId, isNewSession } = eventData;
        this.currentSessionId = sessionId;
        
        if (isNewSession) {
            // 新会话创建，隐藏欢迎界面
            this.hideWelcome();
        } else if (sessionId) {
            // 切换到现有会话，需要检查会话状态
            this.checkSessionStatus();
        } else {
            // 没有会话，显示欢迎界面
            this.showWelcome();
        }
    }
    
    /**
     * 处理面试状态变化
     */
    handleInterviewStateChange(eventData) {
        console.log('📊 处理面试状态变化:', eventData);
        
        const { state } = eventData;
        
        if (state === 'ended') {
            // 面试结束，但不立即显示欢迎界面
            // 等待用户手动切换会话时再显示
            console.log('🏁 面试已结束，等待用户操作');
        } else if (state === 'active') {
            // 面试活跃，隐藏欢迎界面
            this.hideWelcome();
        } else if (state === 'cleared') {
            // 会话已清除，确保显示欢迎界面
            console.log('🧹 会话已清除，确保显示欢迎界面');
            this.forceShowWelcome();
        }
    }
    
    /**
     * 处理面试结束事件
     */
    handleInterviewEnd(eventData) {
        console.log('🏁 处理面试结束事件:', eventData);
        // 面试结束时不立即显示欢迎界面，保持当前状态
        // 用户需要主动切换会话时才显示欢迎界面
    }
    
    /**
     * 处理新会话创建
     */
    handleNewSessionCreated(eventData) {
        console.log('🆕 处理新会话创建:', eventData);
        
        const { sessionId } = eventData;
        this.currentSessionId = sessionId;
        
        // 新会话创建时隐藏欢迎界面
        this.hideWelcome();
    }
    
    /**
     * 处理localStorage变化
     */
    handleStorageChange(newSessionId) {
        console.log('📦 处理存储变化:', {
            from: this.currentSessionId,
            to: newSessionId
        });
        
        this.currentSessionId = newSessionId;
        
        if (!newSessionId) {
            // 会话被清除，显示欢迎界面
            this.showWelcome();
        } else {
            // 切换到新会话，检查状态
            this.checkSessionStatus();
        }
    }
    
    /**
     * 显示欢迎界面
     */
    showWelcome() {
        if (this.isWelcomeVisible) {
            console.log('💡 欢迎界面已经显示');
            return;
        }
        
        console.log('🎉 显示欢迎界面');
        
        // 显示欢迎界面
        if (this.welcomeContainer) {
            this.welcomeContainer.classList.remove('hidden');
            this.welcomeContainer.classList.add('flex');
        }
        
        // 隐藏其他主界面元素
        this.hideMainElements();
        
        // 更新状态
        this.isWelcomeVisible = true;
        
        // 触发自定义事件
        this.dispatchWelcomeStateEvent('shown');
    }
    
    /**
     * 隐藏欢迎界面
     */
    hideWelcome() {
        if (!this.isWelcomeVisible) {
            console.log('💡 欢迎界面已经隐藏');
            return;
        }
        
        console.log('🙈 隐藏欢迎界面');
        
        // 隐藏欢迎界面
        if (this.welcomeContainer) {
            this.welcomeContainer.classList.add('hidden');
            this.welcomeContainer.classList.remove('flex');
        }
        
        // 显示AI视频主界面（默认）
        this.showMainElements();
        
        // 更新状态
        this.isWelcomeVisible = false;
        
        // 触发自定义事件
        this.dispatchWelcomeStateEvent('hidden');
    }
    
    /**
     * 隐藏主界面元素
     */
    hideMainElements() {
        const elements = [this.aiVideoMain, this.userVideoMain, this.codeEditorMain];
        elements.forEach(element => {
            if (element) {
                element.classList.add('hidden');
            }
        });
    }
    
    /**
     * 显示主界面元素（默认显示AI视频）
     */
    showMainElements() {
        // 默认显示AI视频主界面
        if (this.aiVideoMain) {
            this.aiVideoMain.classList.remove('hidden');
        }
        
        // 确保其他元素隐藏
        if (this.userVideoMain) {
            this.userVideoMain.classList.add('hidden');
        }
        if (this.codeEditorMain) {
            this.codeEditorMain.classList.add('hidden');
        }
    }
    
    /**
     * 强制隐藏所有面试相关的UI元素
     */
    forceHideAllInterviewElements() {
        console.log('🧹 强制隐藏所有面试相关元素');
        
        // 隐藏所有主界面元素
        const elements = [this.aiVideoMain, this.userVideoMain, this.codeEditorMain];
        elements.forEach(element => {
            if (element) {
                element.classList.add('hidden');
            }
        });
        
        // 隐藏聊天消息容器
        const chatContainer = document.getElementById('chat-messages-container');
        if (chatContainer) {
            chatContainer.classList.add('hidden');
        }
        
        // 清除任何可能存在的面试结束遮罩
        const endOverlay = document.getElementById('input-disabled-overlay');
        if (endOverlay) {
            endOverlay.remove();
            document.body.style.overflow = ''; // 恢复页面滚动
        }
        
        // 重置底部控制栏状态
        this.resetBottomControls();
    }
    
    /**
     * 重置底部控制栏状态
     */
    resetBottomControls() {
        // 启用所有输入控件
        const micButton = document.querySelector('.mic-pulse');
        if (micButton) {
            micButton.disabled = false;
            micButton.style.opacity = '';
            micButton.style.cursor = '';
            micButton.title = '';
        }
        
        const textInputButton = document.querySelector('[class*="ri-keyboard-line"]')?.closest('button');
        if (textInputButton) {
            textInputButton.disabled = false;
            textInputButton.style.opacity = '';
            textInputButton.style.cursor = '';
            textInputButton.title = '';
        }
        
        const fileUploadButton = document.querySelector('[class*="ri-attachment-line"]')?.closest('button');
        if (fileUploadButton) {
            fileUploadButton.disabled = false;
            fileUploadButton.style.opacity = '';
            fileUploadButton.style.cursor = '';
            fileUploadButton.title = '';
        }
        
        // 显示结束面试按钮
        const endInterviewBtn = document.getElementById('endInterviewBtn');
        if (endInterviewBtn) {
            endInterviewBtn.style.display = '';
        }
    }
    
    /**
     * 强制显示欢迎界面（公共方法）
     */
    forceShowWelcome() {
        console.log('🔨 强制显示欢迎界面');
        
        // 清除当前会话状态
        this.currentSessionId = null;
        
        // 强制隐藏所有面试相关的UI元素
        this.forceHideAllInterviewElements();
        
        // 重置状态以确保显示
        this.isWelcomeVisible = false; 
        this.showWelcome();
    }
    
    /**
     * 强制隐藏欢迎界面（公共方法）
     */
    forceHideWelcome() {
        console.log('🔨 强制隐藏欢迎界面');
        this.isWelcomeVisible = true; // 重置状态以确保隐藏
        this.hideWelcome();
    }
    
    /**
     * 获取用户会话列表
     */
    async loadUserSessions() {
        try {
            const response = await this.callAPI('/langgraph-chat/sessions');
            return response.sessions || [];
        } catch (error) {
            console.error('❌ 获取会话列表失败:', error);
            return [];
        }
    }
    
    /**
     * API调用
     */
    async callAPI(endpoint, method = 'GET', data = null) {
        try {
            const url = `/api/v1${endpoint}`;
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
            
            if (!response.ok) {
                let errorData = {};
                try {
                    errorData = await response.json();
                } catch (e) {
                    console.error('解析错误响应失败:', e);
                }
                const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error('API调用失败:', error);
            throw error;
        }
    }
    
    /**
     * 显示消息提示
     */
    showMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        const typeClasses = {
            'info': 'bg-blue-50 border-blue-200 text-blue-800',
            'success': 'bg-green-50 border-green-200 text-green-800', 
            'error': 'bg-red-50 border-red-200 text-red-800',
            'warning': 'bg-yellow-50 border-yellow-200 text-yellow-800'
        };
        
        messageDiv.className = `fixed top-4 right-4 z-50 p-4 border rounded-lg shadow-lg ${typeClasses[type] || typeClasses.info} max-w-md`;
        messageDiv.innerHTML = `
            <div class="flex items-center space-x-2">
                <i class="ri-information-line"></i>
                <span>${message}</span>
                <button onclick="this.parentNode.parentNode.remove()" class="ml-2 text-current opacity-70 hover:opacity-100">
                    <i class="ri-close-line"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(messageDiv);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 3000);
    }
    
    /**
     * 触发欢迎界面状态变化事件
     */
    dispatchWelcomeStateEvent(state) {
        const event = new CustomEvent('welcomeStateChanged', {
            detail: {
                state: state, // 'shown' | 'hidden'
                isVisible: this.isWelcomeVisible,
                sessionId: this.currentSessionId,
                timestamp: Date.now()
            }
        });
        
        document.dispatchEvent(event);
        console.log('📡 欢迎界面状态变化事件已触发:', state);
    }
    
    /**
     * 获取当前状态
     */
    getCurrentState() {
        return {
            isVisible: this.isWelcomeVisible,
            sessionId: this.currentSessionId
        };
    }
    
    /**
     * 销毁管理器
     */
    destroy() {
        // 清理事件监听器
        // (由于使用了addEventListener，在页面卸载时会自动清理)
        
        // 重置状态
        this.isWelcomeVisible = false;
        this.currentSessionId = null;
        
        console.log('🗑️ 欢迎界面管理器已销毁');
    }
}

// 创建全局实例
let welcomeInterfaceManager = null;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    welcomeInterfaceManager = new WelcomeInterfaceManager();
    
    // 暴露到全局作用域
    window.welcomeInterfaceManager = welcomeInterfaceManager;
    
    console.log('✅ 欢迎界面管理器已加载');
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WelcomeInterfaceManager };
} else {
    window.WelcomeInterfaceManager = WelcomeInterfaceManager;
}
