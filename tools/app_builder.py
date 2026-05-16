import sys
import shutil
from pathlib import Path

from utils import console, PerformanceTracker

if sys.stdout.encoding != "UTF-8":
    sys.stdout.reconfigure(encoding="utf-8")

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.version import __version__


def print_header(text):
    console.rule(f"[bold]{text}[/]")


def print_step(text):
    console.print(f"[*] {text}")


def print_success(text):
    console.print(f"[+] {text}", style="success")


def print_error(text):
    console.print(f"[-] {text}", style="error")


def print_warning(text):
    console.print(f"[!] {text}", style="warning")


class Builder:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.version = __version__

    def create_output_directory(self):
        print_step(f"创建输出目录: {self.output_dir}")
        try:
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print_success(f"输出目录已创建: {self.output_dir}")
            return True
        except Exception as e:
            print_error(f"创建输出目录失败: {e}")
            return False


class FullAppBuilder(Builder):
    def __init__(self, output_dir):
        super().__init__(output_dir)
        self.exe_dir = project_root / "dist"

    def check_dependencies(self):
        print_step("检查完整应用依赖项...")
        exe_file = self.exe_dir / "RefEquiv.exe"
        if not exe_file.exists():
            print_error(f"可执行文件不存在: {exe_file}")
            print_error("请先运行 'make pack' 生成可执行文件")
            return False
        print_success("所有依赖项检查通过")
        return True

    def copy_executable(self):
        print_step("复制可执行文件...")
        try:
            exe_file = self.exe_dir / "RefEquiv.exe"
            if exe_file.exists():
                shutil.copy2(exe_file, self.output_dir / exe_file.name)
            print_success("可执行文件复制完成")
            return True
        except Exception as e:
            print_error(f"复制可执行文件失败: {e}")
            return False


class BuildManager:
    def __init__(self):
        self.version = __version__
        self.dist_dir = project_root / "dist"

    def build_full_app(self):
        print_header(f"构建完整应用版本 (v{self.version})")
        full_app_dir = self.dist_dir / f"RefEquiv-v{self.version}"
        print_step("开始构建完整应用版本...")
        builder = Builder(full_app_dir)
        if not builder.create_output_directory():
            return False
        app_builder = FullAppBuilder(full_app_dir)
        if not app_builder.check_dependencies():
            print_error("缺少可执行文件，无法继续")
            return False
        if not app_builder.copy_executable():
            return False
        print_step("整合并复制README文件")
        try:
            root_readme = project_root / "README.md"
            if root_readme.exists():
                shutil.copy2(root_readme, full_app_dir / "README.md")
                print_success("README文件复制完成")
        except Exception as e:
            print_error(f"复制README文件失败: {e}")
        print_step("创建7z包")
        zip_path = self.dist_dir / f"RefEquiv-v{self.version}.7z"
        if not self.create_zip_package(full_app_dir, zip_path):
            return False
        print_header("完整应用版本构建完成！")
        console.print(f"输出目录: {full_app_dir}")
        console.print(f"7z包: {zip_path}")
        return True

    def check_7zip_availability(self):
        print_step("检查7zip可用性...")
        try:
            import subprocess
            result = subprocess.run(["7z", "--help"], capture_output=True, text=True)
            if result.returncode == 0:
                print_success("7zip可用")
                return True
            else:
                print_error("7zip不可用，请确保7zip已安装并添加到系统PATH中")
                return False
        except FileNotFoundError:
            print_error("7zip未找到，请确保7zip已安装并添加到系统PATH中")
            return False
        except Exception as e:
            print_error(f"检查7zip时出错: {e}")
            return False

    def create_zip_package(self, output_dir, zip_path):
        if not self.check_7zip_availability():
            return False
        print_step(f"创建分发包: {zip_path}")
        try:
            import subprocess
            cmd = [
                "7z",
                "a",
                "-t7z",
                "-mx=9",
                str(zip_path),
                str(output_dir) + "\\*",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                zip_size = zip_path.stat().st_size / 1024
                print_success(f"分发包创建完成: {zip_path} ({zip_size:.1f} KB)")
                return True
            else:
                print_error(f"7zip打包失败: {result.stderr}")
                return False
        except Exception as e:
            print_error(f"创建分发包失败: {e}")
            return False


def build_full_app():
    manager = BuildManager()
    return manager.build_full_app()


def main():
    print_header("RefEquiv 完整应用构建器")
    tracker = PerformanceTracker()
    try:
        result, performance = tracker.execute_with_timing(
            build_full_app, "构建完整应用版本"
        )
        tracker.add_record(performance)
        tracker.generate_report()
        return 0 if result else 1
    except Exception as e:
        console.rule("[bold red]💥 发生未知异常！[/]")
        console.print_exception(show_locals=True)
        console.print(f"异常类型: {type(e).__name__}")
        console.print(f"异常内容: {str(e)}")
        console.print("请联系开发者并附上以上异常信息以便排查问题", style="warning")
        return 1


if __name__ == "__main__":
    sys.exit(main())
