# Final Architecture Blueprint: KSAS V3.4 (Independent Control Edition)

**Core Design Philosophy:**
1.  **Three-Layer Decoupling:** Complete separation of UI (Display) / Scheduler (Control) / Task (Execution).
2.  **Per-Instance Isolation:** Each account possesses independent data, configuration, logs, and scheduling threads to prevent interference.
3.  **Registration-Based Management:** Only devices explicitly "added" by the user are managed by the system, eliminating chaos from automatic scanning.
4.  **Independent Control:** Each instance controls its own start/stop status, rejecting the crude "Start All" logic.

---

## 0. 🚀 The Launcher

* **Role:** The program's **Shell** and **Updater**.
* **Implementation:** Independent executable (e.g., `launcher.exe`).
* **Responsibilities:**
    1.  **Environment Self-Check:** Ensures the runtime environment is normal.
    2.  **Auto-Update:** Checks for versions online; downloads and replaces core files if updates are available.
    3.  **Invoke Core:** Uses a subprocess to call `python KSAS.py` to launch the main program. Users do not run the main script directly.

---

## 1. 🏢 The Instance Manager

* **Role:** The device **Registry Office** and **Status Monitor**.
* **Implementation:** Global Singleton `InstanceManager`.
* **Core Logic:**
    1.  **Startup Load:**
        * Performs an ADB scan upon startup.
        * Reads `data/device_registry.json` to load all known devices (connected or not).
        * Initializes `DataStore` and `Scheduler` for each registered device; sets initial status to `OFFLINE`.
    2.  **Manual Scan:**
        * Executes `adb devices` only when the UI calls `scan_devices()`.
        * **Registered Devices:** Updates status to `ONLINE`; UI icons light up.
        * **Unregistered Devices:** Returns a "Candidate List", **does not automatically add them**, waits for user decision.
    3.  **Manual Registration (Add Instance):**
        * User selects a new device in the UI and confirms; calls `add_instance(serial, alias)`.
        * Creates data objects and writes to `device_registry.json`.
    4.  **Manual Removal:** Completely deletes the instance memory object and registry entry.

---

## 2. 💾 Data Center (Per-Instance DataStore)

* **Role:** The **State Repository** for a single instance.
* **Implementation:** Ordinary Class, one object per `device_id`.
* **Responsibilities:**
    1.  **Connection Status:** Maintains `connection_status` (ONLINE/OFFLINE).
    2.  **Running Status:** Maintains `running_status` (IDLE/RUNNING/ERROR).
    3.  **Config Management:** Stores task toggles and parameter settings for the instance (modifiable even when offline).
    4.  **Signal Driving:** Emits Qt Signals to notify the UI when status or configuration changes.

---

## 3. 🗄️ Persistence System (Structured Persistence)

* **Role:** File System Mapping.
* **Directory Structure:**
    ```text
    root/
    ├── data/
    │   ├── global_settings.json       # Global Settings (ADB path, webhook URL, UI prefs)
    │   ├── device_registry.json       # Device Registry (ID, Alias, Last Online Time)
    │   │
    │   ├── [device_id_A]/             # Exclusive folder for Instance A
    │   │   ├── config.json            # Task Configuration
    │   │   ├── runtime.log            # Runtime Logs
    │   │   └── snapshots/             # Error Screenshot Storage
    │   │
    │   └── [device_id_B]/             # Exclusive folder for Instance B
    │       ├── ...
    ```

---

## 4. ⏰ Central Scheduler (Per-Instance Scheduler)

* **Role:** The **Independent Commander** for a single instance.
* **Implementation:** Inherits `QThread`, one thread per instance.
* **Control Logic:**
    1.  **Independent Start/Stop:** Provides `start_scheduler()` and `stop_scheduler()` methods for independent UI buttons.
    2.  **Safe Execution:**
        * Refuses to start if status is `OFFLINE`.
        * If user clicks "Stop", exits safely after the current task completes its atomic operation.
    3.  **Crash Prevention:** Captures all Task exceptions within `run()`, triggers a snapshot, records logs, and ensures the guardian thread does not crash.

---

## 5. 🛠️ Task Executor (Instance-Aware Tasks)

* **Role:** Business Logic Unit.
* **Implementation:** Subclass of `BaseTask`.
* **Responsibilities:**
    1.  **Context Awareness:** Must hold `instance_id` to read/write correct data.
    2.  **Logic Execution:** Read Config -> Call Toolbox -> Update Status.

---

## 6. 🧰 Toolbox (Toolbox & Snapshot)

* **Role:** Low-level Operations Library & Evidence Retention.
* **Implementation:** `basic.py` (Airtest Wrapper) + `snapshot_manager.py`.
* **Responsibilities:**
    1.  **Safe Invocation:** Encapsulates Airtest APIs, catches low-level exceptions, returns Boolean results.
    2.  **Snapshot Mechanism:**
        * Calls `adb screencap` when a task errors or a key step fails.
        * Saves the image to `data/[device_id]/snapshots/`.
        * Returns the image path to the logging system.

---

## 7. 🖥️ Native UI (Multi-Instance View)

* **Role:** Console / Dashboard.
* **Core Layout:**
    1.  **Top Toolbar:**
        * `[ 🔄 Refresh Connection ]`: Manually triggers ADB scan, updates online status.
        * `[ ➕ Add Device ]`: Pops up a dialog to select and add from scanned unknown devices.
        * `[ ⚙️ Global Settings ]`: Modifies general configs like ADB path.
    2.  **Instance Area (Tab Widget or List):**
        * **Dynamic Rendering:** Generates tabs based on `device_registry`.
        * **Independent Control Panel (Inside each tab):**
            * **Status Bar:** Displays Alias, Connection Status (Lit/Grayed), Current Stamina/AP.
            * **Operation Area:** `[ ▶ Start Script ]` / `[ ⏹ Stop Script ]` (Mutually exclusive buttons).
            * **Config Area:** Task checkbox list.
            * **Log Area:** Scrolling log exclusive to this instance (includes screenshot links).

---

## 8. 🔌 Core Glue (Glue Code)

* **Role:** Signal Routing.
* **Mechanism:**
    * **UI Button -> Scheduler:** Clicking "Start" for Instance A directly calls `instance_manager.get_scheduler(A).start()`.
    * **DataStore -> UI:** If only Instance A's stamina changes, only Instance A's UI controls are refreshed, avoiding a full interface redraw.

---

## 9. 📇 Task Registry (Task Registry)

* **Role:** Static Dictionary.
* **Responsibilities:** Maintains the mapping between Task Names and Classes for UI configuration list generation.

---

## 10. 📝 Log System (Instance-Isolated Logging)

* **Role:** Distributing Recorder.
* **Strategy:**
    1.  **Physical Isolation:** Logs are strictly written to `data/[device_id]/runtime.log`.
    2.  **Real-time Feedback:** Pushes log text (and screenshot paths) to the UI log window via Signals.