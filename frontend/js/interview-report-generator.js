/**
 * 面试报告生成器 - 基于真实会话历史数据
 * 替代静态数据，从后端API加载AI分析的真实报告
 */

class InterviewReportGenerator {
    constructor() {
        this.reportData = null;
        this.charts = {};
        this.reportId = null;
        this.sessionId = null;
        
        this.init();
    }
    
    init() {
        // 从URL参数获取报告信息
        this.parseUrlParams();
        
        // 页面加载完成后获取数据
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.loadReport());
        } else {
            this.loadReport();
        }
        
        console.log('✅ 面试报告生成器初始化完成');
    }
    
    /**
     * 解析URL参数
     */
    parseUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        this.reportId = urlParams.get('report_id');
        this.sessionId = urlParams.get('session_id');
        
        console.log('📊 报告参数:', { 
            reportId: this.reportId, 
            sessionId: this.sessionId 
        });
    }
    
    /**
     * 加载报告数据
     */
    async loadReport() {
        try {
            // 显示加载状态
            this.showLoadingState();
            
            if (this.reportId) {
                // 加载已生成的报告
                await this.loadExistingReport();
            } else if (this.sessionId) {
                // 基于会话生成新报告
                await this.generateNewReport();
            } else {
                // 无参数，显示错误
                throw new Error('缺少报告ID或会话ID参数');
            }
            
            // 数据加载完成后初始化图表
            this.initCharts();
            
        } catch (error) {
            console.error('❌ 加载报告失败:', error);
            this.showErrorState(error.message);
        }
    }
    
    /**
     * 加载已存在的报告
     */
    async loadExistingReport() {
        try {
            console.log('📖 加载已生成的报告:', this.reportId);
            
            const response = await this.callAPI(`/langgraph-chat/reports/${this.reportId}`);
            
            if (response.success && response.report_data) {
                this.reportData = response.report_data;
                
                // 更新AI状态指示器
                this.updateAIStatus(response.ai_powered, response.analysis_summary);
                
                // 更新页面内容
                this.updatePageContent();
                
                console.log('✅ 报告数据加载成功');
                
            } else {
                throw new Error('报告数据不存在或格式错误');
            }
            
        } catch (error) {
            console.error('❌ 加载已生成报告失败:', error);
            throw error;
        }
    }
    
    /**
     * 生成新报告
     */
    async generateNewReport() {
        try {
            console.log('🔄 基于会话生成新报告:', this.sessionId);
            
            const response = await this.callAPI(`/langgraph-chat/sessions/${this.sessionId}/generate-report`, 'POST');
            
            if (response.success) {
                this.reportId = response.report_id;
                this.reportData = response.report_data;
                
                // 更新URL（不刷新页面）
                const newUrl = `${window.location.pathname}?report_id=${this.reportId}&session_id=${this.sessionId}`;
                window.history.replaceState(null, '', newUrl);
                
                // 更新AI状态指示器
                this.updateAIStatus(true, "基于讯飞星火大模型的智能分析，提供个性化面试评估和建议");
                
                // 更新页面内容
                this.updatePageContent();
                
                console.log('✅ 新报告生成成功:', this.reportId);
                
            } else {
                throw new Error(response.message || '生成报告失败');
            }
            
        } catch (error) {
            console.error('❌ 生成新报告失败:', error);
            throw error;
        }
    }
    
    /**
     * 显示加载状态
     */
    showLoadingState() {
        // 更新主要内容区域为加载状态
        const mainContent = document.querySelector('main.container');
        if (mainContent) {
            const loadingHTML = `
                <div class="flex items-center justify-center min-h-screen">
                    <div class="text-center space-y-4">
                        <div class="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
                        <div class="space-y-2">
                            <h3 class="text-lg font-medium text-gray-900">正在生成面试报告</h3>
                            <p class="text-gray-600">AI正在分析您的面试表现，请稍候...</p>
                        </div>
                        <div class="flex items-center justify-center space-x-2 text-sm text-gray-500">
                            <i class="ri-sparkle-line text-blue-600"></i>
                            <span>由讯飞星火大模型提供智能分析</span>
                        </div>
                    </div>
                </div>
            `;
            
            // 保存原始内容
            this.originalContent = mainContent.innerHTML;
            mainContent.innerHTML = loadingHTML;
        }
    }
    
    /**
     * 显示错误状态
     */
    showErrorState(errorMessage) {
        const mainContent = document.querySelector('main.container');
        if (mainContent) {
            const errorHTML = `
                <div class="flex items-center justify-center min-h-screen">
                    <div class="text-center space-y-4 max-w-md">
                        <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
                            <i class="ri-error-warning-line text-red-600 text-2xl"></i>
                        </div>
                        <div class="space-y-2">
                            <h3 class="text-lg font-medium text-gray-900">报告生成失败</h3>
                            <p class="text-gray-600">${errorMessage}</p>
                        </div>
                        <div class="space-y-2">
                            <button onclick="location.reload()" class="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors">
                                重新加载
                            </button>
                            <button onclick="history.back()" class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                                返回上页
                            </button>
                        </div>
                    </div>
                </div>
            `;
            mainContent.innerHTML = errorHTML;
        }
    }
    
    /**
     * 恢复原始页面内容
     */
    restoreOriginalContent() {
        const mainContent = document.querySelector('main.container');
        if (mainContent && this.originalContent) {
            mainContent.innerHTML = this.originalContent;
        }
    }
    
    /**
     * 更新页面内容
     */
    updatePageContent() {
        if (!this.reportData) {
            console.warn('⚠️ 报告数据为空');
            return;
        }
        
        // 恢复原始页面结构
        this.restoreOriginalContent();
        
        const basicInfo = this.reportData.basic_info;
        const competencies = this.reportData.core_competencies;
        const detailedScores = competencies.detailed_scores;
        
        console.log('🎨 更新页面内容:', basicInfo);
        
        // 更新基本信息
        this.updateBasicInfo(basicInfo);
        
        // 更新能力评分
        this.updateCompetencyScores(competencies, detailedScores);
        
        // 更新优势与不足
        this.updateStrengthsWeaknesses(this.reportData.strengths_weaknesses);
        
        // 更新提升建议
        this.updateImprovementSuggestions(this.reportData.improvement_suggestions);
    }
    
    /**
     * 更新基本信息
     */
    updateBasicInfo(basicInfo) {
        // 更新标题
        const titleElement = document.querySelector('h1');
        if (titleElement) {
            titleElement.textContent = `${basicInfo.candidate_name} - 面试评估报告`;
        }
        
        // 更新面试信息
        const interviewInfo = document.querySelector('.flex.items-center.text-sm.text-gray-500');
        if (interviewInfo) {
            interviewInfo.innerHTML = `
                <span>面试时间: ${basicInfo.interview_time}</span>
                <span class="mx-3">|</span>
                <span>时长: ${basicInfo.duration_minutes} 分钟</span>
                <span class="mx-3">|</span>
                <span>岗位: ${basicInfo.position}</span>
            `;
        }
        
        // 更新等级徽章
        const gradeElement = document.querySelector('.px-3.py-1\\.5');
        if (gradeElement) {
            gradeElement.textContent = `${basicInfo.overall_grade} 级`;
            const gradeClasses = {
                'A': 'bg-green-100 text-green-800',
                'B': 'bg-blue-100 text-blue-800', 
                'C': 'bg-yellow-100 text-yellow-800',
                'D': 'bg-red-100 text-red-800'
            };
            gradeElement.className = `px-3 py-1.5 ${gradeClasses[basicInfo.overall_grade] || gradeClasses.B} rounded-full font-medium text-sm`;
        }
        
        // 更新总分
        const overallScore = document.querySelector('.text-4xl.font-bold.text-gray-900');
        if (overallScore) {
            overallScore.textContent = basicInfo.overall_score;
        }
        
        // 更新进度环
        this.updateProgressRing(basicInfo.overall_score);
        
        // 更新得分标记位置
        const scoreMarker = document.querySelector('.absolute[style*="left:"]');
        if (scoreMarker) {
            scoreMarker.style.left = `${basicInfo.overall_score}%`;
        }
    }
    
    /**
     * 更新能力评分卡片
     */
    updateCompetencyScores(competencies, detailedScores) {
        const competencyCards = document.querySelectorAll('.lg\\:w-3\\/5 .grid .ability-card');
        
        const scoreMapping = [
            { key: 'professional_knowledge', card: competencyCards[0] },
            { key: 'skill_matching', card: competencyCards[1] },
            { key: 'language_expression', card: competencyCards[2] },
            { key: 'logical_thinking', card: competencyCards[3] },
            { key: 'innovation_ability', card: competencyCards[4] },
            { key: 'stress_resistance', card: competencyCards[5] }
        ];
        
        scoreMapping.forEach(({ key, card }) => {
            if (card && detailedScores[key]) {
                const scoreData = detailedScores[key];
                
                const scoreElement = card.querySelector('.text-sm.text-gray-500');
                const descElement = card.querySelector('p');
                
                if (scoreElement) {
                    scoreElement.textContent = `${scoreData.score}分 - ${scoreData.level}`;
                }
                if (descElement) {
                    descElement.textContent = scoreData.description;
                }
            }
        });
    }
    
    /**
     * 更新优势与不足
     */
    updateStrengthsWeaknesses(strengthsWeaknesses) {
        // 更新优势列表
        const strengthsList = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2 > div:first-child ul');
        if (strengthsList && strengthsWeaknesses.strengths) {
            strengthsList.innerHTML = strengthsWeaknesses.strengths.map(strength => `
                <li class="strength-weakness-item strength-item">
                    <div class="flex items-center">
                        <div class="w-5 h-5 flex items-center justify-center text-green-600 mr-2">
                            <i class="ri-check-line"></i>
                        </div>
                        <div class="font-medium text-gray-900">${strength.title}</div>
                    </div>
                    <p class="text-sm text-gray-700 mt-1">${strength.description}</p>
                </li>
            `).join('');
        }
        
        // 更新不足列表
        const weaknessesList = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2 > div:last-child ul');
        if (weaknessesList && strengthsWeaknesses.weaknesses) {
            weaknessesList.innerHTML = strengthsWeaknesses.weaknesses.map(weakness => `
                <li class="strength-weakness-item weakness-item">
                    <div class="flex items-center">
                        <div class="w-5 h-5 flex items-center justify-center text-orange-600 mr-2">
                            <i class="ri-arrow-up-line"></i>
                        </div>
                        <div class="font-medium text-gray-900">${weakness.title}</div>
                    </div>
                    <p class="text-sm text-gray-700 mt-1">${weakness.description}</p>
                </li>
            `).join('');
        }
    }
    
    /**
     * 更新提升建议
     */
    updateImprovementSuggestions(improvementSuggestions) {
        // 更新学习资源
        const learningResourcesList = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2 .p-5:first-child ul');
        if (learningResourcesList && improvementSuggestions.learning_resources) {
            learningResourcesList.innerHTML = improvementSuggestions.learning_resources.map(resource => `
                <li class="flex items-start">
                    <div class="w-5 h-5 flex items-center justify-center text-primary mt-0.5 mr-2">
                        <i class="ri-${this.getResourceIcon(resource.type)}"></i>
                    </div>
                    <div>
                        <div class="text-sm font-medium text-gray-900">${resource.title}</div>
                        <p class="text-xs text-gray-500">${resource.description}</p>
                    </div>
                </li>
            `).join('');
        }
        
        // 更新提升方法
        const improvementMethodsList = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2 .p-5:nth-child(2) ul');
        if (improvementMethodsList && improvementSuggestions.improvement_methods) {
            improvementMethodsList.innerHTML = improvementSuggestions.improvement_methods.map(method => `
                <li class="flex items-start">
                    <div class="w-5 h-5 flex items-center justify-center text-primary mt-0.5 mr-2">
                        <i class="ri-mental-health-line"></i>
                    </div>
                    <div>
                        <div class="text-sm font-medium text-gray-900">${method.title}</div>
                        <p class="text-xs text-gray-500">${method.description}</p>
                    </div>
                </li>
            `).join('');
        }
        
        // 更新学习路径
        const learningPathContainer = document.querySelector('.md\\:col-span-2 .space-y-6');
        if (learningPathContainer && improvementSuggestions.learning_path) {
            learningPathContainer.innerHTML = improvementSuggestions.learning_path.map(stage => `
                <div class="flex">
                    <div class="w-8 h-8 flex items-center justify-center bg-primary rounded-full text-white relative z-10 mr-4">${stage.stage}</div>
                    <div class="flex-1 p-4 bg-gray-50 rounded-lg">
                        <h4 class="font-medium text-gray-900 mb-1">${stage.title} (${stage.duration})</h4>
                        <p class="text-sm text-gray-700">${stage.description}</p>
                    </div>
                </div>
            `).join('');
        }
    }
    
    /**
     * 更新AI状态指示器
     */
    updateAIStatus(aiPowered, analysisSummary) {
        const aiStatusBadge = document.getElementById('ai-status-badge');
        const aiAnalysisInfo = document.getElementById('ai-analysis-info');
        const aiAnalysisSummary = document.getElementById('ai-analysis-summary');
        
        if (aiStatusBadge) {
            if (aiPowered) {
                aiStatusBadge.innerHTML = '<i class="ri-sparkle-line mr-1"></i><span>AI 智能分析</span>';
                aiStatusBadge.className = 'px-3 py-1.5 bg-purple-100 text-purple-800 rounded-full font-medium text-sm flex items-center';
            } else {
                aiStatusBadge.innerHTML = '<i class="ri-cpu-line mr-1"></i><span>基础分析</span>';
                aiStatusBadge.className = 'px-3 py-1.5 bg-gray-100 text-gray-800 rounded-full font-medium text-sm flex items-center';
            }
        }
        
        if (aiAnalysisInfo && aiAnalysisSummary) {
            if (aiPowered) {
                aiAnalysisInfo.classList.remove('hidden');
                aiAnalysisSummary.textContent = analysisSummary || '基于讯飞星火大模型的智能分析，为您提供个性化面试建议。';
            } else {
                aiAnalysisInfo.classList.add('hidden');
            }
        }
    }
    
    /**
     * 更新进度环
     */
    updateProgressRing(score) {
        const circumference = 2 * Math.PI * 70;
        const offset = circumference - (score / 100) * circumference;
        const progressCircle = document.querySelector('.progress-ring-circle');
        if (progressCircle) {
            progressCircle.style.strokeDashoffset = offset;
        }
    }
    
    /**
     * 初始化图表
     */
    initCharts() {
        if (typeof echarts === 'undefined') {
            console.warn('⚠️ ECharts未加载，跳过图表初始化');
            return;
        }
        
        // 确保有报告数据
        if (!this.reportData || !this.reportData.core_competencies) {
            console.warn('⚠️ 报告数据不完整，使用默认图表数据');
            this.initChartsWithDefaultData();
            return;
        }
        
        // 使用真实数据初始化图表
        this.initRadarChart();
        this.initAnswerChart();
        this.initTimeChart();
        
        // 窗口大小变化时重新调整图表大小
        window.addEventListener('resize', () => {
            Object.values(this.charts).forEach(chart => chart.resize());
        });
    }
    
    /**
     * 初始化雷达图
     */
    initRadarChart() {
        const radarChartElement = document.getElementById('radar-chart');
        if (!radarChartElement) return;
        
        const radarChart = echarts.init(radarChartElement);
        const scores = this.reportData.core_competencies.detailed_scores;
        
        // 从真实数据提取雷达图数据
        const radarData = [
            scores.professional_knowledge?.score || 75,
            scores.skill_matching?.score || 80,
            scores.language_expression?.score || 70,
            scores.logical_thinking?.score || 78,
            scores.innovation_ability?.score || 72,
            scores.stress_resistance?.score || 80
        ];
        
        const radarOption = {
            animation: true,
            radar: {
                indicator: [
                    { name: '专业知识水平', max: 100 },
                    { name: '技能匹配度', max: 100 },
                    { name: '语言表达能力', max: 100 },
                    { name: '逻辑思维能力', max: 100 },
                    { name: '创新能力', max: 100 },
                    { name: '应变抗压能力', max: 100 }
                ],
                radius: '65%',
                splitNumber: 4,
                axisName: {
                    color: '#1f2937',
                    fontSize: 12
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(224, 225, 228, 0.5)'
                    }
                },
                splitArea: {
                    show: true,
                    areaStyle: {
                        color: ['rgba(255, 255, 255, 0.9)', 'rgba(245, 246, 248, 0.6)']
                    }
                }
            },
            series: [{
                name: '能力评估',
                type: 'radar',
                data: [{
                    value: radarData,
                    name: '个人能力',
                    lineStyle: {
                        width: 2,
                        color: 'rgba(33, 150, 243, 1)'
                    },
                    areaStyle: {
                        color: 'rgba(33, 150, 243, 0.3)'
                    }
                }]
            }]
        };
        
        radarChart.setOption(radarOption);
        this.charts.radar = radarChart;
    }
    
    /**
     * 初始化其他图表（简化版本）
     */
    initAnswerChart() {
        const answerChartElement = document.getElementById('answer-chart');
        if (!answerChartElement) return;
        
        const answerChart = echarts.init(answerChartElement);
        // 使用简化的答题分布数据
        const answerOption = {
            series: [{
                name: '题型分布',
                type: 'pie',
                radius: ['40%', '70%'],
                data: [
                    { value: 40, name: '专业技能', itemStyle: { color: '#2196F3' } },
                    { value: 30, name: '项目经验', itemStyle: { color: '#4CAF50' } },
                    { value: 20, name: '团队协作', itemStyle: { color: '#FF9800' } },
                    { value: 10, name: '其他', itemStyle: { color: '#9E9E9E' } }
                ]
            }]
        };
        
        answerChart.setOption(answerOption);
        this.charts.answer = answerChart;
    }
    
    initTimeChart() {
        const timeChartElement = document.getElementById('time-chart');
        if (!timeChartElement) return;
        
        const timeChart = echarts.init(timeChartElement);
        // 使用简化的时间分布数据
        const timeOption = {
            xAxis: {
                type: 'category',
                data: ['专业知识', '项目经验', '团队协作', '综合素质']
            },
            yAxis: {
                type: 'value',
                name: '回答时间(秒)'
            },
            series: [{
                name: '平均回答时间',
                type: 'bar',
                data: [45, 60, 40, 35],
                itemStyle: {
                    color: '#2196F3'
                }
            }]
        };
        
        timeChart.setOption(timeOption);
        this.charts.time = timeChart;
    }
    
    /**
     * 工具方法
     */
    getResourceIcon(type) {
        const mapping = {
            'book': 'book-2-line',
            'video': 'video-line',
            'course': 'global-line',
            'platform': 'gamepad-line'
        };
        return mapping[type] || 'book-2-line';
    }
    
    /**
     * API调用
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
     * 使用默认数据初始化图表（降级模式）
     */
    initChartsWithDefaultData() {
        console.log('📊 使用默认数据初始化图表');
        // 可以调用原有的图表初始化逻辑
        if (typeof initCharts === 'function') {
            initCharts();
        }
    }
}

// 创建全局实例
let reportGenerator = null;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    reportGenerator = new InterviewReportGenerator();
    
    // 暴露到全局作用域
    window.reportGenerator = reportGenerator;
    
    console.log('✅ 面试报告生成器已加载');
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { InterviewReportGenerator };
} else {
    window.InterviewReportGenerator = InterviewReportGenerator;
}
