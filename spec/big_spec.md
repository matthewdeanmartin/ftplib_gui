# Specification: `ftplib-gui`

## 1. Overview

`ftplib-gui` is a lightweight desktop FTP/FTPS client built entirely with Python standard library modules. It provides a graphical interface for browsing local and remote files, uploading and downloading files, managing directories, and viewing transfer logs.

The application must not require any third-party packages.

Primary stdlib modules:

```python
ftplib
tkinter
tkinter.ttk
tkinter.filedialog
tkinter.messagebox
threading
queue
pathlib
os
stat
time
datetime
json
ssl
logging
webbrowser
```

Optional stdlib modules:

```python
argparse
configparser
hashlib
tempfile
shutil
platform
subprocess
```

---

## 2. Goals

`ftplib-gui` should provide:

1. A usable graphical FTP client for basic file transfer workflows.
2. Support for plain FTP and explicit FTPS using `ftplib.FTP_TLS`.
3. A dual-pane local/remote file browser.
4. Upload, download, delete, rename, mkdir, refresh, and navigation actions.
5. Transfer progress reporting.
6. A queue-based transfer system that keeps the UI responsive.
7. A connection manager for saving host profiles.
8. A log panel for FTP commands, transfer events, and errors.
9. A clean architecture suitable for future extension.

---

## 3. Non-goals

The first version will not support:

1. SFTP, because SFTP is SSH-based and not supported by the Python standard library.
2. Recursive directory synchronization.
3. Parallel transfer workers.
4. Drag-and-drop, since cross-platform DnD is not well supported by stdlib `tkinter`.
5. Site-to-site FTP transfer.
6. Remote text editing.
7. ZIP previewing or archive browsing.
8. Proxy support.
9. Advanced certificate trust management beyond stdlib `ssl`.

---

## 4. Supported Protocols

### 4.1 FTP

Uses:

```python
ftplib.FTP
```

Required features:

* Connect to host and port.
* Login with username and password.
* Anonymous login option.
* Passive mode toggle.
* Directory listing.
* Upload and download files.
* Delete files.
* Create and remove directories.
* Rename files or directories.
* Change remote working directory.

### 4.2 FTPS

Uses:

```python
ftplib.FTP_TLS
ssl
```

Supported mode:

* Explicit FTPS using `AUTH TLS`.

Required features:

* Secure control connection.
* Secure data connection using `prot_p()`.
* Optional insecure certificate mode for legacy servers.
* Optional strict certificate validation using `ssl.create_default_context()`.

Not supported:

* Implicit FTPS on port 990 in v1 unless explicitly added.
* Client certificate authentication.

---

## 5. Application Layout

The main window contains five primary regions.

```text
+-------------------------------------------------------------+
| Menu Bar                                                    |
+-------------------------------------------------------------+
| Connection Toolbar                                          |
+-----------------------------+-------------------------------+
| Local Browser               | Remote Browser                |
|                             |                               |
+-----------------------------+-------------------------------+
| Transfer Queue                                               |
+-------------------------------------------------------------+
| Log Output                                                   |
+-------------------------------------------------------------+
| Status Bar                                                   |
+-------------------------------------------------------------+
```

---

## 6. Main UI Components

### 6.1 Menu Bar

Menus:

#### File

* New Connection
* Open Connection Profile
* Save Current Profile
* Disconnect
* Exit

#### Edit

* Rename
* Delete
* New Folder
* Refresh

#### Transfer

* Upload Selected
* Download Selected
* Cancel Selected Transfer
* Clear Completed Transfers

#### View

* Show Log Panel
* Show Hidden Files
* Refresh Local
* Refresh Remote

#### Help

* About
* Python `ftplib` Documentation

---

### 6.2 Connection Toolbar

Fields:

* Host
* Port
* Username
* Password
* Protocol selector:

  * FTP
  * FTPS Explicit
* Passive mode checkbox
* Anonymous checkbox
* Connect button
* Disconnect button

Behavior:

* Password field must mask input.
* Anonymous mode disables username/password fields and uses:

  * username: `anonymous`
  * password: `anonymous@`
* Port defaults:

  * FTP: `21`
  * FTPS Explicit: `21`

---

### 6.3 Local File Browser

Implemented with `ttk.Treeview`.

Columns:

* Name
* Size
* Modified
* Type

Required behavior:

* Shows the current local directory.
* Supports navigating into folders by double-click.
* Supports going up one directory.
* Supports selecting one or more files.
* Supports refresh.
* Supports creating local folders.
* Supports deleting local files/folders after confirmation.
* Supports rename.

Local path field:

```text
Local: /Users/example/Downloads
```

Local navigation buttons:

* Up
* Home
* Refresh
* Choose Folder

---

### 6.4 Remote File Browser

Implemented with `ttk.Treeview`.

Columns:

* Name
* Size
* Modified
* Type
* Permissions, if available

Required behavior:

* Shows the current remote directory.
* Supports navigating into folders by double-click.
* Supports going up one directory.
* Supports selecting one or more files.
* Supports refresh.
* Supports creating remote folders.
* Supports deleting remote files/folders after confirmation.
* Supports rename.

Remote path field:

```text
Remote: /public_html
```

Remote navigation buttons:

* Up
* Root
* Refresh
* New Folder

---

### 6.5 Transfer Queue

Implemented with `ttk.Treeview`.

Columns:

* Direction
* Source
* Destination
* Size
* Progress
* Status
* Speed
* ETA

Statuses:

* Queued
* Running
* Completed
* Failed
* Cancelled

Transfer directions:

* Upload
* Download

Actions:

* Cancel selected transfer
* Retry failed transfer
* Clear completed transfers

---

### 6.6 Log Panel

Implemented with `tkinter.Text`.

The log panel should display:

* Connection events.
* Login success/failure.
* Directory changes.
* Transfer start/completion.
* Transfer errors.
* Server messages where appropriate.

Example:

```text
[2026-05-01 14:13:22] Connecting to ftp.example.com:21
[2026-05-01 14:13:23] Connected
[2026-05-01 14:13:23] Logged in as matt
[2026-05-01 14:13:25] Download started: /pub/file.txt
[2026-05-01 14:13:27] Download completed: file.txt
```

The log panel should not display raw passwords.

---

### 6.7 Status Bar

Displays:

* Connection state.
* Current remote directory.
* Number of selected local items.
* Number of selected remote items.
* Current transfer status.

Example:

```text
Connected to ftp.example.com | Remote: /pub | 2 remote items selected | 1 transfer running
```

---

## 7. Architecture

The application should use a layered design.

```text
GUI Layer
  |
  v
Application Controller
  |
  +--> LocalFileService
  |
  +--> FTPClientService
  |
  +--> TransferManager
  |
  +--> ProfileStore
  |
  +--> Logger
```

---

## 8. Core Classes

### 8.1 `FTPClientService`

Responsible for all FTP operations.

Suggested interface:

```python
class FTPClientService:
    def connect(self, profile: ConnectionProfile) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...

    def pwd(self) -> str: ...
    def cwd(self, path: str) -> None: ...
    def cdup(self) -> None: ...

    def listdir(self, path: str | None = None) -> list[RemoteEntry]: ...

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int], None],
        cancel_event: threading.Event,
    ) -> None: ...

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Callable[[int], None],
        cancel_event: threading.Event,
    ) -> None: ...

    def mkdir(self, path: str) -> None: ...
    def rmdir(self, path: str) -> None: ...
    def delete_file(self, path: str) -> None: ...
    def rename(self, old_path: str, new_path: str) -> None: ...
```

Implementation notes:

* Use `FTP_TLS` when protocol is FTPS.
* Call `prot_p()` after login for FTPS data-channel protection.
* Use passive mode according to the profile setting.
* Use `retrbinary()` for downloads.
* Use `storbinary()` for uploads.
* Avoid calling FTP methods directly from the Tkinter main thread.

---

### 8.2 `LocalFileService`

Responsible for local filesystem operations.

Suggested interface:

```python
class LocalFileService:
    def listdir(self, path: pathlib.Path) -> list[LocalEntry]: ...
    def mkdir(self, path: pathlib.Path) -> None: ...
    def delete(self, path: pathlib.Path) -> None: ...
    def rename(self, old_path: pathlib.Path, new_path: pathlib.Path) -> None: ...
    def home(self) -> pathlib.Path: ...
```

Use:

```python
pathlib.Path
os.scandir
stat
shutil
```

---

### 8.3 `TransferManager`

Responsible for the transfer queue.

Suggested interface:

```python
class TransferManager:
    def enqueue_upload(self, local_path: Path, remote_path: str) -> TransferJob: ...
    def enqueue_download(self, remote_path: str, local_path: Path) -> TransferJob: ...
    def cancel(self, job_id: str) -> None: ...
    def retry(self, job_id: str) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

Requirements:

* Runs transfers on a background worker thread.
* Uses `queue.Queue` to receive transfer jobs.
* Uses `queue.Queue` to send progress events back to the GUI.
* Supports cancellation via `threading.Event`.
* Processes one transfer at a time in v1.
* Does not mutate Tkinter widgets from worker threads.

---

### 8.4 `ProfileStore`

Responsible for saving and loading connection profiles.

Suggested storage:

```text
~/.ftplib-gui/profiles.json
```

Suggested profile shape:

```json
{
  "profiles": [
    {
      "name": "Example FTP",
      "host": "ftp.example.com",
      "port": 21,
      "protocol": "ftp",
      "username": "matt",
      "anonymous": false,
      "passive": true,
      "default_local_dir": "/Users/matt/Downloads",
      "default_remote_dir": "/"
    }
  ]
}
```

Password handling:

* v1 should not save passwords by default.
* If “remember password” is added, the UI must warn that stdlib-only Python cannot provide a secure cross-platform keychain.
* Stored passwords should be avoided unless the user explicitly opts in.

---

## 9. Data Models

### 9.1 `ConnectionProfile`

```python
@dataclass
class ConnectionProfile:
    name: str
    host: str
    port: int = 21
    protocol: str = "ftp"  # "ftp" or "ftps"
    username: str = ""
    password: str = ""
    anonymous: bool = False
    passive: bool = True
    verify_tls: bool = True
    default_local_dir: str | None = None
    default_remote_dir: str | None = None
```

---

### 9.2 `RemoteEntry`

```python
@dataclass
class RemoteEntry:
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    modified: datetime | None = None
    permissions: str | None = None
```

---

### 9.3 `LocalEntry`

```python
@dataclass
class LocalEntry:
    name: str
    path: pathlib.Path
    is_dir: bool
    size: int | None = None
    modified: datetime | None = None
```

---

### 9.4 `TransferJob`

```python
@dataclass
class TransferJob:
    id: str
    direction: str  # "upload" or "download"
    source: str
    destination: str
    size: int | None = None
    bytes_done: int = 0
    status: str = "queued"
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
```

---

## 10. Remote Directory Listing

`ftplib` provides several listing options with inconsistent server support.

Preferred order:

1. Try `mlsd()` first.
2. Fall back to `dir()`.
3. Fall back to `nlst()`.

### 10.1 `mlsd()`

When available, `mlsd()` should be preferred because it returns structured facts.

Example:

```python
for name, facts in ftp.mlsd():
    entry_type = facts.get("type")
    size = facts.get("size")
    modify = facts.get("modify")
```

Map FTP `type` values:

| FTP type | Meaning           |
| -------- | ----------------- |
| `file`   | File              |
| `dir`    | Directory         |
| `cdir`   | Current directory |
| `pdir`   | Parent directory  |

Skip:

* `cdir`
* `pdir`

### 10.2 `dir()` Fallback

When `mlsd()` fails, parse Unix-like `LIST` output where possible.

Example line:

```text
-rw-r--r-- 1 user group 1024 Jan 01 12:00 file.txt
```

Known limitation:

* FTP `LIST` format is not standardized.
* Parsing may fail on non-Unix servers.
* Unknown entries should still be displayed with best-effort metadata.

### 10.3 `nlst()` Fallback

If only names are available:

* Display names.
* Unknown size.
* Unknown modification date.
* Unknown type unless detected by attempting `cwd`.

Directory detection fallback:

```python
current = ftp.pwd()
try:
    ftp.cwd(candidate)
    is_dir = True
    ftp.cwd(current)
except ftplib.error_perm:
    is_dir = False
```

This should be used sparingly because it is slow.

---

## 11. Transfer Behavior

### 11.1 Downloads

Use:

```python
ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=8192)
```

The callback should:

1. Write the block to the local file.
2. Increment bytes transferred.
3. Send a progress event to the GUI event queue.
4. Check whether the cancel event is set.

Cancellation limitation:

* `ftplib.retrbinary()` does not provide a clean built-in cancellation mechanism.
* The callback may raise a custom exception such as `TransferCancelled`.
* The service should then close or reset the FTP connection if necessary.

---

### 11.2 Uploads

Use:

```python
ftp.storbinary(f"STOR {remote_path}", fileobj, blocksize=8192, callback=callback)
```

The callback should:

1. Increment bytes transferred.
2. Send a progress event.
3. Check cancellation state.

---

### 11.3 Progress

Progress percentage:

```python
percent = int(bytes_done / total_bytes * 100)
```

If total size is unknown:

* Display bytes transferred.
* Show progress as indeterminate.
* Do not display ETA.

---

### 11.4 Transfer Speed

Calculate speed using elapsed time:

```python
speed = bytes_done / elapsed_seconds
```

Display:

* B/s
* KB/s
* MB/s

---

### 11.5 ETA

When total size is known:

```python
remaining_bytes = total_bytes - bytes_done
eta_seconds = remaining_bytes / bytes_per_second
```

---

## 12. Threading Model

Tkinter must run on the main thread.

Rules:

1. All widget creation and updates happen on the Tkinter thread.
2. FTP network operations happen on worker threads.
3. Worker threads send messages to the GUI through `queue.Queue`.
4. The GUI polls the queue using `root.after()`.

Example event loop:

```python
def poll_events():
    while True:
        try:
            event = ui_queue.get_nowait()
        except queue.Empty:
            break
        handle_event(event)

    root.after(100, poll_events)
```

Event types:

```python
@dataclass
class UIEvent:
    type: str
    payload: dict
```

Suggested event names:

* `connected`
* `disconnected`
* `remote_list_loaded`
* `local_list_loaded`
* `transfer_started`
* `transfer_progress`
* `transfer_completed`
* `transfer_failed`
* `transfer_cancelled`
* `log`
* `error`

---

## 13. Error Handling

The application should catch and display errors from:

```python
ftplib.all_errors
OSError
ssl.SSLError
TimeoutError
ValueError
json.JSONDecodeError
```

Error display rules:

* Show user-friendly messages in dialogs for major failures.
* Log full error details in the log panel.
* Never crash the GUI due to a failed FTP command.
* Disable remote actions when disconnected.
* On connection loss, mark remote state as disconnected and fail active transfers.

Example user message:

```text
Could not connect to ftp.example.com:21.

The server rejected the connection or the host is unreachable.
```

Example log message:

```text
[2026-05-01 14:18:04] ERROR: Connection failed: TimeoutError('timed out')
```

---

## 14. Security Requirements

### 14.1 Passwords

* Passwords must be masked in the UI.
* Passwords must not be written to logs.
* Passwords must not be saved by default.
* Clipboard copy of passwords is not provided.

### 14.2 FTPS

* FTPS should verify certificates by default.
* Users may disable certificate verification for legacy servers.
* If verification is disabled, show a warning:

```text
TLS certificate verification is disabled. Your connection may be vulnerable to interception.
```

### 14.3 Config Files

Profile files should be created with user-only permissions where possible.

On POSIX:

```python
os.chmod(profile_path, 0o600)
```

On Windows:

* Use normal user profile directory.
* Document that stdlib-only Python does not provide full credential vault integration.

---

## 15. Platform Support

Target platforms:

* Windows 10+
* macOS 12+
* Linux desktop environments with Tk installed

Python versions:

* Python 3.11+
* Python 3.12+
* Python 3.13+

The application should degrade gracefully if `tkinter` is unavailable.

Startup error:

```text
This Python installation does not include tkinter. Please install a Python build with Tk support.
```

---

## 16. CLI Behavior

The GUI can optionally accept command-line arguments.

Example:

```bash
python -m ftplib_gui --host ftp.example.com --user matt
```

Arguments:

```text
--host
--port
--user
--protocol ftp|ftps
--passive / --active
--local-dir
--remote-dir
--profile
```

Passwords should not be accepted through CLI arguments in v1, because command-line arguments may be visible to other local processes.

---

## 17. Project Layout

Suggested package layout:

```text
ftplib_gui/
  __init__.py
  __main__.py
  app.py
  models.py
  ftp_client.py
  local_files.py
  transfers.py
  profiles.py
  logging_utils.py
  ui/
    __init__.py
    main_window.py
    connection_bar.py
    file_browser.py
    transfer_queue.py
    log_panel.py
```

---

## 18. Main User Flows

### 18.1 Connect to FTP Server

1. User enters host, port, username, and password.
2. User selects FTP or FTPS.
3. User clicks Connect.
4. UI disables connection fields.
5. Worker thread attempts connection.
6. On success:

   * Status bar shows connected state.
   * Remote file browser loads `/` or configured default directory.
7. On failure:

   * UI re-enables connection fields.
   * Error is shown.
   * Failure is logged.

---

### 18.2 Download File

1. User selects one or more remote files.
2. User clicks Download.
3. App asks for destination folder if needed.
4. Transfer jobs are added to queue.
5. Worker downloads each file.
6. Queue updates progress.
7. Local browser refreshes on completion.

---

### 18.3 Upload File

1. User selects one or more local files.
2. User clicks Upload.
3. App uploads into current remote directory.
4. Transfer jobs are added to queue.
5. Worker uploads each file.
6. Queue updates progress.
7. Remote browser refreshes on completion.

---

### 18.4 Create Remote Folder

1. User clicks New Folder in remote pane.
2. Dialog asks for folder name.
3. App calls `FTP.mkd()`.
4. Remote browser refreshes.

---

### 18.5 Rename Remote File

1. User selects remote item.
2. User clicks Rename or presses F2.
3. Dialog asks for new name.
4. App calls `FTP.rename(old, new)`.
5. Remote browser refreshes.

---

### 18.6 Delete Remote File

1. User selects remote item.
2. User clicks Delete.
3. Confirmation dialog appears.
4. For files, app calls `FTP.delete()`.
5. For directories, app calls `FTP.rmd()`.
6. Remote browser refreshes.

Recursive remote deletion is not supported in v1.

---

## 19. Keyboard Shortcuts

| Shortcut  | Action                         |
| --------- | ------------------------------ |
| F5        | Refresh active pane            |
| F2        | Rename selected item           |
| Delete    | Delete selected item           |
| Enter     | Open selected directory        |
| Backspace | Go up one directory            |
| Ctrl+U    | Upload selected local items    |
| Ctrl+D    | Download selected remote items |
| Ctrl+L    | Focus local path               |
| Ctrl+R    | Focus remote path              |
| Ctrl+Q    | Quit                           |

---

## 20. UI State Rules

When disconnected:

* Disable remote browser actions.
* Disable upload/download.
* Enable connection fields.
* Show remote pane as empty or “Not connected.”

When connecting:

* Disable Connect button.
* Disable connection fields.
* Show status: `Connecting...`

When connected:

* Enable Disconnect.
* Enable remote actions.
* Enable upload/download where selections allow.

During transfer:

* Keep browsers usable.
* Disable Disconnect or confirm before disconnecting.
* Allow cancellation of queued/running transfers.

---

## 21. Logging

Use stdlib `logging`.

Log destinations:

1. GUI log panel.
2. Optional rotating file log.

Suggested log path:

```text
~/.ftplib-gui/logs/app.log
```

Use:

```python
logging.handlers.RotatingFileHandler
```

Default log level:

```text
INFO
```

Debug mode:

```bash
python -m ftplib_gui --debug
```

Must not log:

* Passwords.
* Full profile JSON if it contains secrets.
* TLS private material.

---

## 22. Testing Strategy

Since this is stdlib-only, tests should use:

```python
unittest
unittest.mock
tempfile
pathlib
```

### 22.1 Unit Tests

Test:

* Profile loading/saving.
* Local file listing.
* Transfer queue state transitions.
* Remote listing parser.
* Human-readable size formatting.
* Speed and ETA calculation.
* Error formatting.

### 22.2 FTP Client Tests

Use mocks for `ftplib.FTP` and `ftplib.FTP_TLS`.

Test:

* FTP connect.
* FTPS connect.
* Passive mode setting.
* Login behavior.
* Upload calls `storbinary`.
* Download calls `retrbinary`.
* Delete calls `delete`.
* Rename calls `rename`.

### 22.3 GUI Tests

Minimal GUI tests should verify:

* Main window initializes.
* Widgets are created.
* Buttons enable/disable correctly.
* Queue events update model state.

Avoid brittle pixel-level UI tests.

---

## 23. Packaging

No third-party build system is required.

Minimum runnable form:

```bash
python -m ftplib_gui
```

Optional source distribution can use stdlib-compatible metadata if a build backend is eventually added, but v1 should prioritize direct execution.

Suggested `__main__.py`:

```python
from .app import main

if __name__ == "__main__":
    main()
```

---

## 24. Limitations

Because this project uses only the Python standard library:

1. No SFTP support.
2. No native secure credential storage.
3. No robust cross-platform drag-and-drop.
4. No advanced theme system beyond `ttk`.
5. FTP directory listings may be inconsistent across servers.
6. Transfer cancellation may require reconnecting.
7. Recursive remote operations are limited.

---

## 25. MVP Acceptance Criteria

The MVP is complete when:

1. User can open the app with `python -m ftplib_gui`.
2. User can connect to a plain FTP server.
3. User can connect to an explicit FTPS server.
4. User can browse local files.
5. User can browse remote files.
6. User can upload one file.
7. User can download one file.
8. User can create a remote folder.
9. User can delete a remote file.
10. User can rename a remote file.
11. Transfer progress appears in the queue.
12. The UI remains responsive during transfers.
13. Errors appear in the UI instead of crashing the app.
14. Passwords are not logged.
15. No third-party imports are used.

---

## 26. Future Enhancements

Possible future versions:

1. Recursive upload/download.
2. Directory comparison.
3. Sync mode.
4. Bookmarks.
5. Transfer resume using `REST`, where supported.
6. Checksums where server supports `XMD5`, `XSHA1`, or similar nonstandard commands.
7. Implicit FTPS.
8. Import/export profiles.
9. Tabbed connections.
10. Local file search.
11. Remote file filtering.
12. Optional platform-specific credential storage, if the stdlib-only rule is relaxed.
