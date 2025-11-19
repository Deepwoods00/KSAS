# 最终架构蓝图：KSAS V3.4 (独立管控版)

**核心设计理念：**
1.  **三层解耦：** UI (显示) / Scheduler (调度) / Task (执行) 彻底分离。
2.  **实例隔离 (Per-Instance)：** 每个账号拥有独立的数据、配置、日志和调度线程，互不干扰。
3.  **注册制管理：** 只有用户明确“添加”的设备才会被系统接管，杜绝自动扫描的混乱。
4.  **独立管控：** 每个实例独立控制启停，拒绝“一键全开”的粗暴逻辑。

---

## 0. 🚀 启动器 (The Launcher)

* **角色：** 程序的**外壳**与**更新器**。
* **实现：** 独立的可执行文件 (如 `launcher.exe`)。
* **职责：**
    1.  **环境自检：** 确保运行环境正常。
    2.  **自动更新：** 联网检查版本，若有更新则下载并替换核心文件。
    3.  **唤起核心：** 使用子进程调用 `python KSAS.py` 启动主程序。用户不直接运行主脚本。

---

## 1. 🏢 实例管理器 (The Instance Manager)

* **角色：** 设备的**户籍办**与**状态监视器**。
* **实现：** 全局单例 `InstanceManager`。
* **核心逻辑：**
    1.  **注册加载 (Startup Load)：**
        * 启动时进行一次 ADB 扫描。
        * 读取 `data/device_registry.json`，加载所有已知设备（无论是否连接）。
        * 为每个注册设备初始化 `DataStore` 和 `Scheduler`，初始状态设为 `OFFLINE`。
    2.  **手动刷新 (Manual Scan)：**
        * 仅当 UI 调用 `scan_devices()` 时执行 `adb devices`。
        * **已注册设备：** 更新状态为 `ONLINE`，UI 图标点亮。
        * **未注册设备：** 返回“候选列表”，**不自动添加**，等待用户决策。
    3.  **手动注册 (Add Instance)：**
        * 用户在 UI 选择新设备并确认后，调用 `add_instance(serial, alias)`。
        * 创建数据对象，写入 `device_registry.json`。
    4.  **手动移除：** 彻底删除实例内存对象和注册表条目。

---

## 2. 💾 数据中心 (Per-Instance DataStore)

* **角色：** 单个实例的**状态仓库**。
* **实现：** 普通 Class，每个 `device_id` 对应一个对象。
* **职责：**
    1.  **连接状态：** 维护 `connection_status` (ONLINE/OFFLINE)。
    2.  **运行状态：** 维护 `running_status` (IDLE/RUNNING/ERROR)。
    3.  **配置管理：** 存储该实例的任务开关、参数设置（即使离线也可修改）。
    4.  **信号驱动：** 状态或配置变更时，发射 Qt 信号通知 UI。

---

## 3. 🗄️ 持久化系统 (Structured Persistence)

* **角色：** 文件系统映射。
* **目录结构：**
    ```text
    root/
    ├── data/
    │   ├── global_settings.json       # 全局设置 (ADB路径、通知URL、界面偏好)
    │   ├── device_registry.json       # 设备户口本 (ID、别名、最后上线时间)
    │   │
    │   ├── [device_id_A]/             # 实例 A 专属文件夹
    │   │   ├── config.json            # 任务配置
    │   │   ├── runtime.log            # 运行日志
    │   │   └── snapshots/             # 报错截图存放区
    │   │
    │   └── [device_id_B]/             # 实例 B 专属文件夹
    │       ├── ...
    ```

---

## 4. ⏰ 中央调度器 (Per-Instance Scheduler)

* **角色：** 单个实例的**独立指挥官**。
* **实现：** 继承 `QThread`，每个实例一个线程。
* **控制逻辑：**
    1.  **独立启停：** 提供 `start_scheduler()` 和 `stop_scheduler()` 方法，供 UI 上的独立按钮调用。
    2.  **安全运行：**
        * 若状态为 `OFFLINE`，拒绝启动。
        * 若用户点击“停止”，当前任务执行完原子操作后安全退出。
    3.  **防崩循环：** `run()` 内部捕获所有 Task 异常，触发快照并记录日志，确保护送线程不崩溃。

---

## 5. 🛠️ 任务执行器 (Instance-Aware Tasks)

* **角色：** 业务逻辑单元。
* **实现：** `BaseTask` 子类。
* **职责：**
    1.  **上下文感知：** 必须持有 `instance_id` 以便读写正确的数据。
    2.  **逻辑执行：** 读取配置 -> 调用 Toolbox -> 更新状态。

---

## 6. 🧰 工具箱 (Toolbox & Snapshot)

* **角色：** 底层操作库与证据留存。
* **实现：** `basic.py` (Airtest 封装) + `snapshot_manager.py`。
* **职责：**
    1.  **安全调用：** 封装 Airtest API，捕获底层异常，返回 Boolean 结果。
    2.  **快照机制：** * 当任务报错或关键步骤失败时，调用 `adb screencap`。
        * 图片保存至 `data/[device_id]/snapshots/`。
        * 返回图片路径给日志系统。

---

## 7. 🖥️ 原生UI (Multi-Instance View)

* **角色：** 控制台。
* **核心布局：**
    1.  **顶部工具栏：**
        * `[ 🔄 刷新连接 ]`：手动触发 ADB 扫描，更新在线状态。
        * `[ ➕ 添加设备 ]`：弹出对话框，从扫描到的未知设备中选择添加。
        * `[ ⚙️ 全局设置 ]`：修改 ADB 路径等通用配置。
    2.  **实例区域 (Tab Widget 或 列表)：**
        * **动态渲染：** 根据 `device_registry` 生成页签。
        * **独立控制面板 (每个页签内)：**
            * **状态栏：** 显示别名、连接状态 (亮/灰)、当前体力。
            * **操作区：** `[ ▶ 启动脚本 ]` / `[ ⏹ 停止脚本 ]` (互斥按钮)。
            * **配置区：** 任务复选框列表。
            * **日志区：** 该实例专属的滚动日志（含截图链接）。

---

## 8. 🔌 核心胶水 (Glue Code)

* **角色：** 信号路由。
* **机制：**
    * **UI按钮 -> Scheduler:** 点击实例 A 的“启动”，直接调用 `instance_manager.get_scheduler(A).start()`。
    * **DataStore -> UI:** 实例 A 只有体力变化，只刷新实例 A 的 UI 控件，不重绘整个界面。

---

## 9. 📇 任务注册中心 (Task Registry)

* **角色：** 静态字典。
* **职责：** 维护任务名称与 Class 的映射，供 UI 生成配置列表。

---

## 10. 📝 日志系统 (Instance-Isolated Logging)

* **角色：** 分流记录员。
* **策略：**
    1.  **物理隔离：** 日志文件严格写入 `data/[device_id]/runtime.log`。
    2.  **实时反馈：** 通过 Signal 将日志文本（及截图路径）推送到 UI 的日志窗口。