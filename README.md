# FileHub

FileHub 是基于 Django REST Framework、Vue 3 和 TypeScript 的运维管理控制台，提供项目与主机管理、SSH 文件浏览、命令执行、访问控制和审计能力。后端使用 Django ASGI/Daphne 支持 HTTP API 与 WebSocket 实时输出，前端使用 Vite 构建。

## 功能概览

- **概览**：展示主机、资源指标、监控曲线、服务信息和近期动态。
- **项目管理**：维护层级项目，关联主机配置；支持项目移动、排序以及配置导入/导出。
- **SSH 账号**：统一管理 SSH 用户名、密码或私钥，并将敏感凭据加密保存。
- **文件管理**：维护 SSH 主机与目录配置，测试连接、采集主机规格、刷新远程文件；支持批量操作及 Excel 导入/导出。
- **文件列表**：浏览远程文件列表并查看文件内容。需要先为主机配置文件目录并成功刷新列表。
- **命令执行**：通过 SSH 在主机上运行命令；Shell、K8s 和执行历史使用独立标签，两种模式分别保留当前页面的表单草稿。提交后自动在弹窗中展示实时输出，关闭弹窗不会停止任务，可从历史记录重新查看或显式停止。
- **Shell 安全限制**：Shell 不关联文件，默认内置严格危险命令黑名单，可在系统菜单“角色管理”下方的“命令控制”页面搜索、新增、编辑和启停规则，或恢复内置默认规则。只有超级管理员可修改，有 command_control.view 权限的用户可只读查看。规则保存到数据库后立即用于提交及 SSH 连接前的双重检查，执行检查无管理员豁免。删除、磁盘操作、关机重启、脚本解释器及常见间接执行入口被禁止，不支持重定向、后台执行、变量替换或完整 Shell 脚本。普通查看命令、管道和命令连接仍可使用，命中后返回 HTTP 400 与错误码 `dangerous_shell_command`，并记录安全拦截审计。黑名单仅降低风险，不能保证拦截所有危险行为；K8s 文件选择及自由执行能力不受此策略限制，不构成全局安全隔离。生产环境仍应使用远程最小权限账户。
- **审计与通知**：记录文件变更和关键操作，通知用户主机配置的新增、修改与删除。
- **用户与角色**：管理用户、角色和细粒度权限；支持管理员控制双因素认证（TOTP）。
- **系统设置**：配置登录会话时长、GitHub 项目地址、界面字体、水印以及审计数据保留时间。
- **登录安全**：登录滑块验证、可选的管理员强制 TOTP、固定时长登录会话和屏幕锁定。

## 技术栈与目录

| 路径 | 内容 |
| --- | --- |
| `backend/configHub/` | Django 项目设置、ASGI/WSGI 和 URL 配置 |
| `backend/dashboard/` | API、模型、权限、SSH、审计、通知及数据库迁移 |
| `src/views/` | Vue 页面 |
| `src/features/` | 前端认证、权限、项目、审计、命令等领域逻辑 |
| `src/components/` | 通用组件与登录页组件 |
| `deploy/` | Dockerfile、Compose、Nginx 和部署说明 |
| `requirements.txt` | Python 依赖 |
| `package.json` | 前端依赖与脚本 |

## 环境要求

- Python 3.10+（部署镜像使用 Python 3.12）
- Node.js 22+ 和 npm
- 本地开发默认使用 SQLite；Docker 单机部署也使用 SQLite 持久化卷
- 容器部署需要 Docker Engine 和 Docker Compose v2

## 本地开发

### 后端

在项目根目录运行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
cd backend
py manage.py migrate
py manage.py runserver 127.0.0.1:8000
```

Django 开发服务通过 Daphne/ASGI 运行，以支持命令执行的 WebSocket 输出。首次访问登录流程会初始化开发管理员账号：`admin / admin123`。该账号仅供本地开发；上线前务必修改密码，并在生产环境设置独立的 `DJANGO_SECRET_KEY`。

### 前端

另开终端，在项目根目录运行：

```powershell
npm ci
npm run dev
```

默认访问 `http://localhost:5173`。Vite 将 `/api` 和 `/ws` 请求代理到本地 Django 服务 `http://127.0.0.1:8000`。

### 环境变量

后端支持以下环境变量（本地开发均可选）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | 开发用固定密钥 | Django 签名密钥，也用于加密 SSH 凭据；生产环境必须配置强随机值并妥善备份 |
| `DJANGO_DEBUG` | `1` | Django 调试模式；生产环境设为 `0` |
| `DJANGO_ALLOWED_HOSTS` | `*` | 逗号分隔的 Host 名称 |
| `SQLITE_PATH` | `backend/db.sqlite3` | SQLite 数据库文件路径 |
| `CSRF_TRUSTED_ORIGINS` | 空 | 逗号分隔的可信来源，包含协议和域名，例如 `https://filehub.example.com` |
| `CORS_ALLOWED_ORIGINS` | 本地 Vite 地址 | 逗号分隔的跨域来源 |

## 认证与权限

- 登录先获取并完成服务端滑块挑战，再提交账号和密码。勾选“记住用户名”只会记住用户名，不保存密码。
- 管理员可在用户管理中开启、关闭或重置某用户的 TOTP。开启/重置后，用户下次登录时必须完成首次绑定；启用后后续登录需要动态验证码。普通用户不能在个人设置中自行绑定或解绑。
- 登录 Token 使用固定过期时间，默认 480 分钟，系统设置允许配置 1 至 43,200 分钟。会话不会因操作而滑动续期；过期的 API/WebSocket 请求会被拒绝并要求重新登录。
- 权限按角色授权，多个启用角色的权限取并集。每个模块执行新增、编辑、删除、执行、导入或导出等操作权限时同时需要该模块的查看权限。
- 权限模块包括概览、项目、SSH 账号、文件管理、文件列表、文件审计、操作审计、命令执行、系统设置、用户管理和角色管理。超级管理员拥有全部权限；普通权限管理员只能分配自身拥有的权限，且不能管理超级管理员或内置角色。
- 系统级偏好由超级管理员维护。拥有 `settings.view` 的用户可查看设置并维护自己的个人资料。

## API 参考

API 根路径为 `/api/`。除登录、滑块挑战/校验和双因素登录验证外，接口使用 `Authorization: Token <token>` 请求头。受保护接口会根据当前数据库中的角色权限实时授权。

| 路径 | 方法 | 用途 |
| --- | --- | --- |
| `/health/` | `GET` | 服务健康状态 |
| `/auth/slider-challenge/` | `GET` | 获取登录滑块挑战 |
| `/auth/slider-verify/` | `POST` | 校验滑块并获取登录用令牌 |
| `/auth/login/` | `POST` | 用户名密码登录，可能返回 TOTP 绑定或验证挑战 |
| `/auth/verify-two-factor/` | `POST` | 验证已绑定用户的 TOTP 并完成登录 |
| `/auth/verify-two-factor-setup/` | `POST` | 确认管理员要求的首次 TOTP 绑定 |
| `/auth/me/` | `GET` | 获取当前用户和有效权限 |
| `/auth/logout/` | `POST` | 注销当前 Token |
| `/auth/unlock/` | `POST` | 验证密码并解除屏幕锁定 |
| `/dashboard/` | `GET` | 获取概览数据 |
| `/projects/`、`/projects/:id/` | `GET`, `POST`, `PATCH`, `DELETE` | 项目层级及项目操作 |
| `/accounts/`、`/accounts/:id/` | `GET`, `POST`, `PATCH`, `DELETE` | SSH 账号管理；`/accounts/options/` 提供选择项 |
| `/file-configs/`、`/file-configs/:id/` | `GET`, `POST`, `PATCH`, `DELETE` | 主机/目录配置管理 |
| `/file-configs/:id/test-connection/` | `POST` | 测试 SSH 连接 |
| `/file-configs/:id/inspect/` | `POST` | 验证 SSH 并采集主机规格 |
| `/file-configs/:id/refresh/` | `POST` | 刷新远程文件列表 |
| `/file-configs/batch/` | `POST` | 批量移动或删除配置 |
| `/file-configs/import-template/` | `GET` | 下载 Excel 导入模板 |
| `/file-configs/import/`、`/file-configs/export/` | `POST` | 导入预览/确认与导出配置 |
| `/file-lists/` | `GET` | 查询远程文件 |
| `/file-lists/:id/` | `GET`, `PATCH` | 查看或更新远程文件内容 |
| `/command-executions/`、`/command-executions/:id/` | `GET`, `POST` | 查询和创建命令执行记录；列表支持可选 `mode=shell 或 k8s` 类型筛选，省略查询全部，无效值返回 400 |
| `/command-control/` | `GET`, `PATCH` | 查看或保存 Shell 黑名单（修改仅超级管理员，保存需携带 revision；并发冲突返回 409） |
| `/command-executions/options/` | `GET` | 获取可执行主机、文件等选项 |
| `/command-executions/:id/stop/` | `POST` | 停止命令执行 |
| `/ws/command-executions/:id/` | WebSocket | 实时接收命令输出（需有效 Token） |
| `/file-audits/`、`/file-audits/:id/` | `GET` | 文件变更审计及差异详情 |
| `/operation-audits/` | `GET` | 系统操作审计 |
| `/notifications/` | `GET` | 查询当前用户通知 |
| `/notifications/:id/read/`、`/notifications/read-all/` | `POST` | 标记单条或全部通知为已读 |
| `/settings/` | `GET`, `PATCH` | 用户资料与系统偏好 |
| `/appearance/` | `GET` | 获取当前界面偏好和水印信息 |
| `/permissions/`、`/roles/`、`/roles/:id/` | `GET`, `POST`, `PATCH`, `DELETE` | 权限目录与角色管理 |
| `/roles/:id/users/` | `GET` | 查询角色成员 |
| `/users/`、`/users/:id/` | `GET`, `POST`, `PATCH`, `DELETE` | 用户管理 |
| `/users/:id/two-factor/{enable,disable,reset}/` | `POST` | 管理员控制用户双因素认证 |

## Docker 单机部署

部署使用 YAML 配置文件，可选择 SQLite 或 MySQL，并配置 Redis Channel Layer、时区、上传限制和 Django HTTPS 安全选项；前后端镜像分别构建，Docker Compose 仅负责启动容器。先复制配置模板：

```powershell
Copy-Item deploy/config.yaml.example deploy/config.yaml
```

编辑 `deploy/config.yaml`，设置强随机 `secret_key`，并按部署域名调整 `allowed_hosts`、`csrf_trusted_origins`。分别构建两个镜像：

```powershell
docker build -f deploy/backend.Dockerfile -t filehub-backend:latest .
docker build -f deploy/frontend.Dockerfile -t filehub-frontend:latest .
```

使用 Compose 启动已构建镜像：

```powershell
docker compose -f deploy/docker-compose.yaml up -d
```

默认访问 `http://localhost:8080`。后端启动时自动迁移数据库、收集 Django Admin 静态资源并运行 Daphne；Nginx 统一代理前端、API、Admin、静态资源和 WebSocket。SQLite 数据与静态文件分别保存在 Docker 命名卷中。详细步骤见 [`deploy/README.md`](deploy/README.md)。

查看容器和日志：

```powershell
docker ps
docker compose -f deploy/docker-compose.yaml logs -f
```

停止服务但保留数据卷：

```powershell
docker compose -f deploy/docker-compose.yaml down
```

删除 `filehub-data` 卷会永久删除数据库，执行前请确保已有备份。更多镜像构建、容器运行、备份和 HTTPS 说明见 [`deploy/README.md`](deploy/README.md)。当前方案面向单机单后端；多实例需迁移 PostgreSQL，并将 Channels 内存层改为 Redis。

## 测试与构建

```powershell
# 前端单元测试及组件测试
npm run test:run

# 前端类型检查与生产构建
npm run build

# 后端测试（从仓库根目录）
py backend/manage.py test dashboard

# 后端配置与迁移检查
py backend/manage.py check
py backend/manage.py makemigrations --check --dry-run
```

## 安全与运维提示

- 生产环境必须在 `deploy/config.yaml` 中关闭 `debug`，正确配置允许域名和 HTTPS 可信来源，并通过 HTTPS 访问。
- `secret_key` 同时参与 SSH 凭据加密。丢失密钥会导致既有加密凭据无法解密；随意更换会造成同样影响。请限制 `deploy/config.yaml` 文件权限并备份密钥。
- 备份时同时保存 SQLite 数据库与对应密钥。Docker SQLite 数据位于 `filehub-data` 卷；删除该卷会永久删除数据库。
- 默认部署使用 SQLite 和 Channels 内存层，适合单机单后端。横向扩展时应改用 MySQL/PostgreSQL 与 Redis Channel Layer，内存层无法跨进程同步。
- 文件导入、远程 SSH、Shell 命令及 K8s 命令均具有操作风险；只为可信用户分配相应权限，并确认目标主机和命令内容。
