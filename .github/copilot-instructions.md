# MealMate（饭饭之交）— AI 编码代理指南

家庭私有部署的移动端点餐 PWA。FastAPI + SQLAlchemy 异步 + SQLite 后端，Vue 3 + TypeScript + Vite + Vant 4 前端。

> 注意：根目录 `AGENTS.md` 是公开贡献指南；本文件补充 AI 编码代理的详细约束、权限边界和发布门禁。修改二者时保持规则一致。

## 文档导航（先读这些，不要重复其内容）

- [README.md](../../README.md)：本地启动、环境变量、Docker 部署、权限矩阵。
- [PRD.md](../../PRD.md)：完整产品需求、API 契约、订单状态机、安全与发布验收标准。
- [SECURITY.md](../../SECURITY.md)：漏洞报告流程与安全要求。

## 常用命令

```bash
# 后端单元测试（在 backend/ 下，Python 3.13）
python -m unittest discover -s tests -v

# 隔离 E2E 测试（临时数据库/上传目录/随机端口，90+ 项断言）
python run_e2e.py

# 数据库初始化 / 迁移（在 backend/ 下）
python -m app.init_db
python -m app.migrate

# 前端（Node 22，在 frontend/ 下）
npm ci
npm run dev      # http://localhost:3000，Vite 代理 /api 和 /uploads 到 :8000
npm run build    # vue-tsc -b && vite build，类型错误会阻断构建

# 发布树扫描
python scripts/check_release_tree.py
```

## 关键约束与陷阱

- **Python 版本**：必须用 Python 3.13，不要用 3.14（二进制依赖不保证兼容）。
- **`app.migrate` 不是 Alembic**：只幂等补表和补列；改列/删列/数据重构需要专用迁移方案。绝不能通过删库重建来"迁移"。
- **订单状态机严格前向**：`pending -> accepted -> cooking -> done`。禁止跳级、回退、重开。只有订单本人可把自己的 `pending` 订单改为 `cancelled`，饲养员不能代取消。
- **令牌版本机制**：改密、店长重置密码、禁用账号都会递增 `token_version` 使旧令牌失效。JWT payload 含 `ver` 字段，校验逻辑在 `app/core/deps.py`。
- **图片上传管线**：仅 `.jpg/.jpeg/.png/.webp`，最大 5 MiB，必须解码验证真实格式与扩展名匹配，统一转 WebP 并生成 200x200 缩略图，失败时不得落盘。逻辑在 `app/utils/image.py`。
- **Markdown 渲染**：前端输出必须经 DOMPurify 清理（见 `frontend/src/utils/markdown.ts`）。
- **同源约定**：前端默认同源 `/api` 和 `/uploads`，`VITE_API_BASE_URL` 仅跨源部署时设置。生产构建产物不得包含 `localhost:8000`。
- **PWA 更新**：SW 用 `injectManifest` 自定义（`frontend/src/sw.ts`）；新版本由用户确认后刷新。`index.html`、`sw.js`、manifest 禁止长期缓存。
- **推送已停用**：`/api/push` 仅保留无数据库、无外部网络访问的旧客户端兼容响应；不得恢复真实推送而影响订单事务。

## 项目结构

- `backend/app/routers/`：按资源划分的 FastAPI 路由（auth/users/categories/tags/dishes/orders/push/config）。
- `backend/app/models/`：SQLAlchemy 2.0 异步模型；多对多关联在 `association.py`。
- `backend/app/schemas/`：Pydantic 请求/响应模式。
- `backend/tests/`：unittest 风格单元测试（不是 pytest）。
- `backend/e2e_test.py` + `run_e2e.py`：闭环 E2E，需要环境变量 `E2E_ADMIN_PASSWORD`（`run_e2e.py` 会自动生成）。
- `frontend/src/views/`：页面组件；`stores/` Pinia；`api/` axios 封装。
- `backend/data/` 与 `backend/uploads/` 是运行数据，不属于源码发布物。

## 角色与权限

三种角色：店长（唯一管理员）、饲养员（菜单与订单管理）、饭团（点餐）。游客可浏览上架菜品和使用本地购物车但不能下单。修改任何接口的访问范围前，先核对 PRD 第 3 节和第 5 节的权限矩阵。

## 发布门禁

改动涉及安全、上传、认证或部署时，需确认：单元测试、隔离 E2E、`npm run build`、`docker compose config`、发布树扫描均通过。`.env`、PEM、SQLite、上传目录、构建目录不得进入发布树（见 `scripts/check_release_tree.py` 的黑名单）。
