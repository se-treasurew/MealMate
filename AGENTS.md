# Repository Guidelines

## 项目结构

- `backend/app/`：FastAPI 路由、SQLAlchemy 模型、Pydantic schema、安全与工具代码。
- `backend/tests/`：后端 `unittest` 测试；`backend/e2e_test.py` 和 `backend/run_e2e.py` 提供隔离 E2E。
- `frontend/src/`：Vue 页面、API 封装、Pinia store、composables 与公共组件；`frontend/public/` 保存 PWA 图标和预设头像。
- `scripts/`：发布树扫描和静态回归测试；`docker/`：Caddy 等部署配置。

## 构建、测试与开发

后端（Python 3.13）：

```bash
cd backend
python -m unittest discover -s tests -v
python run_e2e.py
python -m app.init_db
python -m app.migrate
```

前端（Node 22）：

```bash
cd frontend
npm ci
npm run dev
npm run build
```

发布前在仓库根目录运行 `python -m unittest discover -s scripts -p 'test_*.py' -v`、`python scripts/check_release_tree.py --mode worktree --check-dist`、`git diff --check` 和 `docker compose config`。

## 编码规范

Python 使用 4 个空格和 `snake_case`；TypeScript/Vue 使用 2 个空格、单引号、无分号，变量和函数采用 `camelCase`，Vue 组件采用 `PascalCase`。项目未配置统一格式化器，请保持相邻代码风格并避免无关重排。

## 测试规范

测试文件命名为 `test_*.py`，测试方法命名为 `test_<behavior>`；异步测试使用 `IsolatedAsyncioTestCase`。E2E 必须使用临时数据库、上传目录和随机账号，不得清理生产数据。认证、上传、订单状态或部署改动必须补充回归测试。

## 提交与 PR

提交信息使用简短中文动词开头，例如“修复登录超时”“新增菜品评价”“优化页面布局”。PR 需说明变更目的、测试命令及结果；界面变化附截图，并说明安全、配置、数据库迁移和回滚影响，必要时关联 issue。

## 安全与配置

禁止提交 `.env`、PEM 私钥、SQLite 数据库、`backend/uploads/`、依赖目录和构建产物，仅提交 `.env.example`。认证、上传和 VAPID 密钥通过环境变量或仓库外只读文件提供；修改发布配置后必须重新运行发布树扫描。
