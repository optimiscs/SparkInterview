/**
 * Web IDE 代码编辑器模块
 * 基于 Monaco Editor 实现多语言代码编辑和语法高亮
 */

class WebIDEManager {
    constructor() {
        this.editor = null;
        this.currentLanguage = 'javascript';
        this.isInitialized = false;
        this.languages = {
            javascript: {
                name: 'JavaScript',
                extension: '.js',
                template: this.getJavaScriptTemplate()
            },
            typescript: {
                name: 'TypeScript', 
                extension: '.ts',
                template: this.getTypeScriptTemplate()
            },
            python: {
                name: 'Python',
                extension: '.py',
                template: this.getPythonTemplate()
            },
            java: {
                name: 'Java',
                extension: '.java',
                template: this.getJavaTemplate()
            },
            cpp: {
                name: 'C++',
                extension: '.cpp',
                template: this.getCppTemplate()
            },
            csharp: {
                name: 'C#',
                extension: '.cs',
                template: this.getCSharpTemplate()
            },
            go: {
                name: 'Go',
                extension: '.go',
                template: this.getGoTemplate()
            },
            rust: {
                name: 'Rust',
                extension: '.rs',
                template: this.getRustTemplate()
            },
            php: {
                name: 'PHP',
                extension: '.php',
                template: this.getPhpTemplate()
            },
            sql: {
                name: 'SQL',
                extension: '.sql',
                template: this.getSqlTemplate()
            },
            html: {
                name: 'HTML',
                extension: '.html',
                template: this.getHtmlTemplate()
            },
            css: {
                name: 'CSS',
                extension: '.css',
                template: this.getCssTemplate()
            }
        };
        
        this.editorSettings = {
            theme: 'vs-dark',
            fontSize: 14,
            fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
            lineNumbers: 'on',
            minimap: { enabled: true },
            automaticLayout: true,
            wordWrap: 'on',
            tabSize: 4,
            insertSpaces: true,
            folding: true,
            lineDecorationsWidth: 10,
            lineNumbersMinChars: 3,
            glyphMargin: false,
            scrollBeyondLastLine: false,
            roundedSelection: false,
            readOnly: false
        };
    }

    /**
     * 初始化IDE
     */
    async init() {
        try {
            console.log('🚀 初始化Web IDE...');
            
            // 等待Monaco Editor加载
            await this.loadMonacoEditor();
            
            // 初始化编辑器
            this.initializeEditor();
            
            // 绑定事件
            this.bindEvents();
            
            // 初始化语言选择器
            this.initializeLanguageSelector();
            
            // 初始化工具栏
            this.initializeToolbar();
            
            this.isInitialized = true;
            console.log('✅ Web IDE 初始化完成');
            
        } catch (error) {
            console.error('❌ Web IDE 初始化失败:', error);
            this.showError('IDE初始化失败: ' + error.message);
        }
    }

    /**
     * 加载Monaco Editor
     */
    async loadMonacoEditor() {
        return new Promise((resolve, reject) => {
            // 检查是否已经加载
            if (window.monaco) {
                console.log('✅ Monaco Editor 已加载');
                resolve();
                return;
            }

            // 动态加载Monaco Editor
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.min.js';
            script.onload = () => {
                require.config({ 
                    paths: { 
                        vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' 
                    }
                });
                
                require(['vs/editor/editor.main'], () => {
                    console.log('✅ Monaco Editor 加载完成');
                    resolve();
                });
            };
            script.onerror = () => {
                reject(new Error('无法加载Monaco Editor'));
            };
            
            document.head.appendChild(script);
        });
    }

    /**
     * 初始化编辑器
     */
    initializeEditor() {
        const editorContainer = document.getElementById('monaco-editor');
        if (!editorContainer) {
            throw new Error('找不到编辑器容器 #monaco-editor');
        }

        // 创建编辑器实例
        this.editor = monaco.editor.create(editorContainer, {
            value: this.languages[this.currentLanguage].template,
            language: this.currentLanguage,
            ...this.editorSettings
        });

        console.log('✅ Monaco Editor 实例创建完成');

        // 监听编辑器事件
        this.editor.onDidChangeCursorPosition((e) => {
            this.updateStatusBar({
                line: e.position.lineNumber,
                column: e.position.column
            });
        });

        this.editor.onDidChangeModelContent(() => {
            this.updateStatusBar({
                characters: this.editor.getValue().length,
                lines: this.editor.getModel().getLineCount()
            });
        });
    }

    /**
     * 初始化语言选择器
     */
    initializeLanguageSelector() {
        const languageSelect = document.getElementById('language-select');
        if (!languageSelect) {
            console.warn('⚠️ 未找到语言选择器 #language-select');
            return;
        }

        // 清空并填充选项
        languageSelect.innerHTML = '';
        
        Object.keys(this.languages).forEach(langKey => {
            const option = document.createElement('option');
            option.value = langKey;
            option.textContent = this.languages[langKey].name;
            if (langKey === this.currentLanguage) {
                option.selected = true;
            }
            languageSelect.appendChild(option);
        });

        // 绑定语言切换事件
        languageSelect.addEventListener('change', (e) => {
            this.changeLanguage(e.target.value);
        });

        console.log('✅ 语言选择器初始化完成');
    }

    /**
     * 初始化工具栏
     */
    initializeToolbar() {
        // 重置代码按钮
        const resetBtn = document.getElementById('reset-code');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetCode());
        }

        // 格式化代码按钮
        const formatBtn = document.getElementById('format-code');
        if (formatBtn) {
            formatBtn.addEventListener('click', () => this.formatCode());
        }

        // 全屏按钮
        const fullscreenBtn = document.getElementById('fullscreen-editor');
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        }

        // 设置按钮
        const settingsBtn = document.getElementById('editor-settings');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => this.showSettings());
        }

        console.log('✅ 工具栏初始化完成');
    }

    /**
     * 切换编程语言
     */
    changeLanguage(language) {
        if (!this.languages[language]) {
            console.error('❌ 不支持的语言:', language);
            return;
        }

        const previousLanguage = this.currentLanguage;
        this.currentLanguage = language;

        if (this.editor) {
            // 确认是否切换（如果有未保存的内容）
            const currentCode = this.editor.getValue();
            const isDefaultTemplate = currentCode === this.languages[previousLanguage].template;
            
            if (!isDefaultTemplate) {
                const confirmed = confirm('切换语言将替换当前代码内容，确定继续吗？');
                if (!confirmed) {
                    // 恢复语言选择器
                    const languageSelect = document.getElementById('language-select');
                    if (languageSelect) {
                        languageSelect.value = previousLanguage;
                    }
                    this.currentLanguage = previousLanguage;
                    return;
                }
            }

            // 更新编辑器语言和内容
            const model = this.editor.getModel();
            monaco.editor.setModelLanguage(model, language);
            this.editor.setValue(this.languages[language].template);
        }

        // 更新状态栏
        this.updateStatusBar({
            language: this.languages[language].name
        });

        console.log(`✅ 已切换到 ${this.languages[language].name}`);
        this.showSuccess(`已切换到 ${this.languages[language].name}`);
    }

    /**
     * 重置代码
     */
    resetCode() {
        if (!this.editor) return;

        const confirmed = confirm('确定要重置代码吗？这将清除所有修改。');
        if (confirmed) {
            this.editor.setValue(this.languages[this.currentLanguage].template);
            this.showSuccess('代码已重置');
        }
    }

    /**
     * 格式化代码
     */
    formatCode() {
        if (!this.editor) return;

        try {
            this.editor.getAction('editor.action.formatDocument').run();
            this.showSuccess('代码已格式化');
        } catch (error) {
            console.error('❌ 格式化失败:', error);
            this.showError('格式化失败');
        }
    }

    /**
     * 切换全屏模式
     */
    toggleFullscreen() {
        const codeMode = document.getElementById('code-mode');
        if (!codeMode) return;

        if (codeMode.classList.contains('fullscreen-mode')) {
            // 退出全屏
            codeMode.classList.remove('fullscreen-mode');
            this.showSuccess('已退出全屏模式');
        } else {
            // 进入全屏
            codeMode.classList.add('fullscreen-mode');
            this.showSuccess('已进入全屏模式');
        }

        // 刷新编辑器布局
        setTimeout(() => {
            if (this.editor) {
                this.editor.layout();
            }
        }, 100);
    }

    /**
     * 显示编辑器设置
     */
    showSettings() {
        const settingsModal = this.createSettingsModal();
        document.body.appendChild(settingsModal);
    }

    /**
     * 创建设置模态框
     */
    createSettingsModal() {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
                <div class="p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-gray-900">编辑器设置</h3>
                        <button class="close-modal text-gray-400 hover:text-gray-600">
                            <i class="ri-close-line text-xl"></i>
                        </button>
                    </div>
                    
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">主题</label>
                            <select id="theme-select" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
                                <option value="vs-dark">深色主题</option>
                                <option value="vs">浅色主题</option>
                                <option value="hc-black">高对比度</option>
                            </select>
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">字体大小</label>
                            <input type="range" id="font-size-range" min="12" max="24" value="${this.editorSettings.fontSize}" 
                                   class="w-full">
                            <div class="flex justify-between text-sm text-gray-500">
                                <span>12px</span>
                                <span id="font-size-display">${this.editorSettings.fontSize}px</span>
                                <span>24px</span>
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <label class="text-sm font-medium text-gray-700">显示小地图</label>
                            <input type="checkbox" id="minimap-toggle" ${this.editorSettings.minimap.enabled ? 'checked' : ''} 
                                   class="rounded">
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <label class="text-sm font-medium text-gray-700">自动换行</label>
                            <input type="checkbox" id="wordwrap-toggle" ${this.editorSettings.wordWrap === 'on' ? 'checked' : ''} 
                                   class="rounded">
                        </div>
                    </div>
                    
                    <div class="flex justify-end space-x-3 mt-6">
                        <button class="close-modal px-4 py-2 text-gray-600 hover:text-gray-900">取消</button>
                        <button id="apply-settings" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">应用</button>
                    </div>
                </div>
            </div>
        `;

        // 绑定事件
        this.bindSettingsEvents(modal);
        
        return modal;
    }

    /**
     * 绑定设置模态框事件
     */
    bindSettingsEvents(modal) {
        // 关闭模态框
        modal.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', () => modal.remove());
        });

        // 字体大小滑块
        const fontSizeRange = modal.querySelector('#font-size-range');
        const fontSizeDisplay = modal.querySelector('#font-size-display');
        fontSizeRange.addEventListener('input', (e) => {
            fontSizeDisplay.textContent = e.target.value + 'px';
        });

        // 应用设置
        modal.querySelector('#apply-settings').addEventListener('click', () => {
            this.applySettings(modal);
            modal.remove();
        });
    }

    /**
     * 应用编辑器设置
     */
    applySettings(modal) {
        const theme = modal.querySelector('#theme-select').value;
        const fontSize = parseInt(modal.querySelector('#font-size-range').value);
        const minimapEnabled = modal.querySelector('#minimap-toggle').checked;
        const wordWrap = modal.querySelector('#wordwrap-toggle').checked ? 'on' : 'off';

        // 更新设置
        this.editorSettings.theme = theme;
        this.editorSettings.fontSize = fontSize;
        this.editorSettings.minimap.enabled = minimapEnabled;
        this.editorSettings.wordWrap = wordWrap;

        // 应用到编辑器
        if (this.editor) {
            monaco.editor.setTheme(theme);
            this.editor.updateOptions({
                fontSize: fontSize,
                minimap: { enabled: minimapEnabled },
                wordWrap: wordWrap
            });
        }

        this.showSuccess('设置已应用');
    }

    /**
     * 更新状态栏
     */
    updateStatusBar(data) {
        if (data.language) {
            const langElement = document.getElementById('current-language');
            if (langElement) {
                langElement.textContent = data.language;
            }
        }

        if (data.line !== undefined && data.column !== undefined) {
            const positionElement = document.getElementById('cursor-position');
            if (positionElement) {
                positionElement.textContent = `行 ${data.line}, 列 ${data.column}`;
            }
        }

        if (data.characters !== undefined) {
            const charsElement = document.getElementById('character-count');
            if (charsElement) {
                charsElement.textContent = `字符: ${data.characters}`;
            }
        }

        if (data.lines !== undefined) {
            const linesElement = document.getElementById('line-count');
            if (linesElement) {
                linesElement.textContent = `行数: ${data.lines}`;
            }
        }
    }

    /**
     * 绑定全局事件
     */
    bindEvents() {
        // 窗口大小改变时重新调整编辑器
        window.addEventListener('resize', () => {
            if (this.editor) {
                this.editor.layout();
            }
        });

        // 快捷键
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key.toLowerCase()) {
                    case 's':
                        e.preventDefault();
                        this.saveCode();
                        break;
                    case 'r':
                        e.preventDefault();
                        this.resetCode();
                        break;
                    case 'f':
                        if (e.shiftKey) {
                            e.preventDefault();
                            this.formatCode();
                        }
                        break;
                }
            }
        });
    }

    /**
     * 保存代码（可以扩展为下载或云端保存）
     */
    saveCode() {
        if (!this.editor) return;

        const code = this.editor.getValue();
        const language = this.languages[this.currentLanguage];
        const filename = `code${language.extension}`;
        
        // 创建下载链接
        const blob = new Blob([code], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);

        this.showSuccess(`代码已保存为 ${filename}`);
    }

    /**
     * 获取当前代码
     */
    getCode() {
        return this.editor ? this.editor.getValue() : '';
    }

    /**
     * 设置代码内容
     */
    setCode(code) {
        if (this.editor) {
            this.editor.setValue(code);
        }
    }

    /**
     * 显示成功消息
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    /**
     * 显示错误消息
     */
    showError(message) {
        this.showNotification(message, 'error');
    }

    /**
     * 显示通知
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm max-w-sm ${
            type === 'success' ? 'bg-green-500' : 
            type === 'error' ? 'bg-red-500' : 'bg-blue-500'
        }`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // 3秒后自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }

    /**
     * 销毁编辑器
     */
    destroy() {
        if (this.editor) {
            this.editor.dispose();
            this.editor = null;
        }
        this.isInitialized = false;
        console.log('✅ Web IDE 已销毁');
    }

    // ==================== 语言模板 ====================

    getJavaScriptTemplate() {
        return `// JavaScript 算法解决方案
function solveProblem(input) {
    // 初始化结果数组
    const result = [];
    
    // 处理输入数据
    for (let i = 0; i < input.length; i++) {
        const current = input[i];
        if (isValid(current)) {
            result.push(current);
        }
    }
    
    return result;
}

// 辅助函数
function isValid(value) {
    return value !== null && value !== undefined;
}

// 测试用例
const testInput = [1, 2, null, 3, undefined, 4];
console.log(solveProblem(testInput));`;
    }

    getTypeScriptTemplate() {
        return `// TypeScript 算法解决方案
interface InputData {
    value: number;
    valid: boolean;
}

function solveProblem(input: number[]): number[] {
    const result: number[] = [];
    
    // 处理输入数据
    for (let i = 0; i < input.length; i++) {
        const current = input[i];
        if (isValid(current)) {
            result.push(current);
        }
    }
    
    return result;
}

function isValid(value: number): boolean {
    return value > 0 && Number.isFinite(value);
}

// 测试用例
const testInput: number[] = [1, 2, -1, 3, 0, 4];
console.log(solveProblem(testInput));`;
    }

    getPythonTemplate() {
        return `# Python 算法解决方案
def solve_problem(input_data):
    """
    解决算法问题的主函数
    
    Args:
        input_data: 输入数据
        
    Returns:
        处理后的结果
    """
    result = []
    
    # 处理输入数据
    for item in input_data:
        if is_valid(item):
            result.append(item)
    
    return result

def is_valid(value):
    """检查值是否有效"""
    return value is not None and value > 0

# 测试用例
if __name__ == "__main__":
    test_input = [1, 2, None, 3, 0, 4]
    print(solve_problem(test_input))`;
    }

    getJavaTemplate() {
        return `// Java 算法解决方案
import java.util.*;

public class Solution {
    
    public List<Integer> solveProblem(int[] input) {
        List<Integer> result = new ArrayList<>();
        
        // 处理输入数据
        for (int i = 0; i < input.length; i++) {
            if (isValid(input[i])) {
                result.add(input[i]);
            }
        }
        
        return result;
    }
    
    private boolean isValid(int value) {
        return value > 0;
    }
    
    public static void main(String[] args) {
        Solution solution = new Solution();
        int[] testInput = {1, 2, -1, 3, 0, 4};
        List<Integer> result = solution.solveProblem(testInput);
        System.out.println(result);
    }
}`;
    }

    getCppTemplate() {
        return `// C++ 算法解决方案
#include <iostream>
#include <vector>
#include <algorithm>

class Solution {
public:
    std::vector<int> solveProblem(const std::vector<int>& input) {
        std::vector<int> result;
        
        // 处理输入数据
        for (const auto& item : input) {
            if (isValid(item)) {
                result.push_back(item);
            }
        }
        
        return result;
    }
    
private:
    bool isValid(int value) const {
        return value > 0;
    }
};

int main() {
    Solution solution;
    std::vector<int> testInput = {1, 2, -1, 3, 0, 4};
    auto result = solution.solveProblem(testInput);
    
    for (const auto& item : result) {
        std::cout << item << " ";
    }
    std::cout << std::endl;
    
    return 0;
}`;
    }

    getCSharpTemplate() {
        return `// C# 算法解决方案
using System;
using System.Collections.Generic;
using System.Linq;

public class Solution 
{
    public List<int> SolveProblem(int[] input) 
    {
        var result = new List<int>();
        
        // 处理输入数据
        foreach (var item in input) 
        {
            if (IsValid(item)) 
            {
                result.Add(item);
            }
        }
        
        return result;
    }
    
    private bool IsValid(int value) 
    {
        return value > 0;
    }
    
    public static void Main(string[] args) 
    {
        var solution = new Solution();
        var testInput = new int[] {1, 2, -1, 3, 0, 4};
        var result = solution.SolveProblem(testInput);
        
        Console.WriteLine(string.Join(", ", result));
    }
}`;
    }

    getGoTemplate() {
        return `// Go 算法解决方案
package main

import (
    "fmt"
)

func solveProblem(input []int) []int {
    var result []int
    
    // 处理输入数据
    for _, item := range input {
        if isValid(item) {
            result = append(result, item)
        }
    }
    
    return result
}

func isValid(value int) bool {
    return value > 0
}

func main() {
    testInput := []int{1, 2, -1, 3, 0, 4}
    result := solveProblem(testInput)
    fmt.Println(result)
}`;
    }

    getRustTemplate() {
        return `// Rust 算法解决方案
fn solve_problem(input: &[i32]) -> Vec<i32> {
    let mut result = Vec::new();
    
    // 处理输入数据
    for &item in input {
        if is_valid(item) {
            result.push(item);
        }
    }
    
    result
}

fn is_valid(value: i32) -> bool {
    value > 0
}

fn main() {
    let test_input = vec![1, 2, -1, 3, 0, 4];
    let result = solve_problem(&test_input);
    println!("{:?}", result);
}`;
    }

    getPhpTemplate() {
        return `<?php
// PHP 算法解决方案

class Solution {
    
    public function solveProblem($input) {
        $result = [];
        
        // 处理输入数据
        foreach ($input as $item) {
            if ($this->isValid($item)) {
                $result[] = $item;
            }
        }
        
        return $result;
    }
    
    private function isValid($value) {
        return is_numeric($value) && $value > 0;
    }
}

// 测试用例
$solution = new Solution();
$testInput = [1, 2, -1, 3, 0, 4, "invalid"];
$result = $solution->solveProblem($testInput);
print_r($result);
?>`;
    }

    getSqlTemplate() {
        return `-- SQL 查询解决方案
-- 创建示例表
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    age INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入测试数据
INSERT INTO users (id, name, email, age) VALUES
(1, '张三', 'zhangsan@example.com', 25),
(2, '李四', 'lisi@example.com', 30),
(3, '王五', 'wangwu@example.com', 28);

-- 查询年龄大于25的用户
SELECT 
    id,
    name,
    email,
    age,
    YEAR(CURDATE()) - age AS birth_year
FROM users 
WHERE age > 25 
ORDER BY age DESC;

-- 统计用户数量
SELECT 
    COUNT(*) as total_users,
    AVG(age) as average_age,
    MIN(age) as min_age,
    MAX(age) as max_age
FROM users;`;
    }

    getHtmlTemplate() {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTML 示例页面</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        .header {
            text-align: center;
            color: #333;
        }
        .content {
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>欢迎来到我的网站</h1>
        <p>这是一个示例HTML页面</p>
    </div>
    
    <div class="content">
        <h2>关于我们</h2>
        <p>这里是页面内容...</p>
        
        <h2>联系方式</h2>
        <ul>
            <li>邮箱: contact@example.com</li>
            <li>电话: 123-456-7890</li>
        </ul>
    </div>
    
    <script>
        console.log('页面加载完成');
    </script>
</body>
</html>`;
    }

    getCssTemplate() {
        return `/* CSS 样式示例 */

/* 重置样式 */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

/* 基础样式 */
body {
    font-family: 'Arial', sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f4f4f4;
}

/* 容器样式 */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}

/* 标题样式 */
h1, h2, h3 {
    margin-bottom: 1rem;
    color: #2c3e50;
}

/* 按钮样式 */
.btn {
    display: inline-block;
    padding: 10px 20px;
    background-color: #3498db;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    transition: background-color 0.3s;
}

.btn:hover {
    background-color: #2980b9;
}

/* 卡片样式 */
.card {
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .container {
        padding: 0 10px;
    }
    
    .btn {
        display: block;
        text-align: center;
        margin: 10px 0;
    }
}`;
    }
}

// 创建全局实例
let webIDE = null;

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    webIDE = new WebIDEManager();
    
    // 暴露到全局作用域以便调试
    window.webIDE = webIDE;
    
    console.log('✅ Web IDE Manager 已加载');
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebIDEManager };
} else {
    window.WebIDEManager = WebIDEManager;
}
