# Val-Halla - QQ群成员自动备份与一键重建工具

## 项目简介

Val-Halla是一个基于OneBot 11协议的QQ群管理工具,支持:
- 🔄 **自动备份**: 定期备份群成员列表及详细信息
- 🚀 **一键重建**: 快速重建群组并批量邀请原成员
- 📊 **数据分析**: 查看成员变化趋势和统计信息
- ⚙️ **灵活配置**: 支持多群管理、定时任务、备份策略配置

## 技术栈

- **后端**: Python 3.10+
- **QQ协议**: OneBot 11 标准
- **协议实现**: 支持 go-cqhttp / NapCat
- **数据库**: SQLite (轻量级) / PostgreSQL (生产环境)
- **任务调度**: APScheduler
- **Web框架**: FastAPI
- **前端**: Vue 3 + Element Plus (可选Web UI)

## 核心功能

### 1. 群成员备份
- 定期获取群成员列表 (OneBot API: `get_group_member_list`)
- 保存成员详细信息:
  - 基础信息: QQ号、昵称、群名片
  - 群内信息: 加群时间、最后发言时间、成员等级、角色(群主/管理员/成员)
  - 扩展信息: 专属头衔、是否允许修改名片
- 支持增量备份和全量备份
- 备份历史版本管理

### 2. 群组重建
- 创建新群或使用现有群
- 自动设置群信息 (名称、公告等)
- 批量邀请成员 (遵守QQ限制)
  - 智能速率控制,避免触发风控
  - 失败重试机制
  - 邀请进度追踪
- 恢复管理员权限 (需bot为群主)
- 恢复成员名片

### 3. 数据管理
- 多版本备份对比
- 成员变化追踪(新增/退出)
- 数据导出(JSON/CSV/Excel)
- 备份数据加密存储

### 4. 自动化任务
- 定时备份任务
- 异常监控和通知
- 备份失败自动重试
- 邮件/QQ消息通知

## 项目结构

```
Val-Halla/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bot_client.py        # OneBot客户端封装
│   │   ├── backup_manager.py    # 备份管理核心
│   │   └── rebuild_manager.py   # 群组重建核心
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py          # 数据库连接
│   │   ├── group.py             # 群组模型
│   │   ├── member.py            # 成员模型
│   │   └── backup.py            # 备份记录模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── onebot.py            # OneBot API封装
│   │   └── web_api.py           # Web API (可选)
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── scheduler.py         # 任务调度器
│   │   └── backup_task.py       # 备份任务
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py            # 配置管理
│   │   ├── logger.py            # 日志工具
│   │   ├── crypto.py            # 加密工具
│   │   └── rate_limiter.py      # 速率限制
│   └── main.py                  # 程序入口
├── web/                         # Web界面(可选)
│   ├── src/
│   ├── public/
│   └── package.json
├── config/
│   ├── config.yaml              # 主配置文件
│   ├── onebot.yaml              # OneBot配置
│   └── database.yaml            # 数据库配置
├── data/
│   ├── backups/                 # 备份数据
│   ├── logs/                    # 日志文件
│   └── database/                # 数据库文件
├── tests/
│   ├── test_backup.py
│   ├── test_rebuild.py
│   └── test_api.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── README.md
└── LICENSE
```

## OneBot API使用说明

### 核心API端点

1. **获取群列表**
   - API: `get_group_list`
   - 用途: 发现并管理多个群组

2. **获取群信息**
   - API: `get_group_info`
   - 参数: `group_id`, `no_cache`
   - 返回: 群名称、成员数、容量等

3. **获取群成员列表**
   - API: `get_group_member_list`
   - 参数: `group_id`
   - 返回: 完整成员列表及详细信息

4. **获取群成员信息**
   - API: `get_group_member_info`
   - 参数: `group_id`, `user_id`, `no_cache`
   - 返回: 单个成员详细信息

5. **发送群消息**
   - API: `send_group_msg`
   - 参数: `group_id`, `message`
   - 用途: 发送通知和邀请

6. **设置群名片**
   - API: `set_group_card`
   - 参数: `group_id`, `user_id`, `card`
   - 用途: 恢复成员名片

7. **设置群管理员**
   - API: `set_group_admin`
   - 参数: `group_id`, `user_id`, `enable`
   - 用途: 恢复管理员权限

## 数据库设计

### 表结构

#### groups (群组表)
- id: 主键
- group_id: QQ群号
- group_name: 群名称
- owner_id: 群主QQ
- member_count: 成员数
- max_member_count: 最大容量
- created_at: 创建时间
- updated_at: 更新时间

#### members (成员表)
- id: 主键
- group_id: 群号(外键)
- user_id: QQ号
- nickname: 昵称
- card: 群名片
- role: 角色(owner/admin/member)
- join_time: 加群时间
- last_sent_time: 最后发言时间
- level: 等级
- title: 专属头衔
- created_at: 记录创建时间
- updated_at: 记录更新时间

#### backups (备份记录表)
- id: 主键
- group_id: 群号(外键)
- backup_type: 备份类型(full/incremental)
- member_count: 备份成员数
- file_path: 备份文件路径
- created_at: 备份时间
- status: 备份状态(success/failed)
- notes: 备份备注

#### member_history (成员变更历史)
- id: 主键
- group_id: 群号
- user_id: QQ号
- action: 操作类型(join/leave)
- timestamp: 时间戳
- backup_id: 关联备份(外键)

## 实现计划

### 第一阶段: 核心功能开发
1. ✅ 项目结构设计
2. ⬜ OneBot客户端封装
   - HTTP/WebSocket连接
   - API调用封装
   - 事件监听
3. ⬜ 数据库模型设计
   - ORM配置(SQLAlchemy)
   - 模型定义
   - 迁移脚本
4. ⬜ 备份功能实现
   - 获取群成员列表
   - 数据持久化
   - 增量备份逻辑
5. ⬜ 重建功能实现
   - 批量邀请逻辑
   - 速率控制
   - 权限恢复

### 第二阶段: 自动化与优化
1. ⬜ 定时任务调度
2. ⬜ 异常处理与重试
3. ⬜ 日志和监控
4. ⬜ 配置管理优化
5. ⬜ 性能优化

### 第三阶段: Web界面(可选)
1. ⬜ FastAPI后端API
2. ⬜ Vue前端界面
3. ⬜ 实时数据展示
4. ⬜ 操作界面

### 第四阶段: 部署与文档
1. ⬜ Docker容器化
2. ⬜ 部署文档
3. ⬜ 使用说明
4. ⬜ API文档

## 配置示例

### config/config.yaml
```yaml
# OneBot配置
onebot:
  protocol: http  # http/websocket
  host: 127.0.0.1
  port: 5700
  access_token: ""
  
# 数据库配置
database:
  type: sqlite  # sqlite/postgresql
  sqlite:
    path: data/database/valhalla.db
  postgresql:
    host: localhost
    port: 5432
    database: valhalla
    user: postgres
    password: ""

# 备份配置
backup:
  auto_backup: true
  interval: 3600  # 秒
  backup_type: incremental  # full/incremental
  max_backups: 30  # 保留最近30次备份
  compression: true
  encryption: false

# 重建配置
rebuild:
  rate_limit:
    invites_per_minute: 10
    retry_delay: 60
  restore_admins: true
  restore_cards: true
  send_welcome: true

# 通知配置
notification:
  enabled: true
  email:
    smtp_host: ""
    smtp_port: 587
    username: ""
    password: ""
  qq:
    notify_groups: []
    notify_users: []
```

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置OneBot
- 安装并配置 go-cqhttp 或 NapCat
- 在 `config/config.yaml` 中填写连接信息

### 3. 初始化数据库
```bash
python -m src.models.database --init
```

### 4. 运行程序
```bash
python src/main.py
```

### 5. 执行备份
```bash
# 手动备份指定群组
python src/main.py backup --group 123456789

# 启动自动备份
python src/main.py auto-backup
```

### 6. 重建群组
```bash
# 从最新备份重建
python src/main.py rebuild --group 123456789 --target 987654321

# 从指定备份重建
python src/main.py rebuild --backup-id 42 --target 987654321
```

## 注意事项

1. **API限制**: 
   - 遵守QQ的API调用频率限制
   - 批量操作需要合理设置速率限制
   - 建议使用增量备份减少API调用

2. **权限要求**:
   - Bot需要是群主才能设置管理员
   - 普通管理员无法邀请所有成员
   - 某些操作需要特定权限

3. **风险提示**:
   - 批量邀请可能触发风控
   - 建议在测试群组先试用
   - 重要数据需要定期备份

4. **隐私保护**:
   - 备份数据包含敏感信息
   - 建议启用加密存储
   - 妥善保管配置文件

## 依赖项

主要Python依赖:
- `httpx` - HTTP客户端
- `websockets` - WebSocket客户端
- `sqlalchemy` - ORM
- `pydantic` - 数据验证
- `apscheduler` - 任务调度
- `pyyaml` - 配置文件解析
- `cryptography` - 加密功能
- `fastapi` - Web API (可选)
- `uvicorn` - ASGI服务器 (可选)

## 协议支持

### OneBot 11标准
- 完全兼容OneBot 11协议规范
- 支持HTTP和WebSocket通信
- 支持扩展API (go-cqhttp/NapCat)

### 推荐实现
1. **go-cqhttp**: 成熟稳定,功能完整
2. **NapCat**: 现代化实现,基于NTQQ

## 贡献

欢迎提交Issue和Pull Request!

## 许可证

MIT License

## 致谢

- [OneBot标准](https://github.com/botuniverse/onebot-11)
- [go-cqhttp](https://github.com/Mrs4s/go-cqhttp)
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ)
