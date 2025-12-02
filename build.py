# -*- coding: utf-8 -*-
import os
import shutil
import sys
import subprocess


def clean_pycache():
    print("Cleaning __pycache__ and .pyc files...")
    root_dir = os.getcwd() # 获取当前目录
    for root, dirs, files in os.walk(root_dir):
        # 1. 删除 __pycache__ 文件夹
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                print(f"Removed: {cache_dir}")
            except Exception as e:
                print(f"Failed to remove {cache_dir}: {e}")
            dirs.remove("__pycache__") # 防止 os.walk 继续遍历已删除的目录

        # 2. (可选) 删除散落的 .pyc 文件
        for file in files:
            if file.endswith(".pyc"):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                except:
                    pass

def install_requirements():
    print("Checking requirements...")
    try:
        import PyInstaller
        print("PyInstaller is already installed.")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build():
    clean_pycache()
    import PyInstaller.__main__

    # Define the app name
    APP_NAME = "KSAS"
    MAIN_SCRIPT = "KSAS.py"
    
    # Clean previous builds
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    # PyInstaller arguments
    args = [
        MAIN_SCRIPT,
        f'--name={APP_NAME}',
        '--onedir',                 # Pack into a directory (faster startup, easier to debug)
        '--windowed',               # No console window
        '--clean',
        '--noconfirm',
        '--icon=assets/logo.ico', 
        
        # Include data folders (source;destination)
        '--add-data=assets;assets',
        '--add-data=i18n;i18n',
        '--add-data=tools;tools',
        '--add-data=data/defaults;data/defaults',
        
        # Hidden imports
        '--hidden-import=PySide6',
        '--hidden-import=yaml',
        '--hidden-import=cv2',
        '--hidden-import=numpy',
        '--hidden-import=airtest',
        '--hidden-import=pocoui',
        '--hidden-import=win32timezone', # Sometimes needed for datetime
        
        # Collect Airtest dependencies
        '--collect-all=airtest',
        '--collect-all=poco',
        '--collect-all=pywinauto',
    ]
    
    print(f"Starting build for {APP_NAME}...")
    PyInstaller.__main__.run(args)
    print("Build finished! Check the 'dist' folder.")

if __name__ == "__main__":
    install_requirements()
    build()