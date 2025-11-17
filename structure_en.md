# Final Architecture Blueprint: KSAS V2 (Native Desktop Edition)

This is a robust "three-tier decoupled" architecture, composed of four independent systems: "The DataStore," "The Scheduler," "The UI," and "The Tasks." It is supplemented by five supporting facilities: "Persistence," "Logging," "The Task Registry," "The Toolbox," and "The Launcher."

This architecture is specifically designed for 7x24 stable operation, state persistence, a native UI experience, and automatic updates.

---

## 0. 🚀 The Launcher & Auto-Updater

*   **Role:** The **sole entry point** for the entire application. The user only runs this script and never runs the main program directly.
*   **Implementation:** A `launcher.py` script located **outside** the `KSAS_v2` folder.
*   **Responsibilities:**
    1.  **Auto-Update:** First, it executes `git pull` (accessing your **private repository** via SSH or PAT) to get the latest code.
    2.  **Install Dependencies:** Next, it runs `pip install -r requirements.txt` to install any new dependencies.
    3.  **Launch:** Finally, it executes `python KSAS_v2/main.py` (your new main program) to start the application.

---

## 1. 💾 The DataStore

*   **Role:** The single "source of truth" (the company's database), managing all "state" and "configuration."
*   **Implementation:** A global singleton `DataStore` Class (in `datastore.py`).
*   **Responsibilities:**
    1.  **Thread-Safe:** It must use `threading.Lock` internally to protect all data (`_stamina`, `_wolf_interval`, etc.).
    2.  **Manage State:** Stores all dynamic data (like current stamina) and static configuration (like the stamina cost for fighting a wolf).
    3.  **Emit Signals:** When data is changed by a `set_...` method, it **must** **emit** a signal (e.g., `stamina_changed_signal.emit(new_value)`) via PySide's signals, allowing the UI to safely receive updates.

---

## 2. 🗄️ Persistence

*   **Role:** The "hard drive save file" for the `DataStore`, preventing data loss upon script restart.
*   **Implementation:** A local file (e.g., `data/datastore.json`).
*   **Responsibilities:**
    1.  **Load:** During **initialization** (`__init__`), the `DataStore` **must** first read the "save file" from `datastore.json` (if the file exists).
    2.  **Save:** All "write" methods in the `DataStore` (like `set_stamina`), while updating the data in memory, **must** immediately write the new data back to `datastore.json`.

---

## 3. ⏰ The Central Scheduler

*   **Role:** The "manager" that only deals with "time" and "execution."
*   **Implementation:** A global singleton `CentralScheduler` Class (in `scheduler.py`).
*   **Responsibilities:**
    1.  **Schedule:** Internally maintains a core **thread-safe priority queue** (`PriorityQueue`).
    2.  **Main Loop (`run`):** Its loop logic is to "**sleep until the next scheduled task is due**."
    3.  **Time Standard:** Must uniformly use **UTC timestamps** (`time.time()`).
    4.  **Error Handling:** The `run` loop, when executing `task.run()`, **must** be wrapped in a `try...except` block to catch crashes, log them, and automatically **reschedule** the task to retry after (for example) 5 minutes, preventing "silent failures."

---

## 4. 🛠️ The Tasks

*   **Role:** The "workers" responsible for all specific business logic.
*   **Implementation:** `BaseTask` (the new contract) and `WolfTask` (the specific implementation), etc., as Classes.
*   **Responsibilities:**
    1.  **`run()` is the core:**
    2.  Reads data from the `DataStore` (e.g., stamina).
    3.  **Performs "smart diagnostics"** (e.g., calling `get_location_image` from `basic.py` to identify the current page).
    4.  **Executes "strategy"** (e.g., `basic.click_coord(*pos)` or "return to the main page and retry").
    5.  Writes data back to the `DataStore` (e.g., consumed stamina).
    6.  **Self-Perpetuation:** At the end of its `run()`, the task **itself** calculates its next execution time and calls `CentralScheduler.add_task(...)` to reschedule itself.
    7.  **Self-Termination:** If the task has completed its required number of runs, it **does not** call `add_task` at the end of `run()`, and the task finishes naturally.

---

## 5. 🧰 The Toolbox

*   **Role:** A purely "dumb toolbox."
*   **Implementation:** The `basic.py` file.
*   **Responsibilities:**
    1.  Provides "primitive" functions like `get_location_image(img, region=None)`, `click_coord(x, y)`, `ocr_text_in_region(region)`, etc.
    2.  **100% Robust:** All functions **must** be wrapped in `try...except` and use `logging` to record errors. They should **never crash**.

---

## 6. 🖥️ The Native UI (The View - PySide)

*   **Role:** The native "application window" (the "remote control").
*   **Implementation:**
    1.  **`Qt Designer`**: Used to **drag-and-drop** to create a `.ui` file (the skin).
    2.  **`pyside6-uic`**: Used to **compile** the `.ui` file into `ui_MainWindow.py` (the skin's code).
    3.  **`main.py` (New)**: Your new "main entry point" (replaces `KSAS.py`). It is responsible for starting the `QApplication`, loading the "core" (`DataStore`, `Scheduler`), and displaying the window.
*   **Replaces:** It **completely replaces** `PyWebIO`, `ui.py`, and `KSAS.py` (the server part).

---

## 7. 🔌 The Glue (UI and Core)

*   **Role:** Connects the "Native UI" and the "backend core."
*   **Implementation:** PySide's **Signals & Slots** and **`QThread`**.
*   **Responsibilities:**
    1.  The backend (`Scheduler`) **must** run in a `QThread` (PySide's own thread) to prevent "freezing" the UI.
    2.  **UI -> Backend:** In `main.py`, a button's `clicked.connect(...)` (signal) **directly** calls `GlobalScheduler.add_task(...)` (slot).
    3.  **Backend -> UI:** The `DataStore` **must** "**emit signals**," and the UI window **must** have "**slots**" to receive these signals to safely update the stamina display or logs.

---

## 8. 📇 The Task Registry

*   **Role:** A "translation dictionary" that connects "UI controls" to "Task Classes."
*   **Implementation:** A global `dict` (in `task_registry.py`).
*   **Responsibilities:** The `main.py` (the "glue") reads this dictionary to **dynamically generate** task checkboxes on the UI and to **know** that when a user clicks "Fight Wolf," it should instantiate the `WolfTask` Class.

---

## 9. 📝 The Logging System

*   **Role:** The "black box" and "real-time monitor."
*   **Implementation:** Python's built-in `logging` module + a "log bridge" in the `DataStore`.
*   **Responsibilities:**
    1.  **Dual Dispatch:** All `logging.info(...)` calls send messages **simultaneously** to `data/ksas.log` (for debugging) and `DataStore._log_deque` (for the UI).
    2.  **UI Consumption:** The `DataStore`'s log bridge **must** "**emit a signal**," and the UI window **must** have a "**slot**" to receive it, in order to safely display the log in a text box (on the UI thread).