# FileTree

**See where your disk space goes.** FileTree scans a folder or a whole drive, adds up every file inside
it, and shows you the biggest folders and files first — in a folder tree, a colourful treemap and a list
of the largest files. When you find something you no longer need, move it to the Recycle Bin right from
the window.

[English](README.md) | [繁體中文](README/README_zh-TW.md) | [简体中文](README/README_zh-CN.md)

![FileTree showing a home folder: the folder tree on the left, the treemap on the right](docs/images/main_window_en.png)

## Features

- **One click to start**: pick a folder, click a drive, drag a folder onto the window, or paste a path.
- **Fast, and live**: several folders are read at once; about 740,000 files and folders are scanned in
  6–8 seconds on an SSD. The tree fills in while the scan runs, biggest folders first, and Stop keeps
  what was read so far.
- **Folder tree** sorted largest first, with a bar showing each entry's share of its folder, file and
  folder counts, and the last change inside it.
- **Treemap**: every file is a rectangle sized by how much space it takes, coloured by file type. Click to
  find it in the tree, double-click to zoom into a folder.
- **Largest files**: the 1,000 biggest files anywhere in the scan, with a filter box.
- **File types** and **Age**: space used per extension and kind (pictures, videos, archives…) and by when
  files last changed; double-click a row to list its largest files.
- **Free space safely**: *Move to Recycle Bin* always asks first and never deletes permanently; the
  numbers update immediately, without a rescan.
- **Export** the folder list or the largest files to CSV (opens in Excel), or the folder tree to JSON.
- **English, 繁體中文 and 简体中文**, switchable at any time; a built-in *How to use* guide.
- Links and junctions are listed but never followed, so nothing is counted twice and a link loop cannot
  trap a scan. Folders that cannot be read are listed under *Problems* instead of stopping the scan.

## Install

FileTree needs Python 3.10 or newer. It runs on Windows, macOS and Linux.

```bash
pip install git+https://github.com/JeffreyChen-s-Utils/FileTree.git
file-tree
```

Or run it from a copy of the source:

```bash
git clone https://github.com/JeffreyChen-s-Utils/FileTree.git
cd FileTree
pip install -r requirements.txt
python start_file_tree.py
```

`python -m file_tree` does the same.

### Build a stand-alone program

To give FileTree to someone without Python, compile it with Nuitka into a program folder or a single
`.exe`: see [nuitka.md](nuitka.md) for the commands and what each option does.

## How to use

1. **Choose what to scan**: click *Choose a folder…* or one of the drives on the start page, drag a
   folder onto the window, or type a path in the box at the top and press Enter. You can also start a
   scan from the command line: `file-tree D:\Projects` (or `python start_file_tree.py D:\Projects`).
2. **Watch it fill in**: the tree appears right away and the biggest folders move to the top while
   FileTree works; the largest files and file types follow when the scan ends. *Stop* (or Esc) ends the
   scan at any time and keeps what was read so far, marked as incomplete.
3. **Find what takes the space**: the biggest folders are at the top of the tree. Open a folder with the
   arrow next to it, or explore the treemap on the right.

### Reading the results

| Where | What it tells you |
|---|---|
| Folder tree | Size, *% of parent* (the share of the folder above), number of files and folders inside, last change |
| Treemap | One rectangle per file, sized by space used and coloured by file type; the legend is under the map |
| Largest files | The 1,000 biggest files; type in the filter box to narrow the list, double-click to find a file in the tree |
| File types | Space per extension; choose a kind above the table to see only that kind, double-click a row to list the largest files of that type |
| Age | Space by when files last changed (within a month … over two years ago); double-click a row to list its largest files |
| Problems | Folders FileTree was not allowed to read; their contents are not counted |

### Freeing space

Right-click any entry to open it, show it in your file manager, copy its path, show it in the treemap,
scan that folder on its own, or move it to the Recycle Bin (the Trash on macOS and Linux). FileTree always
asks before moving anything and never deletes permanently.

### Keyboard shortcuts

| Key | Action |
|---|---|
| Ctrl+O | Choose a folder |
| F5 | Rescan |
| Esc | Stop the scan |
| Delete | Move the selected entry to the Recycle Bin |
| F1 | How to use |
| Ctrl+Q | Quit |

On macOS use ⌘ instead of Ctrl (⌘R rescans).

### Good to know

- Sizes are real file sizes in binary units (1 KB = 1,024 bytes), the same as Windows Explorer. Pick a
  fixed unit under *View → Size unit*.
- On Windows, FileTree asks for administrator rights when it starts, like TreeSize, so it can read protected
  folders too. Say no and it runs normally; folders it could not read are listed under *Problems*, with a
  *Restart as administrator* button (also in the *File* menu). Turn the question off under
  *View → Ask for administrator rights at start*.
- Hidden files are counted. Turn off *View → Include hidden files* to leave them out of the next scan.
- Your language, size unit, window layout and recently scanned folders are remembered (on Windows in the
  registry under `HKEY_CURRENT_USER\Software\JE-Chen\FileTree`).

## Development

```bash
pip install -r dev_requirements.txt
python -m pytest
python -m ruff check .
python tools/make_screenshots.py
```

`tools/make_screenshots.py` redraws the README pictures from a made-up folder, in every language. The
code layout, the main flows and the design rules are described in [architecture.md](architecture.md).

## License

MIT — see [LICENSE](LICENSE).
