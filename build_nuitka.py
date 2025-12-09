# -*- coding: utf-8 -*-
import os
import shutil
import sys
import subprocess
import airtest # <--- 1. 导入 airtest 以便定位它的路径

# 定义输出的基础目录
APP_NAME = "KSAS"
DIST_DIR = os.path.join("nuitka_dist", f"{APP_NAME}.dist")

def clean_build_dirs():
    print("Cleaning previous build directories...")
    # 保留 build 缓存，加快再次打包速度
    # 注意：不要删除 'nuitka_dist' 根目录，否则会把 KSAS.build 缓存也删掉
    dirs_to_clean = [DIST_DIR, 'build', 'dist', f'{APP_NAME}.dist', f'{APP_NAME}.onefile-build']
    for d in dirs_to_clean:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                print(f"Removed: {d}")
            except Exception as e:
                print(f"Failed to remove {d}: {e}")

def copy_folder(src, dst_relative):
    """
    手动复制文件夹的辅助函数
    """
    target_dir = os.path.join(DIST_DIR, dst_relative)
    
    if not os.path.exists(src):
        print(f"⚠️ Warning: Source folder '{src}' not found, skipping.")
        return

    # 如果目标目录的上级目录不存在，先创建上级目录
    parent_dir = os.path.dirname(target_dir)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    # 如果目标已存在，先删掉
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    
    print(f"📂 Copying '{src}' -> '{target_dir}' ...")
    try:
        shutil.copytree(src, target_dir)
    except Exception as e:
        print(f"❌ Failed to copy {src}: {e}")

def install_requirements():
    print("Checking build requirements...")
    required = ["nuitka", "zstandard"] 
    for req in required:
        try:
            __import__(req)
        except ImportError:
            print(f"{req} not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", req])

def fix_airtest_apks():
    """
    专门修复 Airtest 缺少 Yosemite.apk 的问题
    """
    print("\n🔧 Fixing Airtest Dependencies (Yosemite.apk)...")
    try:
        # 1. 找到你电脑上 Airtest 的安装位置
        airtest_root = os.path.dirname(airtest.__file__)
        
        # 2. 定位源路径: airtest/core/android/static/apks
        src_apks = os.path.join(airtest_root, "core", "android", "static", "apks")
        
        # 3. 定位目标路径: dist/airtest/core/android/static/apks
        # 注意：这里必须保持目录结构完全一致，因为 Airtest 代码是硬编码查找的
        dst_relative = os.path.join("airtest", "core", "android", "static", "apks")
        
        if os.path.exists(src_apks):
            copy_folder(src_apks, dst_relative)
            print("✅ Airtest APKs copied successfully!")
        else:
            print(f"⚠️ Warning: Could not find Airtest APKs at {src_apks}")
            
    except Exception as e:
        print(f"❌ Failed to fix Airtest APKs: {e}")

def build():
    clean_build_dirs()
    
    MAIN_SCRIPT = "KSAS.py"
    
    nuitka_args = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--mingw64",
        "--show-progress",
        "--show-memory",
        "--enable-plugin=pyside6",
        "--disable-console",
        f"--windows-icon-from-ico=assets/logo.ico",
        "--output-dir=nuitka_dist",
        
        # === 依赖包 ===
        "--include-package=airtest",
        "--include-package=pywinauto",
        "--include-package=cv2",
        "--include-package=numpy",
        "--include-package=yaml",     
        "--include-package=requests", 
        "--include-package=PIL",      
        
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        
        MAIN_SCRIPT
    ]
    
    print(f"Starting Nuitka build for {APP_NAME}...")
    
    try:
        # 1. 编译
        subprocess.check_call(nuitka_args)
        
        print("\n" + "="*50)
        print("✅ Compilation finished. Now copying resources manually...")
        
        # 2. === 修复 Airtest 缺失文件 (新增步骤) ===
        fix_airtest_apks()

        # 3. === 复制项目资源 ===
        copy_folder(os.path.join("tools", "adb"), os.path.join("tools", "adb"))
        copy_folder("assets", "assets")
        copy_folder("i18n", "i18n")
        copy_folder(os.path.join("data", "defaults"), os.path.join("data", "defaults"))
        
        print("="*50)
        print("🎉 Build Process Complete!")
        print(f"🚀 Executable:    {os.path.join(DIST_DIR, APP_NAME + '.exe')}")
        print("="*50)
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed with error code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_requirements()
    build()