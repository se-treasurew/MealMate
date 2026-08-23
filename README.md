# 饭饭之交（MealMate）

面向家庭私有部署的移动端点餐 PWA。饭团可浏览菜品并下单，饲养员处理菜单和订单，店长负责成员与系统配置。v1.0 已覆盖 90+ 项在临时数据库、临时上传目录和随机端口中运行的隔离端到端测试。

## 技术栈与运行环境

- 后端：Python 3.13、FastAPI、SQLAlchemy 2.0 异步 ORM、aiosqlite、SQLite、JWT、Pillow。
- 前端：Node.js 22、Vue 3、TypeScript、Vite、Vant 4、Pinia、Vue Router、vite-plugin-pwa。
- 部署：Docker Compose、Nginx、Caddy；生产前端默认通过同源 `/api` 和 `/uploads` 访问后端。

推荐使用 Python 3.13 和 Node.js 22 进行本地开发与发布验证。不要使用 Python 3.14：当前锁定的部分二进制依赖不保证兼容。

## 本地启动

### 后端

```bash
cd backend
python -m venv venv
```

激活虚拟环境：

```powershell
# Windows PowerShell
venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source venv/bin/activate
```

安装依赖并准备配置：

```bash
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 可使用 `Copy-Item .env.example .env`。编辑 `.env`，至少为以下两项设置部署专用值：

```env
JWT_SECRET=使用密码管理器生成的高熵随机值
ADMIN_INITIAL_PASSWORD=仅用于首次登录的临时强密码
```

`ADMIN_INITIAL_PASSWORD` 没有内置默认值，缺失或少于 6 位时初始化会失败。初始化创建用户名为 `admin` 的店长账号，并强制首次登录后修改密码；不要把初始化密码长期使用或写入仓库。

```bash
python -m app.init_db
uvicorn app.main:app --reload
```

开发 API 默认为 `http://localhost:8000`，交互文档位于 `/docs`。

### 前端

```bash
cd frontend
npm ci
npm run dev
```

开发服务器默认为 `http://localhost:3000`。未设置 `VITE_API_BASE_URL` 时，前端使用同源地址；本地开发由 Vite 把 `/api` 和 `/uploads` 代理到 `localhost:8000`。只有前后端确实跨源部署时才在构建前设置 `VITE_API_BASE_URL`。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:///./data/mealmate.db` | SQLAlchemy 异步 SQLite URL |
| `JWT_SECRET` | 是 | 无 | Access/Refresh Token 签名密钥 |
| `ADMIN_INITIAL_PASSWORD` | 初始化时是 | 无 | `admin` 首次登录临时密码，首次登录必须修改 |
| `JWT_ALGORITHM` | 否 | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `120` | Access Token 有效期 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 否 | `7` | Refresh Token 有效期 |
| `UPLOAD_DIR` | 否 | `uploads` | 菜品图片和自定义头像目录 |
| `CORS_ORIGINS` | 否 | 本地 `3000` 来源 | 逗号分隔的精确允许来源；生产环境必须改为实际站点来源 |
| `VITE_API_BASE_URL` | 否 | 空（同源） | 前端构建期 API/上传基础地址 |

## 数据库初始化与迁移

- 新部署：在 `backend` 目录运行 `python -m app.init_db`，创建表、初始店长、预设分类、标签和角色显示名称。
- 现有部署：先备份 SQLite 数据库与上传目录，再运行 `python -m app.migrate`。该脚本会幂等创建缺失表，并补充 v1.0 已定义的新增列。
- `app.migrate` 不是通用 Alembic 迁移链，不能自动处理任意改列、删列或数据重构；遇到这类升级必须使用对应版本提供的专用迁移方案。
- 不要在有数据的环境通过删除数据库后重新初始化来代替迁移。

## Docker 部署

先设置密钥，再验证 Compose 配置并构建启动：

```bash
export JWT_SECRET='替换为高熵随机值'
export ADMIN_INITIAL_PASSWORD='替换为首次登录临时强密码'
docker compose config
docker compose up -d --build
docker compose exec backend python -m app.init_db
```

PowerShell 使用 `$env:JWT_SECRET='...'` 和 `$env:ADMIN_INITIAL_PASSWORD='...'`。生产 HTTPS 部署需按实际域名调整 `docker/Caddyfile`；当前默认配置提供 HTTP 同源反向代理，适合本地验证，不应原样暴露到公网。

SQLite 数据保存在 `backend/data/`，上传内容保存在 `backend/uploads/`。两者均为运行数据，不进入发布树，部署者必须同时备份。Web Push 已停用，不需要配置 VAPID，也不依赖 FCM 网络连通性；订单状态请在订单页查看。

前端发布新版本时，只需重新构建 frontend 服务：

```bash
docker compose up -d --build --no-deps frontend
```

PWA 会在后台检测并安装新版本，页面随后显示“发现新版本”。用户点击“立即更新”后才刷新页面；点击“稍后”不会丢失当前订单、购物车或登录状态，也不需要清除浏览器缓存。个人中心的“检查更新”可主动触发检测。反向代理必须沿用 `frontend/nginx.conf` 的缓存策略：`index.html`、`sw.js`、清单和图标禁止长期缓存，带内容哈希的 `/assets/` 文件才使用长期缓存。

## 权限与关键业务规则

| 身份 | 能力 |
| --- | --- |
| 店长 | 唯一管理员；管理成员、启停账号、重置密码、配置角色显示名，并拥有饲养员能力 |
| 饲养员 | 管理分类、标签、菜品和图片；查看全部订单并按严格状态机处理 |
| 饭团 | 浏览上架菜品、管理本地购物车、提交订单、查看并取消本人待处理订单 |
| 游客 | 仅浏览上架菜品、分类、标签和菜品详情，可使用本地购物车；提交订单和查看订单前必须登录 |

订单只允许按 `pending -> accepted -> cooking -> done` 前进，禁止跳级、回退、重复流转或重开终态订单。只有订单本人可在 `pending` 状态取消；饲养员和店长不能代为取消，`accepted` 后也不存在取消请求流程。

## 认证与会话

- `POST /api/auth/refresh` 只接受 JSON 请求体：`{"refresh_token":"..."}`，不兼容查询参数。
- 修改密码成功后，接口直接返回新的 Access Token 与 Refresh Token；前端立即替换本地令牌。
- JWT 包含用户当前 `token_version`。改密、店长重置密码或账号被禁用会提升版本，使旧 Access/Refresh Token 失效；被禁用账号也无法继续使用旧令牌。
- 首次登录和店长重置密码后，用户被限制到个人资料页完成改密。
- v1.0 已移除免密多账号切换，启动时会清理旧版 `mealmate_accounts` 数据；每个浏览器上下文只维护当前登录会话。

## 图片与头像约束

- 每个上传文件最大 5 MiB，仅接受 `.jpg`、`.jpeg`、`.png`、`.webp`，并校验扩展名与真实图片格式是否一致。
- 菜品图片每次最多上传 5 张。随附的 Caddy 配置会在 multipart 解析前把头像和菜品图片请求体分别限制为 6 MB 与 32 MB；公网部署不得绕过 Caddy 直连后端，使用其他反向代理时必须配置等效上限。
- 图片由 Pillow 解码后统一写为 WebP，同时生成最大 `200 x 200` 的 WebP 缩略图；损坏或伪装文件不会落盘。
- 头像可选前端内置的 `/avatars/*.png` 白名单，或通过头像上传接口生成。资料更新只允许清空头像、选择内置头像或保留本人当前上传路径，拒绝外部 URL 和他人的上传路径。
- `backend/uploads/` 包含用户数据和潜在隐私信息，不能提交到 Git 或随源码发布。

## 测试与发布检查

```bash
# 后端单元测试
cd backend
python -m unittest discover -s tests -v

# 90+ 项隔离 E2E（自行创建临时数据库、上传目录与服务端口）
python run_e2e.py

# 前端类型检查与生产构建
cd ../frontend
npm ci
npm run build
```

从仓库根检查即将发布的工作树：

```bash
python scripts/check_release_tree.py --mode worktree
python scripts/check_release_tree.py --mode index
python scripts/check_release_tree.py --mode head
python scripts/check_release_tree.py --mode head --check-dist
```

`worktree` 会包含尚未 `git add` 的非忽略文件并排除已删除文件；`index`/`head` 适合提交前和 CI。`--check-dist` 只扫描实际 `frontend/dist`，用于阻止生产构建残留 `localhost:8000`，不会误报 `frontend/vite.config.ts` 的开发代理。

## 项目结构

```text
MealMate/
|-- backend/                 # FastAPI、异步 SQLAlchemy、测试与隔离 E2E
|-- frontend/                # Vue 3 + TypeScript + Vant 4 + Pinia + PWA
|-- docker/                  # Caddy 配置
|-- scripts/                 # 发布树检查
|-- docker-compose.yml
|-- PRD.md
|-- SECURITY.md
`-- LICENSE
```

安全问题请按 [SECURITY.md](SECURITY.md) 私密报告，不要创建公开 Issue。

## 许可证

[MIT License](LICENSE) - Copyright (c) 2026 MealMate contributors
