import os

# 设置要忽略的文件夹 (黑名单)
IGNORE_DIRS = {
    "venv", ".venv", "ksas_env", "__pycache__", ".git", ".idea", ".vscode", 
    "build", "dist", "paddleocr", "snapshots", "log"
}

# 设置要读取的文件后缀 (白名单)
INCLUDE_EXTS = {".py", ".json", ".ui", ".md", ".txt"}

def pack_project():
    output_file = "project_summary.txt"
    
    with open(output_file, "w", encoding="utf-8") as out:
        # 1. 先写一个目录结构树
        out.write("=== PROJECT STRUCTURE ===\n")
        for root, dirs, files in os.walk("."):
            # 过滤掉黑名单目录
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            level = root.replace(os.getcwd(), '').count(os.sep)
            indent = ' ' * 4 * (level)
            out.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                out.write(f"{subindent}{f}\n")
        
        out.write("\n\n=== FILE CONTENTS ===\n")

        # 2. 遍历读取文件内容
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for filename in files:
                ext = os.path.splitext(filename)[1]
                if ext in INCLUDE_EXTS:
                    filepath = os.path.join(root, filename)
                    
                    # 写入分隔符和文件名
                    out.write(f"\n{'='*50}\n")
                    out.write(f"FILE: {filepath}\n")
                    out.write(f"{'='*50}\n")
                    
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                            out.write(content)
                    except Exception as e:
                        out.write(f"[Error reading file: {e}]")
                    
                    out.write("\n")

    print(f"✅ 打包完成！请把生成的 '{output_file}' 发给我。")

if __name__ == "__main__":
    pack_project()