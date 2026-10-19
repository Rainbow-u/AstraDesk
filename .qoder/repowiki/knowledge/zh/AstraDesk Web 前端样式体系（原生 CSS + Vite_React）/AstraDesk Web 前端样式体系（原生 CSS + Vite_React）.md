---
kind: frontend_style
name: AstraDesk Web 前端样式体系（原生 CSS + Vite/React）
category: frontend_style
scope:
    - '**'
source_files:
    - apps/web/src/styles.css
    - apps/web/src/App.tsx
    - apps/web/package.json
    - apps/web/vite.config.ts
---

## 1. 使用的系统与工具

- **框架**：React 18 + TypeScript，通过 `@vitejs/plugin-react` 在 Vite 5 中编译。
- **构建与开发服务器**：Vite (`apps/web/vite.config.ts`)，dev server 监听 5173 端口，并将 `/api` 代理到后端 FastAPI（默认 `http://127.0.0.1:8000`，可通过 `VITE_API_TARGET` 环境变量覆盖）。
- **样式方案**：纯 CSS（无 Sass/Less、无 Tailwind、无 CSS-in-JS 库），所有样式集中在 `apps/web/src/styles.css`，由 React 组件通过 `className` 引用。
- **设计系统**：无外部 UI 组件库，无 design tokens 文件，主题以 CSS `:root` 变量和硬编码色值定义。

## 2. 关键文件

- `apps/web/src/styles.css` — 唯一的全局样式表，包含暗色主题、布局与检测框等全部视觉规则。
- `apps/web/src/App.tsx` — 单页应用入口，使用内联 `style` 动态设置检测框位置与颜色，配合 `styles.css` 中的静态类。
- `apps/web/package.json` — 声明依赖：仅 `react` / `react-dom` 运行时，以及 `vite` / `typescript` / `@vitejs/plugin-react` 开发依赖。
- `apps/web/vite.config.ts` — 配置 React 插件与 API 代理。
- `apps/web/index.html` — 入口 HTML（由 Vite 加载 `src/main.tsx`）。

## 3. 架构与约定

### 3.1 主题与色彩
- 通过 `:root { color-scheme: dark; }` 启用浏览器原生暗色模式。
- 全局背景 `#12151c`，正文色 `#e6e8ee`，辅助文字 `#9aa3b2`，面板背景 `#171b24`，画布背景 `#0b0d12`。
- 错误/标注边框统一使用 `#ff5050`，成功/置信点使用 `#3ecf8e`，蓝色 `#4aa3ff`，紫色 `#c07bff`，粉色 `#ff7ad9`，黄色 `#ffb020`。
- 检测框颜色由 `App.tsx` 中的常量数组 `BOX_COLORS = ["#ff5050", "#ffb020", "#3ecf8e", "#4aa3ff", "#c07bff", "#ff7ad9"]` 循环分配，按检测结果索引取模。

### 3.2 字体与排版
- 字体栈：`system-ui, -apple-system, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif`，优先系统字体并回退到微软雅黑。
- 字号层级：`h1` 20px，`.panel h2` 15px，正文/列表项 13px，提示 `.hint` 13px，标签 `.tag` 11px，元信息 `.meta` 12px。
- 数字列对齐使用 `font-variant-numeric: tabular-nums`（`.conf`）。

### 3.3 布局策略
- 页面容器 `.page` 最大宽度 1100px，水平居中，左右 padding 20px。
- 主区域采用 CSS Grid `.stage { grid-template-columns: 1fr 280px; gap: 16px; }`，左侧自适应画布，右侧固定 280px 侧边栏。
- 顶部 `header` 使用 Flexbox，`justify-content: space-between`，支持 `flex-wrap: wrap` 的响应式换行。
- 工具栏 `.toolbar` 同样为 Flexbox，元素间 `gap: 12px`。
- 画布 `.canvas` 使用 `position: relative`，内部检测框 `.box` 与标签 `.tag` 使用绝对定位，尺寸通过百分比（基于父图宽高）计算。

### 3.4 组件化约定
- 样式类名采用小写短横线命名（kebab-case）：`.page`、`.toolbar`、`.stage`、`.canvas`、`.panel`、`.placeholder`、`.error`、`.box`、`.tag`、`.dot`、`.conf`、`.caps`、`.meta`。
- 组件状态通过条件渲染的 class 区分：`.error` 显示错误块，`.placeholder` 显示空态提示。
- 动态样式（检测框坐标、颜色、置信度数值）通过 React 的 `style={{ ... }}` 内联注入，静态样式则放在 `styles.css`。

### 3.5 响应式策略
- 未引入媒体查询或断点；主要依赖 Flexbox 的 `flex-wrap` 与 Grid 的 `1fr` 自适应列宽实现基础适配。
- 画布图片通过 `width: 100%` 自适应容器宽度。

## 4. 约定与约束

- **样式组织**：所有样式集中于单一 `styles.css` 文件，无模块化 CSS（无 CSS Modules、无 SCSS、无 Tailwind），无组件级样式文件。
- **主题来源**：无外部主题包（如 Ant Design、Material UI），无 design tokens 配置文件；主题色以硬编码十六进制值散布在 `styles.css` 与 `App.tsx` 中。
- **CSS 方法论**：采用扁平 BEM 风格（仅使用类选择器，无嵌套、无前缀），无 CSS 预处理器。
- **构建产物**：Vite 构建输出至 `apps/web/dist`，生产构建流程为 `tsc && vite build`。
- **开发环境**：前端 dev server 固定端口 5173，通过 Vite proxy 将 `/api` 转发到后端，避免跨域问题。
- **无额外样式工具链**：`package.json` 中未发现 postcss、sass、tailwindcss、styled-components 等任何样式相关依赖。