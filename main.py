import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import chardet
import threading
import webbrowser
import re

# 常见的文本和代码文件扩展名
TEXT_FILE_EXTENSIONS = {
    '.txt', '.log', '.csv', '.json', '.xml', '.html', '.htm', '.css', '.js', 
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.go', 
    '.rs', '.swift', '.kt', '.kts', '.sql', '.md', '.rst', '.yaml', '.yml', 
    '.ini', '.cfg', '.toml', '.sh', '.bat', '.ps1'
}

class EncodingConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("GBK 转 UTF-8 工具 (最终强化版)")
        master.geometry("650x550")

        # UI 布局
        tk.Label(master, text="选择根文件夹:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.folder_path_var = tk.StringVar()
        self.folder_entry = tk.Entry(master, textvariable=self.folder_path_var, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=10, sticky='ew')
        self.browse_button = tk.Button(master, text="浏览", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=10, pady=10)

        tk.Label(master, text="排除关键字 (如: .git, boost):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.exclude_folders_var = tk.StringVar()
        self.exclude_folders_var.set(".git, node_modules, __pycache__, build, dist, boost, google")
        self.exclude_entry = tk.Entry(master, textvariable=self.exclude_folders_var, width=50)
        self.exclude_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        self.convert_button = tk.Button(master, text="🚀 开始扫描并转换", command=self.start_conversion_thread, bg="#4CAF50", fg="white")
        self.convert_button.grid(row=2, column=0, columnspan=3, pady=15)

        tk.Label(master, text="处理日志:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
        self.log_text = scrolledtext.ScrolledText(master, wrap=tk.WORD, height=18)
        self.log_text.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky='nsew')
        self.log_text.config(state=tk.DISABLED)

        self.github_url = "https://github.com/dependon/gbk2utf8"
        self.github_label = tk.Label(master, text="源项目地址: " + self.github_url, fg="blue", cursor="hand2")
        self.github_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky='w') 
        self.github_label.bind("<Button-1>", lambda e: webbrowser.open_new(self.github_url))

        master.grid_rowconfigure(4, weight=1)
        master.grid_columnconfigure(1, weight=1)

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

    def is_likely_chinese(self, text):
        """简单检查字符串中是否包含中文字符，防止西欧字符误判"""
        return any('\u4e00' <= char <= '\u9fff' for char in text)

    def detect_encoding(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(15360) # 进一步扩大采样到15KB
            
            # 1. 尝试 UTF-8
            try:
                raw_data.decode('utf-8')
                return 'utf-8', 1.0
            except UnicodeDecodeError:
                pass

            result = chardet.detect(raw_data)
            enc = result['encoding']
            
            # 2. 针对 Bjønnes 这种西欧字符的保护逻辑
            if enc and enc.lower() in ['ascii', 'windows-1252', 'iso-8859-1']:
                try:
                    # 尝试用 GB18030 解码并检查是否有汉字
                    decoded_text = raw_data.decode('gb18030')
                    if self.is_likely_chinese(decoded_text):
                        return 'gb18030', 0.5
                    else:
                        # 只有特殊符号而没汉字，判定为外文，不转换
                        return 'utf-8', 1.0
                except UnicodeDecodeError:
                    return 'utf-8', 1.0 

            return enc, result['confidence']
        except Exception as e:
            self.log(f"读取失败: {os.path.basename(file_path)} - {e}")
            return None, 0

    def process_folder(self, base_folder):
        raw_excludes = self.exclude_folders_var.get().split(',')
        # 预处理关键字，支持相对路径片段
        exclude_keywords = [x.strip().replace('/', os.sep).replace('\\', os.sep) for x in raw_excludes if x.strip()]

        converted = 0
        skipped = 0
        errors = 0

        for root, dirs, files in os.walk(base_folder, topdown=True):
            # 核心改进：检查当前 root 路径中是否包含任何排除关键字
            rel_root = os.path.relpath(root, base_folder)
            
            # 只要关键字在路径片段中出现，就跳过整个目录
            path_parts = rel_root.split(os.sep)
            if any(key in path_parts or key in rel_root for key in exclude_keywords if key != '.'):
                dirs[:] = [] 
                continue

            for f in files:
                if not any(f.lower().endswith(ext) for ext in TEXT_FILE_EXTENSIONS):
                    continue

                full_path = os.path.join(root, f)
                enc, conf = self.detect_encoding(full_path)

                if not enc or enc.lower() == 'utf-8':
                    skipped += 1
                    continue

                try:
                    # 如果检测到 MACROMAN 或其他罕见编码且没有汉字，跳过
                    if enc.lower() not in ['gbk', 'gb2312', 'gb18030', 'utf-8-sig']:
                        # 再做一次汉字检测，防止把西欧注释转乱码
                        with open(full_path, 'rb') as f_check:
                            if not self.is_likely_chinese(f_check.read(10240).decode(enc, errors='replace')):
                                skipped += 1
                                continue

                    self.log(f"转换中 [{enc.upper()}]: {os.path.relpath(full_path, base_folder)}")
                    with open(full_path, 'r', encoding=enc, errors='replace') as fr:
                        content = fr.read()
                    with open(full_path, 'w', encoding='utf-8') as fw:
                        fw.write(content)
                    converted += 1
                except Exception as e:
                    self.log(f"❌ 失败: {f} - {e}")
                    errors += 1

        self.master.after(0, lambda: self.finish_ui(converted, skipped, errors))

    def finish_ui(self, c, s, e):
        self.log(f"\n✨ 处理完成！ 成功: {c} | 跳过: {s} | 失败: {e}")
        messagebox.showinfo("完成", f"任务已结束\n转换: {c}\n跳过: {s}\n错误: {e}")
        self.convert_button.config(state=tk.NORMAL)
        self.browse_button.config(state=tk.NORMAL)

    def start_conversion_thread(self):
        path = self.folder_path_var.get()
        if not path or not os.path.isdir(path):
            messagebox.showerror("错误", "请选择正确的文件夹路径")
            return
        
        self.convert_button.config(state=tk.DISABLED)
        self.browse_button.config(state=tk.DISABLED)
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        threading.Thread(target=self.process_folder, args=(path,), daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = EncodingConverterApp(root)
    root.mainloop()
