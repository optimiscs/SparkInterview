/**
 * 数字人SDK集成管理器
 * 集成讯飞星火数字人SDK，实现AI面试官的语音播报和视觉呈现
 */

class AvatarIntegrationManager {
    constructor() {
        // 数字人SDK实例
        this.avatarPlatform = null;
        
        // 连接状态
        this.isConnected = false;
        this.isInitialized = false;
        
        // 播放状态
        this.isPlaying = false;
        this.currentRequestId = null;
        
        // 配置信息
        this.config = {
            // API配置
            apiInfo: {
                appId: "015076e9",
                apiKey: "9bcb3472851cf652bd640107f258910a", 
                apiSecret: "YTM3MzAwZDEzMDgyZjFmNjI0MmFhOTg1",
                serverUrl: "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact",
                sceneId: "216904764871544832",
                sceneVersion: ""
            },
            
            // 全局参数配置
            globalParams: {
                // 数字人形象配置
                avatar: {
                    avatar_id: "138801001",
                    width: 720,
                    height: 1280,
                    audio_format: 1, // 1: 16K, 2: 24K
                    scale: 1.0,
                    move_h: 0,
                    move_v: 0
                },
                
                // 流媒体配置
                stream: {
                    protocol: "xrtc",
                    bitrate: 1000000, // 1Mbps
                    fps: 25,
                    alpha: 1,
                    
                },
                
                // TTS语音配置
                tts: {
                    vcn: "x4_yuexiaoni_assist", // 悦小妮助手音色
                    speed: 50,   // 语速 0-100
                    pitch: 50,   // 音调 0-100  
                    volume: 80,  // 音量 0-100
                    audio: {
                        sample_rate: 16000
                    }
                },
                
                // 交互调度配置
                avatar_dispatch: {
                    interactive_mode: 0, // 0: append, 1: break
                    enable_action_status: 1,
                    content_analysis: 0
                },
                
                // 字幕配置
                subtitle: {
                    subtitle: 1,
                    font_color: "#FFFFFF"
                },
                
                // AIR动作配置
                air: {
                    air: 1, // 启用自动动作
                    add_nonsemantic: 1 // 添加无指向动作
                }
            }
        };
        
        // DOM元素
        this.elements = {
            videoContainer: null,
            subtitleText: null,
            statusIndicator: null
        };
        
        // 事件回调
        this.eventCallbacks = {
            onConnected: null,
            onDisconnected: null,
            onError: null,
            onSubtitle: null,
            onPlayingStateChange: null
        };
        
        // 初始化
        this.init();
    }
    
    /**
     * 初始化管理器
     */
    init() {
        console.log('🤖 初始化数字人SDK集成管理器');
        
        try {
            // 获取DOM元素
            this.initDOMElements();
            
            // 检查SDK是否加载
            if (typeof window.IAvatarPlatform === 'undefined' && typeof window.AvatarPlatform === 'undefined') {
                console.error('❌ 数字人SDK未加载，请检查script标签引入');
                return false;
            }
            
            // 检查事件类型是否加载
            if (typeof window.SDKEvents === 'undefined') {
                console.error('❌ SDK事件类型未加载，请检查导入');
                return false;
            }
            
            // 创建数字人平台实例
            this.createAvatarPlatform();
            
            // 绑定事件监听
            this.bindEvents();
            
            this.isInitialized = true;
            console.log('✅ 数字人SDK集成管理器初始化成功');
            
            return true;
            
        } catch (error) {
            console.error('❌ 数字人SDK集成管理器初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 获取DOM元素
     */
    initDOMElements() {
        this.elements.videoContainer = document.getElementById('ai-video-main');
        this.elements.subtitleText = document.getElementById('ai-subtitle-text');
        this.elements.statusIndicator = document.querySelector('[data-analysis-status]');
        
        if (!this.elements.videoContainer) {
            console.error('❌ 找不到数字人视频容器元素 #ai-video-main');
        }
        
        if (!this.elements.subtitleText) {
            console.error('❌ 找不到字幕显示元素 #ai-subtitle-text');
        }
        
        console.log('📱 DOM元素初始化完成');
    }
    
    /**
     * 创建数字人平台实例
     */
    createAvatarPlatform() {
        try {
            // 获取SDK构造函数
            const AvatarSDK = window.IAvatarPlatform || window.AvatarPlatform;
            if (!AvatarSDK) {
                throw new Error('数字人SDK构造函数不可用');
            }
            
            // 创建数字人平台实例
            this.avatarPlatform = new AvatarSDK({
                useInlinePlayer: true,  // 使用内联播放器
                logLevel: 2,           // 日志级别：info
                binaryData: false      // 不使用二进制数据
            });
            
            // 设置API信息
            this.avatarPlatform.setApiInfo(this.config.apiInfo);
            
            // 设置全局参数
            this.avatarPlatform.setGlobalParams(this.config.globalParams);
            
            console.log('🎭 数字人平台实例创建成功');
            
        } catch (error) {
            console.error('❌ 创建数字人平台实例失败:', error);
            throw error;
        }
    }
    
    /**
     * 绑定事件监听
     */
    bindEvents() {
        if (!this.avatarPlatform) {
            console.error('❌ 数字人平台实例不存在，无法绑定事件');
            return;
        }
        
        // 获取事件类型
        const Events = window.SDKEvents;
        if (!Events) {
            console.error('❌ SDK事件类型不可用，无法绑定事件');
            return;
        }
        
        // 连接成功事件
        this.avatarPlatform.on(Events.connected, (connectInfo) => {
            console.log('🔗 数字人连接成功:', connectInfo);
            this.isConnected = true;
            this.updateStatus('已连接');
            
            if (this.eventCallbacks.onConnected) {
                this.eventCallbacks.onConnected(connectInfo);
            }
        });
        
        // 连接断开事件
        this.avatarPlatform.on(Events.disconnected, (error) => {
            console.log('🔌 数字人连接断开:', error);
            this.isConnected = false;
            this.updateStatus('已断开');
            
            if (this.eventCallbacks.onDisconnected) {
                this.eventCallbacks.onDisconnected(error);
            }
        });
        
        // 流开始事件
        this.avatarPlatform.on(Events.stream_start, () => {
            console.log('🎬 数字人视频流开始');
            this.updateStatus('视频流启动');
        });
        
        // 帧开始事件
        this.avatarPlatform.on(Events.frame_start, (data) => {
            console.log('▶️ 数字人开始播放:', data);
            this.isPlaying = true;
            this.updateStatus('正在播放');
            
            if (this.eventCallbacks.onPlayingStateChange) {
                this.eventCallbacks.onPlayingStateChange(true);
            }
        });
        
        // 帧结束事件
        this.avatarPlatform.on(Events.frame_stop, (data) => {
            console.log('⏹️ 数字人停止播放:', data);
            this.isPlaying = false;
            this.updateStatus('播放完毕');
            
            if (this.eventCallbacks.onPlayingStateChange) {
                this.eventCallbacks.onPlayingStateChange(false);
            }
        });
        
        // 字幕信息事件
        this.avatarPlatform.on(Events.subtitle_info, (subtitleInfo) => {
            if (subtitleInfo && subtitleInfo.text) {
                console.log('📝 收到字幕信息:', subtitleInfo.text);
                this.updateSubtitle(subtitleInfo.text);
                
                if (this.eventCallbacks.onSubtitle) {
                    this.eventCallbacks.onSubtitle(subtitleInfo);
                }
            } else {
                // 清空字幕
                this.updateSubtitle('等待语音输入或文字消息...');
            }
        });
        
        // NLP事件（实时文本流）
        this.avatarPlatform.on(Events.nlp, (nlpData) => {
            console.log('🧠 NLP数据:', nlpData);
            
            if (nlpData && nlpData.displayContent) {
                this.updateSubtitle(nlpData.displayContent);
            }
        });
        
        // TTS时长信息
        this.avatarPlatform.on(Events.tts_duration, (durationInfo) => {
            console.log('🎵 TTS时长信息:', durationInfo);
        });
        
        // 动作开始事件
        this.avatarPlatform.on(Events.action_start, (actionInfo) => {
            console.log('🤚 数字人动作开始:', actionInfo);
        });
        
        // 动作结束事件
        this.avatarPlatform.on(Events.action_stop, (actionInfo) => {
            console.log('✋ 数字人动作结束:', actionInfo);
        });
        
        // 错误事件
        this.avatarPlatform.on(Events.error, (error) => {
            console.error('❌ 数字人SDK错误:', error);
            this.updateStatus('错误：' + (error.message || '未知错误'));
            
            if (this.eventCallbacks.onError) {
                this.eventCallbacks.onError(error);
            }
        });
        
        console.log('🔗 数字人事件监听绑定完成');
    }
    
    /**
     * 连接数字人服务
     */
    async connect() {
        if (!this.isInitialized) {
            console.error('❌ 管理器未初始化，无法连接');
            return false;
        }
        
        if (this.isConnected) {
            console.log('⚠️ 数字人已连接，无需重复连接');
            return true;
        }
        
        try {
            console.log('🔄 正在连接数字人服务...');
            this.updateStatus('正在连接...');
            
            // 启动数字人服务
            await this.avatarPlatform.start({
                wrapper: this.elements.videoContainer
            });
            
            console.log('✅ 数字人服务连接成功');
            return true;
            
        } catch (error) {
            console.error('❌ 连接数字人服务失败:', error);
            this.updateStatus('连接失败');
            return false;
        }
    }
    
    /**
     * 断开数字人连接
     */
    disconnect() {
        if (!this.isConnected) {
            console.log('⚠️ 数字人未连接，无需断开');
            return;
        }
        
        try {
            console.log('🔌 正在断开数字人连接...');
            this.updateStatus('正在断开...');
            
            if (this.avatarPlatform) {
                this.avatarPlatform.stop();
            }
            
            this.isConnected = false;
            console.log('✅ 数字人连接已断开');
            
        } catch (error) {
            console.error('❌ 断开数字人连接失败:', error);
        }
    }
    
    /**
     * 让数字人说话（朗读文字）
     * @param {string} text - 要朗读的文字
     * @param {Object} options - 可选参数
     */
    async speak(text, options = {}) {
        if (!this.isConnected) {
            console.error('❌ 数字人未连接，无法播放语音');
            return false;
        }
        
        if (!text || typeof text !== 'string' || text.trim() === '') {
            console.log('⚠️ 文字内容为空，跳过播放');
            return false;
        }
        
        try {
            console.log('🎤 数字人开始朗读:', text.substring(0, 50) + (text.length > 50 ? '...' : ''));
            
            // 更新字幕显示
            this.updateSubtitle('正在准备播放...');
            
            // 构建参数
            const speakOptions = {
                request_id: options.requestId || this.generateRequestId(),
                nlp: false, // 不启用NLP处理，直接播放文字
                avatar_dispatch: {
                    interactive_mode: options.interruptible ? 1 : 0, // 是否可中断
                    ...options.avatar_dispatch
                },
                tts: {
                    vcn: options.voice || this.config.globalParams.tts.vcn,
                    speed: options.speed || this.config.globalParams.tts.speed,
                    pitch: options.pitch || this.config.globalParams.tts.pitch,
                    volume: options.volume || this.config.globalParams.tts.volume,
                    ...options.tts
                },
                ...options
            };
            
            // 发送文字给数字人播放
            const requestId = await this.avatarPlatform.writeText(text, speakOptions);
            this.currentRequestId = requestId;
            
            console.log('✅ 文字发送成功，请求ID:', requestId);
            return requestId;
            
        } catch (error) {
            console.error('❌ 数字人播放语音失败:', error);
            this.updateSubtitle('播放失败');
            return false;
        }
    }
    
    /**
     * 停止当前播放（中断）
     */
    async interrupt() {
        if (!this.isConnected) {
            console.log('⚠️ 数字人未连接，无需中断');
            return;
        }
        
        try {
            console.log('⏸️ 中断数字人当前播放');
            
            await this.avatarPlatform.interrupt();
            this.isPlaying = false;
            this.updateSubtitle('播放已中断');
            
            console.log('✅ 数字人播放已中断');
            
        } catch (error) {
            console.error('❌ 中断数字人播放失败:', error);
        }
    }
    
    /**
     * 更新字幕显示
     * @param {string} text - 字幕文字
     */
    updateSubtitle(text) {
        if (this.elements.subtitleText) {
            this.elements.subtitleText.textContent = text || '等待语音输入或文字消息...';
        }
    }
    
    /**
     * 更新状态显示
     * @param {string} status - 状态文字
     */
    updateStatus(status) {
        if (this.elements.statusIndicator) {
            this.elements.statusIndicator.textContent = status;
        }
        
        console.log('📊 状态更新:', status);
    }
    
    /**
     * 生成请求ID
     */
    generateRequestId() {
        return 'avatar_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * 设置事件回调
     * @param {string} eventName - 事件名称
     * @param {Function} callback - 回调函数
     */
    setEventCallback(eventName, callback) {
        if (this.eventCallbacks.hasOwnProperty(eventName)) {
            this.eventCallbacks[eventName] = callback;
            console.log(`🔗 设置事件回调: ${eventName}`);
        } else {
            console.warn(`⚠️ 未知事件名称: ${eventName}`);
        }
    }
    
    /**
     * 获取连接状态
     */
    getConnectionStatus() {
        return {
            isInitialized: this.isInitialized,
            isConnected: this.isConnected,
            isPlaying: this.isPlaying,
            currentRequestId: this.currentRequestId
        };
    }
    
    /**
     * 更新配置
     * @param {Object} newConfig - 新配置
     */
    updateConfig(newConfig) {
        try {
            // 深度合并配置
            this.config = this.deepMerge(this.config, newConfig);
            
            // 如果数字人实例存在，更新配置
            if (this.avatarPlatform) {
                if (newConfig.apiInfo) {
                    this.avatarPlatform.setApiInfo(this.config.apiInfo);
                }
                
                if (newConfig.globalParams) {
                    this.avatarPlatform.setGlobalParams(this.config.globalParams);
                }
            }
            
            console.log('✅ 配置更新成功');
            return true;
            
        } catch (error) {
            console.error('❌ 配置更新失败:', error);
            return false;
        }
    }
    
    /**
     * 深度合并对象
     */
    deepMerge(target, source) {
        const result = { ...target };
        
        for (const key in source) {
            if (source.hasOwnProperty(key)) {
                if (typeof source[key] === 'object' && source[key] !== null && !Array.isArray(source[key])) {
                    result[key] = this.deepMerge(result[key] || {}, source[key]);
                } else {
                    result[key] = source[key];
                }
            }
        }
        
        return result;
    }
    
    /**
     * 销毁管理器
     */
    destroy() {
        console.log('🗑️ 销毁数字人SDK集成管理器');
        
        try {
            // 断开连接
            this.disconnect();
            
            // 销毁数字人实例
            if (this.avatarPlatform) {
                this.avatarPlatform.destroy();
                this.avatarPlatform = null;
            }
            
            // 重置状态
            this.isConnected = false;
            this.isInitialized = false;
            this.isPlaying = false;
            this.currentRequestId = null;
            
            // 清空事件回调
            Object.keys(this.eventCallbacks).forEach(key => {
                this.eventCallbacks[key] = null;
            });
            
            console.log('✅ 数字人SDK集成管理器销毁完成');
            
        } catch (error) {
            console.error('❌ 销毁数字人SDK集成管理器失败:', error);
        }
    }
}

// 全局实例
let globalAvatarManager = null;

/**
 * 获取全局数字人管理器实例
 */
function getAvatarManager() {
    if (!globalAvatarManager) {
        globalAvatarManager = new AvatarIntegrationManager();
    }
    return globalAvatarManager;
}

/**
 * 初始化数字人系统
 */
async function initializeAvatarSystem() {
    try {
        console.log('🚀 初始化数字人系统');
        
        const manager = getAvatarManager();
        
        if (!manager.isInitialized) {
            console.error('❌ 数字人管理器初始化失败');
            return false;
        }
        
        // 连接数字人服务
        const connected = await manager.connect();
        
        if (connected) {
            console.log('✅ 数字人系统初始化成功');
            
            // 发送测试消息
            setTimeout(() => {
                manager.speak('您好，我是AI面试官，很高兴为您服务！', {
                    interruptible: false
                });
            }, 2000);
            
            return true;
        } else {
            console.error('❌ 数字人系统连接失败');
            return false;
        }
        
    } catch (error) {
        console.error('❌ 初始化数字人系统失败:', error);
        return false;
    }
}

/**
 * 数字人说话（供外部调用）
 * @param {string} text - 要说的文字
 * @param {Object} options - 可选参数
 */
async function speakText(text, options = {}) {
    const manager = getAvatarManager();
    
    if (!manager.isInitialized) {
        console.error('❌ 数字人系统未初始化');
        return false;
    }
    
    return await manager.speak(text, options);
}

/**
 * 中断数字人播放
 */
async function interruptAvatar() {
    const manager = getAvatarManager();
    
    if (!manager.isInitialized) {
        console.log('⚠️ 数字人系统未初始化');
        return;
    }
    
    await manager.interrupt();
}

/**
 * 获取数字人状态
 */
function getAvatarStatus() {
    const manager = getAvatarManager();
    return manager.getConnectionStatus();
}

// 等待SDK加载完成后初始化
function waitForSDKAndInitialize() {
    console.log('📄 页面加载完成，等待数字人SDK加载...');
    
    // 检查SDK是否已经加载
    if (typeof window.IAvatarPlatform !== 'undefined' || typeof window.AvatarPlatform !== 'undefined') {
        console.log('🤖 SDK已加载，开始初始化数字人系统');
        setTimeout(() => {
            initializeAvatarSystem().catch(error => {
                console.error('❌ 自动初始化数字人系统失败:', error);
            });
        }, 500);
        return;
    }
    
    // 监听SDK加载事件
    window.addEventListener('avatarSDKLoaded', function(event) {
        console.log('🤖 收到SDK加载完成事件，开始初始化数字人系统');
        setTimeout(() => {
            initializeAvatarSystem().catch(error => {
                console.error('❌ 自动初始化数字人系统失败:', error);
            });
        }, 500);
    });
    
    // 设置超时检查，如果SDK长时间未加载则使用备用方案
    setTimeout(() => {
        if (typeof window.IAvatarPlatform === 'undefined' && typeof window.AvatarPlatform === 'undefined') {
            console.warn('⚠️ SDK加载超时，尝试备用初始化方案');
            
            // 尝试直接加载SDK文件
            const script = document.createElement('script');
            script.src = './avatar-sdk-web_3.1.2.1002/index-OS7Lza_r.js';
            script.onload = function() {
                console.log('✅ 备用SDK加载成功');
                setTimeout(() => {
                    initializeAvatarSystem().catch(error => {
                        console.error('❌ 备用初始化失败:', error);
                    });
                }, 1000);
            };
            script.onerror = function() {
                console.error('❌ 备用SDK加载失败');
            };
            document.head.appendChild(script);
        }
    }, 3000);
}

// 页面加载完成后等待SDK并初始化
document.addEventListener('DOMContentLoaded', waitForSDKAndInitialize);

// 导出到全局
window.AvatarIntegrationManager = AvatarIntegrationManager;
window.getAvatarManager = getAvatarManager;
window.initializeAvatarSystem = initializeAvatarSystem;
window.speakText = speakText;
window.interruptAvatar = interruptAvatar;
window.getAvatarStatus = getAvatarStatus;

console.log('📦 数字人SDK集成管理器模块加载完成');
