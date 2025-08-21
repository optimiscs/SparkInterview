/**
 * 实时语调分析管理器
 * 处理语音识别WebSocket中的实时语调分析数据
 * 使用Chart.js渲染实时曲线图
 */

class VoiceToneAnalyzer {
    constructor() {
        // 分析状态
        this.isAnalyzing = false;
        this.sessionId = null;
        
        // 数据存储
        this.pitchHistory = [];
        this.volumeHistory = [];
        this.speechRateHistory = [];
        this.maxDataPoints = 60; // 保存60个数据点（约1分钟）
        
        // 综合图表实例
        this.voiceToneChart = null;
        
        // 图表颜色配置
        this.chartColors = {
            pitch: 'rgb(239, 68, 68)', // 红色
            volume: 'rgb(59, 130, 246)', // 蓝色
            speechRate: 'rgb(245, 158, 11)' // 黄色
        };
        
        // 图表容器
        this.chartContainer = null;
        
        console.log('🎼 语调分析管理器初始化完成');
    }
    
    /**
     * 初始化语调分析器
     * @param {string} sessionId - 语音会话ID
     */
    async initialize(sessionId) {
        try {
            this.sessionId = sessionId;
            console.log(`🎼 初始化语调分析器 - 会话ID: ${sessionId}`);
            
            // 查找综合图表容器元素
            this.chartContainer = document.getElementById('voice-tone-chart');
            
            if (!this.chartContainer) {
                console.error('❌ 未找到语调分析图表容器');
                return false;
            }
            
            // 初始化图表
            await this.initializeCharts();
            
            console.log('✅ 语调分析器初始化成功');
            return true;
            
        } catch (error) {
            console.error('❌ 语调分析器初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 初始化Chart.js重叠折线图
     */
    async initializeCharts() {
        try {
            // 确保Chart.js已加载
            if (typeof Chart === 'undefined') {
                console.error('❌ Chart.js未加载');
                throw new Error('Chart.js library not loaded');
            }
            
            // 获取图表上下文
            const ctx = this.chartContainer.getContext('2d');
            
            // 创建重叠折线图
            this.voiceToneChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [
                        // 音高数据集
                        {
                            label: '音高',
                            data: [],
                            borderColor: this.chartColors.pitch,
                            backgroundColor: this.chartColors.pitch + '10',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.4,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            yAxisID: 'y'
                        },
                        // 音量数据集
                        {
                            label: '音量',
                            data: [],
                            borderColor: this.chartColors.volume,
                            backgroundColor: this.chartColors.volume + '10',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.4,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            yAxisID: 'y1'
                        },
                        // 语速数据集
                        {
                            label: '语速',
                            data: [],
                            borderColor: this.chartColors.speechRate,
                            backgroundColor: this.chartColors.speechRate + '10',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.4,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            yAxisID: 'y2'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 0 // 关闭动画以提高性能
                    },
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            position: 'bottom',
                            title: {
                                display: false
                            },
                            grid: {
                                display: false
                            },
                            ticks: {
                                display: false
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 80,
                            max: 400,
                            title: {
                                display: true,
                                text: '音高 (Hz)',
                                color: 'rgb(239, 68, 68)',
                                font: { size: 10 }
                            },
                            ticks: {
                                color: 'rgb(239, 68, 68)',
                                font: { size: 9 }
                            },
                            grid: {
                                color: 'rgba(239, 68, 68, 0.1)',
                                drawOnChartArea: true,
                            },
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            min: -60,
                            max: 0,
                            title: {
                                display: true,
                                text: '音量 (dB)',
                                color: 'rgb(59, 130, 246)',
                                font: { size: 10 }
                            },
                            ticks: {
                                color: 'rgb(59, 130, 246)',
                                font: { size: 9 }
                            },
                            grid: {
                                color: 'rgba(59, 130, 246, 0.1)',
                                drawOnChartArea: false,
                            },
                        },
                        y2: {
                            type: 'linear',
                            display: false, // 隐藏第三个Y轴避免过于拥挤
                            position: 'right',
                            min: 0,
                            max: 200,
                            grid: {
                                drawOnChartArea: false,
                            },
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: true,
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: function(context) {
                                    const datasetLabel = context.dataset.label;
                                    let unit = '';
                                    let value = context.parsed.y;
                                    
                                    switch (datasetLabel) {
                                        case '音高':
                                            unit = ' Hz';
                                            break;
                                        case '音量':
                                            unit = ' dB';
                                            break;
                                        case '语速':
                                            unit = ' BPM';
                                            break;
                                    }
                                    
                                    return `${datasetLabel}: ${value.toFixed(1)}${unit}`;
                                },
                                title: function(context) {
                                    return `时间点: ${context[0].label || ''}`;
                                }
                            }
                        }
                    },
                    elements: {
                        line: {
                            borderJoinStyle: 'round'
                        },
                        point: {
                            hoverBorderWidth: 2
                        }
                    }
                }
            });
            
            console.log('✅ 重叠语调图表初始化完成');
            
        } catch (error) {
            console.error('❌ 图表初始化失败:', error);
            throw error;
        }
    }
    
    /**
     * 处理来自WebSocket的语调分析数据
     * @param {Object} data - 语调分析数据
     */
    processAnalysisData(data) {
        try {
            if (!data || !data.data) {
                console.warn('⚠️ 无效的语调分析数据');
                return;
            }
            
            const analysisData = data.data;
            const timestamp = Date.now() / 1000; // 转换为秒
            
            console.log('📊 处理语调分析数据:', {
                pitch: analysisData.pitch_mean?.toFixed(1) + 'Hz',
                volume: analysisData.volume_mean?.toFixed(1) + 'dB',
                speechRate: analysisData.speech_rate?.toFixed(1) + 'BPM'
            });
            
            // 添加数据到历史记录
            this.addDataPoint({
                timestamp: timestamp,
                pitch: analysisData.pitch_mean || 0,
                volume: analysisData.volume_mean || -60,
                speechRate: analysisData.speech_rate || 0
            });
            
            // 更新图表
            this.updateCharts();
            
            // 更新数值显示
            this.updateValueDisplays(analysisData);
            
        } catch (error) {
            console.error('❌ 处理语调分析数据失败:', error);
        }
    }
    
    /**
     * 添加数据点
     * @param {Object} dataPoint - 数据点
     */
    addDataPoint(dataPoint) {
        // 添加到历史记录
        this.pitchHistory.push({ x: dataPoint.timestamp, y: dataPoint.pitch });
        this.volumeHistory.push({ x: dataPoint.timestamp, y: dataPoint.volume });
        this.speechRateHistory.push({ x: dataPoint.timestamp, y: dataPoint.speechRate });
        
        // 保持数据点数量限制
        if (this.pitchHistory.length > this.maxDataPoints) {
            this.pitchHistory.shift();
        }
        if (this.volumeHistory.length > this.maxDataPoints) {
            this.volumeHistory.shift();
        }
        if (this.speechRateHistory.length > this.maxDataPoints) {
            this.speechRateHistory.shift();
        }
    }
    
    /**
     * 更新重叠图表数据
     */
    updateCharts() {
        try {
            if (this.voiceToneChart) {
                // 更新音高数据集
                this.voiceToneChart.data.datasets[0].data = [...this.pitchHistory];
                // 更新音量数据集
                this.voiceToneChart.data.datasets[1].data = [...this.volumeHistory];
                // 更新语速数据集
                this.voiceToneChart.data.datasets[2].data = [...this.speechRateHistory];
                
                // 无动画更新
                this.voiceToneChart.update('none');
            }
            
        } catch (error) {
            console.error('❌ 更新重叠图表失败:', error);
        }
    }
    
    /**
     * 更新数值显示（已移除数值卡片，仅保留日志记录）
     * @param {Object} data - 分析数据
     */
    updateValueDisplays(data) {
        try {
            // 仅在控制台记录当前数值（已移除UI显示）
            console.log(`🎼 当前语调数据: 音高=${(data.pitch_mean || 0).toFixed(1)}Hz, 音量=${(data.volume_mean || -60).toFixed(1)}dB, 语速=${(data.speech_rate || 0).toFixed(1)}BPM`);
            
        } catch (error) {
            console.error('❌ 更新数值显示失败:', error);
        }
    }
    
    /**
     * 更新状态指示器
     * @param {Object} data - 分析数据
     */
    updateStatusIndicators(data) {
        try {
            // 仅进行状态计算和日志记录（已移除UI显示）
            const pitchStatus = this.getPitchStatus(data.pitch_mean);
            const volumeStatus = this.getVolumeStatus(data.volume_mean);
            const speechRateStatus = this.getSpeechRateStatus(data.speech_rate);
            
            console.log(`📊 语调状态: 音高${pitchStatus.text}, 音量${volumeStatus.text}, 语速${speechRateStatus.text}`);
            
        } catch (error) {
            console.error('❌ 更新状态指示器失败:', error);
        }
    }
    
    /**
     * 获取音高状态
     */
    getPitchStatus(pitch) {
        if (pitch < 100) return { class: 'status-low', text: '偏低' };
        if (pitch > 300) return { class: 'status-high', text: '偏高' };
        return { class: 'status-normal', text: '正常' };
    }
    
    /**
     * 获取音量状态
     */
    getVolumeStatus(volume) {
        if (volume < -40) return { class: 'status-low', text: '偏小' };
        if (volume > -10) return { class: 'status-high', text: '偏大' };
        return { class: 'status-normal', text: '正常' };
    }
    
    /**
     * 获取语速状态
     */
    getSpeechRateStatus(rate) {
        if (rate < 60) return { class: 'status-low', text: '偏慢' };
        if (rate > 150) return { class: 'status-high', text: '偏快' };
        return { class: 'status-normal', text: '正常' };
    }
    
    /**
     * 开始分析
     */
    startAnalysis() {
        this.isAnalyzing = true;
        this.clearData();
        console.log('🎼 开始语调分析');
        
        // 更新UI状态
        const statusElement = document.getElementById('voice-tone-status');
        if (statusElement) {
            statusElement.textContent = '正在分析...';
            statusElement.className = 'status-analyzing';
        }
    }
    
    /**
     * 停止分析
     */
    stopAnalysis() {
        this.isAnalyzing = false;
        console.log('🎼 停止语调分析');
        
        // 更新UI状态
        const statusElement = document.getElementById('voice-tone-status');
        if (statusElement) {
            statusElement.textContent = '已停止';
            statusElement.className = 'status-stopped';
        }
    }
    
    /**
     * 清空数据
     */
    clearData() {
        this.pitchHistory = [];
        this.volumeHistory = [];
        this.speechRateHistory = [];
        
        // 清空重叠图表
        if (this.voiceToneChart) {
            this.voiceToneChart.data.datasets[0].data = []; // 音高
            this.voiceToneChart.data.datasets[1].data = []; // 音量
            this.voiceToneChart.data.datasets[2].data = []; // 语速
            this.voiceToneChart.update();
        }
        
        console.log('🧹 语调分析数据已清空');
    }
    
    /**
     * 销毁图表实例
     */
    destroy() {
        try {
            if (this.voiceToneChart) {
                this.voiceToneChart.destroy();
                this.voiceToneChart = null;
            }
            
            this.clearData();
            console.log('🎼 语调分析器已销毁');
            
        } catch (error) {
            console.error('❌ 销毁语调分析器失败:', error);
        }
    }
}

// 导出到全局作用域
window.VoiceToneAnalyzer = VoiceToneAnalyzer;
