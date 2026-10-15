# ConfigHub

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
- `GET/POST /api/accounts/`：账号列表、新增账号
- `PATCH/DELETE /api/accounts/:id/`：编辑、删除账号
- `GET/POST /api/file-configs/`：文件管理配置列表、新增配置
- `PATCH/DELETE /api/file-configs/:id/`：编辑、删除文件管理配置
- `POST /api/file-configs/:id/test-connection/`：测试 SSH 连接
- `POST /api/file-configs/:id/refresh/`：通过 SSH 获取远程文件列表
- `GET /api/file-lists/`：查询已获取的远程文件列表

除 `POST /api/auth/login/` 外，其余 API 接口均需要在请求头携带
`Authorization: Token <token>`。

默认开发管理员：`admin / admin123`。生产环境请登录后立即修改密码。
