# Netflix NFToken Generator v2.0 (GUI & Multi-Threaded)

High-performance Python application and GUI for generating Netflix `NFToken` auto-login links from session cookies in batch mode using concurrent threads.

Supports complex account list formats such as:
- `email:password:country:NetflixId=...; SecureNetflixId=...`
- `email:password:NetflixId=...; SecureNetflixId=...`
- `NetflixId=...; SecureNetflixId=...`
- Netscape tabular cookie format
- JSON cookie arrays/objects

---

## 🌟 Features

- **🎨 Modern Dark GUI**: Built with Tkinter, featuring a dark theme (`#141414` / Netflix Red accent `#E50914`).
- **⚡ Multithreaded Batch Engine**: Configurable thread pool (1 to 50 threads) for processing hundreds of accounts in seconds.
- **🔍 Smart Multi-Format Parser**: Automatically extracts email, password, country metadata, and Netflix session cookies regardless of order.
- **📊 Live Results & Context Menu**:
  - Interactive table view with color-coded status tags (`SUCCESS` / `FAILED`).
  - Right-click actions to copy `NFToken` link, copy `email:pass:link`, or open link directly in browser.
- **📜 Real-time Log Console**: Live scrollable output log with timestamps and status details.
- **💾 Auto & Manual Export**: Automatically saves valid tokens to `output/valid_tokens.txt` and failed accounts to `output/failed_tokens.txt`.
- **💻 CLI & GUI Modes**: Launch GUI by default (`python nf-token-generator.py`) or run headlessly using `--cli`.

---

## 📦 Requirements

- Python 3.7+
- `requests`
- `customtkinter`

Install dependencies:

```bash
pip install requests customtkinter
```

---

## 🚀 Quick Start

### 1. Launch Graphical User Interface (GUI)

Simply run:

```bash
python nf-token-generator.py
```

- **Paste accounts** into the *Accounts Input* tab or click **📁 Load File** to select your `input.txt`.
- Set **Threads** count (e.g. `5` or `10`).
- Click **▶ START BATCH**.
- View live results in the **Results Table** tab or double-click any row to open the login link in your browser!

---

### 2. Run Command Line Interface (CLI)

To run in headless or terminal mode:

```bash
python nf-token-generator.py --cli --threads 10
```

Custom input & output files:

```bash
python nf-token-generator.py --cli --input my_accounts.txt --threads 15 --output valid_results.txt
```

---

## 📄 Input Formats Supported

The generator automatically parses any of the following formats in `input.txt` or pasted directly into the GUI:

### 1. Email:Pass:Country:Cookies
```text
fellipe1993.fl@gmail.com:Felipe210982:Country:NetflixId=v%3D3%26ct%3D...; SecureNetflixId=v%3D3...
```

### 2. Email:Pass:Cookies
```text
robsoboaventurasantos3258@gmail.com:32586370:NetflixId=v%3D3%26ct%3D...; SecureNetflixId=v%3D3...
```

### 3. Cookies First or Reversed Order
```text
mborgescarmo@bol.com.br:Ma09011992:SecureNetflixId=v%3D3...;NetflixId=v%3D3...;
```

### 4. Pure Raw Cookie String
```text
NetflixId=v%3D3%26ct%3D...; SecureNetflixId=v%3D3...
```

---

## 📁 Output

Valid tokens are saved formatted as:
```text
email:password:country:https://netflix.com/?nftoken=...
email:password:https://netflix.com/?nftoken=...
```

Output files:
- `output/valid_tokens.txt` (Valid auto-login links)
- `output/failed_tokens.txt` (Failed accounts & error reasons)

---

## 👤 Credits & Contact

- Original Author: Harshit Kamboj
- Website: https://harshitkamboj.in
- Discord: https://discord.gg/DYJFE9nu5X

---

## ⚠️ Disclaimer

Educational use only. Use only on accounts and cookies you are authorized to test.
