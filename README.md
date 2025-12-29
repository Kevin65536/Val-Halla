# Val-Halla - QQ群成员自动备份与一键重建工具

## 项目简介

Val-Halla是一个基于OneBot 11协议的QQ群管理工具,支持:
- 🔄 **群成员备份**: 备份群成员列表及详细信息（名片、头衔、权限等）
- 🔄 **信息恢复**: 恢复已在群内成员的名片、头衔、管理员权限
- 📊 **数据导出**: 导出群成员数据为 JSON/CSV 格式
- 🌐 **Web管理界面**: 可视化管理备份和恢复操作
- ⚙️ **灵活配置**: 支持多群管理、备份策略配置

> ⚠️ **重要提示**: 由于 OneBot 11 标准协议限制，**不支持直接邀请成员入群**。重建功能仅能恢复已在目标群内成员的信息（名片、头衔、管理员权限），无法将不在群内的成员拉入群组。

## 技术栈

- **后端**: Python 3.10+
- **QQ协议**: OneBot 11 标准
- **协议实现**: 支持 NapCat / LLOneBot 等
- **数据库**: SQLite (轻量级) / PostgreSQL (生产环境)
- **Web框架**: FastAPI + Jinja2 Templates
- **前端**: 原生 HTML + CSS + JavaScript

## 核心功能

### 1. 群成员备份
- 获取群成员列表 (OneBot API: `get_group_member_list`)
- 保存成员详细信息:
  - 基础信息: QQ号、昵称、群名片
  - 群内信息: 加群时间、最后发言时间、成员等级、角色(群主/管理员/成员)
  - 扩展信息: 专属头衔
- 支持全量备份和增量备份
- 备份历史版本管理
- 成员变化追踪(新增/退出)

### 2. 群信息恢复
> ⚠️ **注意**: OneBot 11 协议不支持直接邀请成员入群，因此"重建"功能仅限于恢复**已在目标群内**成员的信息。

- 恢复群名片 (set_group_card)
- 恢复专属头衔 (set_group_special_title) 
- 恢复管理员权限 (set_group_admin，需 Bot 为群主)
- 支持模拟运行(dry run)预览变更
- 支持跨群恢复（从A群备份恢复到B群）

### 3. 数据导出
- 导出为 JSON 格式
- 导出为 CSV 格式

### 4. Web 管理界面
- 仪表盘：系统状态概览
- 群组管理：查看群列表和成员
- 备份管理：创建/查看/删除备份
- 恢复操作：预览和执行恢复

## 项目结构

```
Val-Halla/
├── src/
│   ├── __init__.py
│   ├── main.py                  # CLI 程序入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── backup_manager.py    # 备份管理核心
│   │   └── rebuild_manager.py   # 信息恢复核心
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py          # 数据库连接
│   │   ├── group.py             # 群组模型
│   │   ├── member.py            # 成员模型
│   │   └── backup.py            # 备份记录模型
│   ├── api/
│   │   ├── __init__.py
│   │   └── onebot.py            # OneBot API 封装
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py            # 配置管理
│   │   └── logger.py            # 日志工具
│   └── web/
│       ├── __init__.py
│       ├── app.py               # FastAPI Web 应用
│       ├── static/              # 静态资源
│       └── templates/           # Jinja2 模板
│           ├── base.html
│           ├── index.html
│           ├── groups.html
│           ├── backups.html
│           └── settings.html
├── config/
│   └── config.yaml              # 主配置文件
├── data/
│   ├── backups/                 # 备份数据
│   └── database/                # 数据库文件
├── export/                      # 导出数据
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── LICENSE
```

## OneBot API 使用说明

### 已实现的 API

| API 端点 | 用途 | 状态 |
|---------|------|------|
| `get_login_info` | 获取登录号信息 | ✅ 已实现 |
| `get_group_list` | 获取群列表 | ✅ 已实现 |
| `get_group_info` | 获取群信息 | ✅ 已实现 |
| `get_group_member_list` | 获取群成员列表 | ✅ 已实现 |
| `get_group_member_info` | 获取群成员信息 | ✅ 已实现 |
| `send_group_msg` | 发送群消息 | ✅ 已实现 |
| `set_group_card` | 设置群名片 | ✅ 已实现 |
| `set_group_name` | 设置群名 | ✅ 已实现 |
| `set_group_admin` | 设置群管理员 | ✅ 已实现 |
| `set_group_special_title` | 设置专属头衔 | ✅ 已实现 |
| `get_friend_list` | 获取好友列表 | ✅ 已实现 |
| `get_stranger_info` | 获取陌生人信息 | ✅ 已实现 |
| `get_status` | 获取运行状态 | ✅ 已实现 |
| `get_version_info` | 获取版本信息 | ✅ 已实现 |

### 不支持的功能

⚠️ **OneBot 11 标准协议不支持以下功能**：
- ❌ 直接邀请成员入群（没有 `set_group_invite` 等 API）
- ❌ 批量拉人入群

这意味着"群组重建"功能**无法**将不在群内的成员拉入群组，只能恢复已在群内成员的信息。

## 实现状态

### ✅ 已完成

- [x] 项目结构设计
- [x] OneBot API 封装 (HTTP 连接、API 调用)
- [x] 数据库模型设计 (SQLAlchemy ORM)
- [x] 群成员备份功能
  - [x] 获取群成员列表
  - [x] 数据持久化到数据库
  - [x] 备份文件保存 (支持 gzip 压缩)
  - [x] 成员变化追踪 (新增/退出)
- [x] 信息恢复功能
  - [x] 恢复群名片
  - [x] 恢复专属头衔
  - [x] 恢复管理员权限
  - [x] 模拟运行 (dry run) 预览
  - [x] 跨群恢复支持
- [x] CLI 命令行工具
- [x] FastAPI Web 界面
- [x] 数据导出 (JSON/CSV)
- [x] 配置文件管理
- [x] 日志系统
- [x] Docker 支持

### ❌ 不支持/无法实现

- [ ] ~~批量邀请成员入群~~ (OneBot 11 协议限制)
- [ ] ~~自动定时备份~~ (需要额外实现调度器)
- [ ] ~~邮件/消息通知~~ (未实现)

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 OneBot
- 安装并配置 NapCat、LLOneBot 或其他 OneBot 11 实现
- 在 `config/config.yaml` 中填写连接信息

### 3. 运行程序

#### 命令行模式
```bash
# 检查连接状态
python -m src.main status

# 查看群信息
python -m src.main info <群号>

# 备份群成员
python -m src.main backup <群号>

# 查看备份历史
python -m src.main history <群号>

# 从备份恢复（预览模式）
python -m src.main rebuild <备份ID> <目标群号> --dry-run

# 导出群成员
python -m src.main export <群号> --format json
```

#### Web 界面模式
```bash
# 启动 Web UI
python -m src.main webui --host 0.0.0.0 --port 8080
```

然后访问 http://localhost:8080

## 注意事项

1. **API 限制**: 
   - OneBot 11 协议**不支持**邀请成员入群
   - "重建"功能仅能恢复已在群内成员的信息
   - 如需拉人，需要使用 QQ 客户端手动操作

2. **权限要求**:
   - Bot 需要是群主才能设置管理员
   - Bot 需要是群主才能设置专属头衔
   - 普通管理员可以设置群名片

3. **恢复功能说明**:
   - 恢复名片：将群成员的名片恢复为备份时的状态
   - 恢复头衔：将专属头衔恢复为备份时的状态
   - 恢复管理员：将备份中是管理员的成员重新设为管理员

4. **数据安全**:
   - 备份数据包含群成员QQ号等信息
   - 建议妥善保管备份文件
   - 默认启用 gzip 压缩

## 依赖项

主要 Python 依赖:
- `requests` - HTTP 客户端
- `sqlalchemy` - ORM
- `aiosqlite` - SQLite 异步支持
- `pydantic` - 数据验证
- `pyyaml` - 配置文件解析
- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `jinja2` - 模板引擎
- `click` - CLI 框架
- `rich` - 终端美化

## 协议支持

### OneBot 11 标准
- 完全兼容 OneBot 11 协议规范
- 仅支持 HTTP 通信

### 推荐实现
1. **NapCatQQ**: 基于 NTQQ 的现代化实现
2. **LLOneBot**: 轻量级 OneBot 实现

## 贡献

欢迎提交Issue和Pull Request!

## 许可证

MIT License

## 致谢

- [OneBot 标准](https://github.com/botuniverse/onebot-11)
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ)
- [LLOneBot](https://github.com/LLOneBot/LLOneBot)
