# 职面星火 - 导航栏组件使用说明

## 📖 概述

为了提高代码的可维护性和一致性，我们将导航栏提取为一个独立的组件。现在您只需要一次修改，就可以应用到所有使用该组件的页面中。

## 🗂️ 文件结构

```
frontend/components/
├── navbar.js              # 导航栏组件主文件
├── navbar-template.html   # 使用组件的HTML模板示例
└── README.md              # 本说明文档
```

## 🚀 快速开始

### 1. 在新页面中使用组件

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <!-- 页面头部内容 -->
    <title>您的页面标题 - 职面星火</title>
    <!-- Tailwind CSS 和其他样式 -->
    <script src="https://cdn.tailwindcss.com/3.4.16"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/remixicon/4.6.0/remixicon.min.css">
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- 导航栏容器 - 组件会自动插入到这里 -->
    <div id="navbar-container"></div>
    
    <!-- 您的页面内容 -->
    <main class="container mx-auto px-4 py-8">
        <h1>页面内容</h1>
    </main>

    <!-- 在页面底部引入导航栏组件 -->
    <script src="./components/navbar.js"></script>
</body>
</html>
```

### 2. 修改现有页面

将现有页面的导航栏部分：

```html
<!-- 删除这部分 -->
<div class="bg-white shadow-sm">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between items-center h-16">
      <!-- 原有的导航栏内容 -->
    </div>
  </div>
</div>
```

替换为：

```html
<!-- 导航栏容器 - 组件会自动插入到这里 -->
<div id="navbar-container"></div>
```

并在页面底部添加脚本引用：

```html
<!-- 导入导航栏组件 -->
<script src="./components/navbar.js"></script>
```

## 🔧 组件功能

### 自动功能

- ✅ **用户认证检查**: 自动检查用户登录状态
- ✅ **用户信息获取**: 自动获取并显示用户信息
- ✅ **当前页面高亮**: 根据当前页面自动高亮对应导航项
- ✅ **用户下拉菜单**: 提供个人设置、简历管理、退出登录等功能
- ✅ **响应式设计**: 适配不同屏幕尺寸

### 导航项目

- 🏠 **首页** (`../index.html`)
- 🎥 **面试模拟** (`./setting_page1.html`)
- 📊 **能力评估** (`./assessment-options.html`)
- 📚 **学习资源** (`./learning-resources.html`)
- ⚙️ **个人中心** (`./user-profile.html`)

## 🎨 页面类型识别

组件会根据页面文件名自动识别当前页面类型：

| 页面类型 | 匹配规则 | 高亮导航项 |
|---------|----------|-----------|
| 首页 | `index.html` | 首页 |
| 面试模拟 | 包含 `setting_page`、`interview` | 面试模拟 |
| 能力评估 | 包含 `assessment`、`logical`、`communication` | 能力评估 |
| 学习资源 | 包含 `learning`、`course` | 学习资源 |
| 个人中心 | 包含 `user-profile`、`Resume`、`career` | 个人中心 |

## ⚙️ 高级用法

### 手动更新用户信息

```javascript
// 在页面中调用
if (window.NavbarComponent) {
    // 获取组件实例并更新用户信息
    const navbarInstance = window.NavbarComponent.init();
    navbarInstance.updateUserInfo();
}
```

### 自定义用户下拉菜单

如果需要自定义用户下拉菜单，可以修改 `navbar.js` 中的 `renderUserInfo()` 方法。

## 🔄 已更新的页面

以下页面已经更新为使用导航栏组件：

- ✅ `resume_management.html`
- ✅ `assessment-options.html`
- ✅ `communication-assessment.html`

## 📝 待更新页面

建议将以下页面也更新为使用组件：

- ⏳ `user-profile.html`
- ⏳ `setting_page1.html`
- ⏳ `learning-resources.html`
- ⏳ `careerPlaning.html`
- ⏳ 其他包含导航栏的页面

## 🎯 组件优势

1. **一致性**: 所有页面使用相同的导航栏，确保用户体验一致
2. **可维护性**: 只需修改一个文件，所有页面自动更新
3. **自动化**: 用户认证、信息获取、页面高亮等功能全自动
4. **灵活性**: 支持不同页面类型的自动识别和高亮
5. **功能完整**: 包含用户下拉菜单、退出登录等完整功能

## 🚨 注意事项

1. **文件路径**: 确保脚本引用路径正确：`./components/navbar.js`
2. **依赖项**: 需要 Tailwind CSS 和 RemixIcon
3. **API 接口**: 组件依赖 `/api/v1/profile` 接口获取用户信息
4. **容器元素**: 需要有 `id="navbar-container"` 的容器元素
5. **登录状态**: 组件会自动检查登录状态，未登录用户会跳转到登录页面

## 🛠️ 故障排除

### 导航栏不显示

1. 检查是否有 `id="navbar-container"` 的容器元素
2. 检查脚本路径是否正确
3. 检查浏览器控制台是否有错误信息

### 用户信息显示异常

1. 检查网络请求是否正常
2. 检查 localStorage 中是否有有效的 access_token
3. 检查 API 接口是否正常响应

### 页面高亮不正确

组件根据文件名自动识别页面类型，如果高亮不正确，可以修改 `getCurrentPage()` 方法中的匹配规则。

## 🔮 未来计划

- 🎨 支持主题切换
- 📱 改进移动端体验
- 🌐 支持多语言
- ⚡ 性能优化和缓存机制
