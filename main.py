import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import chardet
import threading
import webbrowser

# 支持检测和转换的编码列表
SUPPORTED_ENCODINGS = ['gb2312', 'gbk']
# 目标编码
TARGET_ENCODING = 'utf-8'
# 常见的文本和代码文件扩展名 (小写)
TEXT_FILE_EXTENSIONS = {
    '.txt', '.log', '.csv', '.json', '.xml', '.html', '.htm', '.css', '.js', 
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.go', 
    '.rs', '.swift', '.kt', '.kts', '.sql', '.md', '.rst', '.yaml', '.yml', 
    '.ini', '.cfg', '.toml', '.sh', '.bat', '.ps1'
}

class EncodingConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("GBK/GB2312 转 UTF-8 工具")
        master.geometry("600x520")

        # 1. 文件夹选择
        self.folder_path_var = tk.StringVar()
        tk.Label(master, text="选择文件夹:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.folder_entry = tk.Entry(master, textvariable=self.folder_path_var, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.browse_button = tk.Button(master, text="浏览", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)

        # 2. 排除文件夹选项
        self.exclude_folders_var = tk.StringVar()
        self.exclude_folders_var.set(".git, node_modules, __pycache__, build, dist")
        tk.Label(master, text="排除(支持相对路径):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.exclude_entry = tk.Entry(master, textvariable=self.exclude_folders_var, width=50)
        self.exclude_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # 3. 开始转换按钮
        self.convert_button = tk.Button(master, text="开始转换", command=self.start_conversion_thread)
        self.convert_button.grid(row=2, column=0, columnspan=3, pady=10)

        # 4. 日志输出区域
        tk.Label(master, text="转换日志:").grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.log_text = scrolledtext.ScrolledText(master, wrap=tk.WORD, height=15)
        self.log_text.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        self.log_text.config(state=tk.DISABLED)

        # 5. GitHub 链接
        self.github_url = "https://github.com/dependon/gbk2utf8"
        self.github_label = tk.Label(master, text="项目地址: " + self.github_url, fg="blue", cursor="hand2")
        self.github_label.grid(row=5, column=0, columnspan=3, padx=5, pady=(5, 10), sticky='w') 
        self.github_label.bind("<Button-1>", self.open_link)

        # 6. 配置行列权重
        master.grid_rowconfigure(4, weight=1) 
        master.grid_rowconfigure(5, weight=0) 
        master.grid_columnconfigure(1, weight=1)

    def log(self, message):
        """线程安全的日志输出：将 UI 更新放入主线程消息队列"""
        self.master.after(0, self._log_safe, message)

    def _log_safe(self, message):
        """实际执行日志写入的方法（仅在主线程运行）"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_var.set(folder_selected)
            self.log(f"已选择文件夹: {folder_selected}")

    def is_text_file(self, filename):
        _, ext = os.path.splitext(filename)
        return ext.lower() in TEXT_FILE_EXTENSIONS

    def detect_encoding(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(8192)
            
            # 如果文件完全是纯英文(ASCII)，直接判定为 utf-8，避免后续误判和转换
            try:
                raw_data.decode('utf-8')
                return 'utf-8', 1.0
            except UnicodeDecodeError:
                pass

            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence']

            if encoding and encoding.lower() in ['ascii', 'windows-1252', 'iso-8859-1']:
                return 'gb18030', 0.5
            
            return encoding, confidence
        except Exception as e:
            self.log(f"检测编码错误 ({os.path.basename(file_path)}): {e}")
            return None, 0

    def convert_file_encoding(self, file_path, original_encoding):
        try:
            with open(file_path, 'r', encoding=original_encoding, errors='replace') as f_read:
                content = f_read.read()
            
            needs_conversion = False
            try:
                with open(file_path, 'r', encoding='utf-8') as f_utf8_check:
                     utf8_content = f_utf8_check.read()
                if content != utf8_content:
                    needs_conversion = True
            except UnicodeDecodeError:
                 needs_conversion = True
            except Exception:
                 needs_conversion = True

            if needs_conversion:
                with open(file_path, 'w', encoding=TARGET_ENCODING) as f_write:
                    f_write.write(content)
                self.log(f"成功: {os.path.basename(file_path)} ({original_encoding} -> {TARGET_ENCODING})")
                return True
            else:
                self.log(f"跳过: {os.path.basename(file_path)} (无需转换)")
                return False

        except Exception as e:
            self.log(f"转换失败: {os.path.basename(file_path)} - {e}")
            return False

    def process_folder(self, folder_path):
        converted_count = 0
        skipped_count = 0
        error_count = 0
        processed_files = 0

        # 解析排除文件夹列表，统一路径格式，兼容跨平台
        exclude_str = self.exclude_folders_var.get()
        exclude_items = [os.path.normpath(f.strip()) for f in exclude_str.split(',') if f.strip()]

        self.log(f"\n开始扫描文件夹: {folder_path}")
        if exclude_items:
            self.log(f"排除的文件夹/路径: {', '.join(exclude_items)}")

        for root, dirs, files in os.walk(folder_path):
            # 原地修改 dirs，支持按文件夹名或相对路径阻止 os.walk 深入
            dirs_to_keep = []
            for d in dirs:
                # 计算相对路径，例如 'include/boost'
                rel_dir = os.path.relpath(os.path.join(root, d), folder_path)
                
                is_excluded = False
                for ex in exclude_items:
                    # 匹配纯文件夹名，或相对路径，或相对路径的子目录
                    if d == ex or rel_dir == ex or rel_dir.startswith(ex + os.sep):
                        is_excluded = True
                        break
                
                if not is_excluded:
                    dirs_to_keep.append(d)
            
            dirs[:] = dirs_to_keep # 覆盖原列表，os.walk 将只遍历过滤后的目录

            for filename in files:
                if not self.is_text_file(filename):
                    continue

                file_path = os.path.join(root, filename)
                processed_files += 1
                
                encoding, confidence = self.detect_encoding(file_path)

                if encoding and encoding.lower() == 'utf-8':
                    # 直接跳过已确认的纯英文或UTF-8文件
                    skipped_count += 1
                elif encoding:
                    self.log(f"正在处理: {file_path}")
                    self.log(f"尝试转换 {encoding.upper()} -> UTF-8: {filename}")
                    if self.convert_file_encoding(file_path, encoding):
                        converted_count += 1
                    else:
                        error_count += 1
                else:
                    skipped_count += 1
                    error_count += 1
        
        # 扫描结束，恢复UI状态（线程安全调用）
        self.master.after(0, self._finish_conversion, processed_files, converted_count, skipped_count, error_count)

    def _finish_conversion(self, processed_files, converted_count, skipped_count, error_count):
        """线程安全地结束转换并更新UI"""
        self.log(f"\n处理完成。共扫描 {processed_files} 个文本/代码文件。")
        self.log(f"成功转换: {converted_count}")
        self.log(f"跳过文件: {skipped_count}")
        self.log(f"转换/检测失败: {error_count}")
        messagebox.showinfo("完成", f"转换完成！\n成功: {converted_count}\n跳过: {skipped_count}\n失败: {error_count}")
        self.convert_button.config(state=tk.NORMAL)
        self.browse_button.config(state=tk.NORMAL)

    def start_conversion_thread(self):
        folder_path = self.folder_path_var.get()
        if not folder_path or not os.path.isdir(folder_path):
            messagebox.showerror("错误", "请先选择一个有效的文件夹！")
            return

        self.convert_button.config(state=tk.DISABLED)
        self.browse_button.config(state=tk.DISABLED)
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)

        conversion_thread = threading.Thread(target=self.process_folder, args=(folder_path,), daemon=True)
        conversion_thread.start()

    def open_link(self, event):
        webbrowser.open_new(self.github_url)

if __name__ == "__main__":
    root = tk.Tk()
    app = EncodingConverterApp(root)
    root.mainloop()
