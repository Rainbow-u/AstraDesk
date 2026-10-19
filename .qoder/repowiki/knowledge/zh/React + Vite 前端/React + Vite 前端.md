---
kind: external_dependency
name: React + Vite 前端
slug: react-vite
category: external_dependency
category_hints:
    - framework_behavior
scope:
    - '**'
source_files:
    - apps/web/package.json
    - apps/web/vite.config.ts
---

### 桌面预览前端
- 依赖声明于 `apps/web/package.json`：React 18.3、Vite 5.4、TypeScript 5.5、@vitejs/plugin-react 4.3。
- 构建命令 `npm run build`（tsc + vite build），开发命令 `npm run dev`（默认 5173，实测被占用切 5174）。
- 通过 Vite dev server 的同源 `/api` 代理转发到 WSL 后端 8000 端口，无需 CORS。