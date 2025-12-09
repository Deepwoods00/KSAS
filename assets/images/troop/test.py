# -*- encoding=utf8 -*-
from airtest.core.api import *
from airtest.core.cv import Template
import cv2 # Airtest 自带了 cv2，直接引用即可

def compare_two_images(bg_image_path, target_image_path):
    print(f"\n>>> 正在对比...")
    print(f"   1. 背景图 (模拟屏幕): {bg_image_path}")
    print(f"   2. 目标图 (要找的图): {target_image_path}")

    # 1. 手动读取背景图 (这一步替代了 G.DEVICE.snapshot())
    # cv2.imread 会把图片读取为矩阵数据
    screen_mock = cv2.imread(bg_image_path)
    
    if screen_mock is None:
        print("❌ 错误：读取背景图失败，请检查路径。")
        return

    # 2. 初始化目标图片的 Template 对象
    tpl = Template(target_image_path, rgb=False)

    # 3. 强行匹配
    try:
        result = tpl._cv_match(screen_mock)
    except Exception as e:
        print(f"❌ 运算出错 (可能是目标图比背景图还大): {e}")
        return

    # 4. 输出结果
    if result:
        score = result.get('confidence')
        print(f"--------------------------------")
        print(f"✅ 相似度 (Confidence): 【 {score:.4f} 】")
        print(f"--------------------------------")
        
        # 结果解读
        if score > 0.9:
            print("结论：几乎一模一样。文字被算法完全忽略了。")
        elif score > 0.7:
            print("结论：有些危险。虽然匹配上了，但置信度不高。")
        else:
            print("结论：匹配失败（或置信度极低）。文字差异太大，无法混用。")
    else:
        print("❌ 完全无法匹配 (相似度过低)")

# ==========================================
# 请在下面填入你的文件名
# 建议：
# 背景图 -> 放那个中文版的 "MuMu-xxx.png"
# 目标图 -> 放那个英文版的 "Search.png"
if __name__ == "__main__":
    # 注意：背景图的尺寸必须 大于或等于 目标图，否则会报错
    target = r"4.png"  # 中文按钮
    bg = r"ar.png" # 英文按钮
    
    compare_two_images(bg, target)