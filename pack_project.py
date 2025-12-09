import os

# =================配置区域=================

# 1. 黑名单：完全忽略这些目录，连文件名都不看 (节省大量 Token)
IGNORE_DIRS = {
    "venv", ".venv", "ksas_env", "__pycache__", ".git", ".idea", ".vscode", 
    "build", "dist", "nuitka_dist", "KSAS.build", "KSAS.dist", # 构建目录
    "paddleocr", "snapshots", "log", "backup", # 运行时垃圾
    "assets", # 图片资源通常不需要发给AI看代码
    "ui/generated" # 自动生成的代码通常不需要看
}

# 2. 白名单后缀：只读取这些文件的内容
INCLUDE_EXTS = {".py", ".json", ".yaml", ".ui", ".md"}

# 3. 【核心功能】聚焦列表
# 如果列表为空 []，则打包整个项目（除了黑名单）。
# 如果列表有内容，例如 ["ui", "config.py"]，则只打包这些指定的文件或文件夹。
FOCUS_TARGETS = [
    # "ui", 
    # "tasks",
    # "config.py" 
]

# =========================================

def is_target(path):
    """判断文件或目录是否在聚焦列表中"""
    if not FOCUS_TARGETS:
        return True
    
    # 路径标准化，防止 sep 差异
    norm_path = os.path.normpath(path)
    
    for target in FOCUS_TARGETS:
        norm_target = os.path.normpath(target)
        # 检查是否是目标本身，或者是目标的子文件/子目录
        if norm_path == norm_target or norm_path.startswith(norm_target + os.sep):
            return True
    return False

def pack_project():
    output_file = "project_summary.txt"
    
    with open(output_file, "w", encoding="utf-8") as out:
        # --- 第一部分：目录结构 (Tree) ---
        out.write("=== PROJECT STRUCTURE (Simplified) ===\n")
        out.write("./\n")
        
        for root, dirs, files in os.walk("."):
            # 1. 原地修改 dirs 列表，剪除黑名单目录，阻止 os.walk 进入
            # 这一步非常关键，它能阻止扫描 nuitka_dist 下的几万个文件
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            # 如果开启了聚焦模式，且当前目录不在聚焦路径上，只打印目录名但不展开（或者完全跳过）
            # 这里简化处理：结构树还是打印出来，方便AI了解整体架构，但内容只打印聚焦的
            
            level = root.replace(os.getcwd(), '').count(os.sep)
            indent = ' ' * 4 * level
            
            # 只显示非根目录
            if root != ".":
                out.write(f"{indent}{os.path.basename(root)}/\n")
                
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                ext = os.path.splitext(f)[1]
                if ext in INCLUDE_EXTS or f == "requirements.txt":
                     out.write(f"{subindent}{f}\n")

        out.write("\n\n=== FILE CONTENTS ===\n")

        # --- 第二部分：文件内容 ---
        for root, dirs, files in os.walk("."):
            # 同样剪除黑名单
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for filename in files:
                ext = os.path.splitext(filename)[1]
                filepath = os.path.join(root, filename)
                
                # 1. 检查后缀白名单
                if ext not in INCLUDE_EXTS:
                    continue
                
                # 2. 检查聚焦模式 (这是关键！)
                # 相对路径，例如 "ui\main_window.py"
                rel_path = os.path.relpath(filepath, ".")
                if not is_target(rel_path):
                    continue

                # 写入分隔符和文件名
                out.write(f"\n{'='*50}\n")
                out.write(f"FILE: {rel_path}\n")
                out.write(f"{'='*50}\n")
                
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        out.write(content)
                except Exception as e:
                    out.write(f"[Error reading file: {e}]")
                
                out.write("\n")

    print(f"✅ 打包完成！")
    if FOCUS_TARGETS:
        print(f"🎯 聚焦模式已开启，仅包含: {FOCUS_TARGETS}")
    else:
        print(f"📂 全量模式 (已忽略构建目录)")

if __name__ == "__main__":
    pack_project()