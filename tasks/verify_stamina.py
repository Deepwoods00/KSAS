# tasks/verify_stamina.py
import logging
import sys
import os

# 添加父目录到 sys.path 以便导入 basic 和 datastore
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 模拟环境
from basic import DeviceOperator
from datastore import InstanceDataStore
from tasks.base_task import BaseTask

def test_stamina_detection():
    print("=== 开始测试体力检测逻辑 ===")
    
    # 1. 初始化组件
    # 注意：这里需要真实的 serial，请用户手动修改
    serial = "emulator-5554" 
    instance_id = "test_instance"
    
    device = DeviceOperator(serial, instance_id)
    data = InstanceDataStore(instance_id)
    
    # 2. 连接设备
    if not device.connect():
        print("设备连接失败，请检查 serial")
        return

    # 3. 实例化任务
    task = BaseTask(device, data)
    
    # 4. 执行体力检测
    try:
        stamina = task.get_current_stamina()
        print(f"检测结果: {stamina}")
        
        # 5. 验证 DataStore
        stored_val = data.get_stat("stamina")
        print(f"DataStore 中的值: {stored_val}")
        
        if stamina == stored_val:
            print("✅ 测试通过: 读取值与存储值一致")
        else:
            print("❌ 测试失败: 读取值与存储值不一致")
            
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")

if __name__ == "__main__":
    test_stamina_detection()
