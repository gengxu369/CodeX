#!/usr/bin/env python3
"""Disable startup applications on Windows.

Features:
- List startup entries from registry and Startup folders.
- Disable selected entries by name keyword, or disable all discovered entries.
- Creates backups under HKCU/HKLM Run-Disabled and renames Startup files to *.disabled.

Run as Administrator if you want to modify HKLM entries.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

if platform.system() == "Windows":
    import winreg


@dataclass
class StartupEntry:
    source: str
    location: str
    name: str
    command: str


REGISTRY_LOCATIONS: List[Tuple[str, str, str]] = [
    ("HKCU", r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", "user_run"),
    ("HKLM", r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", "machine_run"),
]


def is_admin() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _open_root(root_name: str):
    return winreg.HKEY_CURRENT_USER if root_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE


def get_registry_entries() -> List[StartupEntry]:
    entries: List[StartupEntry] = []
    for root_name, key_path, label in REGISTRY_LOCATIONS:
        try:
            with winreg.OpenKey(_open_root(root_name), key_path, 0, winreg.KEY_READ) as key:
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    name, value, _ = winreg.EnumValue(key, i)
                    entries.append(
                        StartupEntry(
                            source="registry",
                            location=f"{root_name}\\{key_path}",
                            name=name,
                            command=str(value),
                        )
                    )
        except FileNotFoundError:
            continue
        except PermissionError:
            print(f"[WARN] 无权限读取 {root_name}\\{key_path}")
    return entries


def get_startup_folders() -> List[Path]:
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("PROGRAMDATA")
    folders = []
    if appdata:
        folders.append(Path(appdata) / r"Microsoft\\Windows\\Start Menu\\Programs\\Startup")
    if programdata:
        folders.append(Path(programdata) / r"Microsoft\\Windows\\Start Menu\\Programs\\StartUp")
    return folders


def get_startup_folder_entries() -> List[StartupEntry]:
    entries: List[StartupEntry] = []
    for folder in get_startup_folders():
        if not folder.exists():
            continue
        for item in folder.iterdir():
            if item.is_file() and not item.name.endswith(".disabled"):
                entries.append(
                    StartupEntry(
                        source="startup_folder",
                        location=str(folder),
                        name=item.name,
                        command=str(item),
                    )
                )
    return entries


def list_entries() -> List[StartupEntry]:
    if platform.system() != "Windows":
        raise RuntimeError("该脚本仅支持 Windows。")
    return get_registry_entries() + get_startup_folder_entries()


def should_disable(entry: StartupEntry, keywords: List[str], disable_all: bool) -> bool:
    if disable_all:
        return True
    haystack = f"{entry.name} {entry.command}".lower()
    return any(k.lower() in haystack for k in keywords)


def disable_registry_entry(entry: StartupEntry, dry_run: bool) -> None:
    root_name, relative = entry.location.split("\\", 1)
    backup_key_path = relative + "-Disabled"
    root = _open_root(root_name)

    if dry_run:
        print(f"[DRY-RUN] registry: {entry.location} | {entry.name}")
        return

    with winreg.OpenKey(root, relative, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as src:
        value, value_type = winreg.QueryValueEx(src, entry.name)
        winreg.DeleteValue(src, entry.name)

    backup_key = winreg.CreateKeyEx(root, backup_key_path, 0, winreg.KEY_SET_VALUE)
    with backup_key:
        winreg.SetValueEx(backup_key, entry.name, 0, value_type, value)

    print(f"[OK] 已禁用注册表启动项: {entry.name}")


def disable_startup_file(entry: StartupEntry, dry_run: bool) -> None:
    src = Path(entry.command)
    dst = src.with_suffix(src.suffix + ".disabled")
    if dry_run:
        print(f"[DRY-RUN] file: {src} -> {dst}")
        return

    shutil.move(str(src), str(dst))
    print(f"[OK] 已禁用启动文件: {src.name}")


def disable_entries(entries: List[StartupEntry], dry_run: bool) -> None:
    for entry in entries:
        try:
            if entry.source == "registry":
                disable_registry_entry(entry, dry_run)
            else:
                disable_startup_file(entry, dry_run)
        except PermissionError:
            print(f"[WARN] 无权限修改: {entry.name} ({entry.location})")
        except FileNotFoundError:
            print(f"[WARN] 目标不存在，已跳过: {entry.name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="禁用 Windows 开机自启动软件")
    parser.add_argument("keywords", nargs="*", help="按关键字匹配要禁用的启动项名称/路径")
    parser.add_argument("--all", action="store_true", help="禁用所有发现的启动项")
    parser.add_argument("--dry-run", action="store_true", help="仅显示操作，不实际修改")
    parser.add_argument("--list", action="store_true", help="仅列出启动项")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        entries = list_entries()
    except RuntimeError as exc:
        print(exc)
        return 1

    if args.list:
        if not entries:
            print("未发现开机启动项。")
            return 0
        for i, e in enumerate(entries, start=1):
            print(f"[{i}] {e.source} | {e.name} | {e.command}")
        return 0

    if not args.all and not args.keywords:
        print("请提供关键字，或者使用 --all。可先使用 --list 查看启动项。")
        return 1

    target_entries = [e for e in entries if should_disable(e, args.keywords, args.all)]
    if not target_entries:
        print("没有匹配到可禁用的启动项。")
        return 0

    if any(e.location.startswith("HKLM") for e in target_entries) and not is_admin():
        print("[WARN] 包含 HKLM 启动项，建议以管理员身份运行以确保可修改。")

    disable_entries(target_entries, args.dry_run)
    print(f"完成，共处理 {len(target_entries)} 项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
