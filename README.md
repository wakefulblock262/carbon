# ✨ Carbon

[![Main Programming Language](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11-0078d7.svg?color=%23fff\&logo=Python\&logoColor=%23fff\&style=for-the-badge)](https://en.wikipedia.org/wiki/Python_%28programming_language%29) ![Secondary Programming Language](https://img.shields.io/badge/luau-0.676-white.svg?logo=lua&logoColor=white&style=for-the-badge)

[![Operating System](https://img.shields.io/badge/platform-Windows%20|%20Mac%20|%20Linux-0078d7.svg?color=%23fff\&logo=Windows\&logoColor=%23fff\&style=for-the-badge)](https://en.wikipedia.org/wiki/Operating_system) [![Architecture](https://img.shields.io/badge/architecture-x86%20|%20x64%20|%20x32-%23fff.svg?color=%23fff\&logo=Aurelia\&logoColor=%23fff\&style=for-the-badge)](https://en.wikipedia.org/wiki/Instruction_set_architecture)

## 🚀 Getting Started

### Prerequisites

> Make sure Python 3.9 – 3.11 is installed on your system.

> Get Silicon's [official Roblox Plugin](https://create.roblox.com/store/asset/130303466729127).

### Windows

> * Launch Command Prompt:
>
>   1. Press `Windows + R`, type `CMD`, then press Enter.

> * Run the command:

```batch
curl -L -o python-installer.exe https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe && python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=0 && del python-installer.exe && python -m ensurepip && python -m pip install traceback threading argparse requests shutil gzip json yaml
```

### Mac

> * Open Terminal:
>
>   1. Press `Command + Space`, type `Terminal`, then press Enter.

> * Run the command:

```bash
curl -L -o python-installer.pkg https://www.python.org/ftp/python/3.11.0/python-3.11.0-macos11.pkg && sudo installer -pkg python-installer.pkg -target / && rm python-installer.pkg && python3 -m ensurepip && python3 -m pip install traceback threading argparse requests shutil gzip json yaml
```

### Linux

> * Open Terminal:
>
>   1. Press `Ctrl + Alt + T`.

> * Run the command:

```bash
sudo apt-get update && sudo apt-get install python3 && python3 -m ensurepip && python3 -m pip install traceback threading argparse requests shutil gzip json yaml
```

---

## ⚙️ Usage

1. **Open Zed:**
   Open your project in Zed. The Carbon extension will automatically start the synchronization server in the background.

2. **Open Roblox Studio and use the Plugin Toolbar:**

   > Interact with the custom toolbar buttons to initiate script synchronization operations between Roblox Studio and Zed.

---

## 🧪 Features

 1. **Seamless Script Synchronization**

>    * Quickly, easily export/import scripts between Roblox Studio and your code editor.
>    * Bi-directional synchronization supported for efficient live development.

2. **Cross-Platform**

>    * Compatible with Windows, Mac, and Linux systems.

3. **Flexible Modes**

>    * Choose from single or two-way synchronization live-modes, or single-time ones depending on your needs.

4. **Minimal Setup**

>    * Just open Zed and interact via the Roblox Studio UI.

5. **Secure and Local**

>    * All synchronization operations and configurations are handled locally for full privacy.

---

## 📦 Dependencies

This plugin relies on the following Python modules:

```python
traceback, threading, argparse, requests, shutil, gzip, json, yaml, sys, io, os
```

As well as:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading   import Thread
```

And finally the single [Luau module](https://devforum.roblox.com/t/api-service-v107a-a-utility-modulescript-for-roblox-api-methods/1548433):

```
APIService
```

---

## 💡 Tip

Ensure you have the Carbon extension installed and enabled in Zed for automatic server management.
