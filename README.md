# FileHub

Django + Vue 3 运维控制台，前端交互与布局参考 `C:\Users\kaikai\Desktop\kaikai\1Panel\frontend`。

## 启动后端

```powershell
py -m pip install -r requirements.txt
cd backend
py manage.py migrate
py manage.py runserver 127.0.0.1:8000
```

## 启动前端

```powershell
npm install
npm run dev
```

前端默认地址为 `http://localhost:5173`，开发服务器会将 `/api` 请求代理到 Django。

## API

- `GET /api/health/`：服务健康状态
- `GET /api/dashboard/`：节点、资源指标、监控曲线、服务和动态数据
- `POST /api/auth/login/`：用户登录，返回 Token
- `POST /api/auth/logout/`：退出当前 Token 会话
- `GET /api/auth/me/`：获取当前用户
- `GET/POST /api/users/`：管理员查询、新增用户
- `PATCH/DELETE /api/users/:id/`：管理员编辑、启用/禁用、删除用户
- `GET /api/permissions/`：超级管理员查询固定权限目录
- `GET/POST /api/roles/`：超级管理员查询、新增角色
- `PATCH/DELETE /api/roles/:id/`：超级管理员编辑、启用/禁用、删除角色
- `GET /api/roles/:id/users/`：超级管理员查询角色成员
- `GET /api/file-audits/`、`GET /api/file-audits/:id/`：分页查询文件变更审计及差异详情
- `GET /api/operation-audits/`：分页查询系统关键操作审计
- `GET/POST /api/accounts/`：账号列表、新增账号
- `PATCH/DELETE /api/accounts/:id/`：编辑、删除账号
- `GET/POST /api/file-configs/`：文件管理配置列表、新增配置（支持 `project_id`）
- `PATCH/DELETE /api/file-configs/:id/`：编辑、删除文件管理配置
- `POST /api/file-configs/:id/test-connection/`：测试 SSH 连接
- `POST /api/file-configs/:id/refresh/`：通过 SSH 获取远程文件列表
- `GET /api/file-lists/`：查询已获取的远程文件列表
- `GET/POST /api/projects/`：查询、新增层级项目
- `PATCH/DELETE /api/projects/:id/`：编辑、移动、排序或删除空项目
- `POST /api/file-configs/:id/inspect/`：验证 SSH 并采集系统规格
- `POST /api/file-configs/batch/`：批量移动或删除配置
- `GET /api/file-configs/import-template/`、`POST /api/file-configs/import/`、`POST /api/file-configs/export/`：Excel 模板、预览确认导入和导出

项目管理创建主机时不需要配置机器名称或文件路径，机器名称默认为空，由“验证并采集规格”自动读取远程主机名。Excel 模板同样无需填写这两项；导出的机器名称仅供查看，导入时不会恢复验证信息。原文件管理的路径配置继续用于文件列表获取，未配置路径的主机不能执行文件列表获取。

除 `POST /api/auth/login/` 外，其余 API 接口均需要在请求头携带
`Authorization: Token <token>`。

业务接口同时校验角色权限。多个启用角色的权限取并集，停用角色不提供权限；超级管理员始终拥有全部权限。用户和角色管理仅允许超级管理员访问。

默认开发管理员：`admin / admin123`。生产环境请登录后立即修改密码。
