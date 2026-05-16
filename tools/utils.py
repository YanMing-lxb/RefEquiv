import shutil
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

if sys.stdout.encoding != "UTF-8":
    sys.stdout.reconfigure(encoding="utf-8")

custom_theme = Theme({
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "bold blue",
    "status": "bold cyan",
    "time": "bold magenta",
})
console = Console(theme=custom_theme)


class PerformanceTracker:
    """
    用于跟踪和记录性能数据的类。
    """

    def __init__(self):
        self.records = []

    def add_record(self, performance_data: dict) -> None:
        self.records.append({
            "name": performance_data.get("name"),
            "duration": performance_data.get("duration"),
            "status": performance_data.get("status"),
        })

    def execute_with_timing(self, func: any, step_name: str) -> tuple:
        start_time = time.time()
        try:
            result = func()
            duration = time.time() - start_time
            status = "成功" if result else "失败"
            return result, {"name": step_name, "duration": duration, "status": status}
        except Exception as e:
            duration = time.time() - start_time
            console.print(f"❌ [{step_name}] 执行异常 - 耗时: {duration}, 错误: {str(e)}")
            return False, {"name": step_name, "duration": duration, "status": "异常"}

    def generate_report(self) -> None:
        table = Table(title="性能报告")
        table.add_column("步骤", justify="left", style="cyan")
        table.add_column("耗时(秒)", justify="right", style="magenta")
        table.add_column("状态", justify="center")
        total_time = sum(record["duration"] for record in self.records)
        for record in self.records:
            table.add_row(
                record["name"],
                f"{record['duration']:.2f}s",
                f"[{'green' if record['status'] == '成功' else 'red' if record['status'] == '失败' else 'yellow'}]{record['status']}[/]",
            )
        table.add_row("总耗时", f"{total_time:.2f}s", "")
        console.print(table)


def run_command(
    command: list,
    success_msg: str,
    error_msg: str,
    process_name: str = "执行命令",
    encoding: str = "utf-8",
) -> bool:
    try:
        console.print(f"[dim]执行命令: {' '.join(command)}[/]")
        start_time = time.time()
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding=encoding,
            errors="ignore",
        )
        with console.status(f"[status]正在{process_name}..."):
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break
                if output:
                    console.print(f"[dim]{output.strip()}[/]")
        if process.returncode == 0:
            duration = time.time() - start_time
            if duration > 60:
                format_duration = f"{duration // 60:.0f}m {duration % 60:.1f}s"
            else:
                format_duration = f"{duration:.2f}s"
            console.print(f"✓ {success_msg} [time](耗时: {format_duration})[/]", style="success")
            return True
        raise subprocess.CalledProcessError(process.returncode, command, f"退出码: {process.returncode}")
    except subprocess.CalledProcessError as e:
        console.print(f"✗ {error_msg}: {e}", style="error")
        return False


def delete_folder(folder_path):
    path = Path(folder_path)
    if not path.exists():
        print(f"⚠️ 文件夹不存在：{path}")
        return True
    try:
        shutil.rmtree(path)
        print(f"✓ 已删除文件夹：{path}")
        return True
    except Exception as e:
        print(f"✗ 删除失败：{e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "clean":
            delete_folder("dist")
