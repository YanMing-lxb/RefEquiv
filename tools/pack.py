import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding != "UTF-8":
    sys.stdout.reconfigure(encoding="utf-8")

from config import (
    DATA_DIR,
    ENTRY_POINT,
    ICON_FILE,
    PROJECT_NAME,
)


def run_pyinstaller():
    """使用 PyInstaller 打包为单个 exe 文件"""
    cmd = [
        "pyinstaller",
        "--name", PROJECT_NAME,
        "--onefile",  # 打包为单个 exe
        "--noconfirm",
        "--clean",
        "--console",  # 控制台程序
    ]
    
    # 添加图标
    if ICON_FILE.exists():
        cmd.extend(["--icon", str(ICON_FILE)])
    
    # 添加数据文件
    if DATA_DIR.exists():
        cmd.extend(["--add-data", f"{DATA_DIR}{os.pathsep}assets"])
    
    # 最后添加入口点
    cmd.append(str(ENTRY_POINT))
    
    print(f"执行 PyInstaller 命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("PyInstaller 打包成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        return False


def clean_up():
    """清理临时文件"""
    for item in ["build", "__pycache__"]:
        if Path(item).exists():
            shutil.rmtree(item)
            print(f"已删除: {item}")
    
    for spec_file in Path().glob("*.spec"):
        spec_file.unlink()
        print(f"已删除: {spec_file}")
    
    print("清理完成")


def main():
    parser = argparse.ArgumentParser(description="RefEquiv 制冷剂等效气相物性计算器 - 打包工具")
    parser.add_argument(
        "--clean", action="store_true", help="只清理临时文件"
    )
    
    args = parser.parse_args()
    
    if args.clean:
        clean_up()
        return
    
    print(f"开始打包 {PROJECT_NAME}...")
    
    # 打包
    success = run_pyinstaller()
    
    if success:
        print("\n打包完成！")
        exe_path = Path("dist") / f"{PROJECT_NAME}.exe"
        if exe_path.exists():
            print(f"可执行文件位置: {exe_path.resolve()}")
            print(f"文件大小: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
        clean_up()
    else:
        print("\n打包失败，请检查错误信息")


if __name__ == "__main__":
    main()
