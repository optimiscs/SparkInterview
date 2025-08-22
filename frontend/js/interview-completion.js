/**
 * 面试完成和报告生成功能
 * 处理手动结束面试、生成报告、跳转报告页面等功能
 */

class InterviewCompletionManager {
    constructor() {
        this.currentSessionId = null;
        this.reportGenerating = false;
        this.interviewEnded = false;
        
        this.init();
    }
    
    init() {
        // 绑定事件监听器
        this.bindEvents();
        
        // 监听会话状态变化
        this.monitorSessionStatus();
        
        console.log('✅ 面试完成管理器初始化成功');
    }
    
    bindEvents() {
        // 结束面试按钮
        const endInterviewBtn = document.getElementById('endInterviewBtn');
        if (endInterviewBtn) {
            endInterviewBtn.addEventListener('click', () => this.endInterview());
        }
        
        // 查看报告按钮
        const generateReportBtn = document.getElementById('generateReportBtn');
        if (generateReportBtn) {
            generateReportBtn.addEventListener('click', () => this.viewInterviewReport());
        }
    }
    
    /**
     * 监听会话状态变化，控制按钮显示
     */
    monitorSessionStatus() {
        // 监听全局会话状态变化
        const observer = new MutationObserver(() => {
            this.updateControlsVisibility();
        });
        
        // 观察消息容器变化
        const messagesContainer = document.getElementById('chat-messages-container');
        if (messagesContainer) {
            observer.observe(messagesContainer, { childList: true, subtree: true });
        }
        
        // 定期检查会话状态
        setInterval(() => this.checkSessionStatus(), 5000);
    }
    
    /**
     * 检查当前会话状态
     */
    checkSessionStatus() {
        // 从localStorage获取当前会话ID
        this.currentSessionId = localStorage.getItem('current_session_id');
        
        // 更新控件可见性
        this.updateControlsVisibility();
    }
    
    /**
     * 更新控件可见性
     */
    updateControlsVisibility() {
        const endBtn = document.getElementById('endInterviewBtn');
        const reportBtn = document.getElementById('generateReportBtn');
        const sessionStatus = document.getElementById('session-status');
        
        if (this.currentSessionId && !this.interviewEnded) {
            // 有活跃会话且未结束，显示结束面试按钮
            if (endBtn) {
                endBtn.classList.remove('hidden');
            }
            if (sessionStatus) {
                sessionStatus.textContent = '面试进行中';
                sessionStatus.className = 'text-sm text-green-600';
            }
        } else if (this.interviewEnded) {
            // 面试已结束，显示查看报告按钮
            if (endBtn) {
                endBtn.classList.add('hidden');
            }
            if (reportBtn) {
                reportBtn.classList.remove('hidden');
            }
            if (sessionStatus) {
                sessionStatus.textContent = '面试已结束';
                sessionStatus.className = 'text-sm text-orange-600';
            }
        } else {
            // 没有会话，隐藏所有按钮
            if (endBtn) endBtn.classList.add('hidden');
            if (reportBtn) reportBtn.classList.add('hidden');
            if (sessionStatus) {
                sessionStatus.textContent = '等待开始';
                sessionStatus.className = 'text-sm text-gray-600';
            }
        }
    }
    
    /**
     * 手动结束面试
     */
    async endInterview() {
        if (!this.currentSessionId) {
            this.showMessage('没有活跃的面试会话', 'error');
            return;
        }
        
        // 确认对话
        const confirmed = confirm('确定要结束当前面试吗？结束后将生成面试报告。');
        if (!confirmed) return;
        
        try {
            const endBtn = document.getElementById('endInterviewBtn');
            
            // 更新按钮状态
            if (endBtn) {
                endBtn.disabled = true;
                endBtn.innerHTML = '<i class="ri-loader-line animate-spin mr-1"></i>结束中...';
            }
            
            console.log('🏁 手动结束面试:', this.currentSessionId);
            
            // 调用后端API结束面试
            const response = await this.callAPI(`/langgraph-chat/sessions/${this.currentSessionId}/end`, 'POST');
            
            if (response.success) {
                // 标记面试已结束
                this.interviewEnded = true;
                
                // 显示结束消息
                this.displayEndMessage(response.summary_message, response.report_id);
                
                // 更新控件状态
                this.updateControlsVisibility();
                
                // 保存报告ID
                if (response.report_id) {
                    localStorage.setItem(`report_id_${this.currentSessionId}`, response.report_id);
                }
                
                // 触发面试结束事件，通知状态管理器
                this.dispatchInterviewEndEvent(response.summary_message, response.report_id);
                
                this.showMessage('✅ 面试已结束，报告已生成', 'success');
                
            } else {
                throw new Error(response.message || '结束面试失败');
            }
            
        } catch (error) {
            console.error('❌ 结束面试失败:', error);
            this.showMessage(`结束面试失败: ${error.message}`, 'error');
            
            // 恢复按钮状态
            const endBtn = document.getElementById('endInterviewBtn');
            if (endBtn) {
                endBtn.disabled = false;
                endBtn.innerHTML = '<i class="ri-flag-line mr-1"></i>结束面试';
            }
        }
    }
    
    /**
     * 查看面试报告
     */
    async viewInterviewReport() {
        if (!this.currentSessionId) {
            this.showMessage('没有面试会话信息', 'error');
            return;
        }
        
        try {
            // 优先从localStorage获取报告ID
            let reportId = localStorage.getItem(`report_id_${this.currentSessionId}`);
            
            // 如果localStorage没有，从会话数据中获取
            if (!reportId) {
                const sessions = await this.loadUserSessions();
                const currentSession = sessions.find(s => s.session_id === this.currentSessionId);
                if (currentSession && currentSession.report_id) {
                    reportId = currentSession.report_id;
                    // 同步到localStorage
                    localStorage.setItem(`report_id_${this.currentSessionId}`, reportId);
                }
            }
            
            if (reportId) {
                // 直接跳转到报告页面
                this.navigateToReport(reportId);
            } else {
                // 生成新报告
                await this.generateReport();
            }
            
        } catch (error) {
            console.error('❌ 查看报告失败:', error);
            this.showMessage(`查看报告失败: ${error.message}`, 'error');
        }
    }
    
    /**
     * 获取用户会话列表（复用langgraph-interview.js的逻辑）
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
     * 生成面试报告
     */
    async generateReport() {
        if (this.reportGenerating) return;
        
        try {
            this.reportGenerating = true;
            const reportBtn = document.getElementById('generateReportBtn');
            
            // 更新按钮状态
            if (reportBtn) {
                reportBtn.disabled = true;
                reportBtn.innerHTML = '<i class="ri-loader-line animate-spin mr-1"></i>生成中...';
            }
            
            console.log('📊 开始生成面试报告:', this.currentSessionId);
            
            // 调用报告生成API
            const response = await this.callAPI(`/langgraph-chat/sessions/${this.currentSessionId}/generate-report`, 'POST');
            
            if (response.success) {
                const reportId = response.report_id;
                
                // 保存报告ID
                localStorage.setItem(`report_id_${this.currentSessionId}`, reportId);
                
                // 跳转到报告页面
                this.navigateToReport(reportId);
                
                this.showMessage('✅ 报告生成成功', 'success');
                
            } else {
                throw new Error(response.message || '生成报告失败');
            }
            
        } catch (error) {
            console.error('❌ 生成报告失败:', error);
            this.showMessage(`生成报告失败: ${error.message}`, 'error');
            
        } finally {
            this.reportGenerating = false;
            
            // 恢复按钮状态
            const reportBtn = document.getElementById('generateReportBtn');
            if (reportBtn) {
                reportBtn.disabled = false;
                reportBtn.innerHTML = '<i class="ri-file-text-line mr-1"></i>查看报告';
            }
        }
    }
    
    /**
     * 跳转到报告页面
     */
    navigateToReport(reportId) {
        const reportUrl = `./interview_report.html?session_id=${this.currentSessionId}&report_id=${reportId}`;
        console.log('🔗 跳转到报告页面:', reportUrl);
        window.open(reportUrl, '_blank');
    }
    
    /**
     * 显示面试结束消息
     */
    displayEndMessage(summaryMessage, reportId) {
        const messagesContainer = document.getElementById('chat-messages-container');
        if (!messagesContainer) return;
        
        const endMessageDiv = document.createElement('div');
        endMessageDiv.className = 'message-slide-in mb-6';
        
        endMessageDiv.innerHTML = `
            <div class="flex justify-center">
                <div class="max-w-3xl bg-gradient-to-r from-orange-50 to-red-50 border border-orange-200 rounded-lg p-6 shadow-sm">
                    <div class="flex items-center space-x-3 mb-4">
                        <div class="w-12 h-12 bg-gradient-to-r from-orange-500 to-red-500 rounded-full flex items-center justify-center">
                            <i class="ri-flag-line text-white text-xl"></i>
                        </div>
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900">面试结束</h3>
                            <p class="text-sm text-gray-600">感谢您参与本次面试</p>
                        </div>
                    </div>
                    
                    <div class="bg-white rounded-lg p-4 mb-4">
                        <p class="text-gray-800 leading-relaxed">${summaryMessage}</p>
                    </div>
                    
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-2 text-sm text-gray-600">
                            <i class="ri-time-line"></i>
                            <span>面试结束时间: ${new Date().toLocaleString('zh-CN')}</span>
                        </div>
                        ${reportId ? `
                            <button onclick="window.interviewCompletion?.navigateToReport('${reportId}')" 
                                    class="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors text-sm">
                                <i class="ri-file-text-line mr-1"></i>
                                立即查看报告
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(endMessageDiv);
        this.scrollToBottom();
    }
    
    /**
     * 处理智能体返回的end_interview响应
     */
    handleEndInterviewResponse(responseData) {
        if (responseData.decision && responseData.decision.action_type === 'end_interview') {
            console.log('🏁 智能体自动结束面试');
            
            // 标记面试已结束
            this.interviewEnded = true;
            
            // 更新控件显示
            this.updateControlsVisibility();
            
            // 如果有报告ID，保存它
            if (responseData.report_id) {
                localStorage.setItem(`report_id_${this.currentSessionId}`, responseData.report_id);
            }
            
            // 触发面试结束事件，通知状态管理器
            this.dispatchInterviewEndEvent(responseData.summary_message, responseData.report_id);
        }
    }
    
    /**
     * 重置状态（新会话开始时调用）
     */
    resetState() {
        this.interviewEnded = false;
        this.reportGenerating = false;
        this.updateControlsVisibility();
        console.log('🔄 面试完成管理器状态已重置');
    }
    
    /**
     * 设置当前会话ID
     */
    async setCurrentSession(sessionId) {
        this.currentSessionId = sessionId;
        
        // 检查会话是否已结束并有报告
        await this.checkSessionReportStatus(sessionId);
        
        console.log('📝 设置当前会话:', sessionId, '面试已结束:', this.interviewEnded);
    }
    
    /**
     * 检查会话的报告状态
     */
    async checkSessionReportStatus(sessionId) {
        try {
            const sessions = await this.loadUserSessions();
            const session = sessions.find(s => s.session_id === sessionId);
            
            if (session) {
                this.interviewEnded = session.interview_ended || false;
                
                // 如果有报告ID，保存到localStorage
                if (session.report_id) {
                    localStorage.setItem(`report_id_${sessionId}`, session.report_id);
                }
                
                console.log(`📊 会话状态检查: 已结束=${this.interviewEnded}, 报告ID=${session.report_id}`);
            } else {
                this.resetState();
            }
            
            // 更新UI显示
            this.updateControlsVisibility();
            
        } catch (error) {
            console.warn('⚠️ 检查会话报告状态失败:', error);
            this.resetState();
        }
    }
    
    /**
     * API调用函数
     */
    async callAPI(endpoint, method = 'GET', data = null) {
        try {
            const url = `/api/v1${endpoint}`;
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
     * 触发面试结束事件
     */
    dispatchInterviewEndEvent(summaryMessage = null, reportId = null) {
        const event = new CustomEvent('interviewEnded', {
            detail: {
                sessionId: this.currentSessionId,
                reportId: reportId,
                summaryMessage: summaryMessage,
                timestamp: Date.now()
            }
        });
        
        document.dispatchEvent(event);
        console.log('📡 面试结束事件已触发:', {
            sessionId: this.currentSessionId,
            reportId,
            summaryMessage
        });
    }
    
    /**
     * 滚动到底部
     */
    scrollToBottom() {
        const messagesContainer = document.getElementById('chat-messages-container');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
}

// 创建全局实例
let interviewCompletion = null;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    interviewCompletion = new InterviewCompletionManager();
    
    // 暴露到全局作用域
    window.interviewCompletion = interviewCompletion;
    
    console.log('✅ 面试完成管理器已加载');
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { InterviewCompletionManager };
} else {
    window.InterviewCompletionManager = InterviewCompletionManager;
}
