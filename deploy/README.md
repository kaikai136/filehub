# FileHub Docker 部署

部署使用 YAML 配置文件和两个独立 Dockerfile。前后端镜像分别通过 `docker build` 构建；`docker-compose.yaml` **不包含 build 配置，只负责挂载运行配置、创建网络/数据卷并启动容器**。Nginx 配置文件 `deploy/nginx.conf` 在启动时只读挂载，修改代理规则无需重新构建前端镜像。

## 部署要求

- Docker Engine 与 Docker Compose v2。
- 仓库源码和可用的 Docker build 环境。
- 宿主机 `8080` 端口可用；需要时修改 Compose 中前端 `ports` 映射。

## 1. 准备 YAML 配置

以下命令从仓库根目录执行：

```powershell
Copy-Item deploy/config.yaml.example deploy/config.yaml
```

编辑 `deploy/config.yaml`：

| 字段 | 用途 |
| --- | --- |
| `secret_key` | Django 密钥，也参与加密 SSH 密码和私钥；替换占位值并安全备份，部署后不要随意更换 |
| `debug` | 生产环境必须为 `false` |
| `allowed_hosts` | 请求 Host 白名单；添加实际访问域名及必要的 IP/localhost |
| `csrf_trusted_origins` | 完整来源地址，如 `https://filehub.example.com`；本地访问保留 `http://localhost:8080` |
| `cors_allowed_origins` | 跨域来源列表；生产环境按需收紧 |
| `database` | 数据库引擎和连接参数，支持 SQLite 或 MySQL；字段见下文 |
| `channels` | Channels 后端，支持单实例内存层或外部 Redis |
| `application` | 语言、时区、静态文件目录和上传限制 |
| `security` | HTTPS 代理识别、Cookie 安全属性、HSTS 等 Django 安全选项 |

`deploy/config.yaml` 已加入 Git 和 Docker 构建上下文忽略规则。请勿提交真实密钥。配置采用 YAML 格式，缩进使用空格；布尔值写作 `true`/`false`，列表按模板格式填写。

### 数据库选择

- **SQLite**：默认 `database.engine: sqlite`，文件名 `/data/filehub.sqlite3` 会保存在 `filehub-data` 命名卷中，适用于单机单后端。
- **MySQL/MariaDB**：将 `database.engine` 改为 `mysql`，设置数据库名、用户、密码、主机和端口。建议使用 MySQL 8.0+ 或 MariaDB 10.6+，数据库/表字符集使用 `utf8mb4`，并只授予 FileHub 数据库所需权限。后端镜像包含 PyMySQL 驱动。

Compose 不会创建或管理 MySQL 服务，数据库需由外部提供。容器内的 `localhost` 指向后端容器本身，不是宿主机或数据库容器；请填写容器网络中可解析的数据库服务名、内网地址，或在 Docker Desktop 使用 `host.docker.internal`。Linux 主机部署时需自行配置宿主机网关/网络可达性。密码建议用引号包裹，避免 YAML 将特殊值解析为其他类型。

`database` 可配置 `engine`、`name`、`user`、`password`、`host`、`port`、`conn_max_age`、`conn_health_checks` 和 `options`。`options` 会传给 Django 驱动，可设置 `charset`、连接超时及驱动支持的 SSL 参数，例如 MySQL TLS 可配置 `ssl: {}` 并按驱动要求挂载证书。切换数据库后，先备份数据并重新执行迁移；现有 SQLite 数据不会自动复制到 MySQL。

### Redis 与其他运行设置

默认 `channels.backend: memory` 使用进程内存层，适用于单后端实例。使用外部 Redis 时将其设为 `redis`，并配置 `channels.redis.url`，格式为 `redis://[:密码@]主机:端口/数据库`；TLS Redis 使用 `rediss://`。Compose 不包含 Redis 服务，Redis 必须可由后端容器访问。多后端实例应同时使用 MySQL/PostgreSQL 和 Redis，不要使用 SQLite 与内存 Channel Layer 横向扩展。

`application` 可以配置 `language_code`、`time_zone`、`static_url`、`static_root`、`use_i18n`、`use_tz`、`data_upload_max_memory_size`、`file_upload_max_memory_size` 和 `file_upload_temp_dir`。上传限制的单位是字节。容器部署时 `static_root` 必须与 Compose 中静态卷挂载路径一致（默认 `/app/backend/staticfiles`）。

`security` 可配置 `trust_proxy_ssl_header`、`secure_ssl_redirect`、`session_cookie_secure`、`csrf_cookie_secure`、`session_cookie_httponly`、`csrf_cookie_httponly`、`hsts_seconds`、`hsts_include_subdomains`、`hsts_preload`、`content_type_nosniff`、`referrer_policy` 和 `use_x_forwarded_host`。若在 HTTPS 反向代理后部署，应确认代理会覆盖并传递 `X-Forwarded-Proto: https`，然后启用安全 Cookie。仅在 HTTPS 已稳定启用后设置 `hsts_seconds`；错误启用 HSTS 可能导致浏览器强制使用 HTTPS。`use_x_forwarded_host` 只应在可信代理确实覆盖该请求头时开启。

## 2. 分别构建镜像

从仓库根目录分别执行两个 Dockerfile 构建命令：

```powershell
docker build -f deploy/backend.Dockerfile -t filehub-backend:latest .
docker build -f deploy/frontend.Dockerfile -t filehub-frontend:latest .
```

后端镜像安装 Python 依赖并打包 Django/Daphne；前端镜像安装 npm 依赖、运行生产构建，再将静态页面放入 Nginx 镜像。Compose 文件只引用以上镜像，不会构建镜像。

## 3. 使用 Compose 启动

确认配置文件和两个镜像均已准备好后，从仓库根目录运行：

```powershell
docker compose -f deploy/docker-compose.yaml up -d
```

Compose 将 `deploy/config.yaml`、`deploy/nginx.conf` 以只读方式挂载到后端和前端容器，创建 `filehub-data`、`filehub-static` 数据卷并启动服务。后端入口自动执行数据库迁移、收集 Django Admin 静态资源并启动 Daphne；前端容器会等待后端健康检查通过后启动。访问 `http://localhost:8080`。

首次登录开发管理员为 `admin / admin123`，部署后请立即修改密码，并按生产要求配置用户和权限。

## 日常运维

```powershell
docker compose -f deploy/docker-compose.yaml ps
docker compose -f deploy/docker-compose.yaml logs -f
docker compose -f deploy/docker-compose.yaml logs -f backend
docker compose -f deploy/docker-compose.yaml restart
```

修改 `deploy/nginx.conf` 后重启前端使 Nginx 重新加载挂载配置：

```powershell
docker compose -f deploy/docker-compose.yaml restart frontend
```

停止并移除容器、保留数据卷：

```powershell
docker compose -f deploy/docker-compose.yaml down
```

删除数据卷会永久删除数据库；不要在需要保留数据时使用 `docker compose down -v`。

## 更新镜像

重新构建所需镜像，然后让 Compose 使用新镜像重建容器。只改前端页面时可只构建前端镜像；后端代码改动则构建后端镜像。修改 `nginx.conf` 或 `config.yaml` 不需要构建镜像，应用配置修改需重建对应容器：

```powershell
docker build -f deploy/backend.Dockerfile -t filehub-backend:latest .
docker build -f deploy/frontend.Dockerfile -t filehub-frontend:latest .
docker compose -f deploy/docker-compose.yaml up -d --force-recreate
```

Compose 不会执行镜像构建。容器重建会保留命名数据卷；不要删除 `filehub-data`。

## 数据备份与恢复

- SQLite 数据存储在 `filehub-data` 卷中的 `/data/filehub.sqlite3`。如选择 MySQL，请使用 MySQL 自身的备份工具（例如 `mysqldump`）备份外部数据库。
- Django Admin 静态文件存储于 `filehub-static` 卷，可由后端重新收集生成。
- `deploy/config.yaml` 中的 `secret_key` 必须与数据库备份一起安全保存，否则无法解密已保存的 SSH 凭据。

使用 SQLite 时，建议停机后备份数据库，避免复制运行中的文件：

```powershell
docker compose -f deploy/docker-compose.yaml stop frontend backend
docker compose -f deploy/docker-compose.yaml cp backend:/data/filehub.sqlite3 .\filehub.sqlite3.backup
docker compose -f deploy/docker-compose.yaml start backend frontend
```

SQLite 恢复时先停服务并备份当前数据库，再将备份文件复制回后端容器的 `/data/filehub.sqlite3`，之后启动服务。MySQL 恢复使用对应数据库工具执行。配置密钥必须与数据库属于同一部署。限制 `deploy/config.yaml` 的读取权限，不要提交或外传真实密钥。

## HTTPS 与安全

生产环境建议由受信任的 HTTPS 反向代理终止 TLS，再转发到宿主机 `8080`。将 `allowed_hosts` 加入实际域名，并将 `csrf_trusted_origins` 设置为完整 HTTPS 来源。反向代理应保留 `Host`、传递 `X-Forwarded-Proto: https` 并支持 WebSocket Upgrade。

不要将后端 `8000` 端口直接暴露到公网。默认部署采用 SQLite 和 Django Channels `InMemoryChannelLayer`，适合单机单后端。YAML 可切换至外部 MySQL 和 Redis；多个后端实例应使用共享关系数据库及 Redis Channel Layer。
