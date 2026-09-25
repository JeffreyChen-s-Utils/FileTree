"""Every text the window shows, per language (see ``file_tree.gui.i18n``)."""

from __future__ import annotations


def _cjk(html: str) -> str:
    """Join the source lines of Chinese HTML: a line break there would show up as a space between characters."""
    return "".join(line.strip() for line in html.splitlines())


EN: dict[str, str] = {
    "app_title": "FileTree",
    "about_text": "<h3>FileTree {version}</h3><p>See where your disk space goes.</p>"
                  "<p>MIT License · © 2026 JE-Chen</p>",
    # menus and actions
    "menu_file": "&File",
    "menu_export": "&Export",
    "menu_view": "&View",
    "menu_unit": "Size &unit",
    "menu_language": "&Language",
    "menu_help": "&Help",
    "action_open": "Choose folder…",
    "action_open_tip": "Pick a folder or drive to scan",
    "action_rescan": "Rescan",
    "action_rescan_tip": "Scan the same folder again to pick up changes",
    "action_stop": "Stop",
    "action_stop_tip": "Stop the scan that is running",
    "action_export_folders": "Folder list (CSV)…",
    "action_export_folders_tip": "Save every folder with its size, for Excel or other spreadsheets",
    "action_export_largest": "Largest files (CSV)…",
    "action_export_largest_tip": "Save the list of the largest files",
    "action_export_json": "Folder tree (JSON)…",
    "action_export_json_tip": "Save the folder tree for scripts and other programs",
    "action_trash": "Move to Recycle Bin",
    "action_trash_tip": "Move the selected file or folder to the Recycle Bin (you are asked first)",
    "action_quit": "Quit",
    "action_quit_tip": "Close FileTree",
    "action_hidden": "Include hidden files",
    "action_hidden_tip": "Count hidden files and folders (applies to the next scan)",
    "action_help": "How to use",
    "action_help_tip": "Short guide to FileTree",
    "action_about": "About FileTree",
    "action_about_tip": "Version and license",
    "unit_auto": "Automatic",
    "path_placeholder": "Type or paste a folder path and press Enter",
    "choose_folder_title": "Choose a folder to scan",
    # welcome page
    "welcome_title": "See where your disk space goes",
    "welcome_subtitle": "Pick a folder or a whole drive. FileTree adds up every file inside it and shows "
                        "you the biggest folders and files first.",
    "welcome_choose": "Choose a folder…",
    "welcome_drives": "Drives",
    "welcome_drive_tip": "Scan {path}",
    "welcome_drive_free": "{free} free of {total}",
    "welcome_recent": "Recently scanned",
    "welcome_tip": "Tip: you can also drag a folder from your file manager onto this window.",
    # scanning
    "scan_starting": "Starting…",
    "scan_progress": "Scanning… {files} files in {folders} folders · {size} · {time}",
    "scan_stop": "Stop",
    "scan_stopping": "Stopping…",
    "scan_cancelled": "Scan stopped.",
    "scan_stopped_partial": "Scan stopped: the results show what was read so far.",
    "scan_failed_title": "Cannot scan",
    "scan_failed": "FileTree could not read {path}.\n\nReason: {reason}",
    "not_a_folder": "{path} is not a folder that exists.",
    "duration_seconds": "{value} s",
    "duration_minutes": "{minutes} min {seconds} s",
    # results
    "summary": "<b>{path}</b> — {size} in {files} files and {folders} folders (scanned in {time})",
    "summary_live": "<b>{path}</b> — {size} in {files} files and {folders} folders so far",
    "summary_partial": "<b>{path}</b> — {size} in {files} files and {folders} folders · "
                       "<b>incomplete</b>: the scan was stopped after {time}",
    "tab_treemap": "Treemap",
    "tab_largest": "Largest files",
    "tab_types": "File types",
    "tab_problems": "Problems",
    "tab_problems_count": "Problems ({count})",
    "column_name": "Name",
    "column_size": "Size",
    "column_share": "% of parent",
    "column_share_total": "% of total",
    "column_files": "Files",
    "column_folders": "Folders",
    "column_modified": "Modified",
    "column_folder": "Folder",
    "column_extension": "Extension",
    "column_type": "Type",
    "column_path": "Path",
    "column_problem": "Problem",
    "no_extension": "(no extension)",
    "tooltip_unreadable": "{path}\nCould not be read: {reason}",
    "tooltip_link": "{path}\nLink: shown but not followed",
    "tooltip_not_scanned": "{path}\nNot scanned: the scan was stopped first",
    "treemap_empty": "Nothing to show",
    "treemap_up": "↑ Up",
    "treemap_up_tip": "Show the folder above",
    "treemap_tooltip": "<b>{name}</b><br>{size} ({share} of this view)<br>{path}",
    "largest_filter": "Filter by name or folder…",
    "types_all": "All types",
    "category_images": "Pictures",
    "category_video": "Videos",
    "category_audio": "Music and audio",
    "category_documents": "Documents",
    "category_archives": "Archives and disk images",
    "category_code": "Code and data",
    "category_programs": "Programs",
    "category_other": "Other",
    "status_selected": "{name}: {size} ({share} of its folder)",
    "status_selected_root": "{name}: {size}",
    # entry menu
    "menu_open_item": "Open",
    "menu_reveal": "Show in file manager",
    "menu_copy_path": "Copy path",
    "menu_show_treemap": "Show in treemap",
    "menu_scan_here": "Scan this folder",
    "trash_confirm_title": "Move to Recycle Bin",
    "trash_confirm": "Move “{name}” ({size}) to the Recycle Bin?\n\nYou can restore it from there.",
    "trash_failed": "“{name}” could not be moved to the Recycle Bin. It may be in use or read-only.",
    "trash_done": "Moved “{name}” to the Recycle Bin: {size} freed.",
    # export
    "export_title": "Export",
    "csv_filter": "CSV files (*.csv)",
    "json_filter": "JSON files (*.json)",
    "export_done": "Saved {count} rows to {path}",
    "export_failed": "The file could not be saved.\n\nReason: {reason}",
    # help
    "help_title": "How to use FileTree",
    "help_html": """
<h2>FileTree in three steps</h2>
<ol>
<li><b>Choose what to scan.</b> Click <i>Choose a folder…</i> or one of the drives, drag a folder
onto the window, or type a path in the box at the top and press Enter.</li>
<li><b>Watch it fill in.</b> The tree appears right away and the biggest folders move to the top
while FileTree adds up every file; the largest files and file types follow when the scan ends. Press
<i>Stop</i> (or Esc) at any time: what was read so far stays on screen, marked as incomplete.</li>
<li><b>Find what takes the space.</b> The biggest folders are at the top of the tree. Click the arrow
next to a folder to look inside.</li>
</ol>
<h2>Reading the results</h2>
<ul>
<li><b>Folder tree</b> (left): the size of each folder or file, a <i>% of parent</i> bar (how much of
the folder above it this entry takes), how many files and folders it holds, and when something in it
last changed. Click a column title to sort by it.</li>
<li><b>Treemap</b>: every file is a rectangle, and the bigger the file, the bigger the rectangle.
Colours show the file type (the legend is under the map). Click a rectangle to find it in the tree,
double-click to zoom into a folder, and press <i>Up</i> to zoom out again.</li>
<li><b>Largest files</b>: the 1,000 biggest files anywhere in the scan. Type in the filter box to
narrow the list; double-click a row to find the file in the tree.</li>
<li><b>File types</b>: how much space each kind of file takes, per extension. Pick a type in the list
above the table to see only that kind.</li>
<li><b>Problems</b>: folders FileTree was not allowed to read. What is inside them is not counted.</li>
</ul>
<h2>Freeing space</h2>
<p>Right-click any entry to <i>Open</i> it, <i>Show in file manager</i>, <i>Copy path</i>,
<i>Show in treemap</i>, <i>Scan this folder</i> on its own, or <i>Move to Recycle Bin</i>.
FileTree never deletes anything for good: it always asks first, and whatever it moves can be restored
from the Recycle Bin (the Trash on macOS and Linux). The numbers update right away, without a rescan.</p>
<h2>Keyboard shortcuts</h2>
<table cellpadding="3">
<tr><td><b>Ctrl+O</b></td><td>Choose a folder</td></tr>
<tr><td><b>F5</b></td><td>Rescan</td></tr>
<tr><td><b>Esc</b></td><td>Stop the scan</td></tr>
<tr><td><b>Delete</b></td><td>Move the selected entry to the Recycle Bin</td></tr>
<tr><td><b>F1</b></td><td>This guide</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
</table>
<p>On macOS use ⌘ instead of Ctrl (⌘R to rescan).</p>
<h2>Good to know</h2>
<ul>
<li>Sizes are the real file sizes in binary units (1 KB = 1,024 bytes), the same as Windows Explorer.
Choose a fixed unit under <i>View → Size unit</i>.</li>
<li>Shortcuts and links (symbolic links, junctions) are listed but never followed, so nothing is
counted twice.</li>
<li>Some system folders can only be read by an administrator; run FileTree as administrator to count
them too.</li>
<li>Hidden files are counted. Turn off <i>View → Include hidden files</i> to leave them out of the
next scan.</li>
<li>Save the results with <i>File → Export</i>: CSV opens in Excel, JSON is for scripts.</li>
</ul>
""",
}

ZH_TW: dict[str, str] = {
    "app_title": "FileTree",
    "about_text": "<h3>FileTree {version}</h3><p>看看磁碟空間都用到哪裡去了。</p>"
                  "<p>MIT 授權 · © 2026 JE-Chen</p>",
    "menu_file": "檔案(&F)",
    "menu_export": "匯出(&E)",
    "menu_view": "檢視(&V)",
    "menu_unit": "大小單位(&U)",
    "menu_language": "語言(&L)",
    "menu_help": "說明(&H)",
    "action_open": "選擇資料夾…",
    "action_open_tip": "選一個資料夾或磁碟來掃描",
    "action_rescan": "重新掃描",
    "action_rescan_tip": "再掃描一次同一個資料夾，取得最新的變動",
    "action_stop": "停止",
    "action_stop_tip": "停止正在進行的掃描",
    "action_export_folders": "資料夾清單（CSV）…",
    "action_export_folders_tip": "把每個資料夾和它的大小存成試算表，可用 Excel 開啟",
    "action_export_largest": "最大的檔案（CSV）…",
    "action_export_largest_tip": "把最大的檔案清單存起來",
    "action_export_json": "資料夾樹（JSON）…",
    "action_export_json_tip": "把資料夾樹存起來，給程式或其他軟體使用",
    "action_trash": "移到資源回收筒",
    "action_trash_tip": "把選取的檔案或資料夾移到資源回收筒（會先詢問）",
    "action_quit": "結束",
    "action_quit_tip": "關閉 FileTree",
    "action_hidden": "包含隱藏檔案",
    "action_hidden_tip": "把隱藏的檔案和資料夾也算進去（下次掃描時生效）",
    "action_help": "使用說明",
    "action_help_tip": "FileTree 的簡短使用說明",
    "action_about": "關於 FileTree",
    "action_about_tip": "版本與授權",
    "unit_auto": "自動",
    "path_placeholder": "輸入或貼上資料夾路徑，按 Enter 開始掃描",
    "choose_folder_title": "選擇要掃描的資料夾",
    "welcome_title": "看看磁碟空間都用到哪裡去了",
    "welcome_subtitle": "選一個資料夾或整顆磁碟，FileTree 會把裡面每個檔案的大小加總，"
                        "先列出最大的資料夾和檔案。",
    "welcome_choose": "選擇資料夾…",
    "welcome_drives": "磁碟",
    "welcome_drive_tip": "掃描 {path}",
    "welcome_drive_free": "可用 {free}，共 {total}",
    "welcome_recent": "最近掃描過",
    "welcome_tip": "小技巧：也可以直接把資料夾從檔案總管拖曳到這個視窗。",
    "scan_starting": "準備中…",
    "scan_progress": "正在掃描… {folders} 個資料夾中的 {files} 個檔案 · {size} · {time}",
    "scan_stop": "停止",
    "scan_stopping": "正在停止…",
    "scan_cancelled": "已停止掃描。",
    "scan_stopped_partial": "已停止掃描：結果只包含停止前讀到的部分。",
    "scan_failed_title": "無法掃描",
    "scan_failed": "FileTree 無法讀取 {path}。\n\n原因：{reason}",
    "not_a_folder": "{path} 不是存在的資料夾。",
    "duration_seconds": "{value} 秒",
    "duration_minutes": "{minutes} 分 {seconds} 秒",
    "summary": "<b>{path}</b> — {size}，共 {files} 個檔案、{folders} 個資料夾（掃描耗時 {time}）",
    "summary_live": "<b>{path}</b> — 目前 {size}，{files} 個檔案、{folders} 個資料夾",
    "summary_partial": "<b>{path}</b> — {size}，{files} 個檔案、{folders} 個資料夾 · "
                       "<b>不完整</b>：掃描在 {time} 後停止",
    "tab_treemap": "方塊圖",
    "tab_largest": "最大的檔案",
    "tab_types": "檔案類型",
    "tab_problems": "無法讀取",
    "tab_problems_count": "無法讀取（{count}）",
    "column_name": "名稱",
    "column_size": "大小",
    "column_share": "佔上層比例",
    "column_share_total": "佔總量比例",
    "column_files": "檔案數",
    "column_folders": "資料夾數",
    "column_modified": "修改時間",
    "column_folder": "所在資料夾",
    "column_extension": "副檔名",
    "column_type": "類型",
    "column_path": "路徑",
    "column_problem": "原因",
    "no_extension": "（沒有副檔名）",
    "tooltip_unreadable": "{path}\n無法讀取：{reason}",
    "tooltip_link": "{path}\n連結：只列出，不會跟進去計算",
    "tooltip_not_scanned": "{path}\n沒有掃描到：掃描在讀到這裡之前就停止了",
    "treemap_empty": "沒有可以顯示的內容",
    "treemap_up": "↑ 上一層",
    "treemap_up_tip": "顯示上一層資料夾",
    "treemap_tooltip": "<b>{name}</b><br>{size}（佔目前畫面的 {share}）<br>{path}",
    "largest_filter": "依名稱或資料夾篩選…",
    "types_all": "所有類型",
    "category_images": "圖片",
    "category_video": "影片",
    "category_audio": "音樂與音訊",
    "category_documents": "文件",
    "category_archives": "壓縮檔與映像檔",
    "category_code": "程式碼與資料",
    "category_programs": "應用程式",
    "category_other": "其他",
    "status_selected": "{name}：{size}（佔所在資料夾的 {share}）",
    "status_selected_root": "{name}：{size}",
    "menu_open_item": "開啟",
    "menu_reveal": "在檔案總管中顯示",
    "menu_copy_path": "複製路徑",
    "menu_show_treemap": "在方塊圖中顯示",
    "menu_scan_here": "只掃描這個資料夾",
    "trash_confirm_title": "移到資源回收筒",
    "trash_confirm": "要把「{name}」（{size}）移到資源回收筒嗎？\n\n之後仍可以從資源回收筒還原。",
    "trash_failed": "無法把「{name}」移到資源回收筒，可能正在使用中或是唯讀。",
    "trash_done": "已把「{name}」移到資源回收筒，釋出 {size}。",
    "export_title": "匯出",
    "csv_filter": "CSV 檔案 (*.csv)",
    "json_filter": "JSON 檔案 (*.json)",
    "export_done": "已把 {count} 列存到 {path}",
    "export_failed": "無法儲存檔案。\n\n原因：{reason}",
    "help_title": "FileTree 使用說明",
    "help_html": _cjk("""
<h2>三個步驟就會用</h2>
<ol>
<li><b>選擇要掃描的地方。</b>按<i>選擇資料夾…</i>或其中一顆磁碟，把資料夾拖曳到視窗上，
或在上方的方框輸入路徑後按 Enter。</li>
<li><b>邊掃邊看。</b>資料夾樹會立刻出現，FileTree 一邊加總，最大的資料夾一邊往上排；
最大的檔案與檔案類型在掃描結束時補上。
隨時可以按<i>停止</i>（或 Esc）：已經讀到的部分會留在畫面上，並標示為不完整。</li>
<li><b>找出佔空間的東西。</b>最大的資料夾排在最上面，按資料夾旁的箭頭就能看裡面的內容。</li>
</ol>
<h2>看懂結果</h2>
<ul>
<li><b>資料夾樹</b>（左邊）：每個資料夾或檔案的大小、<i>佔上層比例</i>長條（它佔上一層資料夾多少空間）、
裡面有幾個檔案和資料夾，以及裡面最近一次變動的時間。按欄位標題可以依該欄排序。</li>
<li><b>方塊圖</b>：每個檔案都是一個方塊，檔案越大、方塊越大；顏色代表檔案類型（圖例在方塊圖下方）。
按一下方塊可以在資料夾樹中找到它，按兩下可以放大到那個資料夾，按<i>上一層</i>再縮小回來。</li>
<li><b>最大的檔案</b>：整個掃描範圍內最大的 1,000 個檔案。在篩選框輸入文字可以縮小清單，
按兩下某一列就會在資料夾樹中找到那個檔案。</li>
<li><b>檔案類型</b>：各種檔案依副檔名各佔多少空間；在表格上方的清單選一種類型，就只顯示那一類。</li>
<li><b>無法讀取</b>：FileTree 沒有權限讀取的資料夾，裡面的內容不會算進去。</li>
</ul>
<h2>釋出空間</h2>
<p>在任何項目上按右鍵，可以<i>開啟</i>、<i>在檔案總管中顯示</i>、<i>複製路徑</i>、<i>在方塊圖中顯示</i>、
<i>只掃描這個資料夾</i>，或<i>移到資源回收筒</i>。FileTree 不會永久刪除任何東西：每次都會先詢問，
移走的東西都能從資源回收筒（macOS 與 Linux 是「垃圾桶」）還原。數字會立刻更新，不必重新掃描。</p>
<h2>鍵盤快速鍵</h2>
<table cellpadding="3">
<tr><td><b>Ctrl+O</b></td><td>選擇資料夾</td></tr>
<tr><td><b>F5</b></td><td>重新掃描</td></tr>
<tr><td><b>Esc</b></td><td>停止掃描</td></tr>
<tr><td><b>Delete</b></td><td>把選取的項目移到資源回收筒</td></tr>
<tr><td><b>F1</b></td><td>這份說明</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>結束</td></tr>
</table>
<p>在 macOS 上請用 ⌘ 取代 Ctrl（⌘R 是重新掃描）。</p>
<h2>小知識</h2>
<ul>
<li>大小是檔案的實際大小，以二進位單位計算（1 KB = 1,024 位元組），和 Windows 檔案總管相同；
可以在<i>檢視 → 大小單位</i>改用固定的單位。</li>
<li>捷徑與連結（符號連結、目錄連接）會列出來，但不會跟進去計算，所以不會重複計算。</li>
<li>有些系統資料夾只有系統管理員能讀取；用系統管理員身分執行 FileTree 就能一起計算。</li>
<li>預設會計算隱藏檔案；關掉<i>檢視 → 包含隱藏檔案</i>，下次掃描就不會算進去。</li>
<li>用<i>檔案 → 匯出</i>儲存結果：CSV 可用 Excel 開啟，JSON 給程式使用。</li>
</ul>
"""),
}

ZH_CN: dict[str, str] = {
    "app_title": "FileTree",
    "about_text": "<h3>FileTree {version}</h3><p>看看磁盘空间都用到哪里去了。</p>"
                  "<p>MIT 许可证 · © 2026 JE-Chen</p>",
    "menu_file": "文件(&F)",
    "menu_export": "导出(&E)",
    "menu_view": "视图(&V)",
    "menu_unit": "大小单位(&U)",
    "menu_language": "语言(&L)",
    "menu_help": "帮助(&H)",
    "action_open": "选择文件夹…",
    "action_open_tip": "选一个文件夹或磁盘来扫描",
    "action_rescan": "重新扫描",
    "action_rescan_tip": "再扫描一次同一个文件夹，获取最新的变动",
    "action_stop": "停止",
    "action_stop_tip": "停止正在进行的扫描",
    "action_export_folders": "文件夹列表（CSV）…",
    "action_export_folders_tip": "把每个文件夹和它的大小保存为表格，可用 Excel 打开",
    "action_export_largest": "最大的文件（CSV）…",
    "action_export_largest_tip": "保存最大的文件列表",
    "action_export_json": "文件夹树（JSON）…",
    "action_export_json_tip": "保存文件夹树，供脚本或其他软件使用",
    "action_trash": "移到回收站",
    "action_trash_tip": "把选中的文件或文件夹移到回收站（会先询问）",
    "action_quit": "退出",
    "action_quit_tip": "关闭 FileTree",
    "action_hidden": "包含隐藏文件",
    "action_hidden_tip": "把隐藏的文件和文件夹也算进去（下次扫描时生效）",
    "action_help": "使用说明",
    "action_help_tip": "FileTree 的简短使用说明",
    "action_about": "关于 FileTree",
    "action_about_tip": "版本与许可证",
    "unit_auto": "自动",
    "path_placeholder": "输入或粘贴文件夹路径，按 Enter 开始扫描",
    "choose_folder_title": "选择要扫描的文件夹",
    "welcome_title": "看看磁盘空间都用到哪里去了",
    "welcome_subtitle": "选一个文件夹或整个磁盘，FileTree 会把里面每个文件的大小加总，"
                        "先列出最大的文件夹和文件。",
    "welcome_choose": "选择文件夹…",
    "welcome_drives": "磁盘",
    "welcome_drive_tip": "扫描 {path}",
    "welcome_drive_free": "可用 {free}，共 {total}",
    "welcome_recent": "最近扫描过",
    "welcome_tip": "小技巧：也可以直接把文件夹从文件管理器拖到这个窗口。",
    "scan_starting": "准备中…",
    "scan_progress": "正在扫描… {folders} 个文件夹中的 {files} 个文件 · {size} · {time}",
    "scan_stop": "停止",
    "scan_stopping": "正在停止…",
    "scan_cancelled": "已停止扫描。",
    "scan_stopped_partial": "已停止扫描：结果只包含停止前读到的部分。",
    "scan_failed_title": "无法扫描",
    "scan_failed": "FileTree 无法读取 {path}。\n\n原因：{reason}",
    "not_a_folder": "{path} 不是存在的文件夹。",
    "duration_seconds": "{value} 秒",
    "duration_minutes": "{minutes} 分 {seconds} 秒",
    "summary": "<b>{path}</b> — {size}，共 {files} 个文件、{folders} 个文件夹（扫描用时 {time}）",
    "summary_live": "<b>{path}</b> — 目前 {size}，{files} 个文件、{folders} 个文件夹",
    "summary_partial": "<b>{path}</b> — {size}，{files} 个文件、{folders} 个文件夹 · "
                       "<b>不完整</b>：扫描在 {time} 后停止",
    "tab_treemap": "方块图",
    "tab_largest": "最大的文件",
    "tab_types": "文件类型",
    "tab_problems": "无法读取",
    "tab_problems_count": "无法读取（{count}）",
    "column_name": "名称",
    "column_size": "大小",
    "column_share": "占上级比例",
    "column_share_total": "占总量比例",
    "column_files": "文件数",
    "column_folders": "文件夹数",
    "column_modified": "修改时间",
    "column_folder": "所在文件夹",
    "column_extension": "扩展名",
    "column_type": "类型",
    "column_path": "路径",
    "column_problem": "原因",
    "no_extension": "（没有扩展名）",
    "tooltip_unreadable": "{path}\n无法读取：{reason}",
    "tooltip_link": "{path}\n链接：只列出，不会进入计算",
    "tooltip_not_scanned": "{path}\n没有扫描到：扫描在读到这里之前就停止了",
    "treemap_empty": "没有可以显示的内容",
    "treemap_up": "↑ 上一级",
    "treemap_up_tip": "显示上一级文件夹",
    "treemap_tooltip": "<b>{name}</b><br>{size}（占当前画面的 {share}）<br>{path}",
    "largest_filter": "按名称或文件夹筛选…",
    "types_all": "所有类型",
    "category_images": "图片",
    "category_video": "视频",
    "category_audio": "音乐与音频",
    "category_documents": "文档",
    "category_archives": "压缩包与镜像",
    "category_code": "代码与数据",
    "category_programs": "应用程序",
    "category_other": "其他",
    "status_selected": "{name}：{size}（占所在文件夹的 {share}）",
    "status_selected_root": "{name}：{size}",
    "menu_open_item": "打开",
    "menu_reveal": "在文件管理器中显示",
    "menu_copy_path": "复制路径",
    "menu_show_treemap": "在方块图中显示",
    "menu_scan_here": "只扫描这个文件夹",
    "trash_confirm_title": "移到回收站",
    "trash_confirm": "要把“{name}”（{size}）移到回收站吗？\n\n之后仍可以从回收站还原。",
    "trash_failed": "无法把“{name}”移到回收站，可能正在使用或是只读。",
    "trash_done": "已把“{name}”移到回收站，释放 {size}。",
    "export_title": "导出",
    "csv_filter": "CSV 文件 (*.csv)",
    "json_filter": "JSON 文件 (*.json)",
    "export_done": "已把 {count} 行保存到 {path}",
    "export_failed": "无法保存文件。\n\n原因：{reason}",
    "help_title": "FileTree 使用说明",
    "help_html": _cjk("""
<h2>三个步骤就会用</h2>
<ol>
<li><b>选择要扫描的地方。</b>点击<i>选择文件夹…</i>或其中一个磁盘，把文件夹拖到窗口上，
或在上方的输入框输入路径后按 Enter。</li>
<li><b>边扫边看。</b>文件夹树会立刻出现，FileTree 一边加总，最大的文件夹一边往上排；
最大的文件与文件类型在扫描结束时补上。
随时可以点<i>停止</i>（或按 Esc）：已经读到的部分会留在画面上，并标示为不完整。</li>
<li><b>找出占空间的东西。</b>最大的文件夹排在最上面，点文件夹旁的箭头就能看里面的内容。</li>
</ol>
<h2>看懂结果</h2>
<ul>
<li><b>文件夹树</b>（左边）：每个文件夹或文件的大小、<i>占上级比例</i>条（它占上一级文件夹多少空间）、
里面有几个文件和文件夹，以及里面最近一次变动的时间。点列标题可以按该列排序。</li>
<li><b>方块图</b>：每个文件都是一个方块，文件越大、方块越大；颜色代表文件类型（图例在方块图下方）。
单击方块可以在文件夹树中找到它，双击可以放大到那个文件夹，点<i>上一级</i>再缩小回来。</li>
<li><b>最大的文件</b>：整个扫描范围内最大的 1,000 个文件。在筛选框输入文字可以缩小列表，
双击某一行就会在文件夹树中找到那个文件。</li>
<li><b>文件类型</b>：各种文件按扩展名各占多少空间；在表格上方的列表选一种类型，就只显示那一类。</li>
<li><b>无法读取</b>：FileTree 没有权限读取的文件夹，里面的内容不会算进去。</li>
</ul>
<h2>释放空间</h2>
<p>在任何项目上点右键，可以<i>打开</i>、<i>在文件管理器中显示</i>、<i>复制路径</i>、<i>在方块图中显示</i>、
<i>只扫描这个文件夹</i>，或<i>移到回收站</i>。FileTree 不会永久删除任何东西：每次都会先询问，
移走的东西都能从回收站（macOS 与 Linux 是“废纸篓”）还原。数字会立刻更新，不必重新扫描。</p>
<h2>键盘快捷键</h2>
<table cellpadding="3">
<tr><td><b>Ctrl+O</b></td><td>选择文件夹</td></tr>
<tr><td><b>F5</b></td><td>重新扫描</td></tr>
<tr><td><b>Esc</b></td><td>停止扫描</td></tr>
<tr><td><b>Delete</b></td><td>把选中的项目移到回收站</td></tr>
<tr><td><b>F1</b></td><td>这份说明</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>退出</td></tr>
</table>
<p>在 macOS 上请用 ⌘ 代替 Ctrl（⌘R 是重新扫描）。</p>
<h2>小知识</h2>
<ul>
<li>大小是文件的实际大小，按二进制单位计算（1 KB = 1,024 字节），和 Windows 资源管理器相同；
可以在<i>视图 → 大小单位</i>改用固定的单位。</li>
<li>快捷方式与链接（符号链接、目录联接）会列出来，但不会进入计算，所以不会重复计算。</li>
<li>有些系统文件夹只有管理员能读取；以管理员身份运行 FileTree 就能一起计算。</li>
<li>默认会计算隐藏文件；关掉<i>视图 → 包含隐藏文件</i>，下次扫描就不会算进去。</li>
<li>用<i>文件 → 导出</i>保存结果：CSV 可用 Excel 打开，JSON 供脚本使用。</li>
</ul>
"""),
}

STRINGS: dict[str, dict[str, str]] = {"en": EN, "zh-TW": ZH_TW, "zh-CN": ZH_CN}
