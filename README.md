# Kitsu Publisher

A lightweight Windows desktop tool for publishing shot previews to [Kitsu](https://www.cg-wire.com/kitsu) directly from your local machine — without opening a browser.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Features

- **Login with saved credentials** — server URL, email and password stored securely in the Windows Credential Manager (never in plain text)
- **Remembers your last project, sequence and shot** across sessions
- **Cascading dropdowns** — Project → Sequence → Shot → Task Type
- **Drag & drop or browse** a clip to publish (`.mp4` `.mov` `.avi` `.mkv` `.webm` `.png` `.jpg` `.exr` `.tiff`)
- **Add a comment** with each revision
- **Set task status** after publishing (e.g. WFA — Waiting For Approval)
- **Real-time upload progress bar**

---

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- A running [Kitsu / Zou](https://kitsu.cg-wire.com) instance

---

## Installation

### 1. Install Python

Download from [python.org](https://www.python.org/downloads/).  
During installation, check **"Add Python to PATH"**.

### 2. Clone or download this repository

```bash
git clone https://github.com/yourusername/kitsu-publisher.git
cd kitsu-publisher
```

Or just download `KitsuPublisher.py` directly.

### 3. Install dependencies

```bash
pip install PySide6 gazu requests keyring
```

### 4. Run

```bash
python KitsuPublisher.py
```

---

## Compiling to a standalone .exe

You can package the app into a single `.exe` that runs on any Windows machine without requiring Python to be installed.

### 1. Install PyInstaller

```bash
pip install pyinstaller
```

### 2. Build

```bash
pyinstaller --onefile --windowed --name "KitsuPublisher" KitsuPublisher.py
```

| Flag | Purpose |
|---|---|
| `--onefile` | Bundle everything into a single `.exe` |
| `--windowed` | No terminal window (GUI only) |
| `--name` | Name of the output executable |

### 3. Find your executable

The compiled file will be at:

```
dist/KitsuPublisher.exe
```

### Notes on compilation

- The first build takes a few minutes — PyInstaller is bundling Python and all dependencies
- Windows Defender or antivirus may flag or lock the `.exe` during build — this is a false positive common with PyInstaller. Temporarily pause your antivirus if the build fails with a permission error
- If you get `PermissionError: [WinError 5]` during build, it means the old `.exe` is still running — close it first, then rebuild
- The `.exe` will be around 80–120 MB due to the bundled PySide6 libraries

### Optional: add an icon

```bash
pyinstaller --onefile --windowed --name "KitsuPublisher" --icon=icon.ico KitsuPublisher.py
```

---

## Usage

1. Launch the app and enter your Kitsu server URL, email and password
2. Check **Remember me** to save credentials securely in Windows Credential Manager
3. Select your **Project → Sequence → Shot → Task Type**
4. Drag & drop a clip onto the drop zone (or click **Browse file…**)
5. Optionally add a comment
6. Choose the status to set after publishing (e.g. **Waiting For Approval**)
7. Click **Publish to Kitsu**

The app will post the comment, upload the preview, and set it as the main preview on the shot. The task status will be updated automatically.

---

## Security

- Passwords, server URL and email are stored in the **Windows Credential Manager** via the `keyring` library — not in any file
- The settings file (`~/.kitsu_publisher.json`) only stores non-sensitive data: last selected project, sequence and shot IDs
- No credentials are ever written to disk in plain text

---

## Troubleshooting

**Login fails**  
Double-check your server URL includes the protocol: `http://` or `https://`. No trailing slash needed.

**Projects don't load after login**  
Your Kitsu account may not have access to any open projects. Check your role and project assignments in Kitsu.

**Upload succeeds in the app but preview is stuck on "processing" in Kitsu**  
This is handled server-side by Kitsu's FFmpeg transcoder. For large files it can take a minute. If it stays stuck indefinitely, check that your Zou instance has the job queue worker running.

**`PermissionError` when building .exe**  
The old `KitsuPublisher.exe` in `dist/` is still running. Close it and try again.

**Antivirus blocks the .exe**  
Add an exclusion for the `dist/` folder, or sign the executable with a code-signing certificate.

---

## Dependencies

| Package | Purpose |
|---|---|
| `PySide6` | Qt6 GUI framework |
| `gazu` | Official Kitsu/Zou Python client |
| `requests` | HTTP streaming for file upload |
| `keyring` | Secure OS credential storage |

---

## License

MIT — free to use, modify and distribute.
