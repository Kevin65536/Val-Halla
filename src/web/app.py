"""
Val-Halla Web UI 应用
FastAPI 后端 + Jinja2 模板前端
"""
import os
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.api.onebot import OneBotAPI
from src.core.backup_manager import BackupManager
from src.core.rebuild_manager import RebuildManager
from src.models.database import DatabaseManager
from src.models.backup import BackupType
from src.utils.logger import get_logger, setup_logger
from src.utils.config import config_manager

# 设置日志
setup_logger()
logger = get_logger(__name__)

# 应用实例
app = FastAPI(
    title="Val-Halla",
    description="QQ群成员自动备份与一键重建工具",
    version="1.0.0"
)

# 模板目录
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# 确保目录存在
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 全局状态
class AppState:
    def __init__(self):
        self.onebot: Optional[OneBotAPI] = None
        self.db: Optional[DatabaseManager] = None
        self.backup_manager: Optional[BackupManager] = None
        self.rebuild_manager: Optional[RebuildManager] = None
        self.config: Dict = {}
        self.connected: bool = False
        self.login_info: Dict = {}

state = AppState()


# ==================== 启动/关闭事件 ====================

@app.on_event("startup")
async def startup():
    """应用启动时初始化"""
    logger.info("Val-Halla WebUI 启动中...")
    
    # 加载配置
    try:
        state.config = config_manager.load()
    except FileNotFoundError:
        from src.utils.config import Config
        state.config = Config()
    
    # 初始化数据库 - 使用全局实例
    from src.models import db_manager
    db_manager.init_sqlite("data/database/valhalla.db")
    db_manager.create_tables()
    state.db = db_manager
    
    # 初始化 OneBot API
    onebot_cfg = state.config.onebot
    state.onebot = OneBotAPI(
        host=onebot_cfg.http.host,
        port=onebot_cfg.http.port,
        access_token=onebot_cfg.access_token,
        timeout=onebot_cfg.api_timeout
    )
    
    # 初始化管理器
    backup_cfg = state.config.backup
    state.backup_manager = BackupManager(
        client=state.onebot,
        backup_dir=backup_cfg.backup_dir,
        compression=backup_cfg.compression,
        encryption=backup_cfg.encryption
    )
    
    rebuild_cfg = state.config.rebuild
    state.rebuild_manager = RebuildManager(
        client=state.onebot,
        invites_per_minute=rebuild_cfg.rate_limit.invites_per_minute,
        restore_admins=rebuild_cfg.restore_admins,
        restore_cards=rebuild_cfg.restore_cards,
        restore_titles=rebuild_cfg.restore_titles
    )
    
    # 尝试连接
    await check_connection()
    
    logger.info("Val-Halla WebUI 启动完成")


@app.on_event("shutdown")
async def shutdown():
    """应用关闭时清理"""
    logger.info("Val-Halla WebUI 关闭中...")


async def check_connection():
    """检查 OneBot 连接状态"""
    try:
        info = await state.onebot.get_login_info()
        state.connected = True
        state.login_info = info
        logger.info(f"OneBot 连接成功: {info.get('nickname')}({info.get('user_id')})")
    except Exception as e:
        state.connected = False
        state.login_info = {}
        logger.warning(f"OneBot 连接失败: {e}")


# ==================== API 数据模型 ====================

class BackupRequest(BaseModel):
    group_id: int
    backup_type: str = "full"

class RebuildRequest(BaseModel):
    group_id: int  # 备份来源群号
    backup_id: int
    target_group_id: int = None  # 目标群号（可选，默认为来源群）
    restore_cards: bool = True
    restore_titles: bool = True
    restore_admins: bool = False
    dry_run: bool = True


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页/仪表盘"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "page": "dashboard"
    })


@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    """群组管理页面"""
    return templates.TemplateResponse("groups.html", {
        "request": request,
        "page": "groups"
    })


@app.get("/backups", response_class=HTMLResponse)
async def backups_page(request: Request):
    """备份历史页面"""
    return templates.TemplateResponse("backups.html", {
        "request": request,
        "page": "backups"
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """设置页面"""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "page": "settings"
    })


# ==================== API 路由 ====================

@app.get("/api/status")
async def api_status():
    """获取系统状态"""
    await check_connection()
    
    version_info = {}
    if state.connected:
        try:
            version_info = await state.onebot.get_version_info()
        except:
            pass
    
    return {
        "connected": state.connected,
        "login_info": state.login_info,
        "version_info": version_info,
        "config": {
            "host": state.config.onebot.http.host,
            "port": state.config.onebot.http.port
        }
    }


@app.get("/api/groups")
async def api_groups():
    """获取群列表"""
    if not state.connected:
        raise HTTPException(status_code=503, detail="OneBot 未连接")
    
    try:
        groups = await state.onebot.get_group_list()
        return {"groups": groups, "total": len(groups)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/groups/{group_id}")
async def api_group_info(group_id: int):
    """获取群详情"""
    if not state.connected:
        raise HTTPException(status_code=503, detail="OneBot 未连接")
    
    try:
        info = await state.onebot.get_group_info(group_id)
        members = await state.onebot.get_group_member_list(group_id)
        
        # 统计角色
        owner_count = sum(1 for m in members if m.get("role") == "owner")
        admin_count = sum(1 for m in members if m.get("role") == "admin")
        member_count = sum(1 for m in members if m.get("role") == "member")
        
        return {
            "info": info,
            "members": members,
            "stats": {
                "owner": owner_count,
                "admin": admin_count,
                "member": member_count,
                "total": len(members)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/groups/{group_id}/members")
async def api_group_members(group_id: int):
    """获取群成员列表"""
    if not state.connected:
        raise HTTPException(status_code=503, detail="OneBot 未连接")
    
    try:
        members = await state.onebot.get_group_member_list(group_id)
        return {"members": members, "total": len(members)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backup")
async def api_backup(req: BackupRequest, background_tasks: BackgroundTasks):
    """创建备份"""
    if not state.connected:
        raise HTTPException(status_code=503, detail="OneBot 未连接")
    
    try:
        # 将字符串转换为 BackupType 枚举
        backup_type = BackupType(req.backup_type) if req.backup_type else BackupType.FULL
        
        backup = await state.backup_manager.backup_group(
            req.group_id,
            backup_type=backup_type
        )
        return {
            "success": True,
            "backup_id": backup.id,
            "member_count": backup.member_count,
            "new_members": backup.new_members,
            "left_members": backup.left_members,
            "file_path": backup.file_path
        }
    except Exception as e:
        logger.error(f"备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backups")
async def api_backups(group_id: Optional[int] = None, limit: int = 50):
    """获取备份历史"""
    try:
        backups = await state.backup_manager.get_backup_history(
            group_id=group_id,
            limit=limit
        )
        # 转换为字典格式
        backups_data = [b.to_dict() for b in backups]
        return {"backups": backups_data, "total": len(backups_data)}
    except Exception as e:
        import traceback
        logger.error(f"获取备份历史失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backups/{backup_id}")
async def api_backup_detail(backup_id: int):
    """获取备份详情"""
    try:
        backup = await state.backup_manager.get_backup_detail(backup_id)
        if not backup:
            raise HTTPException(status_code=404, detail="备份不存在")
        return backup
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/backups/{backup_id}")
async def api_delete_backup(backup_id: int):
    """删除备份"""
    try:
        await state.backup_manager.delete_backup(backup_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rebuild")
async def api_rebuild(req: RebuildRequest):
    """执行群重建"""
    if not state.connected:
        raise HTTPException(status_code=503, detail="OneBot 未连接")
    
    try:
        # 如果未指定目标群，则使用备份来源群
        target_group_id = req.target_group_id or req.group_id
        
        result = await state.rebuild_manager.rebuild_group(
            group_id=req.group_id,  # 备份来源群
            target_group_id=target_group_id,  # 实际恢复到的目标群
            backup_id=req.backup_id,
            restore_cards=req.restore_cards,
            restore_titles=req.restore_titles,
            restore_admins=req.restore_admins,
            dry_run=req.dry_run
        )
        return result
    except Exception as e:
        logger.error(f"重建失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/{group_id}")
async def api_export(group_id: int, format: str = "json"):
    """导出群成员数据"""
    if not state.connected:
        raise HTTPException(status_code=503, detail="OneBot 未连接")
    
    try:
        members = await state.onebot.get_group_member_list(group_id)
        
        if format == "json":
            import json
            filename = f"members_{group_id}.json"
            filepath = Path("export") / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(members, f, ensure_ascii=False, indent=2)
            
            return FileResponse(
                filepath,
                filename=filename,
                media_type="application/json"
            )
        elif format == "csv":
            import csv
            filename = f"members_{group_id}.csv"
            filepath = Path("export") / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                if members:
                    writer = csv.DictWriter(f, fieldnames=members[0].keys())
                    writer.writeheader()
                    writer.writerows(members)
            
            return FileResponse(
                filepath,
                filename=filename,
                media_type="text/csv"
            )
        else:
            raise HTTPException(status_code=400, detail="不支持的格式")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 运行入口 ====================

def run_webui(host: str = "0.0.0.0", port: int = 8080):
    """运行 WebUI"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_webui()
