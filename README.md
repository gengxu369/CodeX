# Disable Startup Apps Script (Windows)

这个仓库提供了一个 Python 脚本：`disable_startup_apps.py`，用于管理和禁用 Windows 的开机自启动软件。

## 功能

- 列出注册表与启动文件夹中的自启动项。
- 按关键字禁用指定启动项。
- 支持 `--all` 一键禁用所有发现的启动项。
- 支持 `--dry-run` 预演（只看结果，不做实际修改）。
- 禁用注册表项时会移动到 `Run-Disabled` 备份键，便于手动恢复。

## 使用方式

```bash
python disable_startup_apps.py --list
python disable_startup_apps.py QQ WeChat --dry-run
python disable_startup_apps.py QQ WeChat
python disable_startup_apps.py --all --dry-run
```

## 注意事项

- 仅支持 Windows。
- 如果涉及 `HKLM` 项，请使用管理员权限运行命令行。
- 建议先执行 `--dry-run` 确认目标，再进行实际禁用。
