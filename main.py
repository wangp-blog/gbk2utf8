import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import threading
import webbrowser
import re
import tkinter.font as tkFont

# 常见的文本和代码文件扩展名
TEXT_FILE_EXTENSIONS = {
    '.txt', '.log', '.csv', '.json', '.xml', '.html', '.htm', '.css', '.js', 
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.go', 
    '.rs', '.swift', '.kt', '.kts', '.sql', '.md', '.rst', '.yaml', '.yml', 
    '.ini', '.cfg', '.toml', '.sh', '.bat', '.ps1'
}

# --- 乱码检测字典 ---
CORRUPTED_WORDS = ['锟斤拷', '烫烫烫', '屯屯屯']
MISREAD_PATTERNS = ['鍐堝瓨', '涓枃', '閿欒', '鏂囦欢', '浠ｇ爜', '鐩綍', '鏁版嵁', '缂栬瘧', '鍙傛暟', '杩斿洖', '锘匡']

class EncodingConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("编码处理工具)")
        master.geometry("1000x780")

        # ===== 字体缩放支持 =====
        self.font_size = 12
        self.min_font_size = 8
        self.max_font_size = 24

        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.text_font = tkFont.nametofont("TkTextFont")
        self.fixed_font = tkFont.nametofont("TkFixedFont")

        self.update_font_size()

        master.bind_all("<Control-MouseWheel>", self.on_ctrl_mousewheel)
        master.bind_all("<Control-Button-4>", self.on_ctrl_mousewheel_linux)
        master.bind_all("<Control-Button-5>", self.on_ctrl_mousewheel_linux)

        # UI 布局 - 设置区
        tk.Label(master, text="选择根文件夹:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.folder_path_var = tk.StringVar()
        self.folder_entry = tk.Entry(master, textvariable=self.folder_path_var, width=60)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=10, sticky='ew')
        self.browse_button = tk.Button(master, text="浏览", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=10, pady=10)

        tk.Label(master, text="排除目录 (如: .git, boost):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.exclude_folders_var = tk.StringVar()
        self.exclude_folders_var.set(".git, node_modules, __pycache__, build, dist, boost, google")
        self.exclude_entry = tk.Entry(master, textvariable=self.exclude_folders_var, width=60)
        self.exclude_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # UI 布局 - 按钮控制区 (使用 Frame 水平排列)
        btn_frame = tk.Frame(master)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=15)

        self.btn_scan_mojibake = tk.Button(btn_frame, text="🔍 1. 全量扫描乱码", command=lambda: self.start_task(self.task_scan_mojibake), bg="#FF9800", fg="white", width=20)
        self.btn_scan_mojibake.pack(side=tk.LEFT, padx=10)

        self.btn_scan_gbk = tk.Button(btn_frame, text="🔍 2. 仅扫描 GBK 文件", command=lambda: self.start_task(self.task_scan_gbk), bg="#2196F3", fg="white", width=20)
        self.btn_scan_gbk.pack(side=tk.LEFT, padx=10)

        self.btn_convert = tk.Button(btn_frame, text="🚀 3. 安全转换 GBK 为 UTF8", command=lambda: self.start_task(self.task_convert), bg="#4CAF50", fg="white", width=24)
        self.btn_convert.pack(side=tk.LEFT, padx=10)

        # UI 布局 - 日志区
        tk.Label(master, text="处理日志:").grid(row=3, column=0, padx=10, pady=0, sticky='w')
        self.log_text = scrolledtext.ScrolledText(master, wrap=tk.WORD, height=20)
        self.log_text.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky='nsew')
        self.log_text.config(state=tk.DISABLED)


        master.grid_rowconfigure(4, weight=1)
        master.grid_columnconfigure(1, weight=1)

        # 匹配中文及其全角标点，用于确保 GBK 转换的绝对精准 (安全转换用)
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef]')


    def update_font_size(self):
        self.default_font.configure(size=self.font_size)
        self.text_font.configure(size=self.font_size)
        self.fixed_font.configure(size=self.font_size)

        if hasattr(self, "log_text"):
            self.log_text.configure(font=("Microsoft YaHei UI", self.font_size))

        if hasattr(self, "font_label"):
            self.font_label.config(text=f"字体: {self.font_size}px")

    def on_ctrl_mousewheel(self, event):
        self.font_size += 1 if event.delta > 0 else -1
        self.font_size = max(self.min_font_size, min(self.max_font_size, self.font_size))
        self.update_font_size()

    def on_ctrl_mousewheel_linux(self, event):
        if event.num == 4:
            self.font_size += 1
        elif event.num == 5:
            self.font_size -= 1

        self.font_size = max(self.min_font_size, min(self.max_font_size, self.font_size))
        self.update_font_size()

    # ================= 基础日志与状态管理 =================
    def log(self, message):
        self.master.after(0, self._log_safe, message)

    def _log_safe(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path_var.set(os.path.normpath(folder))

    def set_ui_state(self, state):
        self.browse_button.config(state=state)
        self.btn_scan_mojibake.config(state=state)
        self.btn_scan_gbk.config(state=state)
        self.btn_convert.config(state=state)
        if state == tk.DISABLED:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete('1.0', tk.END)
            self.log_text.config(state=tk.DISABLED)

    def start_task(self, target_func):
        path = self.folder_path_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showerror("错误", "请选择正确的文件夹路径")
            return
        
        self.set_ui_state(tk.DISABLED)
        threading.Thread(target=target_func, args=(path,), daemon=True).start()

    # ================= 统一的文件遍历生成器 (核心逻辑共享) =================
    def _get_files_generator(self, base_folder):
        """遍历文件夹，严格执行用户设置的排除规则，并 yield 返回每个文件信息"""
        raw_excludes = self.exclude_folders_var.get().split(',')
        exclude_keywords = [x.strip().replace('/', os.sep).replace('\\', os.sep) for x in raw_excludes if x.strip()]

        for root, dirs, files in os.walk(base_folder, topdown=True):
            rel_root = os.path.relpath(root, base_folder)
            
            path_parts = rel_root.split(os.sep)
            if any(key in path_parts or key in rel_root for key in exclude_keywords if key != '.'):
                dirs[:] = [] 
                continue

            for f in files:
                if any(f.lower().endswith(ext) for ext in TEXT_FILE_EXTENSIONS):
                    yield os.path.join(root, f), os.path.relpath(os.path.join(root, f), base_folder)

    # ================= 辅助函数 =================
    def _format_line_numbers(self, lines):
        if not lines: return ""
        if len(lines) > 10:
            return f"第 {', '.join(map(str, lines[:8]))} ... 等共 {len(lines)} 行"
        return f"第 {', '.join(map(str, lines))} 行"

    # ================= 功能 1：全量乱码扫描 =================
    def _analyze_mojibake(self, file_path):
        try:
            with open(file_path, 'rb') as f: raw_bytes = f.read()
        except Exception as e:
            return 'ERROR', f"无法读取: {e}", []

        if not raw_bytes or b'\x00' in raw_bytes: return 'OK', "", []

        is_utf8_strict = True
        try: raw_bytes.decode('utf-8', errors='strict')
        except: is_utf8_strict = False

        is_gbk_strict = True
        try: raw_bytes.decode('gb18030', errors='strict')
        except: is_gbk_strict = False

        raw_lines = raw_bytes.split(b'\n')
        corrupted_lines, mixed_lines, ansi_lines, misread_lines = [], [], [], []

        for i, line_b in enumerate(raw_lines):
            line_num = i + 1
            is_corrupted = False
            if b'\xef\xbf\xbd' in line_b:
                corrupted_lines.append(line_num)
                is_corrupted = True
            else:
                line_u = line_b.decode('utf-8', errors='replace')
                line_g = line_b.decode('gb18030', errors='replace')
                for word in CORRUPTED_WORDS:
                    if word in line_u or word in line_g:
                        corrupted_lines.append(line_num)
                        is_corrupted = True
                        break
            if is_corrupted: continue

            if not is_utf8_strict and not is_gbk_strict:
                fails_u = fails_g = False
                try: line_b.decode('utf-8', errors='strict')
                except: fails_u = True
                try: line_b.decode('gb18030', errors='strict')
                except: fails_g = True
                if fails_u and fails_g: mixed_lines.append(line_num)

            if is_gbk_strict and not is_utf8_strict:
                try: line_b.decode('utf-8', errors='strict')
                except: ansi_lines.append(line_num)

            if is_utf8_strict:
                line_g_forced = line_b.decode('gb18030', errors='replace')
                for p in MISREAD_PATTERNS:
                    if p in line_g_forced:
                        misread_lines.append(line_num)
                        break

        if corrupted_lines: return 'CORRUPTED', "物理损坏(死胡同乱码或固化占位符)", corrupted_lines
        if mixed_lines: return 'MIXED', "编码混合(包含无法用任何标准解析的非法字节)", mixed_lines
        if is_gbk_strict and not is_utf8_strict: return 'TRUE_ANSI', "旧式ANSI(GBK)编码", ansi_lines or [1]
        if misread_lines: return 'MISREAD', "视错觉(易被编辑器误判的UTF-8特征)", misread_lines

        return 'OK', "", []

    def task_scan_mojibake(self, base_folder):
        self.log(f"🔍 [乱码扫描] 开始深度分析目录: {base_folder}\n" + "="*60)
        results = {'CORRUPTED': [], 'MIXED': [], 'MISREAD': [], 'TRUE_ANSI': []}
        total = 0

        for full_path, rel_path in self._get_files_generator(base_folder):
            total += 1
            status, reason, line_nums = self._analyze_mojibake(full_path)
            
            if status in results:
                results[status].append((rel_path, reason, line_nums))
                if status in ['CORRUPTED', 'MIXED', 'TRUE_ANSI']:
                    icon = '🚨' if status == 'CORRUPTED' else ('💥' if status == 'MIXED' else '⚠️')
                    self.log(f"[{icon}] {rel_path}\n    -> {reason} ({self._format_line_numbers(line_nums)})")

        self.log("="*60 + "\n扫描完毕统计报告：")
        self.log(f"共检查文件: {total} 个")
        self.log(f"🚨 彻底损坏: {len(results['CORRUPTED'])} 个")
        self.log(f"💥 混合字节: {len(results['MIXED'])} 个")
        self.log(f"⚠️ 旧式GBK : {len(results['TRUE_ANSI'])} 个 (建议转换)")
        self.log(f"👀 视错觉 : {len(results['MISREAD'])} 个 (安全UTF-8，忽略即可)")

        self.master.after(0, lambda: self.set_ui_state(tk.NORMAL))
        messagebox.showinfo("完成", f"乱码扫描完毕，共发现 {len(results['CORRUPTED']) + len(results['MIXED'])} 个损坏文件。")

    # ================= 功能 2：仅扫描 GBK 文件 =================
    def _is_gbk_file(self, file_path):
        try:
            with open(file_path, 'rb') as f: raw_bytes = f.read()
        except: return False
        
        if not raw_bytes or b'\x00' in raw_bytes: return False

        try: 
            raw_bytes.decode('ascii', errors='strict')
            return False # 纯英文
        except: pass

        try:
            raw_bytes.decode('utf-8', errors='strict')
            return False # 纯 UTF-8
        except: pass

        try:
            raw_bytes.decode('gb18030', errors='strict')
            return True # 是 GBK!
        except: return False

    def task_scan_gbk(self, base_folder):
        self.log(f"🔍 [GBK排查] 开始扫描纯 GBK/ANSI 文件: {base_folder}\n" + "="*60)
        gbk_files = []
        total = 0

        for full_path, rel_path in self._get_files_generator(base_folder):
            total += 1
            if self._is_gbk_file(full_path):
                gbk_files.append(rel_path)
                self.log(f"[⚠️ 发现 GBK 文件] {rel_path}")

        self.log("="*60 + f"\n扫描完毕！共检查 {total} 个文件。")
        if gbk_files:
            self.log(f"🚨 共揪出 {len(gbk_files)} 个 GBK(ANSI) 编码的文件！可以点击转换按钮进行处理。")
        else:
            self.log("🎉 恭喜！没有发现任何 GBK 编码的文件。")

        self.master.after(0, lambda: self.set_ui_state(tk.NORMAL))
        messagebox.showinfo("完成", f"GBK 扫描完毕，发现 {len(gbk_files)} 个 GBK 文件。")

    # ================= 功能 3：保守安全转换 =================
    def _detect_convert_target(self, file_path):
        try:
            with open(file_path, 'rb') as f: raw_bytes = f.read()
            if not raw_bytes or b'\x00' in raw_bytes or raw_bytes.startswith(b'\xef\xbb\xbf'): return False
            try:
                raw_bytes.decode('utf-8', errors='strict')
                return False
            except: pass
            
            gbk_text = raw_bytes.decode('gbk', errors='strict')
            if self.chinese_pattern.search(gbk_text):
                return True
            return False
        except: return False

    def task_convert(self, base_folder):
        self.log(f"🚀 [安全转换] 启动防御型转换流程: {base_folder}\n" + "="*60)
        converted, skipped, errors = 0, 0, 0

        for full_path, rel_path in self._get_files_generator(base_folder):
            if self._detect_convert_target(full_path):
                try:
                    self.log(f"[🟢 锁定 GBK 文件] 转换中: {rel_path}")
                    with open(full_path, 'r', encoding='gbk', errors='strict') as fr: content = fr.read()
                    
                    temp_path = full_path + ".tmp_convert"
                    with open(temp_path, 'w', encoding='utf-8') as fw: fw.write(content)
                    os.replace(temp_path, full_path)
                    
                    converted += 1
                    self.log(f"   └── ✅ 成功！")
                except Exception as e:
                    self.log(f"   └── ❌ 失败: {e}")
                    errors += 1
                    if os.path.exists(full_path + ".tmp_convert"): os.remove(full_path + ".tmp_convert")
            else:
                skipped += 1

        self.log("="*60)
        report = (f"✨ 转换任务结束！\n"
                  f"✅ 成功提取并转换 GBK: {converted} 个\n"
                  f"⏭️ 已安全跳过 (UTF-8/纯英文/西欧乱码): {skipped} 个\n"
                  f"❌ 处理失败: {errors} 个")
        self.log(report)
        self.master.after(0, lambda: self.set_ui_state(tk.NORMAL))
        messagebox.showinfo("转换完毕", report)

if __name__ == "__main__":
    root = tk.Tk()
    app = EncodingConverterApp(root)
    root.mainloop()
