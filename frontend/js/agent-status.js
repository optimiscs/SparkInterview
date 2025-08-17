/**
 * 智能体状态显示组件
 * 展示感知-决策-行动的实时状态
 */

class AgentStatusDisplay {
    constructor(containerId = 'agent-status-panel') {
        this.container = document.getElementById(containerId);
        this.currentStatus = {
            perception: {},
            decision: {},
            action: {},
            userProfile: {}
        };
        
        this.initializeDisplay();
    }
    
    initializeDisplay() {
        if (!this.container) {
            console.warn('智能体状态容器未找到');
            return;
        }
        
        this.container.innerHTML = this.createStatusHTML();
        this.bindEvents();
    }
    
    createStatusHTML() {
        return `
            <div class="agent-status-container bg-white rounded-lg shadow-sm border">
                <!-- 头部标题 -->
                <div class="agent-status-header p-4 border-b bg-gradient-to-r from-blue-50 to-purple-50">
                    <div class="flex items-center space-x-2">
                        <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                            <i class="ri-robot-line text-blue-600"></i>
                        </div>
                        <h3 class="font-medium text-gray-900">智能体状态</h3>
                        <div class="flex-1"></div>
                        <div class="agent-status-indicator w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                    </div>
                </div>
                
                <!-- 感知层状态 -->
                <div class="perception-section p-4 border-b">
                    <div class="flex items-center space-x-2 mb-3">
                        <div class="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
                            <i class="ri-eye-line text-blue-600 text-sm"></i>
                        </div>
                        <h4 class="text-sm font-medium text-gray-800">🧠 感知层</h4>
                        <div class="perception-status-dot w-2 h-2 bg-gray-300 rounded-full"></div>
                    </div>
                    <div class="perception-content space-y-2 text-xs">
                        <div class="info-completeness">
                            <div class="flex justify-between items-center mb-1">
                                <span class="text-gray-600">信息完整度</span>
                                <span class="completeness-percent text-blue-600 font-medium">0%</span>
                            </div>
                            <div class="w-full bg-gray-200 rounded-full h-1.5">
                                <div class="completeness-bar bg-gradient-to-r from-red-400 via-yellow-400 to-green-500 h-1.5 rounded-full transition-all duration-500" style="width: 0%"></div>
                            </div>
                        </div>
                        <div class="missing-info">
                            <span class="text-gray-600">缺失信息：</span>
                            <div class="missing-items flex flex-wrap gap-1 mt-1"></div>
                        </div>
                        <div class="user-emotion">
                            <span class="text-gray-600">用户情绪：</span>
                            <span class="emotion-badge bg-gray-100 px-2 py-0.5 rounded text-gray-700">未知</span>
                        </div>
                    </div>
                </div>
                
                <!-- 决策层状态 -->
                <div class="decision-section p-4 border-b">
                    <div class="flex items-center space-x-2 mb-3">
                        <div class="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center">
                            <i class="ri-brain-line text-purple-600 text-sm"></i>
                        </div>
                        <h4 class="text-sm font-medium text-gray-800">🤖 决策层</h4>
                        <div class="decision-status-dot w-2 h-2 bg-gray-300 rounded-full"></div>
                    </div>
                    <div class="decision-content text-xs space-y-2">
                        <div class="current-action">
                            <span class="text-gray-600">当前策略：</span>
                            <span class="action-type bg-purple-100 text-purple-800 px-2 py-0.5 rounded text-xs">等待中</span>
                        </div>
                        <div class="decision-reasoning text-gray-600 text-xs">
                            <div class="reasoning-text">等待用户输入...</div>
                        </div>
                        <div class="priority-indicator">
                            <span class="text-gray-600">优先级：</span>
                            <span class="priority-level">-</span>
                        </div>
                    </div>
                </div>
                
                <!-- 行动层状态 -->
                <div class="action-section p-4">
                    <div class="flex items-center space-x-2 mb-3">
                        <div class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
                            <i class="ri-flashlight-line text-green-600 text-sm"></i>
                        </div>
                        <h4 class="text-sm font-medium text-gray-800">⚡ 行动层</h4>
                        <div class="action-status-dot w-2 h-2 bg-gray-300 rounded-full"></div>
                    </div>
                    <div class="action-content text-xs space-y-2">
                        <div class="recent-actions">
                            <span class="text-gray-600">最近行动：</span>
                            <div class="action-timeline mt-1 space-y-1"></div>
                        </div>
                        <div class="database-ops">
                            <span class="text-gray-600">数据库操作：</span>
                            <span class="db-status text-gray-500">无</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    bindEvents() {
        // 可以添加点击展开/折叠等交互
        const header = this.container?.querySelector('.agent-status-header');
        if (header) {
            header.addEventListener('click', () => {
                this.toggleExpanded();
            });
        }
    }
    
    updatePerceptionStatus(perceptionData) {
        if (!perceptionData) return;
        
        this.currentStatus.perception = perceptionData;
        
        // 更新感知状态指示器
        const perceptionDot = this.container?.querySelector('.perception-status-dot');
        if (perceptionDot) {
            perceptionDot.className = 'perception-status-dot w-2 h-2 bg-blue-500 rounded-full animate-pulse';
        }
        
        // 更新信息完整度
        const completeness = (perceptionData.information_completeness || 0) * 100;
        const completenessPercent = this.container?.querySelector('.completeness-percent');
        const completenessBar = this.container?.querySelector('.completeness-bar');
        
        if (completenessPercent) {
            completenessPercent.textContent = `${Math.round(completeness)}%`;
        }
        if (completenessBar) {
            completenessBar.style.width = `${completeness}%`;
        }
        
        // 更新缺失信息
        this.updateMissingInfo(perceptionData.missing_info || []);
        
        // 更新用户情绪
        this.updateUserEmotion(perceptionData.user_emotion || 'neutral');
    }
    
    updateMissingInfo(missingInfo) {
        const container = this.container?.querySelector('.missing-items');
        if (!container) return;
        
        const infoLabels = {
            'work_years': '工作年限',
            'current_company': '当前公司',
            'education_level': '学历水平',
            'graduation_year': '毕业年份',
            'expected_salary': '期望薪资'
        };
        
        container.innerHTML = '';
        missingInfo.forEach(info => {
            const label = infoLabels[info] || info;
            const badge = document.createElement('span');
            badge.className = 'bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs';
            badge.textContent = label;
            container.appendChild(badge);
        });
        
        if (missingInfo.length === 0) {
            const badge = document.createElement('span');
            badge.className = 'bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs';
            badge.textContent = '信息完整';
            container.appendChild(badge);
        }
    }
    
    updateUserEmotion(emotion) {
        const badge = this.container?.querySelector('.emotion-badge');
        if (!badge) return;
        
        const emotionConfig = {
            'neutral': { label: '中性', class: 'bg-gray-100 text-gray-700' },
            'confident': { label: '自信', class: 'bg-green-100 text-green-700' },
            'anxious': { label: '紧张', class: 'bg-yellow-100 text-yellow-700' },
            'excited': { label: '兴奋', class: 'bg-blue-100 text-blue-700' }
        };
        
        const config = emotionConfig[emotion] || emotionConfig.neutral;
        badge.className = `emotion-badge px-2 py-0.5 rounded text-xs ${config.class}`;
        badge.textContent = config.label;
    }
    
    updateDecisionStatus(decisionData) {
        if (!decisionData) return;
        
        this.currentStatus.decision = decisionData;
        
        // 更新决策状态指示器
        const decisionDot = this.container?.querySelector('.decision-status-dot');
        if (decisionDot) {
            decisionDot.className = 'decision-status-dot w-2 h-2 bg-purple-500 rounded-full animate-pulse';
        }
        
        // 更新当前策略
        const actionType = this.container?.querySelector('.action-type');
        if (actionType && decisionData.action_type) {
            const actionLabels = {
                'ask_question': '询问信息',
                'provide_comfort': '情绪安抚',
                'generate_question': '生成问题',
                'update_database': '更新数据'
            };
            
            const label = actionLabels[decisionData.action_type] || decisionData.action_type;
            actionType.textContent = label;
            
            // 根据行动类型设置颜色
            const colorMap = {
                'ask_question': 'bg-blue-100 text-blue-800',
                'provide_comfort': 'bg-green-100 text-green-800',
                'generate_question': 'bg-purple-100 text-purple-800',
                'update_database': 'bg-orange-100 text-orange-800'
            };
            actionType.className = `action-type px-2 py-0.5 rounded text-xs ${colorMap[decisionData.action_type] || 'bg-gray-100 text-gray-800'}`;
        }
        
        // 更新决策推理
        const reasoning = this.container?.querySelector('.reasoning-text');
        if (reasoning && decisionData.reasoning) {
            reasoning.textContent = decisionData.reasoning;
        }
        
        // 更新优先级
        const priority = this.container?.querySelector('.priority-level');
        if (priority && decisionData.priority) {
            const priorityLabels = { 1: '高', 2: '中', 3: '低' };
            priority.textContent = priorityLabels[decisionData.priority] || decisionData.priority;
            
            const priorityColors = { 1: 'text-red-600', 2: 'text-yellow-600', 3: 'text-green-600' };
            priority.className = `priority-level font-medium ${priorityColors[decisionData.priority] || 'text-gray-600'}`;
        }
    }
    
    updateActionStatus(actionType, description) {
        // 更新行动状态指示器
        const actionDot = this.container?.querySelector('.action-status-dot');
        if (actionDot) {
            actionDot.className = 'action-status-dot w-2 h-2 bg-green-500 rounded-full animate-pulse';
        }
        
        // 添加到行动时间线
        this.addActionToTimeline(actionType, description);
        
        // 如果是数据库操作，更新数据库状态
        if (actionType === 'database_update') {
            this.updateDatabaseStatus('更新成功');
        }
    }
    
    addActionToTimeline(actionType, description) {
        const timeline = this.container?.querySelector('.action-timeline');
        if (!timeline) return;
        
        const actionItem = document.createElement('div');
        actionItem.className = 'flex items-center space-x-2 text-xs text-gray-600';
        
        const time = new Date().toLocaleTimeString('zh-CN', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit' 
        });
        
        actionItem.innerHTML = `
            <span class="text-gray-400">${time}</span>
            <span class="w-1 h-1 bg-green-500 rounded-full"></span>
            <span>${description}</span>
        `;
        
        timeline.insertBefore(actionItem, timeline.firstChild);
        
        // 保持最多5个历史记录
        while (timeline.children.length > 5) {
            timeline.removeChild(timeline.lastChild);
        }
    }
    
    updateDatabaseStatus(status) {
        const dbStatus = this.container?.querySelector('.db-status');
        if (dbStatus) {
            dbStatus.textContent = status;
            dbStatus.className = 'db-status text-green-600';
            
            // 3秒后恢复默认状态
            setTimeout(() => {
                dbStatus.textContent = '无';
                dbStatus.className = 'db-status text-gray-500';
            }, 3000);
        }
    }
    
    updateUserProfile(profileData) {
        this.currentStatus.userProfile = profileData;
        
        // 这里可以添加用户画像的显示更新
        // 例如在另一个面板中显示用户画像的详细信息
    }
    
    toggleExpanded() {
        const container = this.container?.querySelector('.agent-status-container');
        if (container) {
            container.classList.toggle('collapsed');
        }
    }
    
    // 处理WebSocket消息
    handleWebSocketMessage(message) {
        try {
            const data = JSON.parse(message);
            
            switch (data.type) {
                case 'chunk':
                    // 智能体正在生成回应
                    this.addActionToTimeline('generate_response', '生成回应中...');
                    break;
                    
                case 'profile_update':
                    // 用户画像更新
                    this.updateUserProfile(data.profile);
                    this.addActionToTimeline('database_update', '用户画像已更新');
                    this.updateDatabaseStatus('画像已更新');
                    break;
                    
                case 'perception_data':
                    // 感知数据更新
                    this.updatePerceptionStatus(data.perception);
                    break;
                    
                case 'decision_data':
                    // 决策数据更新
                    this.updateDecisionStatus(data.decision);
                    break;
                    
                case 'complete':
                    // 回应完成
                    this.addActionToTimeline('complete', '回应生成完成');
                    this.resetStatusIndicators();
                    break;
            }
        } catch (error) {
            console.error('处理智能体状态消息失败:', error);
        }
    }
    
    resetStatusIndicators() {
        // 重置状态指示器为默认状态
        setTimeout(() => {
            const indicators = this.container?.querySelectorAll('.perception-status-dot, .decision-status-dot, .action-status-dot');
            indicators?.forEach(indicator => {
                indicator.className = indicator.className.replace('animate-pulse', '').replace('bg-blue-500', 'bg-gray-300').replace('bg-purple-500', 'bg-gray-300').replace('bg-green-500', 'bg-gray-300');
            });
        }, 2000);
    }
}

// 全局实例
let agentStatusDisplay = null;

// 初始化智能体状态显示
function initializeAgentStatus() {
    agentStatusDisplay = new AgentStatusDisplay('analysisPanel');
}

// 导出给其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AgentStatusDisplay };
} else {
    window.AgentStatusDisplay = AgentStatusDisplay;
    window.initializeAgentStatus = initializeAgentStatus;
}
