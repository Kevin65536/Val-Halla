# Val-Halla

QQ群成员快照、变动对比和导出工具。Windows 默认使用 **Python + 独立 NapCat Node 运行目录**，日常使用不需要 Docker Desktop。

备份包括 QQ 号、昵称、名片、角色、头衔、入群和最后发言时间，**不包含聊天消息、群文件或相册**。

## 日常使用

1. 双击 `Start.cmd`，启动或复用本项目服务，并在 Chrome Default 配置中打开 `http://127.0.0.1:8080`。
2. 有效会话自动登录；失效时，页面显示二维码，用手机 QQ 扫码确认。
3. 选择群并备份，在“备份历史”查看变化、下载 JSON.gz 文件。

`Status.cmd` 查看状态，`Stop.cmd` 停止本项目拥有的进程。重复启动不会建立第二份服务；停止时核验路径、参数、工作目录和进程创建时间，避免 PID 复用误伤其他程序。关闭网页不会停止服务。

`Start.cmd --no-browser` 只启动后台服务。找不到 Chrome 时输出地址，不切换到其他浏览器。没有新增开机任务或持续进程守护。

## 首次安装

适用于 Windows x64、Python 3.11+。代码仓库不包含 QQ 登录数据、令牌和大型运行文件。

1. 安装 Python 3.11，运行 `Setup.cmd`，使用 `requirements-lock.txt` 安装验证过的依赖。
2. 从 [NapCat 官方 v4.18.38 Release](https://github.com/NapNeko/NapCatQQ/releases/tag/v4.18.38) 下载 `NapCat.Shell.Windows.Node.zip`。此版本已实机验证，内置 QQ 运行时为 `9.9.31-49738`。
3. 在项目目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\install_native.py "下载路径\NapCat.Shell.Windows.Node.zip" --account 你的QQ号
.\.venv\Scripts\python.exe scripts\activate_native.py
.\Start.cmd
```

安装器校验 SHA-256：`b88007a373a30deefb387e7cf17911752ff900bce22c534b3da6b644f5c6d0ae`。不匹配时拒绝安装，不覆盖已有运行目录。升级必须先备份并验证新版本。

运行目录：`runtime/napcat`。安装器解压官方包并创建独立配置，不复制其他机器人的账号或配置。QQ SDK 可能把账号数据保存在系统腾讯用户目录，本机观察到 `Documents/Tencent Files/NapCat/data`；独立程序目录不意味着 QQ 数据完全隔离。

默认本机端口：WebUI `8080`、OneBot HTTP `15701`、NapCat 管理接口 `16098`。都绑定 `127.0.0.1`。修改端口需同时更新 `config/config.yaml` 和 NapCat 配置。启动器检测占用和 Windows 保留端口，不修改系统网络设置。

## 架构与登录

```text
Start.cmd → src.desktop
              ├─ 管理本项目 NapCat 进程
              └─ 启动 Val-Halla WebUI
                       ├─ ConnectionService：在线状态、账号核验、操作前检查
                       ├─ NapCatRuntime：管理认证、二维码、快速登录
                       └─ OneBotAPI → BackupManager → SQLite + JSON.gz
```

页面区分未安装、未启动、启动中、等待扫码、离线、认证失败、账号不匹配和就绪。备份请求重新检查连接，不依赖页面上次轮询。扫码成功后自动刷新群列表，离线时可筛选和下载历史备份。

管理接口适配固定的 NapCat 4.18.38。管理 Token 在后端换取短期凭据，不返回给页面；二维码在本地渲染。OneBot HTTP 复用连接，并关闭本地请求的环境代理继承。WebSocket 仍可使用，事件流不会无限延长请求超时。

## 数据和功能边界

- 数据库：`data/database/valhalla.db`；备份：`data/backups/<群号>/`。
- CLI 与 WebUI 共用初始化，配置中的相对路径均以项目根目录解析。
- 同群并发备份使用跨进程文件锁；空列表和无效／重复编号会中止，不覆盖已有成员快照。
- 文件先写临时文件再替换；数据库失败会回滚成员变更并记录失败状态。
- `full`、`incremental` 都保存完整快照；新增／退出为成员差异统计，不是仅保存差量文件。
- 加密尚未实现；`encryption: true` 会报错，避免明文被标为已加密。
- 自动定时备份和邮件／QQ 通知尚未实现。保留旧版配置字段不代表功能已启用，默认关闭自动备份。
- 重建仅恢复已在目标群内的成员信息，不支持邀请入群。实际恢复会修改群内信息，应先预览。迁移验收不执行恢复、不发送群消息。

停止服务后备份 `data/`、`config/config.yaml`、`runtime/napcat/napcat/config/`，以及需要保留的 QQ SDK 账号目录。账号和群成员数据不应加入 Git。

## CLI

```powershell
.\.venv\Scripts\python.exe -m src.desktop start --no-browser
.\.venv\Scripts\python.exe -m src.main status
.\.venv\Scripts\python.exe -m src.main backup <群号>
.\.venv\Scripts\python.exe -m src.main history <群号>
.\.venv\Scripts\python.exe -m src.main export <群号> --format json
.\.venv\Scripts\python.exe -m src.desktop stop
```

环境变量 `VALHALLA_CONFIG` 可指定另一份 YAML，用于隔离测试。`/api/health` 检查应用启动状态，`/api/status` 检查 QQ 在线状态。

## 可选外部 OneBot / Docker

复制 `config/config.example.yaml` 为 `config/config.yaml`，填写 OneBot 地址、端口和 Token，使用 `runtime.mode: external`。外部模式不启动或停止远端 NapCat。

`docker compose up -d --build` 仅部署 Val-Halla WebUI，不再捆绑旧版 go-cqhttp 示例和多余的 PostgreSQL。容器配置必须填写从容器可访问的 OneBot 地址；容器内 `127.0.0.1` 不是 Windows 主机。不要直接用本机原生模式配置启动容器部署。

默认 SQLite；需要 PostgreSQL 时，安装 `requirements-postgres.txt` 并填写数据库配置。

## 迁移状态

Windows 原生迁移已合并到 `main` 并推送远端。2026-10-27 按用户要求清理了旧 NapCat Docker 容器、关联账号与配置卷，以及旧运行镜像，不再维护旧 Docker 回退环境。

当前原生运行时、配置、数据库和群成员备份继续使用。Git 只记录代码；切换到历史提交不会恢复已删除的 Docker 容器或数据卷。

本次迁移详情见 `docs/migration-20261027.md`。

## 开发与测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend ci --ignore-scripts
npm.cmd --prefix frontend run build
```

Alpine 3.14.9、编译后的 Tailwind 3.4.17 已随代码保存在 `src/web/static/vendor/`；日常运行不依赖 CDN 或 Node 构建工具。测试使用临时数据库和模拟接口。

Git 跟踪代码、依赖锁文件、构建结果和文档；忽略 `runtime/`、`work/`、真实配置、日志、数据库、导出和备份。

MIT License.
