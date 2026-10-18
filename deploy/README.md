# FileHub Docker 部署

本目录提供面向单机部署的 Docker Compose 示例：Nginx 提供前端静态页面并代理 API、Django Admin 和 WebSocket；Daphne 提供 Django ASGI 服务；SQLite 和 Django 静态文件分别存放在 Docker 命名卷中。

## 部署要求

- Docker Engine 和 Docker Compose v2。
- 对外开放一个 TCP 端口（默认 `8080`）；生产环境建议在前置反向代理终止 HTTPS。
- 持久化保存 `DJANGO_SECRET_KEY` 和 Docker 卷数据。

## 首次启动

以下命令从仓库根目录执行：

```powershell
Copy-Item deploy/.env.example deploy/.env
```

编辑 `deploy/.env`：

| 变量 | 示例/默认值 | 说明 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | 示例占位值 | 必须替换为强随机密钥。该值参与加密 SSH 密码和私钥，必须备份且部署后不可随意更换 |
| `DJANGO_DEBUG` | `0` | 生产环境保持关闭 |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | 逗号分隔的请求 Host；通过域名访问时加入实际域名 |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8080` | 完整来源 URL；HTTPS 部署需设置为 `https://你的域名` |
| `FILEHUB_PORT` | `8080` | 宿主机对外端口，容器内部仍使用 80 |

启动并构建镜像：

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml up -d --build
```

浏览器访问 `http://localhost:8080`（如修改 `FILEHUB_PORT`，请使用对应端口）。首次启动时，后端容器会自动执行 Django 数据库迁移、收集 Admin 静态资源并启动 Daphne。开发管理员为 `admin / admin123`；首次登录后立即修改密码，并按生产安全要求配置管理员和用户。

## 日常运维

```powershell
# 查看容器状态
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml ps

# 查看全部日志或指定服务日志
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml logs -f
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml logs -f backend

# 拉取代码后重新构建并更新
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml up -d --build

# 停止并移除容器、网络，但保留数据卷
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml down
```

不要在需要保留数据时使用 `docker compose down -v`，该命令会删除 SQLite 数据卷和静态文件卷。

## 数据与备份

- SQLite 数据库：`filehub_data` 卷内的 `/data/filehub.sqlite3`。
- Django Admin 静态文件：`filehub_static` 卷；容器启动时由 `collectstatic` 更新，可重新生成。
- SSH 凭据加密密钥：`deploy/.env` 中的 `DJANGO_SECRET_KEY`。数据库备份必须与对应密钥一起安全保存；仅有数据库而丢失密钥时，已存 SSH 凭据将无法解密。

为获得一致的 SQLite 备份，建议先停止服务，再复制数据库文件：

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml stop frontend backend
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml cp backend:/data/filehub.sqlite3 ./filehub.sqlite3.backup
docker compose --env-file deploy/.env -f deploy/docker-compose.yaml start backend frontend
```

将备份文件和 `deploy/.env`（尤其是 `DJANGO_SECRET_KEY`）放到权限受限的位置。恢复时停止服务，将备份数据库复制回后端容器的 `/data/filehub.sqlite3`，再启动服务。恢复前请先另存当前数据库；不要把密钥提交到 Git 或发送到不可信位置。

## HTTPS 反向代理

可在宿主机或负载均衡器上配置 TLS，再将请求转发到 FileHub 暴露的宿主机端口。设置 `CSRF_TRUSTED_ORIGINS` 为浏览器使用的完整 HTTPS 来源，例如 `https://filehub.example.com`，同时将域名加入 `DJANGO_ALLOWED_HOSTS`。代理必须保留正确的 `Host` 和 `X-Forwarded-Proto: https` 请求头，并支持 WebSocket Upgrade；项目 Nginx 会将 `/ws/` 转发至 Daphne。

不要将 `DJANGO_DEBUG=1` 用于公网生产环境。限制宿主机端口访问范围或仅允许可信 HTTPS 反向代理访问。

## 架构边界

当前配置使用 SQLite 和 Django Channels `InMemoryChannelLayer`，面向单机单个后端实例。不要直接扩展多个 Daphne 后端实例：内存 Channel Layer 不会在进程间共享。若需多实例部署，应改用 PostgreSQL 和 Redis Channel Layer，并相应调整 Compose、数据库备份和部署流程。

