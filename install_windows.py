import os
import sys
import ctypes
import time
import winreg
import shutil
import struct
import psutil
import requests
import tempfile
import subprocess
import stat
import tkinter as tk
from tkinter import filedialog
from rich.console import Console
from rich.markdown import Markdown

# 当前版本号
current_version = "1.11"

# 存储反代服务器的URL
PROXY_URL = 'https://mirror.ghproxy.com/'

# 设置标准输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# x64 or x86 signatures and replacements
SIG_X64 = bytes(
    [0x48, 0x89, 0xCE, 0x48, 0x8B, 0x11, 0x4C, 0x8B, 0x41, 0x08, 0x49, 0x29, 0xD0, 0x48, 0x8B, 0x49, 0x18, 0xE8])
FIX_X64 = bytes(
    [0x48, 0x89, 0xCE, 0x48, 0x8B, 0x11, 0x4C, 0x8B, 0x41, 0x08, 0x49, 0x29, 0xD0, 0x48, 0x8B, 0x49, 0x18, 0xB8, 0x01,
     0x00, 0x00, 0x00])

SIG_X86 = bytes([0x89, 0xCE, 0x8B, 0x01, 0x8B, 0x49, 0x04, 0x29, 0xC1, 0x51, 0x50, 0xFF, 0x76, 0x0C, 0xE8])
FIX_X86 = bytes(
    [0x89, 0xCE, 0x8B, 0x01, 0x8B, 0x49, 0x04, 0x29, 0xC1, 0x51, 0x50, 0xFF, 0x76, 0x0C, 0xB8, 0x01, 0x00, 0x00, 0x00])


def scan_and_replace(buffer, pattern, replacement):
    index = 0
    while index < len(buffer):
        index = buffer.find(pattern, index)
        if index == -1:
            break
        buffer[index:index + len(replacement)] = replacement
        print(f'Found at 0x{index:08X}')
        index += len(replacement)


def patch_pe_file(file_path):
    try:
        save_path = file_path + ".bak"
        os.rename(file_path, save_path)
        print(f"已将原版备份在 : {save_path}")

        with open(save_path, 'rb') as file:
            pe_file = bytearray(file.read())

        if struct.calcsize("P") * 8 == 64:
            scan_and_replace(pe_file, SIG_X64, FIX_X64)
        else:
            scan_and_replace(pe_file, SIG_X86, FIX_X86)

        with open(file_path, 'wb') as output_file:
            output_file.write(pe_file)

        print("修补成功!")
    except Exception as e:
        print(f"发生错误: {e}")
        input("按 任意键 退出。")


def get_qq_exe_path():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="选择 QQ.exe 文件", filetypes=[("Executable files", "*.exe")])
    return file_path


def read_registry_key(hive, subkey, value_name):
    try:
        # 打开指定的注册表项
        key = winreg.OpenKey(hive, subkey)

        # 读取注册表项中指定名称的值
        value, _ = winreg.QueryValueEx(key, value_name)

        # 关闭注册表项
        winreg.CloseKey(key)

        return value
    except Exception as e:
        print(f"注册表读取失败: {e}")
        return None


def compare_versions(version1, version2):
    v1_parts = [int(part) for part in version1.split('.')]
    v2_parts = [int(part) for part in version2.split('.')]

    # 对比版本号的每个部分
    for i in range(max(len(v1_parts), len(v2_parts))):
        v1_part = v1_parts[i] if i < len(v1_parts) else 0
        v2_part = v2_parts[i] if i < len(v2_parts) else 0

        if v1_part < v2_part:
            return False
        elif v1_part > v2_part:
            return True

    return False  # 两个版本号相等


def check_for_updates():
    try:
        # 获取最新版本号
        response = requests.get("https://api.github.com/repos/Mzdyl/LiteLoaderQQNT_Install/releases/latest", timeout=3)
        latest_release = response.json()
        tag_name = latest_release['tag_name']
        body = latest_release['body']
        if compare_versions(tag_name, current_version):
            print(f"发现新版本 {tag_name}！开始自动更新")
            print(f"更新日志：\n ")
            console = Console()
            markdown = Markdown(body)
            console.print(markdown)
            download_url = (
                f"https://github.com/Mzdyl/LiteLoaderQQNT_Install/releases/download/{tag_name}/install_windows.exe")
            # urllib.request.urlretrieve(download_url, f"install_windows-{tag_name}.exe")
            download_file(download_url, f"install_windows-{tag_name}.exe", PROXY_URL)
            print("版本已更新，请重新运行最新脚本。")
            input("按任意键退出")
            sys.exit(0)
        else:
            print("当前已是最新版本，开始安装。")
    except Exception as e:
        print(f"检查更新阶段发生错误: {e}")


def get_qq_path():
    # 定义注册表路径和键名
    registry_hive = winreg.HKEY_LOCAL_MACHINE
    registry_subkey = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ"
    registry_value_name = "UninstallString"

    # 读取 UninstallString 信息
    uninstall_string = read_registry_key(registry_hive, registry_subkey, registry_value_name)
    if uninstall_string is None:
        print('无法通过注册表读取 QQNT 的安装目录，请手动选择')
        qq_exe_path = get_qq_exe_path()
    else:
        if os.path.exists(uninstall_string):
            qq_exe_path = uninstall_string.replace("Uninstall.exe", "QQ.exe")
            print(f"QQNT 的安装目录为: {qq_exe_path}")
        else:
            print("系统 QQNT 的安装路径不存在，请手动选择.")
            qq_exe_path = get_qq_exe_path()

    return qq_exe_path


def can_connect_to_github():
    try:
        response = requests.get('https://github.com', timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def download_file(url, filename, proxy_url=None):
    if not can_connect_to_github() and proxy_url:
        proxy_url = proxy_url + url  # 将代理地址和要下载的文件 URL 拼接在一起
        response = requests.get(proxy_url, timeout=10)
    else:
        response = requests.get(url, timeout=10)

    with open(filename, 'wb') as file:
        file.write(response.content)


def download_and_install_liteloader(file_path):
    # 获取Windows下的临时目录
    temp_dir = tempfile.gettempdir()
    print(f"临时目录：{temp_dir}")

    # 使用urllib下载最新版本的仓库
    print("正在拉取最新版本的仓库…")
    zip_url = "https://github.com/LiteLoaderQQNT/LiteLoaderQQNT/archive/master.zip"
    zip_path = os.path.join(temp_dir, "LiteLoader.zip")
    download_file(zip_url, zip_path, PROXY_URL)

    shutil.unpack_archive(zip_path, os.path.join(temp_dir, "LiteLoader"))

    print("拉取完成，正在安装 LiteLoaderQQNT")

    print(f"Moving from: {os.path.join(temp_dir, 'LiteLoader', 'LiteLoaderQQNT-main')}")
    print(f"Moving to: {os.path.join(file_path, 'resources', 'app')}")

    # 遍历LiteLoaderQQNT_bak目录下的所有目录和文件，更改为可写权限
    for root, dirs, files in os.walk(os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT_bak'), topdown=False):
        # 更改文件权限
        for name in files:
            path = os.path.join(root, name)
            os.chmod(path, stat.S_IWRITE)
        # 更改目录权限
        for name in dirs:
            path = os.path.join(root, name)
            os.chmod(path, stat.S_IWRITE)
    # 移除目标路径及其内容
    shutil.rmtree(os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT_bak'), ignore_errors=True)

    source_dir = os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT-main')
    destination_dir = os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT_bak')

    if os.path.exists(source_dir):
        os.rename(source_dir, destination_dir)
        print(f"已将旧版重命名为: {destination_dir}")
    else:
        print(f" {source_dir} 不存在，全新安装。")

    shutil.move(os.path.join(temp_dir, 'LiteLoader', 'LiteLoaderQQNT-main'),
                os.path.join(file_path, 'resources', 'app'))


def prepare_for_installation(qq_exe_path):
    # 检测是否安装过旧版 Liteloader
    file_path = os.path.dirname(qq_exe_path)
    package_file_path = os.path.join(file_path, 'resources', 'app', 'package.json')
    replacement_line = '"main": "./app_launcher/index.js"'
    target_line = '"main": "./LiteLoader"'
    with open(package_file_path, 'r') as file:
        content = file.read()
    if target_line in content:
        print("检测到安装过旧版，执行复原 package.json")
        content = content.replace(target_line, replacement_line)
        with open(package_file_path, 'w') as file:
            file.write(content)
        print(f"成功替换目标行: {target_line} -> {replacement_line}")
        print("请根据需求自行删除 LiteloaderQQNT 0.x 版本本体以及 LITELOADERQQNT_PROFILE 环境变量以及对应目录")
    else:
        print(f"未安装过旧版，全新安装")

    bak_file_path = qq_exe_path + ".bak"
    if os.path.exists(bak_file_path):
        os.remove(bak_file_path)
        print(f"已删除备份文件: {bak_file_path}")
    else:
        print("备份文件不存在，无需删除。")


def copy_old_files(file_path):
    old_plugins_path = os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT_bak', 'plugins')
    new_liteloader_path = os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT-main')
    # 复制 LiteLoader_bak 中的插件到新的 LiteLoader 目录
    if os.path.exists(old_plugins_path):
        shutil.copytree(old_plugins_path, os.path.join(new_liteloader_path, "plugins"), dirs_exist_ok=True)
        print("已将 LiteLoader_bak 中旧插件 Plugins 复制到新的 LiteLoader 目录")
    # 复制 LiteLoader_bak 中的数据文件到新的 LiteLoader 目录
    old_data_path = os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT_bak', 'data')
    if os.path.exists(old_data_path):
        shutil.copytree(old_data_path, os.path.join(new_liteloader_path, "data"), dirs_exist_ok=True)
        print("已将 LiteLoader_bak 中旧数据文件 data 复制到新的 LiteLoader 目录")


def patch_index_js(file_path):
    app_launcher_path = os.path.join(file_path, "resources", "app", "app_launcher")
    os.chdir(app_launcher_path)
    print("开始修补 index.js…")
    index_path = os.path.join(app_launcher_path, "index.js")
    # 备份原文件
    print("已将旧版文件备份为 index.js.bak ")
    bak_index_path = index_path + ".bak"
    shutil.copyfile(index_path, bak_index_path)
    with open(index_path, "w", encoding='utf-8') as f:
        f.write(f"require('{os.path.join(file_path, 'resources', 'app', 'LiteLoaderQQNT-main').replace(os.sep, '/')}');\n")
        f.write("require('./launcher.node').load('external_index', module);")


def check_and_kill_qq(process_name):
    try:
        for proc in psutil.process_iter():
            # 检查进程是否与指定的名称匹配
            if proc.name() == process_name:
                print(f"找到进程 {process_name}，将于3秒后尝试关闭...")
                time.sleep(3)
                proc.kill()
                print(f"进程 {process_name} 已关闭。")

    except Exception as e:
        print(f"关闭进程 {process_name} 时出错: {e}")


def change_folder_permissions(folder_path, user, permissions):
    try:
        cmd = ['icacls', folder_path, '/grant', f'{user}:{permissions}', '/t']
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        print(f"成功修改文件夹 {folder_path} 的权限。")
    except subprocess.CalledProcessError as e:
        print(f"修改文件夹权限时出错: {e}")


def main():
    try:
        check_for_updates()
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("推荐使用管理员运行")
        check_and_kill_qq("QQ.exe")
        qq_exe_path = get_qq_path()
        file_path = os.path.dirname(qq_exe_path)
        prepare_for_installation(qq_exe_path)
        if os.path.exists(os.path.join(qq_exe_path, 'dbghelp.dll')):
            print("检测到dbghelp.dll，推测你已修补QQ，跳过修补")
        else:
            patch_pe_file(qq_exe_path)
        download_and_install_liteloader(file_path)
        copy_old_files(file_path)
        patch_index_js(file_path)
        print("LiteLoaderQQNT 安装完成！插件商店作者不维护删库了，安装到此结束")
        
        # 检测是否在 GitHub Actions 中运行
        github_actions = os.getenv("GITHUB_ACTIONS", False)

        if not github_actions:
            print("按 回车键 退出…")
            input("如有问题请截图安装界面反馈")

    except Exception as e:
        print(f"发生错误: {e}")
        input("按 任意键 退出。")


if __name__ == "__main__":
    main()
    
