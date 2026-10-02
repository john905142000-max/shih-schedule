import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

def run_push(repo_url, status_label, root):
    repo_url = repo_url.strip()
    if not repo_url:
        messagebox.showwarning("提示", "請輸入或貼上 GitHub Repository 網址！")
        return

    work_dir = os.path.dirname(os.path.abspath(__file__))
    status_label.config(text="正在連線並推送到 GitHub，請稍候...", fg="#2563eb")
    root.update()

    try:
        subprocess.run(["git", "branch", "-M", "main"], cwd=work_dir, capture_output=True)
        subprocess.run(["git", "remote", "remove", "origin"], cwd=work_dir, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=work_dir, capture_output=True)
        
        result = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=work_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            status_label.config(text="🎉 推送成功！已成功上傳至 GitHub", fg="#16a34a")
            messagebox.showinfo("成功", "程式已成功推送到 GitHub！\n現在您可以前往 Render.com 進行下一步了。")
        else:
            err_msg = result.stderr if result.stderr else result.stdout
            status_label.config(text="推送失敗，請查看提示", fg="#dc2626")
            messagebox.showerror("推送失敗", f"GitHub 推送失敗：\n{err_msg}\n\n若您尚未登入 GitHub，請確認網址是否正確或具有權限。")
    except Exception as e:
        messagebox.showerror("錯誤", f"執行出錯：{str(e)}")

def main():
    root = tk.Tk()
    root.title("一鍵推送到 GitHub (Render 部署專用)")
    root.geometry("520x240")
    root.resizable(False, False)

    # Styling
    tk.Label(root, text="壽山國中課表系統 - 部署到 GitHub", font=("Microsoft JhengHei", 14, "bold"), fg="#1e293b").pack(pady=(15, 5))
    tk.Label(root, text="請貼上您在 GitHub 建立的 Repository 網址：", font=("Microsoft JhengHei", 10), fg="#64748b").pack(pady=2)

    entry = tk.Entry(root, font=("Consolas", 11), width=48)
    entry.pack(pady=8, ipady=4)
    entry.focus()

    status_label = tk.Label(root, text="", font=("Microsoft JhengHei", 9))
    status_label.pack(pady=2)

    btn = tk.Button(
        root, 
        text="🚀 立即推送到 GitHub", 
        font=("Microsoft JhengHei", 11, "bold"), 
        bg="#2563eb", 
        fg="white", 
        activebackground="#1d4ed8", 
        activeforeground="white",
        padx=15, 
        pady=5, 
        cursor="hand2",
        command=lambda: run_push(entry.get(), status_label, root)
    )
    btn.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
