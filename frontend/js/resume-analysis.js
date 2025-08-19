/**
 * 简历AI分析管理器
 * 负责JD智能匹配分析和STAR原则检测功能
 */
class ResumeAnalysisManager {
    constructor() {
        this.currentJDAnalysisId = null;
        this.currentSTARAnalysisId = null;
        this.jdAnalysisPollingInterval = null;
        this.starAnalysisPollingInterval = null;
        this.isInitialized = false;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.initializeCharts();
        
        console.log('✅ 简历AI分析管理器初始化完成');
    }
    
    // ==================== API调用函数 ====================
    
    async callAPI(endpoint, method = 'GET', data = null) {
        try {
            const url = `/api/v1/resume${endpoint}`;
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
    
    // ==================== JD智能匹配分析 ====================
    
    async startJDAnalysis() {
        const currentResumeId = window.resumeManager?.getCurrentResumeId();
        console.log('🔍 启动JD匹配分析，当前简历ID:', currentResumeId);
        
        const jdTextarea = document.querySelector('textarea');
        const jdContent = jdTextarea ? jdTextarea.value.trim() : '';
        console.log('JD内容长度:', jdContent.length);
        
        if (!currentResumeId) {
            console.error('没有选中的简历');
            this.showErrorMessage('请先选择一个简历版本');
            return;
        }
        
        if (!jdContent) {
            this.showErrorMessage('请填写岗位职责描述（JD）');
            return;
        }
        
        console.log('开始触发JD匹配分析...');
        await this.triggerJDAnalysis(currentResumeId, jdContent);
    }
    
    async triggerJDAnalysis(resumeId, jdContent) {
        try {
            console.log('🔍 准备触发JD匹配分析:', { resumeId, jdContent: jdContent.substring(0, 100) + '...' });
            
            const requestData = {
                jd_content: jdContent
            };

            // 显示JD分析中状态
            this.showJDAnalysisInProgress();

            console.log('发送JD分析API请求:', `/analyze/${resumeId}`, requestData);
            const response = await this.callAPI(`/analyze/${resumeId}`, 'POST', requestData);
            console.log('JD分析API响应:', response);
            
            if (response.success) {
                this.currentJDAnalysisId = response.analysis_id;
                console.log('✅ JD匹配分析任务已启动:', this.currentJDAnalysisId);
                
                // 开始轮询JD分析状态
                this.startJDAnalysisPolling();
                
                // 显示成功消息
                this.showSuccessMessage('JD智能匹配分析已开始，请稍候...');
                
                return response.analysis_id;
            } else {
                throw new Error(response.message || '启动JD分析失败');
            }
        } catch (error) {
            console.error('❌ 触发JD分析失败:', error);
            this.showErrorMessage('启动JD分析失败: ' + (error.message || error.toString()));
            this.hideJDAnalysisLoading();
            return null;
        }
    }
    
    async loadSTARAnalysisStatus(resumeId) {
        try {
            // 验证resumeId的有效性
            if (!resumeId || resumeId === 'undefined' || resumeId === 'null') {
                console.warn('⚠️ 无效的简历ID，显示默认状态:', resumeId);
                this.showDefaultAnalysisState();
                this.showSTARAnalysisInProgress();
                return;
            }

            console.log('⭐ 检查STAR分析状态:', resumeId);
            
            // 查询简历的分析结果
            const response = await this.callAPI(`/analysis/result/${resumeId}`);
            
            if (response.success && response.data) {
                // 检查是否有STAR分析结果
                if (response.data.star_principle) {
                    console.log('✅ 找到已完成的STAR分析结果');
                    this.renderSTARPrinciple(response.data.star_principle);
                } else {
                    console.log('⏳ STAR分析进行中或尚未开始');
                    this.showSTARAnalysisInProgress();
                }
                
                // 检查是否有JD匹配分析结果
                if (response.data.jd_matching) {
                    console.log('✅ 找到已完成的JD匹配分析结果');
                    this.renderJDMatching(response.data.jd_matching);
                } else {
                    console.log('💭 等待用户触发JD匹配分析');
                    this.showDefaultAnalysisState();
                }
                
            } else {
                console.log('📝 新简历，等待分析完成');
                this.showSTARAnalysisInProgress();
                this.showDefaultAnalysisState();
            }
        } catch (error) {
            console.error('❌ 检查分析状态失败:', error);
            this.showAnalysisError();
        }
    }
    
    // 保留原方法用于向后兼容
    async triggerResumeAnalysis(resumeId, jdContent = '') {
        console.warn('⚠️ triggerResumeAnalysis已废弃，请使用triggerJDAnalysis');
        return await this.triggerJDAnalysis(resumeId, jdContent);
    }
    
    // ==================== 分析状态管理 ====================
    
    startJDAnalysisPolling() {
        if (this.jdAnalysisPollingInterval) {
            clearInterval(this.jdAnalysisPollingInterval);
        }

        this.jdAnalysisPollingInterval = setInterval(async () => {
            if (!this.currentJDAnalysisId) {
                clearInterval(this.jdAnalysisPollingInterval);
                return;
            }

            try {
                const response = await this.callAPI(`/analysis/status/${this.currentJDAnalysisId}`);
                
                if (response.success && response.data) {
                    const analysisData = response.data;
                    console.log('JD分析状态更新:', analysisData.status);

                    if (analysisData.status === 'completed') {
                        clearInterval(this.jdAnalysisPollingInterval);
                        
                        // 渲染JD匹配分析结果
                        if (analysisData.jd_matching) {
                            this.renderJDMatching(analysisData.jd_matching);
                        }
                        
                        this.currentJDAnalysisId = null;
                        this.jdAnalysisPollingInterval = null;
                        console.log('✅ JD匹配分析完成');
                        
                        // 显示完成消息
                        this.showSuccessMessage('JD智能匹配分析已完成！');
                    } else if (analysisData.status === 'failed') {
                        clearInterval(this.jdAnalysisPollingInterval);
                        this.showJDAnalysisError(analysisData.error || 'JD分析失败');
                        this.currentJDAnalysisId = null;
                        this.jdAnalysisPollingInterval = null;
                    }
                }
            } catch (error) {
                console.error('❌ 获取JD分析状态失败:', error);
            }
        }, 3000); // 每3秒检查一次
    }
    
    startSTARAnalysisPolling() {
        if (this.starAnalysisPollingInterval) {
            clearInterval(this.starAnalysisPollingInterval);
        }

        this.starAnalysisPollingInterval = setInterval(async () => {
            if (!this.currentSTARAnalysisId) {
                clearInterval(this.starAnalysisPollingInterval);
                return;
            }

            try {
                const response = await this.callAPI(`/analysis/status/${this.currentSTARAnalysisId}`);
                
                if (response.success && response.data) {
                    const analysisData = response.data;
                    console.log('STAR分析状态更新:', analysisData.status);

                    if (analysisData.status === 'completed') {
                        clearInterval(this.starAnalysisPollingInterval);
                        
                        // 渲染STAR原则检测结果
                        if (analysisData.star_principle) {
                            this.renderSTARPrinciple(analysisData.star_principle);
                        }
                        
                        this.currentSTARAnalysisId = null;
                        this.starAnalysisPollingInterval = null;
                        console.log('✅ STAR原则检测完成');
                        
                        // 显示完成消息
                        this.showSuccessMessage('STAR原则检测已完成！');
                    } else if (analysisData.status === 'failed') {
                        clearInterval(this.starAnalysisPollingInterval);
                        this.showSTARAnalysisError(analysisData.error || 'STAR检测失败');
                        this.currentSTARAnalysisId = null;
                        this.starAnalysisPollingInterval = null;
                    }
                }
            } catch (error) {
                console.error('❌ 获取STAR分析状态失败:', error);
            }
        }, 5000); // 每5秒检查一次
    }
    
    // 保留原方法用于向后兼容
    startAnalysisPolling() {
        console.warn('⚠️ startAnalysisPolling已废弃，请使用startJDAnalysisPolling或startSTARAnalysisPolling');
        this.startJDAnalysisPolling();
    }
    
    updateAnalysisProgress(analysisData) {
        const progress = analysisData.progress || 0;
        const status = analysisData.status;
        
        // 更新JD匹配分析进度
        const jdProgress = document.querySelector('#jdAnalysisProgress');
        const starProgress = document.querySelector('#starAnalysisProgress');
        
        if (jdProgress) {
            if (progress >= 50) {
                jdProgress.style.width = '100%';
                jdProgress.parentElement?.classList.add('completed');
            } else {
                jdProgress.style.width = Math.min(progress * 2, 100) + '%';
            }
        }
        
        if (starProgress) {
            if (progress >= 100) {
                starProgress.style.width = '100%';
                starProgress.parentElement?.classList.add('completed');
            } else if (progress >= 50) {
                starProgress.style.width = ((progress - 50) * 2) + '%';
            }
        }

        // 更新状态文本
        const statusText = document.querySelector('#analysisStatusText');
        if (statusText) {
            const statusMessages = {
                'processing': 'AI分析准备中...',
                'analyzing_jd': 'JD智能匹配分析中...',
                'analyzing_star': 'STAR原则检测中...',
                'completed': 'AI分析完成'
            };
            statusText.textContent = statusMessages[status] || `分析中... ${progress}%`;
        }
    }
    
    // ==================== 分析结果渲染 ====================
    
    async loadResumeAnalysis(resumeId) {
        try {
            const response = await this.callAPI(`/analysis/result/${resumeId}`);
            
            if (response.success && response.data) {
                console.log('加载分析结果成功:', response.data);
                this.renderAnalysisResults(response.data);
                return response.data;
            } else {
                console.log('暂无分析结果，显示默认数据');
                this.showDefaultAnalysisState();
                return null;
            }
        } catch (error) {
            console.error('加载分析结果失败:', error);
            this.showAnalysisError();
            return null;
        }
    }
    
    renderAnalysisResults(analysisData) {
        try {
            console.log('渲染分析结果:', analysisData);
            
            // 渲染JD匹配分析
            if (analysisData.jd_matching) {
                this.renderJDMatching(analysisData.jd_matching);
            }
            
            // 渲染STAR原则检测
            if (analysisData.star_principle) {
                this.renderSTARPrinciple(analysisData.star_principle);
            }

        } catch (error) {
            console.error('渲染分析结果失败:', error);
            this.showErrorMessage('分析结果渲染失败');
        }
    }
    
    renderJDMatching(jdData) {
        const matchChart = document.getElementById('matchChart');
        const jdResult = document.querySelector('.jd-analysis-result');
        
        if (!jdResult) return;

        // 更新匹配度百分比
        const matchPercentage = jdResult.parentElement?.querySelector('.text-primary');
        if (matchPercentage) {
            matchPercentage.textContent = `${jdData.overall_match || 82}%`;
        }

        // 更新进度条
        const progressBar = jdResult.parentElement?.querySelector('.bg-primary');
        if (progressBar) {
            progressBar.style.width = `${jdData.overall_match || 82}%`;
        }

        // 重新渲染雷达图
        if (matchChart && jdData.match_details && typeof echarts !== 'undefined') {
            const chart = echarts.init(matchChart);
            const option = {
                animation: false,
                radar: {
                    indicator: Object.keys(jdData.match_details).map(key => ({
                        name: key,
                        max: 100
                    })),
                    radius: 60,
                    axisLine: { lineStyle: { color: '#e5e7eb' } },
                    splitLine: { lineStyle: { color: '#e5e7eb' } },
                    axisLabel: { fontSize: 10, color: '#6b7280' }
                },
                series: [{
                    type: 'radar',
                    data: [{
                        value: Object.values(jdData.match_details),
                        name: '匹配度',
                        areaStyle: { color: 'rgba(87, 181, 231, 0.1)' },
                        lineStyle: { color: 'rgba(87, 181, 231, 1)' },
                        itemStyle: { color: 'rgba(87, 181, 231, 1)' }
                    }]
                }]
            };
            chart.setOption(option);
        }

        // 更新优势和需要加强的内容
        const strengthsElement = jdResult.querySelector('.bg-green-50 p');
        if (strengthsElement && jdData.strengths) {
            strengthsElement.textContent = jdData.strengths.join(', ');
        }

        const gapsElement = jdResult.querySelector('.bg-yellow-50 p');
        if (gapsElement && jdData.gaps) {
            gapsElement.textContent = jdData.gaps.join(', ');
        }
    }
    
    renderSTARPrinciple(starData) {
        console.log('📊 渲染STAR原则检测结果:', starData);
        
        this.hideAllSTARStates();
        const resultsEl = document.getElementById('starAnalysisResults');
        if (!resultsEl) {
            console.error('❌ 找不到STAR分析结果容器');
            return;
        }
        
        try {
            const starItems = starData.star_items || [];
            const overallScore = starData.overall_score || 0;
            
            resultsEl.innerHTML = `
                <div class="mb-4 p-4 bg-gray-50 rounded-lg">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-medium text-gray-700">整体STAR完整度</span>
                        <span class="text-sm font-bold text-primary">${overallScore}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-primary h-2 rounded-full" style="width: ${overallScore}%"></div>
                    </div>
                </div>
                
                ${starItems.map(item => `
                    <div class="star-item border border-gray-200 rounded-lg p-4 mb-4">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-medium text-gray-900">${item.name || '项目经历'}</span>
                            <div class="flex space-x-1">
                                <span class="w-2 h-2 ${item.situation_score >= 80 ? 'bg-green-400' : item.situation_score >= 60 ? 'bg-yellow-400' : 'bg-red-400'} rounded-full"></span>
                                <span class="w-2 h-2 ${item.task_score >= 80 ? 'bg-green-400' : item.task_score >= 60 ? 'bg-yellow-400' : 'bg-red-400'} rounded-full"></span>
                                <span class="w-2 h-2 ${item.action_score >= 80 ? 'bg-green-400' : item.action_score >= 60 ? 'bg-yellow-400' : 'bg-red-400'} rounded-full"></span>
                                <span class="w-2 h-2 ${item.result_score >= 80 ? 'bg-green-400' : item.result_score >= 60 ? 'bg-yellow-400' : 'bg-red-400'} rounded-full"></span>
                            </div>
                        </div>
                        <div class="grid grid-cols-4 gap-2 text-xs">
                            <div class="text-center">
                                <div class="w-6 h-6 ${item.situation_score >= 80 ? 'bg-green-100 text-green-600' : item.situation_score >= 60 ? 'bg-yellow-100 text-yellow-600' : 'bg-red-100 text-red-600'} rounded-full flex items-center justify-center mx-auto mb-1">S</div>
                                <span class="${item.situation_score >= 80 ? 'text-green-600' : item.situation_score >= 60 ? 'text-yellow-600' : 'text-red-600'}">${item.situation_score >= 80 ? '完整' : item.situation_score >= 60 ? '良好' : '待改进'}</span>
                            </div>
                            <div class="text-center">
                                <div class="w-6 h-6 ${item.task_score >= 80 ? 'bg-green-100 text-green-600' : item.task_score >= 60 ? 'bg-yellow-100 text-yellow-600' : 'bg-red-100 text-red-600'} rounded-full flex items-center justify-center mx-auto mb-1">T</div>
                                <span class="${item.task_score >= 80 ? 'text-green-600' : item.task_score >= 60 ? 'text-yellow-600' : 'text-red-600'}">${item.task_score >= 80 ? '清晰' : item.task_score >= 60 ? '良好' : '待改进'}</span>
                            </div>
                            <div class="text-center">
                                <div class="w-6 h-6 ${item.action_score >= 80 ? 'bg-green-100 text-green-600' : item.action_score >= 60 ? 'bg-yellow-100 text-yellow-600' : 'bg-red-100 text-red-600'} rounded-full flex items-center justify-center mx-auto mb-1">A</div>
                                <span class="${item.action_score >= 80 ? 'text-green-600' : item.action_score >= 60 ? 'text-yellow-600' : 'text-red-600'}">${item.action_score >= 80 ? '详细' : item.action_score >= 60 ? '良好' : '待改进'}</span>
                            </div>
                            <div class="text-center">
                                <div class="w-6 h-6 ${item.result_score >= 80 ? 'bg-green-100 text-green-600' : item.result_score >= 60 ? 'bg-yellow-100 text-yellow-600' : 'bg-red-100 text-red-600'} rounded-full flex items-center justify-center mx-auto mb-1">R</div>
                                <span class="${item.result_score >= 80 ? 'text-green-600' : item.result_score >= 60 ? 'text-yellow-600' : 'text-red-600'}">${item.result_score >= 80 ? '优秀' : item.result_score >= 60 ? '良好' : '待改进'}</span>
                            </div>
                        </div>
                        ${item.suggestions && item.suggestions.length > 0 ? `
                            <div class="mt-3 p-2 bg-blue-50 rounded text-xs text-blue-700">
                                <strong>建议：</strong>${item.suggestions.join('；')}
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
                
                ${starData.improvement_suggestions && starData.improvement_suggestions.length > 0 ? `
                    <div class="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                        <h4 class="text-sm font-semibold text-blue-800 mb-2">💡 整体优化建议</h4>
                        <ul class="text-xs text-blue-700 space-y-1">
                            ${starData.improvement_suggestions.map(suggestion => 
                                `<li>• ${suggestion}</li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;
            
            resultsEl.classList.remove('hidden');
            console.log('✅ STAR分析结果渲染完成');
            
        } catch (error) {
            console.error('❌ 渲染STAR分析结果失败:', error);
            this.showSTARAnalysisError();
        }
    }
    
    // ==================== UI状态管理 ====================
    
    showJDAnalysisInProgress() {
        const jdAnalysis = document.querySelector('.jd-analysis-result');
        if (jdAnalysis) {
            jdAnalysis.innerHTML = `
                <div class="analysis-loading text-center py-8">
                    <div class="flex flex-col items-center space-y-4">
                        <div class="w-12 h-12 relative">
                            <div class="w-full h-full border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
                        </div>
                        <div class="space-y-2">
                            <p class="text-sm font-medium text-gray-900">JD智能匹配分析中...</p>
                            <div class="w-64 bg-gray-200 rounded-full h-2">
                                <div class="bg-blue-500 h-2 rounded-full transition-all duration-1000 animate-pulse" style="width: 60%"></div>
                            </div>
                        </div>
                        <div class="text-xs text-gray-500 text-center max-w-sm">
                            <p>• 正在分析简历与岗位要求的匹配度</p>
                            <p>• 识别优势技能和改进建议</p>
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    showSTARAnalysisInProgress() {
        const starDetection = document.querySelector('#starDetectionContent') || 
                             document.querySelector('.space-y-4');
        if (starDetection) {
            starDetection.innerHTML = `
                <div class="text-center py-8">
                    <div class="flex flex-col items-center space-y-4">
                        <div class="w-10 h-10 relative">
                            <div class="w-full h-full border-4 border-yellow-200 border-t-yellow-500 rounded-full animate-spin"></div>
                        </div>
                        <div class="space-y-2">
                            <p class="text-sm font-medium text-gray-900">STAR原则检测中...</p>
                            <div class="w-48 bg-gray-200 rounded-full h-1.5">
                                <div class="bg-yellow-500 h-1.5 rounded-full transition-all duration-1000 animate-pulse" style="width: 45%"></div>
                            </div>
                        </div>
                        <div class="text-xs text-gray-500 text-center">
                            <p>正在分析项目经历的完整性和结构化程度</p>
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    hideJDAnalysisLoading() {
        const progressEl = document.getElementById('jdAnalysisProgress');
        if (progressEl) progressEl.classList.add('hidden');
        console.log('✅ 隐藏JD分析加载状态');
    }
    
    showJDAnalysisError(error = 'JD分析失败') {
        const jdResult = document.querySelector('.jd-analysis-result');
        if (jdResult) {
            jdResult.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="ri-error-warning-line text-red-500 text-xl"></i>
                    </div>
                    <p class="text-red-600 mb-4">${error}</p>
                    <button onclick="window.resumeAnalyzer?.retryJDAnalysis()" class="px-4 py-2 bg-primary text-white rounded-button hover:bg-primary/90 transition-colors">
                        重新分析
                    </button>
                </div>
            `;
        }
    }
    
    showSTARAnalysisError(error = 'STAR检测失败') {
        const starDetection = document.querySelector('#starDetectionContent') || 
                             document.querySelector('.space-y-4');
        if (starDetection) {
            starDetection.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="ri-error-warning-line text-red-500 text-lg"></i>
                    </div>
                    <p class="text-red-600 mb-4">${error}</p>
                    <p class="text-xs text-gray-500">STAR检测会在简历更新后自动重新进行</p>
                </div>
            `;
        }
    }
    
    // 保留原方法用于向后兼容
    showAnalysisInProgress() {
        console.warn('⚠️ showAnalysisInProgress已废弃，请使用showJDAnalysisInProgress或showSTARAnalysisInProgress');
        this.showJDAnalysisInProgress();
        this.showSTARAnalysisInProgress();
    }
    
    showDefaultAnalysisState() {
        // JD分析显示默认状态
        this.hideAllJDStates();
        const defaultEl = document.getElementById('jdAnalysisDefault');
        if (defaultEl) defaultEl.classList.remove('hidden');
        console.log('✅ 显示JD分析默认状态');
    }
    
    showAnalysisError(error = '分析加载失败') {
        const jdResult = document.querySelector('.jd-analysis-result');
        if (jdResult) {
            jdResult.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="ri-error-warning-line text-red-500 text-xl"></i>
                    </div>
                    <p class="text-red-600 mb-4">${error}</p>
                    <button onclick="window.resumeAnalyzer?.retryAnalysis()" class="px-4 py-2 bg-primary text-white rounded-button hover:bg-primary/90 transition-colors">
                        重新分析
                    </button>
                </div>
            `;
        }
    }
    
    retryJDAnalysis() {
        const currentResumeId = window.resumeManager?.getCurrentResumeId();
        const jdTextarea = document.querySelector('textarea');
        const jdContent = jdTextarea ? jdTextarea.value.trim() : '';
        
        if (currentResumeId && jdContent) {
            this.triggerJDAnalysis(currentResumeId, jdContent);
        } else if (!jdContent) {
            this.showErrorMessage('请先填写职位描述（JD）内容');
        } else {
            this.showErrorMessage('请先选择一个简历版本');
        }
    }
    
    // 主要入口方法：当简历切换时调用
    async onResumeChanged(resumeId) {
        console.log('📋 简历切换，加载分析状态:', resumeId);
        
        if (!resumeId) {
            this.showDefaultAnalysisState();
            this.showSTARAnalysisInProgress();
            return;
        }
        
        // 加载现有的分析结果或显示相应状态
        await this.loadSTARAnalysisStatus(resumeId);
    }
    
    // 保留原方法用于向后兼容
    retryAnalysis() {
        console.warn('⚠️ retryAnalysis已废弃，请使用retryJDAnalysis');
        this.retryJDAnalysis();
    }
    
    // ==================== 图表初始化 ====================
    
    initializeCharts() {
        if (typeof echarts === 'undefined') {
            console.warn('⚠️ ECharts未加载，跳过图表初始化');
            return;
        }
        
        // 初始化匹配度雷达图
        this.initMatchChart();
    }
    
    initMatchChart() {
        const matchChart = document.getElementById('matchChart');
        if (!matchChart) return;
        
        const chart = echarts.init(matchChart);
        const matchOption = {
            animation: false,
            radar: {
                indicator: [
                    { name: '技术能力', max: 100 },
                    { name: '项目经验', max: 100 },
                    { name: '教育背景', max: 100 },
                    { name: '工作经验', max: 100 },
                    { name: '软技能', max: 100 }
                ],
                radius: 60,
                axisLine: { lineStyle: { color: '#e5e7eb' } },
                splitLine: { lineStyle: { color: '#e5e7eb' } },
                axisLabel: { fontSize: 10, color: '#6b7280' }
            },
            series: [{
                type: 'radar',
                data: [{
                    value: [85, 78, 92, 45, 88],
                    name: '匹配度',
                    areaStyle: { color: 'rgba(87, 181, 231, 0.1)' },
                    lineStyle: { color: 'rgba(87, 181, 231, 1)' },
                    itemStyle: { color: 'rgba(87, 181, 231, 1)' }
                }]
            }],
            grid: { top: 0, bottom: 0, left: 0, right: 0 }
        };
        chart.setOption(matchOption);
        
        // 响应式调整
        window.addEventListener('resize', function() {
            chart.resize();
        });
    }
    
    // ==================== 事件绑定 ====================
    
    bindEvents() {
        // 等待DOM加载完成后绑定事件
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.bindDOMEvents());
        } else {
            this.bindDOMEvents();
        }
    }
    
    bindDOMEvents() {
        // 暴露全局函数供HTML调用
        window.startJDAnalysis = () => this.startJDAnalysis();
        window.retryAnalysis = () => this.retryAnalysis();
    }
    
    // ==================== 辅助函数 ====================
    
    showSuccessMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'fixed top-6 right-6 bg-green-50 text-green-800 px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2';
        messageDiv.innerHTML = `
            <div class="w-5 h-5 flex items-center justify-center">
                <i class="ri-check-line text-green-600"></i>
            </div>
            <span>${message}</span>
        `;
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 3000);
    }

    showErrorMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'fixed top-6 right-6 bg-red-50 text-red-800 px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2';
        messageDiv.innerHTML = `
            <div class="w-5 h-5 flex items-center justify-center">
                <i class="ri-close-line text-red-600"></i>
            </div>
            <span>${message}</span>
        `;
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 4000);
    }
    
    // ==================== 新增状态管理方法 ====================
    
    retrySTARAnalysis() {
        const currentResumeId = window.resumeManager?.getCurrentResumeId();
        if (currentResumeId) {
            this.loadSTARAnalysisStatus(currentResumeId);
        } else {
            this.showErrorMessage('请先选择一个简历');
        }
    }
    
    // 辅助方法：隐藏所有JD分析状态
    hideAllJDStates() {
        const jdStates = ['jdAnalysisDefault', 'jdAnalysisProgress', 'jdAnalysisError', 'jdAnalysisResults'];
        jdStates.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
    }
    
    // 辅助方法：隐藏所有STAR分析状态
    hideAllSTARStates() {
        const starStates = ['starAnalysisLoading', 'starAnalysisProgress', 'starAnalysisEmpty', 'starAnalysisError', 'starAnalysisResults'];
        starStates.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
    }
    
    // 更新STAR分析状态管理方法
    showSTARAnalysisInProgress() {
        this.hideAllSTARStates();
        const progressEl = document.getElementById('starAnalysisProgress');
        if (progressEl) progressEl.classList.remove('hidden');
        console.log('⭐ STAR分析进行中...');
    }
    
    showSTARAnalysisError() {
        this.hideAllSTARStates();
        const errorEl = document.getElementById('starAnalysisError');
        if (errorEl) errorEl.classList.remove('hidden');
        console.log('❌ 显示STAR分析错误状态');
    }
    
    showJDAnalysisInProgress() {
        this.hideAllJDStates();
        const progressEl = document.getElementById('jdAnalysisProgress');
        if (progressEl) progressEl.classList.remove('hidden');
        console.log('⏳ JD分析进行中...');
    }
}

// 导出供其他模块使用
if (typeof window !== 'undefined') {
    window.ResumeAnalysisManager = ResumeAnalysisManager;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ResumeAnalysisManager };
}
