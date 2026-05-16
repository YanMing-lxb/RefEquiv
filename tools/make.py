"""
 =======================================================================
 ····Y88b···d88P················888b·····d888·d8b·······················
 ·····Y88b·d88P·················8888b···d8888·Y8P·······················
 ······Y88o88P··················88888b·d88888···························
 ·······Y888P··8888b···88888b···888Y88888P888·888·88888b·····d88b·······
 ········888······"88b·888·"88b·888·Y888P·888·888·888·"88b·d88P"88b·····
 ········888···d888888·888··888·888··Y8P··888·888·888··888·888··888·····
 ········888··888··888·888··888·888···"···888·888·888··888·Y88b·888·····
 ········888··"Y888888·888··888·888·······888·888·888··888··"Y88888·····
 ································································888·····
 ··························································Y8b·d88P·····
 ···························································"Y88P"······
 =======================================================================

 -----------------------------------------------------------------------
Author       : 焱铭
Date         : 2025-07-16 20:53:22 +0800
LastEditTime : 2025-07-16 20:53:53 +0800
Github       : https://github.com/YanMing-lxb/
FilePath     : /test454c/tools/make.py
Description  : 
 -----------------------------------------------------------------------
"""

import subprocess
import sys
from pathlib import Path

from utils import console, run_command

from config import __version__


def inswhl():
    console.print("📦 开始安装测试 test454c", style="status")

    uninstall_success = run_command(
        command=["uv", "pip", "uninstall", "test454c"],
        success_msg="旧版 test454c 卸载完成",
        error_msg="旧版 test454c 卸载失败",
        process_name="卸载旧版 test454c",
    )

    whl_files = list(Path("dist").glob("*.whl"))
    if not whl_files:
        raise FileNotFoundError("dist 目录中没有找到 .whl 文件")
    install_success = run_command(
        command=["uv", "pip", "install", str(whl_files[0])],
        success_msg="测试 test454c 安装完成",
        error_msg="测试 test454c 安装失败",
        process_name="安装测试版 test454c",
    )
    return uninstall_success and install_success


def upload():
    tag_name = f"v{__version__}"

    run_command(
        command=["git", "tag", tag_name],
        success_msg=f"标签 {tag_name} 创建成功",
        error_msg=f"标签 {tag_name} 创建失败",
        process_name="创建标签",
    )
    console.log(f"创建标签: {tag_name}")

    run_command(
        command=["git", "push", "origin", tag_name],
        success_msg=f"标签 {tag_name} 推送成功",
        error_msg=f"标签 {tag_name} 推送失败",
        process_name="推送标签",
    )
    console.log(f"推送标签: {tag_name}")

    console.log("成功上传标签和推送到远程仓库，发布到 github")


def main():
    targets = {
        "upload": upload,
        "inswhl": inswhl,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in targets:
        console.log(f"用法: {sys.argv[0]} <目标>")
        console.log("可用目标:", ", ".join(targets.keys()))
        sys.exit(1)

    target = sys.argv[1]
    try:
        targets[target]()
    except subprocess.CalledProcessError as e:
        console.log(f"执行命令时出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
