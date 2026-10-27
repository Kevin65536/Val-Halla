"""
Val-Halla Web UI 应用
FastAPI 后端 + Jinja2 模板前端
"""
import io
import hashlib
from contextlib import asynccontextmanager
from typing import Literal
import qrcode
import qrcode.image.svg
from starlette.middleware.trustedhost import TrustedHostMiddleware
from src.application import initialize, create_client
from src.runtime.napcat import NapCatRuntime, ManagementError
from src.runtime.connection import ConnectionService
from src.utils.config import PROJECT_ROOT, project_path
from pathlib import Path
from typing import Optional, Dict

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.api.onebot import OneBotAPI
from src.core.backup_manager import BackupManager
from src.core.rebuild_manager import RebuildManager
from src.models.database import DatabaseManager
from src.models.backup import BackupType
from src.utils.logger import get_logger, setup_logger

# 设置日志
setup_logger()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app):
    await startup()
    try:
        yield
    finally:
        await shutdown()


# 应用实例
app = FastAPI(lifespan=lifespan,
    title="Val-Halla",
    description="QQ群成员备份与信息恢复工具",
    version="2.0.0"
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver", "[::1]"])


@app.middleware("http")
async def local_requests(request: Request, call_next):
    # Local lifecycle/mutation endpoints must not accept cross-site browser requests.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if origin and origin != expected:
            return JSONResponse({"detail": "不接受跨站操作"}, status_code=403)
        if request.method != "DELETE" and request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "需要 application/json 请求"}, status_code=415)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


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
        self.runtime = None
        self.connection = None
        self.connected: bool = False
        self.login_info: Dict = {}

state = AppState()


# ==================== 启动/关闭事件 ====================

async def startup():
    state.config = initialize()
    from src.models import db_manager
    state.db = db_manager
    state.onebot = create_client(state.config)
    state.runtime = NapCatRuntime(state.config)
    state.connection = ConnectionService(state.config, state.onebot, state.runtime)
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
    
    logger.info("Val-Halla WebUI 启动完成")


async def shutdown():
    await state.onebot.close()
    await state.runtime.close()
    await state.db.close()


async def check_connection(force=False):
    result = await state.connection.check(force=force)
    state.connected = result["connected"]
    state.login_info = result["login_info"]
    return result


async def require_connection():
    result = await check_connection(force=True)
    if not result["connected"]:
        raise HTTPException(status_code=503, detail=result["message"])


# ==================== API 数据模型 ====================

class BackupRequest(BaseModel):
    group_id: int = Field(gt=0)
    backup_type: Literal["full", "incremental"] = "full"

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
    return templates.TemplateResponse(request, "index.html", {
        "page": "dashboard"
    })


@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    """群组管理页面"""
    return templates.TemplateResponse(request, "groups.html", {
        "page": "groups"
    })


@app.get("/backups", response_class=HTMLResponse)
async def backups_page(request: Request):
    """备份历史页面"""
    return templates.TemplateResponse(request, "backups.html", {
        "page": "backups"
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """设置页面"""
    return templates.TemplateResponse(request, "settings.html", {
        "page": "settings"
    })


# ==================== API 路由 ====================

@app.get("/api/health")
async def health():
    return {"app": "Val-Halla", "project": hashlib.sha256(str(PROJECT_ROOT).encode()).hexdigest()[:16],
            "version": "2.0.0", "runtime": state.config.runtime.mode}


@app.get("/api/status")
async def api_status():
    return await check_connection()


@app.post("/api/runtime/start")
async def runtime_start():
    try:
        result = await state.runtime.start()
        state.connection.invalidate()
        return result
    except (ManagementError, OSError) as error:
        raise HTTPException(409, str(error)) from error


@app.post("/api/runtime/refresh-qr")
async def runtime_refresh():
    try:
        await state.runtime.refresh_qrcode()
        state.connection.invalidate()
        return {"success": True}
    except Exception as error:
        raise HTTPException(503, "刷新二维码失败，请检查 NapCat 登录状态。") from error


@app.post("/api/runtime/quick-login")
async def runtime_quick_login():
    try:
        await state.runtime.quick_login()
        state.connection.invalidate()
        return {"success": True}
    except Exception as error:
        raise HTTPException(503, "快速登录失败，请改用扫码登录。") from error


@app.get("/api/runtime/qrcode")
async def runtime_qrcode():
    try:
        value = await state.runtime.qrcode()
        output = io.BytesIO()
        qrcode.make(value, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=4).save(output)
        return Response(output.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
    except Exception as error:
        raise HTTPException(503, "二维码暂不可用，请刷新登录状态。") from error


@app.get("/api/groups")
async def api_groups():
    """获取群列表"""
    await require_connection()
    
    try:
        groups = await state.onebot.get_group_list()
        return {"groups": groups, "total": len(groups)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/groups/{group_id}")
async def api_group_info(group_id: int):
    """获取群详情"""
    await require_connection()
    
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
    await require_connection()
    
    try:
        members = await state.onebot.get_group_member_list(group_id)
        return {"members": members, "total": len(members)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backup")
async def api_backup(req: BackupRequest):
    """创建备份"""
    await require_connection()
    
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
async def api_backups(group_id: Optional[int] = None, limit: int = Query(50, ge=1, le=1000)):
    """获取备份历史"""
    try:
        backups = await state.backup_manager.get_backup_history(
            group_id=group_id,
            limit=limit
        )
        # 转换为字典格式
        backups_data = [b.to_dict() for b in backups]
        from sqlalchemy import select, func
        from src.models.backup import Backup
        query = select(func.count()).select_from(Backup)
        if group_id is not None:
            query = query.where(Backup.group_id == group_id)
        async with state.db.get_async_session() as session:
            total = (await session.execute(query)).scalar_one()
        return {"backups": backups_data, "total": total}
    except Exception as e:
        import traceback
        logger.error(f"获取备份历史失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/archived-groups")
async def archived_groups():
    """Filter historical snapshots even when QQ is offline or the account left a group."""
    from sqlalchemy import select
    from src.models import Group, Backup
    async with state.db.get_async_session() as session:
        groups = (await session.execute(select(Group).join(Backup, Backup.group_id == Group.group_id).distinct())).scalars().all()
        return {"groups": [{"group_id": group.group_id, "group_name": group.group_name} for group in groups]}


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


@app.get("/api/backups/{backup_id}/download")
async def download_backup(backup_id: int):
    from sqlalchemy import select
    from src.models.backup import Backup
    async with state.db.get_async_session() as session:
        backup = (await session.execute(select(Backup).where(Backup.id == backup_id))).scalar_one_or_none()
        if not backup or backup.status != "success" or not backup.file_path:
            raise HTTPException(404, "备份文件不存在")
        path = project_path(backup.file_path).resolve()
        root = project_path(state.config.backup.backup_dir).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, "备份文件不存在")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/api/backups/{backup_id}/changes")
async def api_backup_changes(backup_id: int):
    """获取备份的成员变动明细"""
    try:
        return await state.backup_manager.get_backup_changes(backup_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    await require_connection()
    
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
    await require_connection()
    
    try:
        members = await state.onebot.get_group_member_list(group_id)
        
        if format == "json":
            import json
            filename = f"members_{group_id}.json"
            filepath = project_path("export") / filename
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
            filepath = project_path("export") / filename
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

def run_webui(host: str = "127.0.0.1", port: int = 8080):
    """运行 WebUI"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_webui()
