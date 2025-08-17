/**
 * 批量更新脚本 - 将所有页面更新为使用导航栏组件
 * 
 * 使用方法：
 * 1. 在 frontend 目录下运行：node components/update-all-pages.js
 * 2. 或者手动按照这个脚本的逻辑更新各个页面
 */

const fs = require('fs');
const path = require('path');

// 需要更新的HTML文件列表
const htmlFiles = [
    'assessment-options.html'

];

// 导航栏的HTML模式（用于识别和替换）
const navbarPatterns = [
    // 模式1：完整的导航栏结构
    /<div class="bg-white shadow-sm">[\s\S]*?<\/div>\s*<\/div>\s*<\/div>/,
    // 模式2：顶部导航栏注释开始到结构结束
    /<!-- 顶部导航栏 -->[\s\S]*?<\/div>\s*<\/div>\s*<\/div>/,
    // 模式3：用户信息脚本
    /<script[^>]*>\s*document\.addEventListener\('DOMContentLoaded'[\s\S]*?fetchAndShowUserInfo[\s\S]*?<\/script>/,
    // 模式4：用户信息加载脚本
    /<script[^>]*id="user-info-loader"[\s\S]*?<\/script>/
];

// 替换后的内容
const navbarReplacement = `<!-- 导航栏容器 - 组件会自动插入到这里 -->
    <div id="navbar-container"></div>`;

const scriptReplacement = `    <!-- 导入导航栏组件 -->
    <script src="./components/navbar.js"></script>`;

/**
 * 更新单个HTML文件
 */
function updateHtmlFile(filename) {
    const filepath = path.join(__dirname, '..', filename);
    
    if (!fs.existsSync(filepath)) {
        console.log(`⚠️  文件不存在: ${filename}`);
        return;
    }

    try {
        let content = fs.readFileSync(filepath, 'utf8');
        let modified = false;

        console.log(`🔍 检查文件: ${filename}`);

        // 1. 替换导航栏HTML结构
        navbarPatterns.forEach((pattern, index) => {
            if (pattern.test(content)) {
                content = content.replace(pattern, navbarReplacement);
                modified = true;
                console.log(`   ✅ 替换了导航栏模式 ${index + 1}`);
            }
        });

        // 2. 添加导航栏组件脚本（如果还没有）
        if (!content.includes('./components/navbar.js')) {
            // 在 </body> 标签前插入脚本
            content = content.replace('</body>', `${scriptReplacement}
</body>`);
            modified = true;
            console.log(`   ✅ 添加了导航栏组件脚本`);
        }

        // 3. 保存文件
        if (modified) {
            // 创建备份
            fs.writeFileSync(`${filepath}.backup`, fs.readFileSync(filepath));
            fs.writeFileSync(filepath, content);
            console.log(`   💾 文件已更新并创建备份`);
        } else {
            console.log(`   ℹ️  文件无需更新`);
        }

    } catch (error) {
        console.error(`❌ 更新文件 ${filename} 失败:`, error.message);
    }

    console.log(''); // 空行分隔
}

/**
 * 主函数
 */
function main() {
    console.log('🚀 开始批量更新HTML文件以使用导航栏组件...\n');
    
    // 检查组件文件是否存在
    const navbarComponentPath = path.join(__dirname, 'navbar.js');
    if (!fs.existsSync(navbarComponentPath)) {
        console.error('❌ 导航栏组件文件不存在: components/navbar.js');
        console.log('请先确保导航栏组件文件存在。');
        return;
    }

    console.log('✅ 导航栏组件文件存在\n');

    // 更新每个HTML文件
    htmlFiles.forEach(updateHtmlFile);

    console.log('🎉 批量更新完成！\n');
    console.log('📝 更新说明：');
    console.log('   1. 原文件已备份为 .backup 扩展名');
    console.log('   2. 导航栏HTML结构已替换为组件容器');
    console.log('   3. 已添加导航栏组件脚本引用');
    console.log('   4. 如有问题，可从备份文件恢复\n');
    
    console.log('🔧 手动检查建议：');
    console.log('   - 检查页面是否正常显示导航栏');
    console.log('   - 检查用户信息是否正确加载');
    console.log('   - 检查当前页面是否正确高亮');
    console.log('   - 测试用户下拉菜单和退出登录功能');
}

// 如果直接运行此脚本
if (require.main === module) {
    main();
}

module.exports = {
    updateHtmlFile,
    htmlFiles,
    navbarPatterns,
    navbarReplacement,
    scriptReplacement
};
