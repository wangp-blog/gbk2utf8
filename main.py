import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
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
        master.title("GBK 转 UTF-8 工具 (绝对保守防御版 - 0误伤)")
        master.geometry("680x580")

        # UI 布局
        tk.Label(master, text="选择根文件夹:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        self.folder_path_var = tk.StringVar()
        self.folder_entry = tk.Entry(master, textvariable=self.folder_path_var, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=10, sticky='ew')
        self.browse_button = tk.Button(master, text="浏览", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=10, pady=10)

        tk.Label(master, text="排除目录 (如: .git, boost):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.exclude_folders_var = tk.StringVar()
        self.exclude_folders_var.set(".git, node_modules, __pycache__, build, dist, boost, google")
        self.exclude_entry = tk.Entry(master, textvariable=self.exclude_folders_var, width=50)
        self.exclude_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        self.convert_button = tk.Button(master, text="🚀 开始安全扫描与转换", command=self.start_conversion_thread, bg="#4CAF50", fg="white")
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

        # 核心防线：只认基本汉字和中文全角标点，没有这些绝对不转！
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef]')

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

    def detect_encoding(self, file_path):
        """
        极简防御型探测：
        只返回两个动作指令 -> 'convert_gbk' 或者是 'skip'
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read() 
            
            if not raw_data or b'\x00' in raw_data or raw_data.startswith(b'\xef\xbb\xbf'):
                return 'skip', '空文件/二进制/UTF8-BOM'

            # 1. UTF-8 和 纯英文 ASCII 测试
            try:
                raw_data.decode('utf-8', errors='strict')
                return 'skip', '健康的 UTF-8 或 纯英文'
            except UnicodeDecodeError:
                pass 

            # 2. 只有不是 UTF-8 的情况，才尝试 GBK 测试
            try:
                gbk_text = raw_data.decode('gbk', errors='strict')
                # 3. 终极验证：代码里到底有没有真正的中文？
                if self.chinese_pattern.search(gbk_text):
                    return 'convert_gbk', '确认'
                else:
                    return 'skip', '触发保护: 发现西欧/特殊字符，但不含中文'
            except UnicodeDecodeError:
                pass 

            # 4. 连 GBK 都解不了的乱码文件
            return 'skip', '未知编码或严重损坏的乱码'
            
        except Exception as e:
            return 'skip', f'读取异常: {e}'

    def process_folder(self, base_folder):
        raw_excludes = self.exclude_folders_var.get().split(',')
        exclude_keywords = [x.strip().replace('/', os.sep).replace('\\', os.sep) for x in raw_excludes if x.strip()]

        converted = 0
        skipped = 0
        errors = 0

        for root, dirs, files in os.walk(base_folder, topdown=True):
            rel_root = os.path.relpath(root, base_folder)
            
            # 排除特定目录
            path_parts = rel_root.split(os.sep)
            if any(key in path_parts or key in rel_root for key in exclude_keywords if key != '.'):
                dirs[:] = [] 
                continue

            for f in files:
                if not any(f.lower().endswith(ext) for ext in TEXT_FILE_EXTENSIONS):
                    continue

                full_path = os.path.join(root, f)
                action, reason = self.detect_encoding(full_path)

                if action == 'convert_gbk':
                    try:
                        self.log(f"[🟢 锁定 GBK 文件] 准备转换: {os.path.relpath(full_path, base_folder)}")
                        
                        # 按 GBK 读取
                        with open(full_path, 'r', encoding='gbk', errors='strict') as fr:
                            content = fr.read()
                        
                        # 按 UTF-8 覆盖保存（使用原子级临时文件防断电）
                        temp_path = full_path + ".tmp_convert"
                        with open(temp_path, 'w', encoding='utf-8') as fw:
                            fw.write(content)
                        
                        os.replace(temp_path, full_path)
                        converted += 1
                        self.log(f"   └── ✅ 转换成功！")
                        
                    except Exception as e:
                        self.log(f"   └── ❌ 失败: {e}")
                        errors += 1
                        if os.path.exists(full_path + ".tmp_convert"):
                            os.remove(full_path + ".tmp_convert")
                else:
                    # 对于被保护跳过的文件，如果原因是“西欧字符”，稍微提示一下
                    if '触发保护' in reason:
                        self.log(f"[🛡️ 保护机制] 原样保留西欧特殊文件: {os.path.relpath(full_path, base_folder)}")
                    skipped += 1

        self.master.after(0, lambda: self.finish_ui(converted, skipped, errors))

    def finish_ui(self, c, s, e):
        report = (f"\n✨ 全部处理完成！\n"
                  f"---------------------------------\n"
                  f"✅ 成功提取并转换 GBK: {c} 个\n"
                  f"⏭️ 已安全跳过 (UTF-8/纯英文/西欧文): {s} 个\n"
                  f"❌ 处理失败: {e} 个")
        self.log(report)
        messagebox.showinfo("完成", report)
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
