/**
 * 体态语言分析器
 * 处理实时体态语言分析数据的接收、处理和UI更新
 * 与video-analysis-manager.js协同工作
 */

class BodyLanguageAnalyzer {
    constructor() {
        // 分析状态
        this.isAnalyzing = false;
        this.currentData = null;
        
        // 历史数据存储
        this.postureHistory = [];
        this.gestureHistory = [];
        this.maxHistoryLength = 50; // 保存最近50个数据点
        
        // UI元素引用
        this.uiElements = {
            // 体态语言指标
            postureScore: document.querySelector('[data-analysis="posture-score"]'),
            bodyAngle: document.querySelector('[data-analysis="body-angle"]'), 
            tensionLevel: document.querySelector('[data-analysis="tension-level"]'),
            postureType: document.querySelector('[data-analysis="posture-type"]'),
            
            // 手势指标
            gestureActivity: document.querySelector('[data-analysis="gesture-activity"]'),
            dominantGesture: document.querySelector('[data-analysis="dominant-gesture"]'),
            handsDetected: document.querySelector('[data-analysis="hands-detected"]'),
            
            // 状态指示器
            eyeContactText: document.querySelector('.eye-contact-text'),
            eyeContactDesc: document.querySelector('.eye-contact-desc'),
            postureText: document.querySelector('.posture-text'),
            postureDesc: document.querySelector('.posture-desc'),
            gestureText: document.querySelector('.gesture-text'),
            gestureDesc: document.querySelector('.gesture-desc')
        };
        
        console.log('🧍 体态语言分析器初始化完成');
    }
    
    /**
     * 启动体态语言分析
     */
    startAnalysis() {
        this.isAnalyzing = true;
        this.updateStatusUI('analyzing');
        console.log('🧍 体态语言分析已启动');
    }
    
    /**
     * 停止体态语言分析
     */
    stopAnalysis() {
        this.isAnalyzing = false;
        this.updateStatusUI('stopped');
        console.log('🛑 体态语言分析已停止');
    }
    
    /**
     * 处理来自WebSocket的体态语言分析数据
     * @param {Object} analysisData - 分析数据
     */
    processAnalysisData(analysisData) {
        console.log('🧍 体态语言分析器收到数据:', analysisData);
        
        if (!this.isAnalyzing) {
            console.log('⚠️ 体态语言分析器未启动，忽略数据');
            return;
        }
        
        if (!analysisData) {
            console.log('⚠️ 体态语言分析数据为空');
            return;
        }
        
        try {
            const timestamp = Date.now();
            
            // 处理体态语言数据
            if (analysisData.body_language) {
                console.log('📊 处理体态语言数据:', analysisData.body_language);
                this.processBodyLanguageData(analysisData.body_language, timestamp);
            } else {
                console.log('⚠️ 未找到body_language字段');
            }
            
            // 处理手势数据
            if (analysisData.gestures) {
                console.log('👋 处理手势数据:', analysisData.gestures);
                this.processGestureData(analysisData.gestures, timestamp);
            } else {
                console.log('⚠️ 未找到gestures字段');
            }
            
            // 更新UI显示
            this.updateUI(analysisData);
            
            // 保存当前数据
            this.currentData = analysisData;
            
        } catch (error) {
            console.error('❌ 处理体态语言分析数据失败:', error);
        }
    }
    
    /**
     * 处理体态语言数据
     * @param {Object} bodyLanguageData - 体态语言数据
     * @param {number} timestamp - 时间戳
     */
    processBodyLanguageData(bodyLanguageData, timestamp) {
        const postureData = {
            timestamp: timestamp,
            posture_score: bodyLanguageData.posture_score || 0,
            body_angle: bodyLanguageData.body_angle || 0,
            tension_level: bodyLanguageData.tension_level || 0,
            posture_type: bodyLanguageData.posture_type || 'sitting',
            body_stability: bodyLanguageData.body_stability || 0
        };
        
        // 添加到历史记录
        this.postureHistory.push(postureData);
        
        // 维护历史记录长度
        if (this.postureHistory.length > this.maxHistoryLength) {
            this.postureHistory.shift();
        }
        
        console.log(`🧍 体态数据: 姿态分数=${postureData.posture_score}分, 身体角度=${postureData.body_angle}°, 紧张度=${postureData.tension_level}%`);
    }
    
    /**
     * 处理手势数据
     * @param {Object} gestureData - 手势数据
     * @param {number} timestamp - 时间戳
     */
    processGestureData(gestureData, timestamp) {
        const processedGesture = {
            timestamp: timestamp,
            hands_detected: gestureData.hands_detected || 0,
            gesture_activity: gestureData.gesture_activity || 0,
            dominant_gesture: gestureData.dominant_gesture || 'none',
            total_movement: gestureData.total_movement || 0
        };
        
        // 添加到历史记录
        this.gestureHistory.push(processedGesture);
        
        // 维护历史记录长度
        if (this.gestureHistory.length > this.maxHistoryLength) {
            this.gestureHistory.shift();
        }
        
        console.log(`👋 手势数据: 检测到${processedGesture.hands_detected}只手, 活跃度=${processedGesture.gesture_activity}%, 主导手势=${processedGesture.dominant_gesture}`);
    }
    
    /**
     * 更新UI显示
     * @param {Object} analysisData - 完整的分析数据
     */
    updateUI(analysisData) {
        // 更新体态语言相关UI
        if (analysisData.body_language) {
            this.updatePostureUI(analysisData.body_language);
        }
        
        // 更新手势相关UI
        if (analysisData.gestures) {
            this.updateGestureUI(analysisData.gestures);
        }
        
        // 更新综合状态显示
        this.updateBodyLanguageStatus(analysisData);
    }
    
    /**
     * 更新姿态相关UI
     * @param {Object} bodyLanguageData - 体态语言数据
     */
    updatePostureUI(bodyLanguageData) {
        console.log('🎯 更新姿态UI，数据:', bodyLanguageData);
        
        // 更新姿态文本描述
        if (this.uiElements.postureText && this.uiElements.postureDesc) {
            const postureScore = bodyLanguageData.posture_score || 0;
            const bodyAngle = bodyLanguageData.body_angle || 0;
            const tensionLevel = bodyLanguageData.tension_level || 0;
            
            console.log('📊 姿态数据:', { postureScore, bodyAngle, tensionLevel });
            
            let postureStatus, postureAdvice;
            
            if (postureScore >= 80) {
                postureStatus = "坐姿端正优雅";
                postureAdvice = "保持良好姿态";
            } else if (postureScore >= 60) {
                postureStatus = "坐姿基本良好";
                postureAdvice = "可以稍微调整坐姿";
            } else if (tensionLevel > 60) {
                postureStatus = "坐姿略显紧张";
                postureAdvice = "建议放松肩膀";
            } else if (bodyAngle > 15) {
                postureStatus = "身体有些倾斜";
                postureAdvice = "建议保持身体平衡";
            } else {
                postureStatus = "坐姿需要调整";
                postureAdvice = "建议挺直背部";
            }
            
            console.log('✏️ 更新UI文本:', { postureStatus, postureAdvice });
            
            this.uiElements.postureText.textContent = postureStatus;
            this.uiElements.postureDesc.textContent = postureAdvice;
            
            console.log('✅ UI元素已更新');
        } else {
            console.log('⚠️ 未找到postureText或postureDesc元素:', {
                postureText: !!this.uiElements.postureText,
                postureDesc: !!this.uiElements.postureDesc
            });
        }
    }
    
    /**
     * 更新手势相关UI
     * @param {Object} gestureData - 手势数据
     */
    updateGestureUI(gestureData) {
        // 更新手势文本描述
        if (this.uiElements.gestureText && this.uiElements.gestureDesc) {
            const gestureActivity = gestureData.gesture_activity || 0;
            const dominantGesture = gestureData.dominant_gesture || 'none';
            const handsDetected = gestureData.hands_detected || 0;
            
            let gestureStatus, gestureAdvice;
            
            if (handsDetected === 0) {
                gestureStatus = "未检测到手势";
                gestureAdvice = "可以适当使用手势辅助表达";
            } else if (gestureActivity >= 60) {
                gestureStatus = "手势表达丰富";
                gestureAdvice = "很好地配合了语言表达";
            } else if (gestureActivity >= 30) {
                gestureStatus = "手势表达自然";
                gestureAdvice = "有效辅助了语言表达";
            } else if (dominantGesture === 'fist') {
                gestureStatus = "手部较为紧张";
                gestureAdvice = "建议放松手部";
            } else {
                gestureStatus = "手势表达较少";
                gestureAdvice = "可以增加适当的手势";
            }
            
            this.uiElements.gestureText.textContent = gestureStatus;
            this.uiElements.gestureDesc.textContent = gestureAdvice;
        }
    }
    
    /**
     * 更新眼神接触相关UI
     * @param {Object} analysisData - 完整分析数据
     */
    updateBodyLanguageStatus(analysisData) {
        // 更新眼神接触状态（基于视线分析）
        if (this.uiElements.eyeContactText && this.uiElements.eyeContactDesc && analysisData.body_language) {
            const eyeContactRatio = analysisData.body_language.eye_contact_ratio || 0;
            
            let eyeContactStatus, eyeContactAdvice;
            
            if (eyeContactRatio >= 70) {
                eyeContactStatus = "眼神接触良好";
                eyeContactAdvice = `保持了 ${eyeContactRatio}% 的时间`;
            } else if (eyeContactRatio >= 50) {
                eyeContactStatus = "眼神接触一般";
                eyeContactAdvice = `建议增加眼神交流`;
            } else if (eyeContactRatio >= 30) {
                eyeContactStatus = "眼神接触较少";
                eyeContactAdvice = "建议更多地看向镜头";
            } else {
                eyeContactStatus = "缺乏眼神接触";
                eyeContactAdvice = "建议主动进行眼神交流";
            }
            
            this.uiElements.eyeContactText.textContent = eyeContactStatus;
            this.uiElements.eyeContactDesc.textContent = eyeContactAdvice;
        }
    }
    
    /**
     * 更新状态UI
     * @param {string} status - 状态 ('analyzing', 'stopped')
     */
    updateStatusUI(status) {
        // 更新状态指示器
        const statusElements = document.querySelectorAll('[data-status="body-language"]');
        statusElements.forEach(element => {
            if (status === 'analyzing') {
                element.textContent = '体态分析中';
                element.className = 'text-sm text-green-600';
            } else {
                element.textContent = '体态分析未启动';
                element.className = 'text-sm text-gray-500';
            }
        });
    }
    
    /**
     * 获取当前体态语言数据
     * @returns {Object|null} 当前体态语言数据
     */
    getCurrentData() {
        return this.currentData;
    }
    
    /**
     * 获取体态语言历史数据
     * @returns {Object} 历史数据
     */
    getHistoryData() {
        return {
            posture: [...this.postureHistory],
            gestures: [...this.gestureHistory]
        };
    }
    
    /**
     * 清空历史数据
     */
    clearHistory() {
        this.postureHistory = [];
        this.gestureHistory = [];
        this.currentData = null;
        console.log('🧹 体态语言分析历史数据已清空');
    }
    
    /**
     * 获取体态语言分析统计
     * @returns {Object} 统计数据
     */
    getAnalysisStats() {
        if (this.postureHistory.length === 0 && this.gestureHistory.length === 0) {
            return null;
        }
        
        const stats = {
            posture: {},
            gestures: {}
        };
        
        // 姿态统计
        if (this.postureHistory.length > 0) {
            const postureScores = this.postureHistory.map(p => p.posture_score);
            const tensionLevels = this.postureHistory.map(p => p.tension_level);
            
            stats.posture = {
                avgPostureScore: this.calculateAverage(postureScores),
                maxPostureScore: Math.max(...postureScores),
                minPostureScore: Math.min(...postureScores),
                avgTensionLevel: this.calculateAverage(tensionLevels),
                dataPoints: this.postureHistory.length
            };
        }
        
        // 手势统计
        if (this.gestureHistory.length > 0) {
            const gestureActivities = this.gestureHistory.map(g => g.gesture_activity);
            const handsDetectedCounts = this.gestureHistory.map(g => g.hands_detected);
            
            stats.gestures = {
                avgGestureActivity: this.calculateAverage(gestureActivities),
                maxGestureActivity: Math.max(...gestureActivities),
                avgHandsDetected: this.calculateAverage(handsDetectedCounts),
                dataPoints: this.gestureHistory.length
            };
        }
        
        return stats;
    }
    
    /**
     * 计算数组平均值
     * @param {number[]} values - 数值数组
     * @returns {number} 平均值
     */
    calculateAverage(values) {
        if (values.length === 0) return 0;
        return values.reduce((sum, val) => sum + val, 0) / values.length;
    }
    
    /**
     * 销毁分析器
     */
    destroy() {
        this.stopAnalysis();
        this.clearHistory();
        this.uiElements = {};
        console.log('🧍 体态语言分析器已销毁');
    }
}

// 导出到全局作用域
window.BodyLanguageAnalyzer = BodyLanguageAnalyzer;

// 创建全局实例（可选）
if (typeof window !== 'undefined') {
    window.globalBodyLanguageAnalyzer = new BodyLanguageAnalyzer();
}
