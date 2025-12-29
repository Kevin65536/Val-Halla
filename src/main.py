"""
主程序入口
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.utils.config import get_config, config_manager
from src.utils.logger import setup_logger, get_logger
from src.api.onebot import OneBotAPI
from src.models import init_database, db_manager
from src.core.backup_manager import BackupManager
from src.core.rebuild_manager import RebuildManager


logger = get_logger(__name__)
console = Console()


def init_app():
    """初始化应用"""
    try:
        config = config_manager.load()
    except FileNotFoundError:
        console.print("[yellow]配置文件不存在，使用默认配置[/yellow]")
        from src.utils.config import Config
        config = Config()
    
    # 设置日志
    setup_logger(
        level=config.logging.level,
        log_file=config.logging.file,
        max_size=config.logging.max_size,
        backup_count=config.logging.backup_count,
        console=config.logging.console
    )
    
    # 初始化数据库
    init_database(config.database)
    
    return config


def create_client(config) -> OneBotAPI:
    """创建 OneBot 客户端"""
    return OneBotAPI(
        host=config.onebot.http.host,
        port=config.onebot.http.port,
        access_token=config.onebot.access_token,
        timeout=config.onebot.api_timeout
    )


@click.group()
@click.version_option(version="0.1.0", prog_name="Val-Halla")
def cli():
    """Val-Halla - QQ群成员自动备份与一键重建工具"""
    pass


@cli.command()
def status():
    """检查系统状态和连接"""
    config = init_app()
    client = create_client(config)
    
    async def check_status():
        console.print("\n[bold cyan]═══ Val-Halla 系统状态 ═══[/bold cyan]\n")
        
        # 检查 OneBot 连接
        with console.status("[bold green]正在检查 OneBot 连接..."):
            try:
                login_info = await client.get_login_info()
                version_info = await client.get_version_info()
                
                table = Table(title="OneBot 连接状态")
                table.add_column("项目", style="cyan")
                table.add_column("值", style="green")
                
                table.add_row("状态", "✅ 已连接")
                table.add_row("Bot QQ", str(login_info.get("user_id", "N/A")))
                table.add_row("Bot 昵称", login_info.get("nickname", "N/A"))
                table.add_row("OneBot 实现", version_info.get("app_name", "N/A"))
                table.add_row("版本", version_info.get("app_version", "N/A"))
                
                console.print(table)
                
            except Exception as e:
                console.print(f"[red]❌ OneBot 连接失败: {str(e)}[/red]")
                return
        
        # 获取群列表
        with console.status("[bold green]正在获取群列表..."):
            try:
                groups = await client.get_group_list()
                
                if groups:
                    table = Table(title=f"群列表 (共 {len(groups)} 个)")
                    table.add_column("群号", style="cyan")
                    table.add_column("群名称", style="green")
                    table.add_column("成员数", style="yellow")
                    
                    for g in groups[:10]:  # 最多显示10个
                        table.add_row(
                            str(g.get("group_id")),
                            g.get("group_name", "N/A"),
                            str(g.get("member_count", 0))
                        )
                    
                    if len(groups) > 10:
                        table.add_row("...", f"还有 {len(groups) - 10} 个群", "...")
                    
                    console.print(table)
                else:
                    console.print("[yellow]未加入任何群组[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]获取群列表失败: {str(e)}[/red]")
    
    asyncio.run(check_status())


@cli.command()
@click.argument("group_id", type=int)
@click.option("--no-cache", is_flag=True, help="不使用缓存")
def info(group_id: int, no_cache: bool):
    """查看群组详细信息"""
    config = init_app()
    client = create_client(config)
    
    async def get_info():
        console.print(f"\n[bold cyan]获取群 {group_id} 信息...[/bold cyan]\n")
        
        try:
            # 获取群信息
            group_info = await client.get_group_info(group_id, no_cache=no_cache)
            
            table = Table(title=f"群信息: {group_info.get('group_name', 'N/A')}")
            table.add_column("项目", style="cyan")
            table.add_column("值", style="green")
            
            table.add_row("群号", str(group_info.get("group_id")))
            table.add_row("群名称", group_info.get("group_name", "N/A"))
            table.add_row("成员数", str(group_info.get("member_count", 0)))
            table.add_row("最大成员数", str(group_info.get("max_member_count", 0)))
            
            console.print(table)
            
            # 获取成员列表
            members = await client.get_group_member_list(group_id, no_cache=no_cache)
            
            # 统计
            owners = [m for m in members if m.get("role") == "owner"]
            admins = [m for m in members if m.get("role") == "admin"]
            
            stats_table = Table(title="成员统计")
            stats_table.add_column("角色", style="cyan")
            stats_table.add_column("人数", style="green")
            
            stats_table.add_row("群主", str(len(owners)))
            stats_table.add_row("管理员", str(len(admins)))
            stats_table.add_row("普通成员", str(len(members) - len(owners) - len(admins)))
            stats_table.add_row("总计", str(len(members)))
            
            console.print(stats_table)
            
        except Exception as e:
            console.print(f"[red]获取信息失败: {str(e)}[/red]")
    
    asyncio.run(get_info())


@cli.command()
@click.argument("group_id", type=int)
@click.option("--type", "backup_type", type=click.Choice(["full", "incremental"]), default="full", help="备份类型")
@click.option("--note", default="", help="备份备注")
def backup(group_id: int, backup_type: str, note: str):
    """备份群成员"""
    config = init_app()
    client = create_client(config)
    
    backup_manager = BackupManager(
        client=client,
        backup_dir=config.backup.backup_dir,
        compression=config.backup.compression,
        encryption=config.backup.encryption
    )
    
    async def do_backup():
        console.print(f"\n[bold cyan]开始备份群 {group_id}...[/bold cyan]\n")
        
        try:
            from src.models.backup import BackupType
            bt = BackupType.FULL if backup_type == "full" else BackupType.INCREMENTAL
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("备份中...", total=None)
                
                result = await backup_manager.backup_group(group_id, bt, note)
                
                progress.update(task, completed=True)
            
            # 显示结果
            table = Table(title="备份完成")
            table.add_column("项目", style="cyan")
            table.add_column("值", style="green")
            
            table.add_row("备份ID", str(result.id))
            table.add_row("备份类型", result.backup_type)
            table.add_row("成员数", str(result.member_count))
            table.add_row("新增成员", str(result.new_members))
            table.add_row("退出成员", str(result.left_members))
            table.add_row("文件大小", f"{result.file_size} bytes")
            table.add_row("耗时", f"{result.duration:.2f}s" if result.duration else "N/A")
            
            console.print(table)
            console.print(f"\n[green]✅ 备份文件: {result.file_path}[/green]")
            
        except Exception as e:
            console.print(f"[red]❌ 备份失败: {str(e)}[/red]")
            logger.exception("备份异常")
    
    asyncio.run(do_backup())


@cli.command()
@click.argument("group_id", type=int)
@click.option("--limit", default=10, help="显示数量")
def history(group_id: int, limit: int):
    """查看备份历史"""
    config = init_app()
    client = create_client(config)
    
    backup_manager = BackupManager(
        client=client,
        backup_dir=config.backup.backup_dir
    )
    
    async def show_history():
        console.print(f"\n[bold cyan]群 {group_id} 备份历史[/bold cyan]\n")
        
        try:
            backups = await backup_manager.get_backup_history(group_id, limit)
            
            if not backups:
                console.print("[yellow]没有备份记录[/yellow]")
                return
            
            table = Table(title=f"备份历史 (共 {len(backups)} 条)")
            table.add_column("ID", style="cyan")
            table.add_column("类型", style="blue")
            table.add_column("状态", style="green")
            table.add_column("成员数", style="yellow")
            table.add_column("新增/退出", style="magenta")
            table.add_column("时间", style="white")
            
            for b in backups:
                status_color = "green" if b.status == "success" else "red"
                table.add_row(
                    str(b.id),
                    b.backup_type,
                    f"[{status_color}]{b.status}[/{status_color}]",
                    str(b.member_count),
                    f"+{b.new_members}/-{b.left_members}",
                    b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "N/A"
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]获取历史失败: {str(e)}[/red]")
    
    asyncio.run(show_history())


@cli.command()
@click.argument("backup_id", type=int)
@click.argument("target_group_id", type=int)
@click.option("--dry-run", is_flag=True, help="仅预览,不实际执行")
def rebuild(backup_id: int, target_group_id: int, dry_run: bool):
    """从备份重建群组"""
    config = init_app()
    client = create_client(config)
    
    rebuild_manager = RebuildManager(
        client=client,
        invites_per_minute=config.rebuild.rate_limit.invites_per_minute,
        restore_admins=config.rebuild.restore_admins,
        restore_cards=config.rebuild.restore_cards,
        restore_titles=config.rebuild.restore_titles,
        send_welcome=config.rebuild.send_welcome,
        welcome_message=config.rebuild.welcome_message,
    )
    
    backup_manager = BackupManager(client=client)
    
    async def do_rebuild():
        console.print(f"\n[bold cyan]从备份 {backup_id} 重建到群 {target_group_id}[/bold cyan]\n")
        
        try:
            # 获取备份成员
            members = await backup_manager.get_backup_members(backup_id)
            
            if not members:
                console.print("[red]备份中没有成员数据[/red]")
                return
            
            # 显示预览
            table = Table(title=f"将要恢复的成员 ({len(members)} 人)")
            table.add_column("QQ", style="cyan")
            table.add_column("昵称", style="green")
            table.add_column("名片", style="yellow")
            table.add_column("角色", style="magenta")
            
            for m in members[:20]:
                table.add_row(
                    str(m.user_id),
                    m.nickname or "N/A",
                    m.card or "-",
                    m.role
                )
            
            if len(members) > 20:
                table.add_row("...", f"还有 {len(members) - 20} 人", "...", "...")
            
            console.print(table)
            
            if dry_run:
                console.print("\n[yellow]预览模式，未实际执行[/yellow]")
                return
            
            # 确认
            if not click.confirm("\n确认执行重建?"):
                console.print("[yellow]已取消[/yellow]")
                return
            
            # 执行重建
            def progress_callback(progress):
                console.print(
                    f"\r进度: {progress.processed}/{progress.total} "
                    f"(成功:{progress.success} 失败:{progress.failed})",
                    end=""
                )
            
            result = await rebuild_manager.rebuild_from_backup(
                backup_id,
                target_group_id,
                progress_callback=progress_callback
            )
            
            console.print("\n")
            
            # 显示结果
            table = Table(title="重建完成")
            table.add_column("项目", style="cyan")
            table.add_column("值", style="green")
            
            table.add_row("状态", result.status.value)
            table.add_row("总计", str(result.total))
            table.add_row("成功", str(result.success))
            table.add_row("失败", str(result.failed))
            table.add_row("跳过", str(result.skipped))
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]重建失败: {str(e)}[/red]")
            logger.exception("重建异常")
    
    asyncio.run(do_rebuild())


@cli.command()
@click.argument("group_id", type=int)
@click.option("--format", "export_format", type=click.Choice(["json", "csv"]), default="json", help="导出格式")
@click.option("--output", "-o", default=None, help="输出文件路径")
def export(group_id: int, export_format: str, output: str):
    """导出群成员数据"""
    import json
    import csv
    
    config = init_app()
    client = create_client(config)
    
    async def do_export():
        console.print(f"\n[bold cyan]导出群 {group_id} 成员...[/bold cyan]\n")
        
        try:
            members = await client.get_group_member_list(group_id, no_cache=True)
            
            if not output:
                filename = f"export/members_{group_id}.{export_format}"
            else:
                filename = output
            
            if export_format == "json":
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(members, f, ensure_ascii=False, indent=2)
            else:
                with open(filename, 'w', encoding='utf-8', newline='') as f:
                    if members:
                        writer = csv.DictWriter(f, fieldnames=members[0].keys())
                        writer.writeheader()
                        writer.writerows(members)
            
            console.print(f"[green]✅ 已导出 {len(members)} 个成员到 {filename}[/green]")
            
        except Exception as e:
            console.print(f"[red]导出失败: {str(e)}[/red]")
    
    asyncio.run(do_export())


@cli.command()
@click.option("--host", default="0.0.0.0", help="监听地址")
@click.option("--port", default=8080, help="监听端口")
def webui(host: str, port: int):
    """启动 Web UI"""
    import uvicorn
    
    console.print(f"\n[bold cyan]═══ Val-Halla Web UI ═══[/bold cyan]\n")
    console.print(f"[green]✨ 启动 Web 界面...[/green]")
    console.print(f"[blue]📍 地址: http://{host}:{port}[/blue]")
    console.print(f"[yellow]💡 按 Ctrl+C 停止服务[/yellow]\n")
    
    uvicorn.run(
        "src.web.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()
