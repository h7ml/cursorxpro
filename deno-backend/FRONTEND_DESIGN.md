# CursorX Pro - 奢华前端设计

## 🎨 设计理念

CursorX Pro 采用**奢华精致**的设计语言，强调**排他性**和**高端体验**。

### 核心设计元素

1. **液态玻璃效果 (Glassmorphism)**
   - 半透明背景
   - 20px 模糊效果
   - 180% 饱和度增强
   - 微妙的边框和阴影

2. **柔和粉彩色调**
   - 粉色 (#f093fb)
   - 紫色 (#c084fc)
   - 蓝色 (#93c5fd)
   - 渐变过渡动画

3. **流畅动画**
   - 15秒渐变背景循环
   - 悬浮提升效果
   - 平滑的主题切换
   - 淡入动画

4. **暗黑模式支持**
   - 自动保存用户偏好
   - 平滑过渡动画
   - 优化的对比度

## 📁 文件结构

```
deno-backend/
├── index.html      # 奢华落地页
├── admin.html      # 管理后台（奢华版）
├── main.ts         # 后端路由（已更新）
└── FRONTEND_DESIGN.md  # 本文档
```

## 🎯 页面说明

### 首页 (index.html)

**访问**: `http://localhost:8000/` 或 `http://localhost:8000/index.html`

**特性**:
- Hero 区域带动画渐变背景
- 产品特性展示（6个玻璃卡片）
- 定价区域
- 响应式设计
- 暗黑模式切换

**设计亮点**:
- 渐变文字标题
- 发光按钮效果
- 悬浮卡片动画
- 平滑滚动

### 管理后台 (admin.html)

**访问**: `http://localhost:8000/admin`

**特性**:
- 统计卡片（5个指标）
- 票据管理表格
- 使用记录查询
- 批量操作
- 暗黑模式支持

**设计亮点**:
- 玻璃拟态卡片
- 渐变按钮
- 状态徽章
- 优雅的表格设计
- 浮动主题切换按钮

## 🎨 设计系统

### 色彩变量

```css
/* Light Mode */
--bg-primary: #fef6fb;
--text-primary: #2d1b2e;
--accent-pink: #f093fb;
--accent-purple: #c084fc;
--accent-blue: #93c5fd;

/* Dark Mode */
--bg-primary: #1a0f1e;
--text-primary: #f5e6f7;
```

### 渐变

```css
--gradient-1: linear-gradient(135deg, #ffd1dc 0%, #e0c3fc 50%, #c3e0fc 100%);
--gradient-accent: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
```

### 玻璃效果

```css
background: rgba(255, 255, 255, 0.7);
backdrop-filter: blur(20px) saturate(180%);
border: 1px solid rgba(255, 255, 255, 0.18);
box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
```

### 动画

```css
/* 渐变背景动画 */
@keyframes gradientShift {
  0%, 100% { background: var(--gradient-1); }
  33% { background: var(--gradient-2); }
  66% { background: var(--gradient-3); }
}

/* 淡入动画 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

## 🚀 使用方法

### 启动服务器

```bash
cd deno-backend
deno run --allow-net --allow-read --allow-env --unstable-kv main.ts
```

### 访问页面

- **首页**: http://localhost:8000/
- **管理后台**: http://localhost:8000/admin

### 主题切换

点击右下角的浮动按钮（🌙/☀️）切换暗黑/明亮模式。

## 📱 响应式设计

### 断点

- **Desktop**: > 768px
- **Mobile**: ≤ 768px

### 移动端优化

- 堆叠布局
- 全宽按钮
- 隐藏次要表格列
- 触摸友好的间距

## ✨ 交互细节

### 悬浮效果

- 卡片: `translateY(-4px)` + 阴影增强
- 按钮: `translateY(-2px)` + 发光效果
- 主题切换: `scale(1.1)` + `rotate(15deg)`

### 过渡时间

- 快速: 150ms (微交互)
- 正常: 250ms (常规过渡)
- 慢速: 400ms (复杂动画)

### 缓动函数

```css
transition: all 0.3s ease;
```

## 🎯 设计目标达成

✅ **液态玻璃效果** - 所有卡片使用 glassmorphism
✅ **高端产品展示** - Hero 区域 + 特性卡片
✅ **精致和排他性** - 渐变、发光、优雅动画
✅ **柔和粉彩色** - 粉色/紫色/蓝色渐变
✅ **舒缓美感** - 平滑动画、柔和过渡
✅ **暗黑模式** - 完整支持，自动保存偏好

## 🔧 自定义

### 修改主色调

编辑 CSS 变量：

```css
:root {
  --accent-pink: #your-color;
  --gradient-accent: linear-gradient(135deg, #color1, #color2);
}
```

### 调整玻璃效果

```css
.glass-card {
  backdrop-filter: blur(20px) saturate(180%);
  /* 调整模糊度和饱和度 */
}
```

### 修改动画速度

```css
.bg-gradient {
  animation: gradientShift 15s ease infinite;
  /* 调整秒数 */
}
```

## 📝 技术栈

- **HTML5** - 语义化标签
- **CSS3** - 变量、渐变、动画、backdrop-filter
- **Vanilla JavaScript** - 无框架依赖
- **Deno** - 后端服务器

## 🎨 设计灵感

- Apple 产品页面的精致感
- Stripe 的玻璃拟态设计
- Vercel 的渐变美学
- Dribbble 上的高端 UI 设计

## 📄 许可

本设计系统为 CursorX Pro 项目专用。
