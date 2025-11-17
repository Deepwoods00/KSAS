import logging
from airtest.core.api import (
    Template,
    touch,
    exists,
    ocr_text, 
    snapshot  
)
from airtest.core.helper import crop_image
from airtest.core.error import TargetNotFoundError

def screenshot():
    '''截取当前屏幕并返回截图对象'''
    try:
        img = snapshot()
        if img:
            return img
        logging.warning("[Basic] 截图失败: snapshot() 返回 None")
        return None
    except Exception as e:
        logging.error(f"[Basic] 截图崩溃: {e}")
        return None
    

def crop_image_with_offset(img, area):
    """
    :param img: 传入的 PIL Image 对象 (来自 screenshot())
    :param area: 一个四元组 [x_min, y_min, x_max, y_max]
    :return: (cropped_image, offset) | (None, None)
             cropped_image: 裁剪后的小图
             offset: 裁剪的偏移值 (x_min, y_min)
    """
    try:
        (cropped_img, offset) = crop_image(img, area)
        if cropped_img:
            return (cropped_img, offset)
        else:
            logging.warning(f"[Basic] 裁剪图像失败，区域 {area} 可能无效")
            return (None, None)
    except Exception as e:
        logging.error(f"[Basic] crop_image 崩溃: {e}")
        return (None, None)


def get_ocr_from_image(img_object):
    """
    [基础函数] 对 *已传入* 的截图对象进行OCR。
    (我重命名了它以示清晰)
    :param img_object: 一个 PIL Image 对象 (通常是已裁剪的)
    :return: str | None
    """
    try:
        results = ocr_text(img_object)
        if not results:
            logging.warning(f"[Basic-OCR] 未在传入的图像中识别到文字")
            return None
        
        full_text = " ".join([res['text'] for res in results])
        logging.info(f"[Basic-OCR] 识别到文字: '{full_text}'")
        return full_text
    except Exception as e:
        logging.error(f"[Basic-OCR] get_ocr_from_image 崩溃: {e}")
        return None

def text_to_int(text):
    '''将传入的文本，可以是get_ocr的输出值，转换为整数，去除非数字字符，返回整数值'''

def exist_image(target_image, area_image, confidence = 0.9):
    '''检测图片在传入的截图上是否存在。存在则返回坐标，不存在则返回False'''


def click(x, y):
    '''点击指定坐标。坐标可以是直接的x和y，也可以是exist_image的返回值'''