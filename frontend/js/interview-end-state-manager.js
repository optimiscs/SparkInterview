/**
 * 面试结束状态管理器
 * 处理面试结束后的UI状态、报告入口显示和输入禁用功能
 */

class InterviewEndStateManager {
    constructor() {
        this.isInterviewEnded = false;
        this.currentSessionId = null;
        this.reportId = null;
        
        this.init();
    }
    
    init() {
        // 绑定事件监听器
        this.bindEvents();
        
        // 初始化UI状态检查
        this.checkInitialState();
        
        console.log('✅ 面试结束状态管理器初始化完成');
    }
    
    bindEvents() {
        // 监听面试完成管理器的状态变化
        document.addEventListener('interviewEnded', (event) => {
            this.handleInterviewEnd(event.detail);
        });
        
        // 监听会话切换事件
        document.addEventListener('sessionSwitched', (event) => {
            this.handleSessionSwitch(event.detail);
        });
        
        // 页面刷新时检查状态
        window.addEventListener('load', () => {
            this.checkInitialState();
        });
        
        // 监听全局会话变化（通过localStorage监听）
        window.addEventListener('storage', (event) => {
            if (event.key === 'current_session_id') {
                this.handleStorageSessionChange(event.newValue);
            }
        });
        
        // 定期检查会话状态变化
        this.startSessionMonitoring();
    }
    
    /**
     * 检查页面初始状态
     */
    async checkInitialState() {
        try {
            // 从localStorage获取当前会话信息
            this.currentSessionId = localStorage.getItem('current_session_id');
            
            if (this.currentSessionId) {
                // 检查会话是否已结束
                await this.checkSessionEndStatus();
            }
        } catch (error) {
            console.warn('⚠️ 检查初始状态失败:', error);
        }
    }
    
    /**
     * 检查会话结束状态
     */
    async checkSessionEndStatus() {
        try {
            const sessions = await this.loadUserSessions();
            const currentSession = sessions.find(s => s.session_id === this.currentSessionId);
            
            if (currentSession) {
                const isEnded = currentSession.interview_ended || currentSession.status === 'completed';
                const reportId = currentSession.report_id;
                
                if (isEnded) {
                    this.setInterviewEndedState(this.currentSessionId, reportId);
                } else {
                    this.setInterviewActiveState();
                }
            }
        } catch (error) {
            console.warn('⚠️ 检查会话状态失败:', error);
        }
    }
    
    /**
     * 处理面试结束事件
     */
    handleInterviewEnd(eventData) {
        console.log('🏁 接收到面试结束事件:', eventData);
        
        const { sessionId, reportId, summaryMessage } = eventData;
        this.setInterviewEndedState(sessionId, reportId, summaryMessage);
    }
    
    /**
     * 开始会话状态监控
     */
    startSessionMonitoring() {
        // 每2秒检查一次会话状态变化
        this.sessionMonitorInterval = setInterval(() => {
            this.checkCurrentSessionChange();
        }, 2000);
        
        console.log('🔍 会话状态监控已启动');
    }
    
    /**
     * 检查当前会话是否发生变化
     */
    async checkCurrentSessionChange() {
        const currentStoredSessionId = localStorage.getItem('current_session_id');
        
        if (currentStoredSessionId !== this.currentSessionId) {
            console.log('🔄 检测到会话变化:', {
                from: this.currentSessionId,
                to: currentStoredSessionId
            });
            
            this.handleStorageSessionChange(currentStoredSessionId);
        }
    }
    
    /**
     * 处理通过localStorage监听到的会话变化
     */
    handleStorageSessionChange(newSessionId) {
        console.log('📦 Storage会话变化:', { 
            from: this.currentSessionId, 
            to: newSessionId 
        });
        
        this.currentSessionId = newSessionId;
        
        if (newSessionId) {
            // 切换到新会话，检查其状态
            this.checkSessionEndStatus();
        } else {
            // 没有会话，设置为活跃状态（清除结束状态）
            this.setInterviewActiveState();
        }
    }
    
    /**
     * 处理会话切换事件
     */
    handleSessionSwitch(eventData) {
        console.log('🔄 接收到会话切换事件:', eventData);
        
        const { sessionId } = eventData;
        this.currentSessionId = sessionId;
        
        // 重新检查新会话的状态
        this.checkSessionEndStatus();
    }
    
    /**
     * 设置面试已结束状态
     */
    setInterviewEndedState(sessionId, reportId = null, summaryMessage = null) {
        this.isInterviewEnded = true;
        this.currentSessionId = sessionId;
        this.reportId = reportId;
        
        console.log('🔒 设置面试结束状态:', { sessionId, reportId });
        
        // 禁用输入功能（显示全屏居中提示弹框）
        this.disableInterviewInputs();
        
        // 更新底部控制栏
        this.updateBottomControls();
        
        // 触发自定义事件
        this.dispatchStateChangeEvent('ended');
    }
    
    /**
     * 设置面试活跃状态
     */
    setInterviewActiveState() {
        this.isInterviewEnded = false;
        this.reportId = null;
        
        console.log('▶️ 设置面试活跃状态');
        
        // 启用输入功能（移除全屏提示弹框）
        this.enableInterviewInputs();
        
        // 恢复底部控制栏
        this.restoreBottomControls();
        
        // 触发自定义事件
        this.dispatchStateChangeEvent('active');
    }
    

    
    /**
     * 禁用面试输入功能
     */
    disableInterviewInputs() {
        // 禁用麦克风按钮
        const micButton = document.querySelector('.mic-pulse');
        if (micButton) {
            micButton.disabled = true;
            micButton.style.opacity = '0.5';
            micButton.style.cursor = 'not-allowed';
            micButton.title = '面试已结束，无法继续录音';
        }
        
        // 禁用文字输入按钮
        const textInputButton = document.querySelector('[class*="ri-keyboard-line"]')?.closest('button');
        if (textInputButton) {
            textInputButton.disabled = true;
            textInputButton.style.opacity = '0.5';
            textInputButton.style.cursor = 'not-allowed';
            textInputButton.title = '面试已结束，无法发送消息';
        }
        
        // 禁用文件上传按钮
        const fileUploadButton = document.querySelector('[class*="ri-attachment-line"]')?.closest('button');
        if (fileUploadButton) {
            fileUploadButton.disabled = true;
            fileUploadButton.style.opacity = '0.5';
            fileUploadButton.style.cursor = 'not-allowed';
            fileUploadButton.title = '面试已结束，无法上传文件';
        }
        
        // 在控制区域添加禁用遮罩
        this.addInputDisabledOverlay();
        
        console.log('🔒 面试输入功能已禁用');
    }
    
    /**
     * 启用面试输入功能
     */
    enableInterviewInputs() {
        // 启用麦克风按钮
        const micButton = document.querySelector('.mic-pulse');
        if (micButton) {
            micButton.disabled = false;
            micButton.style.opacity = '';
            micButton.style.cursor = '';
            micButton.title = '';
        }
        
        // 启用文字输入按钮
        const textInputButton = document.querySelector('[class*="ri-keyboard-line"]')?.closest('button');
        if (textInputButton) {
            textInputButton.disabled = false;
            textInputButton.style.opacity = '';
            textInputButton.style.cursor = '';
            textInputButton.title = '';
        }
        
        // 启用文件上传按钮
        const fileUploadButton = document.querySelector('[class*="ri-attachment-line"]')?.closest('button');
        if (fileUploadButton) {
            fileUploadButton.disabled = false;
            fileUploadButton.style.opacity = '';
            fileUploadButton.style.cursor = '';
            fileUploadButton.title = '';
        }
        
        // 移除禁用遮罩
        this.removeInputDisabledOverlay();
        
        console.log('🔓 面试输入功能已启用');
    }
    
    /**
     * 添加输入禁用遮罩（全屏覆盖）
     */
    addInputDisabledOverlay() {
        // 移除现有遮罩
        this.removeInputDisabledOverlay();
        
        const overlay = document.createElement('div');
        overlay.id = 'input-disabled-overlay';
        overlay.className = 'fixed inset-0 bg-gray-900 bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50';
        
        overlay.innerHTML = `
            <div class="bg-white rounded-xl shadow-2xl p-8 max-w-md mx-4 text-center transform scale-100 transition-all duration-300">
                <div class="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6">
                    <i class="ri-lock-line text-orange-600 text-2xl"></i>
                </div>
                <h3 class="text-xl font-bold text-gray-900 mb-4">面试已结束</h3>
                <p class="text-gray-600 leading-relaxed mb-6">无法继续进行面试交互，请查看面试报告了解详细评估结果。</p>
                <div class="space-y-3">
                    <button id="overlay-view-report" class="w-full px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all duration-200 font-medium">
                        <i class="ri-file-text-line mr-2"></i>
                        查看面试报告
                    </button>
                    <button id="overlay-switch-session" class="w-full px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors duration-200 font-medium">
                        <i class="ri-arrow-left-line mr-2"></i>
                        切换其他会话
                    </button>
                </div>
            </div>
        `;
        
        // 添加到页面根部
        document.body.appendChild(overlay);
        
        // 阻止页面滚动
        document.body.style.overflow = 'hidden';
        
        // 绑定按钮事件
        this.bindOverlayEvents();
        
        console.log('🛡️ 全屏面试结束遮罩已显示');
    }
    
    /**
     * 绑定遮罩按钮事件
     */
    bindOverlayEvents() {
        // 查看报告按钮
        const viewReportBtn = document.getElementById('overlay-view-report');
        if (viewReportBtn) {
            viewReportBtn.addEventListener('click', () => {
                if (this.reportId) {
                    this.openReportPage();
                } else {
                    this.generateAndOpenReport();
                }
            });
        }
        
        // 切换会话按钮
        const switchSessionBtn = document.getElementById('overlay-switch-session');
        if (switchSessionBtn) {
            switchSessionBtn.addEventListener('click', () => {
                this.triggerSessionSwitch();
            });
        }
    }
    
    /**
     * 触发会话切换
     */
    triggerSessionSwitch() {
        console.log('🔄 触发会话切换');
        
        // 清除当前会话状态
        localStorage.removeItem('current_session_id');
        
        // 移除结束提示遮罩
        this.removeInputDisabledOverlay();
        
        // 重置当前状态但不激活面试
        this.currentSessionId = null;
        this.isInterviewEnded = false;
        this.reportId = null;
        
        // 显示欢迎界面
        if (window.welcomeInterfaceManager) {
            window.welcomeInterfaceManager.forceShowWelcome();
        }
        
        // 触发状态变化事件（设置为非面试状态）
        this.dispatchStateChangeEvent('cleared');
        
        console.log('🔄 已清除当前会话，显示欢迎界面');
    }
    
    /**
     * 移除输入禁用遮罩
     */
    removeInputDisabledOverlay() {
        const overlay = document.getElementById('input-disabled-overlay');
        if (overlay) {
            overlay.remove();
            
            // 恢复页面滚动
            document.body.style.overflow = '';
            
            console.log('🗑️ 全屏面试结束遮罩已移除');
        }
    }
    
    /**
     * 更新底部控制栏
     */
    updateBottomControls() {
        // 隐藏结束面试按钮
        const endInterviewBtn = document.getElementById('endInterviewBtn');
        if (endInterviewBtn) {
            endInterviewBtn.style.display = 'none';
        }
        
        // 更新状态指示
        const statusElements = document.querySelectorAll('[data-status]');
        statusElements.forEach(element => {
            if (element.textContent.includes('录音中')) {
                element.innerHTML = '<div class="w-2 h-2 bg-gray-500 rounded-full"></div><span>面试已结束</span>';
            }
        });
    }
    
    /**
     * 恢复底部控制栏
     */
    restoreBottomControls() {
        // 显示结束面试按钮
        const endInterviewBtn = document.getElementById('endInterviewBtn');
        if (endInterviewBtn) {
            endInterviewBtn.style.display = '';
        }
    }
    
    /**
     * 打开报告页面
     */
    openReportPage() {
        if (!this.currentSessionId) {
            this.showMessage('会话信息缺失，无法查看报告', 'error');
            return;
        }
        
        const reportUrl = this.reportId 
            ? `./interview_report.html?session_id=${this.currentSessionId}&report_id=${this.reportId}`
            : `./interview_report.html?session_id=${this.currentSessionId}`;
            
        console.log('🔗 打开报告页面:', reportUrl);
        window.open(reportUrl, '_blank');
    }
    
    /**
     * 生成并打开报告
     */
    async generateAndOpenReport() {
        if (!this.currentSessionId) {
            this.showMessage('会话信息缺失，无法生成报告', 'error');
            return;
        }
        
        try {
            // 显示生成中状态
            this.showGeneratingState();
            
            console.log('📊 开始生成面试报告:', this.currentSessionId);
            
            // 调用报告生成API
            const response = await this.callAPI(`/langgraph-chat/sessions/${this.currentSessionId}/generate-report`, 'POST');
            
            if (response.success) {
                this.reportId = response.report_id;
                
                // 保存报告ID
                localStorage.setItem(`report_id_${this.currentSessionId}`, this.reportId);
                
                // 更新UI状态
                this.updateReportButtons();
                
                // 打开报告页面
                this.openReportPage();
                
                this.showMessage('✅ 报告生成成功', 'success');
                
            } else {
                throw new Error(response.message || '生成报告失败');
            }
            
        } catch (error) {
            console.error('❌ 生成报告失败:', error);
            this.showMessage(`生成报告失败: ${error.message}`, 'error');
        } finally {
            this.hideGeneratingState();
        }
    }
    
    /**
     * 显示报告生成中状态
     */
    showGeneratingState() {
        const buttons = document.querySelectorAll('#view-report-btn, #generate-report-btn, #panel-report-btn, #overlay-view-report');
        buttons.forEach(btn => {
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="ri-loader-line animate-spin mr-1"></i>生成中...';
            }
        });
    }
    
    /**
     * 隐藏报告生成中状态
     */
    hideGeneratingState() {
        // 将在updateReportButtons中更新
        this.updateReportButtons();
    }
    
    /**
     * 更新报告按钮状态
     */
    updateReportButtons() {
        const buttonText = this.reportId ? '查看报告' : '生成报告';
        const buttonIcon = this.reportId ? 'ri-file-text-line' : 'ri-file-add-line';
        
        const buttons = document.querySelectorAll('#view-report-btn, #generate-report-btn, #panel-report-btn, #overlay-view-report');
        buttons.forEach(btn => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="${buttonIcon} mr-1"></i>${buttonText}`;
            }
        });
    }
    
    /**
     * 加载用户会话列表
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
     * API调用函数
     */
    async callAPI(endpoint, method = 'GET', data = null) {
        try {
            const url = `/api/v1${endpoint}`;
            console.log('API调用:', method, url);
            
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
     * 触发状态变化事件
     */
    dispatchStateChangeEvent(newState) {
        const event = new CustomEvent('interviewStateChanged', {
            detail: {
                state: newState, // 'ended' | 'active' | 'cleared'
                sessionId: this.currentSessionId,
                reportId: this.reportId,
                timestamp: Date.now()
            }
        });
        
        document.dispatchEvent(event);
        console.log('📡 面试状态变化事件已触发:', newState);
    }
    
    /**
     * 获取当前状态
     */
    getCurrentState() {
        return {
            isEnded: this.isInterviewEnded,
            sessionId: this.currentSessionId,
            reportId: this.reportId
        };
    }
    
    /**
     * 重置状态
     */
    resetState() {
        this.isInterviewEnded = false;
        this.currentSessionId = null;
        this.reportId = null;
        
        // 恢复UI状态
        this.setInterviewActiveState();
        
        console.log('🔄 面试结束状态已重置');
    }
    
    /**
     * 销毁管理器
     */
    destroy() {
        // 清理定时器
        if (this.sessionMonitorInterval) {
            clearInterval(this.sessionMonitorInterval);
            this.sessionMonitorInterval = null;
        }
        
        // 清理UI
        this.removeInputDisabledOverlay();
        this.enableInterviewInputs();
        
        // 重置状态
        this.resetState();
        
        console.log('🗑️ 面试结束状态管理器已销毁');
    }
}

// 创建全局实例
let interviewEndStateManager = null;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    interviewEndStateManager = new InterviewEndStateManager();
    
    // 暴露到全局作用域
    window.interviewEndStateManager = interviewEndStateManager;
    
    console.log('✅ 面试结束状态管理器已加载');
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { InterviewEndStateManager };
} else {
    window.InterviewEndStateManager = InterviewEndStateManager;
}
