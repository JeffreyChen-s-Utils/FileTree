# FileTree

**快速找出磁盘空间都被什么占用了。**

FileTree 会扫描文件夹或磁盘，列出最占空间的文件与文件夹。
通过文件夹树、彩色矩形图和最大文件列表，帮你决定哪些要保留、哪些可以清理。

[English](../README.md) | [繁體中文](README_zh-TW.md) | [简体中文](README_zh-CN.md) | [日本語](README_ja.md) | [한국어](README_ko.md)

![FileTree：左侧显示文件夹大小，右侧用矩形图呈现空间分布](../docs/images/main_window_zh-CN.png)

## 可以做什么

- **找出大文件、大文件夹**：从最大的项目开始看，用图表了解空间占比。
- **搜索与筛选**：按名称、类型、大小或修改时间查找文件。
- **查看清理建议**：检查缓存、临时文件和重复文件，再决定是否处理。
- **找出变大的文件夹**：比较前后两次扫描，看看空间增加在哪里。
- **导出报告**：将结果保存为 CSV、JSON 或 Excel。
- **切换语言**：支持英语、繁体中文、简体中文、日语和韩语。

## 安装

### Windows：无需安装 Python

1. 到 [Releases](https://github.com/JeffreyChen-s-Utils/FileTree/releases) 下载 `FileTree-<version>-windows-standalone.zip`。
2. **完整解压** ZIP 文件。
3. 运行文件夹内的 `FileTree.exe`，其他文件请一起保留。

也提供 MSI 安装程序，可通过 Windows 安装。

### Windows、macOS、Linux：使用 Python

需要 **Python 3.10 或更新版本**：

```bash
python -m pip install je_file_tree
je-file-tree
```

Windows 可以用 `py -3` 代替 `python`。
从源码运行或编译成独立程序，请看[完整说明](../docs/guide_zh-CN.md)和[编译指南](../nuitka.zh-CN.md)。

## 开始使用

1. **选择文件夹或磁盘**，也可以直接把文件夹拖进窗口。
2. **等待扫描完成**，查看最大的文件夹和文件。图上的矩形越大，表示占用空间越多。
3. **确认不需要的项目**，右键 → **移到回收站**。程序会先询问确认。

扫描过程中可以随时停止；已读取的结果会保留，并标记为不完整。

## 使用前了解这些就好

- 文件移到回收站后，**要清空回收站才会释放空间**。
- 清理建议需要自行检查。后台监视默认关闭，也不会自动清理。
- 没有读取权限的文件夹会列在**无法读取**标签页中，里面的内容不会计入总大小。
- 扫描不会跟随符号链接或目录联接。文件大小与实际占用磁盘空间可能不同。
- Windows 启动时可能询问管理员权限；拒绝后仍可扫描有权限读取的文件夹。
- 清空回收站、将重复文件改成硬链接等高级操作，有各自的确认步骤与影响；使用前请看[完整说明](../docs/guide_zh-CN.md)。

## 常用快捷键

| 按键 | 功能 |
|---|---|
| Ctrl+O | 选择文件夹 |
| F5 | 重新扫描 |
| Esc | 停止扫描 |
| Ctrl+F | 搜索 |
| Delete | 将选中项目移到回收站 |
| F1 | 打开帮助 |
| Ctrl+Q | 退出程序 |

macOS 请用 ⌘ 代替 Ctrl，重新扫描则用 ⌘R。

## 更多说明

- [完整使用说明与技术细节](../docs/guide_zh-CN.md)：所有功能、命令行示例、设置与限制。
- [编译指南](../nuitka.zh-CN.md)：用 Nuitka 创建独立程序。
- [核心 API](../docs/core-api.md)和[项目架构](../architecture.md)：集成或开发 FileTree。
- [更新记录](../docs/updates/README.md)：功能变更与验证记录。

## 许可证

[MIT](../LICENSE)。
