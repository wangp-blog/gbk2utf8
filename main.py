import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import chardet
import threading
import webbrowser

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
        master.title("GBK/GB2312 转 UTF-8 工具 (增强版)")
        master.geometry("650x550")

        # UI 布局
        tk.Label(master, text="选择根文件夹:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.folder_path_var = tk.StringVar()
        self.folder_entry = tk.Entry(master, textvariable=self.folder_path_var, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=10, sticky='ew')
        self.browse_button = tk.Button(master, text="浏览", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=10, pady=10)

        tk.Label(master, text="排除路径 (逗号分隔):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.exclude_folders_var = tk.StringVar()
        self.exclude_folders_var.set(".git, node_modules, __pycache__, build, dist, include/boost")
        self.exclude_entry = tk.Entry(master, textvariable=self.exclude_folders_var, width=50)
        self.exclude_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        self.convert_button = tk.Button(master, text="🚀 开始转换", command=self.start_conversion_thread, bg="#e1e1e1")
        self.convert_button.grid(row=2, column=0, columnspan=3, pady=15)

        tk.Label(master, text="处理日志:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
        self.log_text = scrolledtext.ScrolledText(master, wrap=tk.WORD, height=18)
        self.log_text.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky='nsew')
        self.log_text.config(state=tk.DISABLED)

        self.github_url = "https://github.com/dependon/gbk2utf8"
        self.github_label = tk.Label(master, text="项目地址: " + self.github_url, fg="blue", cursor="hand2")
        self.github_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky='w') 
        self.github_label.bind("<Button-1>", lambda e: webbrowser.open_new(self.github_url))

        master.grid_rowconfigure(4, weight=1)
        master.grid_columnconfigure(1, weight=1)

    def log(self, message):
        """线程安全的日志记录"""
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

    def detect_encoding(self, file_path):
        """增强版编码检测：保护西欧特殊字符"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10240) # 读取10KB提高准确度
            
            # 1. 尝试直接以 UTF-8 解码（涵盖了纯英文 ASCII）
            try:
                raw_data.decode('utf-8')
                return 'utf-8', 1.0
            except UnicodeDecodeError:
                pass

            result = chardet.detect(raw_data)
            enc = result['encoding']
            conf = result['confidence']

            # 2. 针对可能包含特殊西欧字符（如 Hervé）的情况进行保护
            if enc and enc.lower() in ['ascii', 'windows-1252', 'iso-8859-1']:
                try:
                    # 尝试用中文编码严格检测，如果报错，说明它真的就是西欧文，不是GBK误判
                    raw_data.decode('gb18030')
                    return 'gb18030', 0.5
                except UnicodeDecodeError:
                    # 确认为外文，返回 utf-8 让其跳过处理，或者保留原样
                    return 'utf-8', 1.0 

            return enc, conf
        except Exception as e:
            self.log(f"读取错误: {os.path.basename(file_path)} - {e}")
            return None, 0

    def process_folder(self, base_folder):
        # 预处理排除列表：统一斜杠并清理空格
        raw_excludes = self.exclude_folders_var.get().split(',')
        exclude_list = [os.path.normpath(x.strip().replace('/', os.sep)) for x in raw_excludes if x.strip()]

        converted = 0
        skipped = 0
        errors = 0

        for root, dirs, files in os.walk(base_folder, topdown=True):
            # 获取当前目录相对于根目录的路径
            rel_root = os.path.relpath(root, base_folder)
            
            # 检查当前目录是否在排除名单中（支持 include/boost 这种写法）
            # 注意：'.' 表示根目录本身
            if any(rel_root == ex or rel_root.startswith(ex + os.sep) for ex in exclude_list):
                dirs[:] = [] # 阻止继续向下遍历
                continue

            # 过滤子目录，防止下一步进入排除名单
            dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(rel_root, d)) not in exclude_list]

            for f in files:
                if not any(f.lower().endswith(ext) for ext in TEXT_FILE_EXTENSIONS):
                    continue

                full_path = os.path.join(root, f)
                enc, conf = self.detect_encoding(full_path)

                # 逻辑优化：如果是 UTF-8 或无法识别，直接跳过
                if not enc or enc.lower() == 'utf-8':
                    skipped += 1
                    continue

                try:
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
