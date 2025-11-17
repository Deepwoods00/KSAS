# 最终架构蓝图：KSAS V2 (原生桌面版)

这是一个“三层解耦”的健壮架构，由“数据中心”、“调度器”、“UI”和“任务”四大独立体系构成，并辅以“持久化”、“日志”、“注册中心”、“工具箱”和“启动器”五大配套设施。

本架构专为 7x24 稳定运行、状态持久化、原生UI体验和自动更新而设计。

---

## 0. 🚀 启动器 & 自动更新 (The Launcher)

* **角色：** 整个应用的**唯一入口**。用户只运行这个脚本，从不直接运行主程序。
* **实现：** 一个位于 `KSAS_v2` 文件夹**外部**的 `launcher.py` 脚本。
* **职责：**
    1.  **自动更新：** 首先执行 `git pull` (通过 SSH 或 PAT 访问你的**私有仓库**) 来获取最新代码。
    2.  **安装依赖：** 接着运行 `pip install -r requirements.txt` 来安装任何新依赖。
    3.  **启动：** 最后才执行 `python KSAS_v2/main.py` (你的新主程序) 来启动应用。

---

## 1. 💾 数据中心 (The DataStore)

* **角色：** 唯一的“真理之源”（公司数据库），管理所有“状态”和“配置”。
* **实现：** 一个全局单例的 `DataStore` Class (在 `datastore.py` 中)。
* **职责：**
    1.  **线程安全：** 内部必须使用 `threading.Lock` 保护所有数据（`_stamina`, `_wolf_interval` 等）。
    2.  **管理状态：** 存储所有动态数据（如当前体力）和静态配置（如刷狼消耗）。
    3.  **信号发射：** 当数据被 `set_...` 方法更改时，**必须**（通过 PySide 的信号）**发射**一个信号（例如 `stamina_changed_signal.emit(new_value)`），以便 UI 可以安全地接收更新。

---

## 2. 🗄️ 持久化 (Persistence)

* **角色：** `DataStore` 的“硬盘存档”，防止脚本重启导致数据丢失。
* **实现：** 一个本地文件（例如 `data/datastore.json`）。
* **职责：**
    1.  **读取 (Load)：** `DataStore` 在**初始化**（`__init__`） 时，**必须**先从 `datastore.json` 读取“存档”（如果文件存在）。
    2.  **写入 (Save)：** `DataStore` 的所有“写入”方法（如 `set_stamina`）在更新内存的同时，**必须**立刻将新数据写回 `datastore.json`。

---

## 3. ⏰ 中央调度器 (The Scheduler)

* **角色：** 只管“时间”和“执行”的“经理”。
* **实现：** 一个全局单例的 `CentralScheduler` Class (在 `scheduler.py` 中)。
* **职责：**
    1.  **排班表：** 内部维护一个核心的**线程安全优先队列** (`PriorityQueue`)。
    2.  **主循环 (`run`)：** 它的循环逻辑是“**睡觉，直到排班表上的下一个任务到点**”。
    3.  **时间标准：** 必须统一使用 **UTC 时间戳**（`time.time()`）。
    4.  **错误处理：** `run` 循环在执行 `task.run()` 时，**必须**使用 `try...except` 包裹，捕获崩溃，记录日志，并自动将该任务**重新排班**到（例如）5分钟后重试，以防止“静默死亡”。

---

## 4. 🛠️ 任务执行器 (The Tasks)

* **角色：** 负责所有具体业务逻辑的“工人”。
* **实现：** `BaseTask` (新合同) 和 `WolfTask` (具体实现) 等 Class。
* **职责：**
    1.  **`run()` 是核心：**
    2.  从 `DataStore` 读取数据（如体力）。
    3.  **做“智能诊断”**（比如调用 `basic.py` 里的 `get_location_image` 来判断页面）。
    4.  **做“策略执行”**（比如 `basic.click_coord(*pos)` 或“返回首页重试”）。
    5.  向 `DataStore` 写回数据（消耗体力）。
    6.  **自我延续：** 在 `run()` 结束时，**自己**计算下次执行时间，并调用 `CentralScheduler.add_task(...)` 重新排班。
    7.  **自我终止：** 如果刷满次数，`run()` 结束时**不**调用 `add_task`，任务即自然完成。

---

## 5. 🧰 工具箱 (The Toolbox)

* **角色：** 纯粹的“哑巴工具箱”。
* **实现：** `basic.py` 文件。
* **职责：**
    1.  提供 `get_location_image(img, region=None)`、`click_coord(x, y)`、`ocr_text_in_region(region)` 等“原语”函数。
    2.  **100% 健壮：** 所有函数都**必须**用 `try...except` 包裹，并使用 `logging` 记录错误，**永不崩溃**。

---

## 6. 🖥️ 原生UI (The View - PySide)

* **角色：** 原生的“应用窗口”（“遥控器”）。
* **实现：**
    1.  **`Qt Designer`**：用于**拖拽**生成 `.ui` 文件（皮肤）。
    2.  **`pyside6-uic`**：用于将 `.ui` 文件**编译**成 `ui_MainWindow.py`（皮肤代码）。
    3.  **`main.py` (新)**：你的新“主入口”（取代 `KSAS.py`）。它负责启动 `QApplication`、加载“核心”（`DataStore`, `Scheduler`），并显示窗口。
* **取代：** 它**彻底取代**了 `PyWebIO`、`ui.py` 和 `KSAS.py`（作为服务器的部分）。

---

## 7. 🔌 UI与核心的“胶水” (The Glue)

* **角色：** 连接“原生UI”和“后台核心”。
* **实现：** `PySide` 的**信号与槽 (Signals & Slots)** 和 **`QThread`**。
* **职责：**
    1.  **后台 (`Scheduler`) 必须**在 `QThread` (PySide 自己的线程) 中运行，以防“冻结”UI。
    2.  **UI -> 后台：** `main.py` 中，按钮的 `clicked.connect(...)`（信号）**直接**调用 `GlobalScheduler.add_task(...)`（槽）。
    3.  **后台 -> UI：** `DataStore` **必须**“**发射信号**”(`emit`)，UI 窗口**必须**“**接收信号**”(`slot`) 来安全地更新体力显示或日志。

---

## 8. 📇 任务注册中心 (The Task Registry)

* **角色：** 连接“UI控件”和“任务Class”的“翻译字典”。
* **实现：** 一个全局的 `dict`（在 `task_registry.py` 中）。
* **职责：** `main.py`（“胶水”）读取这个字典，用来**动态生成** UI 上的任务复选框，并**知道**当用户点击“刷狼”时，它应该去实例化 `WolfTask` Class。

---

## 9. 📝 日志系统 (The Logging)

* **角色：** “黑匣子”和“实时监视器”。
* **实现：** Python 内置的 `logging` 模块 + `DataStore` 的“日志桥”。
* **职责：**
    1.  **双重分发：** 所有 `logging.info(...)` 都**同时**发送到 `data/ksas.log` (用于调试) 和 `DataStore._log_deque` (用于UI)。
    2.  **UI消费：** `DataStore` 的日志桥**必须**“**发射信号**”(`emit`)，UI 窗口**必须**“**接收信号**”(`slot`)，才能安全地（在UI线程）将日志显示在文本框里。