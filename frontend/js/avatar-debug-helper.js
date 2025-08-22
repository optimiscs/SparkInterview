/**
 * 数字人调试辅助工具
 * 提供控制台调试命令和状态检查功能
 */

(function() {
    'use strict';
    
    console.log('🔧 数字人调试助手已加载');
    
    // 添加全局调试函数到window对象
    window.avatarDebug = {
        
        /**
         * 检查数字人系统状态
         */
        checkStatus: function() {
            console.log('=== 数字人系统状态检查 ===');
            
            // 检查SDK是否加载
            if (typeof IAvatarPlatform !== 'undefined') {
                console.log('✅ 数字人SDK已加载');
            } else {
                console.error('❌ 数字人SDK未加载');
                return false;
            }
            
            // 检查管理器是否初始化
            if (typeof window.getAvatarManager === 'function') {
                console.log('✅ 数字人管理器已加载');
                
                const manager = window.getAvatarManager();
                const status = manager.getConnectionStatus();
                
                console.log('管理器状态:', status);
                
                if (status.isInitialized) {
                    console.log('✅ 管理器已初始化');
                } else {
                    console.warn('⚠️ 管理器未初始化');
                }
                
                if (status.isConnected) {
                    console.log('✅ 数字人已连接');
                } else {
                    console.warn('⚠️ 数字人未连接');
                }
                
                if (status.isPlaying) {
                    console.log('🎤 数字人正在播放');
                } else {
                    console.log('⏸️ 数字人未在播放');
                }
                
                return status;
            } else {
                console.error('❌ 数字人管理器未加载');
                return false;
            }
        },
        
        /**
         * 手动初始化数字人系统
         */
        init: async function() {
            console.log('🚀 手动初始化数字人系统...');
            
            if (typeof window.initializeAvatarSystem === 'function') {
                try {
                    const result = await window.initializeAvatarSystem();
                    if (result) {
                        console.log('✅ 数字人系统初始化成功');
                    } else {
                        console.error('❌ 数字人系统初始化失败');
                    }
                    return result;
                } catch (error) {
                    console.error('❌ 初始化过程中出错:', error);
                    return false;
                }
            } else {
                console.error('❌ 初始化函数不存在');
                return false;
            }
        },
        
        /**
         * 测试数字人朗读
         */
        testSpeak: async function(text = '您好，这是数字人测试语音，请确认能听到声音并看到口型同步。') {
            console.log('🎤 测试数字人朗读...');
            
            if (typeof window.speakText === 'function') {
                try {
                    const requestId = await window.speakText(text, {
                        interruptible: true,
                        speed: 50,
                        volume: 80
                    });
                    
                    if (requestId) {
                        console.log('✅ 朗读请求发送成功:', requestId);
                        console.log('🗣️ 正在朗读:', text);
                    } else {
                        console.error('❌ 朗读请求失败');
                    }
                    
                    return requestId;
                } catch (error) {
                    console.error('❌ 朗读测试失败:', error);
                    return false;
                }
            } else {
                console.error('❌ speakText 函数不存在');
                return false;
            }
        },
        
        /**
         * 停止数字人播放
         */
        stop: async function() {
            console.log('⏸️ 停止数字人播放...');
            
            if (typeof window.interruptAvatar === 'function') {
                try {
                    await window.interruptAvatar();
                    console.log('✅ 数字人播放已停止');
                    return true;
                } catch (error) {
                    console.error('❌ 停止播放失败:', error);
                    return false;
                }
            } else {
                console.error('❌ interruptAvatar 函数不存在');
                return false;
            }
        },
        
        /**
         * 重连数字人
         */
        reconnect: async function() {
            console.log('🔄 重连数字人...');
            
            if (typeof window.getAvatarManager === 'function') {
                try {
                    const manager = window.getAvatarManager();
                    
                    // 先断开
                    manager.disconnect();
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                    // 重新连接
                    const result = await manager.connect();
                    
                    if (result) {
                        console.log('✅ 数字人重连成功');
                    } else {
                        console.error('❌ 数字人重连失败');
                    }
                    
                    return result;
                } catch (error) {
                    console.error('❌ 重连过程中出错:', error);
                    return false;
                }
            } else {
                console.error('❌ 数字人管理器不存在');
                return false;
            }
        },
        
        /**
         * 更新数字人配置
         */
        updateConfig: function(newConfig) {
            console.log('⚙️ 更新数字人配置...');
            
            if (typeof window.getAvatarManager === 'function') {
                try {
                    const manager = window.getAvatarManager();
                    const result = manager.updateConfig(newConfig);
                    
                    if (result) {
                        console.log('✅ 配置更新成功');
                        console.log('新配置:', newConfig);
                    } else {
                        console.error('❌ 配置更新失败');
                    }
                    
                    return result;
                } catch (error) {
                    console.error('❌ 更新配置时出错:', error);
                    return false;
                }
            } else {
                console.error('❌ 数字人管理器不存在');
                return false;
            }
        },
        
        /**
         * 显示帮助信息
         */
        help: function() {
            console.log(`
=== 数字人调试命令帮助 ===

在浏览器控制台中可以使用以下命令：

avatarDebug.checkStatus()     - 检查数字人系统状态
avatarDebug.init()           - 手动初始化数字人系统
avatarDebug.testSpeak(text)  - 测试数字人朗读（可选传入文字）
avatarDebug.stop()           - 停止数字人播放
avatarDebug.reconnect()      - 重连数字人服务
avatarDebug.updateConfig(config) - 更新配置
avatarDebug.help()           - 显示此帮助信息

示例用法：
avatarDebug.testSpeak("这是测试语音")
avatarDebug.updateConfig({
    globalParams: {
        tts: { speed: 60, volume: 90 }
    }
})

=== 状态检查 ===
`);
            
            // 自动显示当前状态
            this.checkStatus();
        }
    };
    
    // 页面加载完成后显示调试信息
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            console.log(`
🤖 数字人调试助手已就绪！

在控制台输入 avatarDebug.help() 查看可用命令
或输入 avatarDebug.checkStatus() 检查系统状态
            `);
        }, 2000);
    });
    
})();

console.log('🔧 数字人调试助手模块加载完成');
