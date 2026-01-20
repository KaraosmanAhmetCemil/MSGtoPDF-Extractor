# MSG → PDF Attachment Extractor (GUI)

A lightweight desktop **GUI application** that extracts **PDF attachments** from Outlook **`.msg` email files** and saves them into a chosen output directory.

This tool is ideal if you have many `.msg` files (single files or entire folders) and want to quickly collect all PDF attachments without opening the emails manually.

---

## ✅ What this tool does

* Reads Microsoft Outlook **`.msg` email files**
* Scans them for **attachments**
* Extracts **only PDFs**
* Saves extracted PDFs into a selected output folder
* Provides a live **log output** showing exactly what happened

---

## 🖥️ GUI Overview (Buttons + Options)

### **Input (.msg files / folders)**

#### **Add .msg Files…**

* Opens a file picker dialog
* Lets you select **one or multiple** `.msg` files
* Adds them to the file list

✅ Use this when you already know exactly which `.msg` emails you want to process.

---

#### **Add Folder…**

* Opens a folder picker dialog
* Adds all `.msg` files found inside the chosen folder
* If **Recursive folder scan** is enabled, it will also search subfolders

✅ Best option for batch processing large archives.

---

#### **Remove Selected**

* Removes the highlighted entries from the list
* Useful if you accidentally added the wrong files

---

#### **Clear**

* Removes **everything** from the list
* Resets the input selection to empty

---

### **Options**

#### ✅ Recursive folder scan

* **Unchecked:** only scans the folder you selected (top level)
* **Checked:** scans the folder **and all nested folders**

Example:

* `Emails/`

  * `January/`
  * `February/`
  * `2025/April/`

With recursion enabled, it will collect `.msg` files from all of those automatically.

---

#### ✅ Debug log

* Adds additional technical output to the log (useful for troubleshooting)
* Recommended only if something fails or doesn’t extract as expected

---

### **Output directory**

#### Output directory field

* Shows the currently selected output path
* This is where extracted PDFs will be saved

#### **Browse…**

* Opens a folder picker
* Lets you select your desired destination folder for extracted PDF files

---

### **Actions**

#### **Start Extraction**

* Starts processing all selected `.msg` files
* For each `.msg`, it checks the attachments and extracts PDFs
* Progress is shown in the log window
* When finished, you’ll see a “Done. Extracted X PDF(s).” message

---

#### **Cancel**

* Stops the extraction process (if currently running)
* Useful if you accidentally selected too many files or want to restart

*(Depending on the extraction progress, it may stop immediately or after finishing the current file.)*

---

## 🧾 Log Output (What it shows)

During extraction the log displays things like:

* Which `.msg` file is being processed
* Whether extraction was successful
* How many PDFs were extracted from each `.msg`
* Final summary like:
  **Done. Extracted 8 PDF(s).**

✅ This makes it easy to verify that everything worked correctly.

---

## 🚀 Typical Workflow

1. Click **Add .msg Files…** *(or Add Folder…)*
2. *(Optional)* Enable **Recursive folder scan**
3. Choose output directory using **Browse…**
4. Click **Start Extraction**
5. Check the log output
6. Find your PDFs in the output folder ✅

---

## 📦 Supported Attachments

✅ Extracted:

* `.pdf`

❌ Ignored (by design):

* `.png`, `.jpg`, `.docx`, `.xlsx`, `.zip`, etc.

*(This keeps output clean when you only care about PDFs.)*

---

## 🧰 Requirements

* Python **3.10+** recommended
* Works best with a clean virtual environment

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## ▶️ Run Locally (Development)

```bash
python msg_pdf_extractor_gui.py
```

---

## 🏗️ Build as Executable (PyInstaller)

### ✅ Build for macOS

```bash
pyinstaller --noconfirm --windowed --name "MSG PDF Extractor" msg_pdf_extractor_gui.py
```

### ✅ Build for Windows

```bash
pyinstaller --noconfirm --onefile --windowed --name "MSG PDF Extractor" msg_pdf_extractor.py
```

---

## 📌 Notes / Known Behavior

* If a single `.msg` file contains **multiple PDFs**, all will be extracted
* If duplicate PDF names exist, the tool may auto-rename files to avoid overwriting
* Extraction speed depends on:

  * number of `.msg` files
  * attachment sizes
  * disk performance

---

## 👤 Author

Made by **ACK**

---
