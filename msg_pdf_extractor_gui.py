from __future__ import annotations

import argparse
import re
import threading
import queue
from pathlib import Path
from typing import Callable, Iterable

import extract_msg

# ----------------------------
# Core extraction logic
# ----------------------------

LogFn = Callable[[str], None]


def safe_filename(name: str) -> str:
    name = (name or "").strip().replace("\x00", "")
    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", name)  # Windows-illegal chars
    name = re.sub(r"\s+", " ", name).strip()
    return name or "attachment.bin"


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending ' (1)', ' (2)', ... if needed."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def looks_like_pdf(file_path: Path) -> bool:
    """Check PDF magic bytes: %PDF-"""
    try:
        with file_path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def _detect_saved_file(out_dir: Path, before: set[str]) -> Path | None:
    """Figure out which file extract_msg just created in out_dir."""
    after = {p.name for p in out_dir.iterdir() if p.is_file()}
    new_names = list(after - before)
    if not new_names:
        return None
    if len(new_names) == 1:
        return out_dir / new_names[0]
    candidates = [out_dir / n for n in new_names]
    return max(candidates, key=lambda p: p.stat().st_mtime, default=None)


def extract_pdfs_from_msg(
    msg_path: Path,
    out_dir: Path,
    debug: bool = False,
    log: LogFn | None = None,
) -> int:
    """Extract PDF attachments from one .msg file into out_dir. Returns count of PDFs extracted."""
    def _log(s: str) -> None:
        if log:
            log(s)

    count = 0
    msg = extract_msg.Message(str(msg_path))

    if hasattr(msg, "process"):
        msg.process()
    elif hasattr(msg, "parse"):
        msg.parse()

    attachments = getattr(msg, "attachments", None) or []
    if debug:
        _log(f"  -> Attachments found: {len(attachments)}")

    for att in attachments:
        raw_name = getattr(att, "longFilename", None) or getattr(att, "shortFilename", None) or ""
        base_name = safe_filename(raw_name)

        before = {p.name for p in out_dir.iterdir() if p.is_file()}
        att.save(customPath=str(out_dir))

        saved_path = _detect_saved_file(out_dir, before)
        if saved_path is None or not saved_path.exists():
            continue

        is_pdf = saved_path.suffix.lower() == ".pdf" or looks_like_pdf(saved_path)
        if debug:
            _log(f"  - Saved: {saved_path.name} | pdf={is_pdf}")

        if not is_pdf:
            continue

        # Preferred final name (first one should NOT have (1))
        preferred = out_dir / base_name
        if preferred.suffix.lower() != ".pdf":
            preferred = preferred.with_suffix(".pdf")

        target = preferred

        # Only add (1) if the preferred name already exists AND it's not the same file
        if target.exists():
            try:
                if not target.samefile(saved_path):
                    target = unique_path(target)
            except OSError:
                target = unique_path(target)

        # Rename only if needed
        if saved_path != target:
            saved_path.rename(target)

        count += 1

    if hasattr(msg, "close"):
        msg.close()

    return count


def scan_msg_files(path: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.msg" if recursive else "*.msg"
    return sorted(path.glob(pattern))


def dedupe_keep_order(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


# ----------------------------
# Tkinter GUI
# ----------------------------

def run_gui() -> None:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class App:
        def __init__(self, root: tk.Tk):
            self.root = root
            self.root.title("MSG → PDF Attachment Extractor - Made By ACK")
            self.root.geometry("900x600")

            self.msg_files: list[Path] = []
            self.out_dir = tk.StringVar(value=str((Path.cwd() / "pdfs").resolve()))
            self.recursive = tk.BooleanVar(value=False)
            self.debug = tk.BooleanVar(value=False)

            self._worker_thread: threading.Thread | None = None
            self._cancel = threading.Event()
            self._q: queue.Queue[tuple[str, object]] = queue.Queue()

            self._build_ui()
            self._poll_queue()

        def _build_ui(self) -> None:
            pad = {"padx": 10, "pady": 6}

            # Inputs
            frm_inputs = ttk.LabelFrame(self.root, text="Input (.msg files / folders)")
            frm_inputs.pack(fill="both", expand=False, **pad)

            btns = ttk.Frame(frm_inputs)
            btns.pack(fill="x", padx=10, pady=6)

            ttk.Button(btns, text="Add .msg Files…", command=self.add_files).pack(side="left")
            ttk.Button(btns, text="Add Folder…", command=self.add_folder).pack(side="left", padx=(8, 0))
            ttk.Button(btns, text="Remove Selected", command=self.remove_selected).pack(side="left", padx=(8, 0))
            ttk.Button(btns, text="Clear", command=self.clear_list).pack(side="left", padx=(8, 0))

            opts = ttk.Frame(frm_inputs)
            opts.pack(fill="x", padx=10, pady=(0, 6))
            ttk.Checkbutton(opts, text="Recursive folder scan", variable=self.recursive).pack(side="left")
            ttk.Checkbutton(opts, text="Debug log", variable=self.debug).pack(side="left", padx=(16, 0))

            self.count_label = ttk.Label(opts, text="0 file(s) selected")
            self.count_label.pack(side="right")

            list_frame = ttk.Frame(frm_inputs)
            list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            self.listbox = tk.Listbox(list_frame, height=6, selectmode=tk.EXTENDED)
            self.listbox.pack(side="left", fill="both", expand=True)

            sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
            sb.pack(side="right", fill="y")
            self.listbox.configure(yscrollcommand=sb.set)

            # Output directory
            frm_out = ttk.LabelFrame(self.root, text="Output directory")
            frm_out.pack(fill="x", expand=False, **pad)

            out_row = ttk.Frame(frm_out)
            out_row.pack(fill="x", padx=10, pady=10)

            ttk.Entry(out_row, textvariable=self.out_dir).pack(side="left", fill="x", expand=True)
            ttk.Button(out_row, text="Browse…", command=self.choose_out_dir).pack(side="left", padx=(8, 0))

            # Actions + Progress
            frm_actions = ttk.Frame(self.root)
            frm_actions.pack(fill="x", **pad)

            self.start_btn = ttk.Button(frm_actions, text="Start Extraction", command=self.start)
            self.start_btn.pack(side="left")

            self.cancel_btn = ttk.Button(frm_actions, text="Cancel", command=self.cancel, state="disabled")
            self.cancel_btn.pack(side="left", padx=(8, 0))

            self.progress = ttk.Progressbar(frm_actions, mode="determinate")
            self.progress.pack(side="right", fill="x", expand=True, padx=(12, 0))

            self.status = ttk.Label(self.root, text="Ready.")
            self.status.pack(fill="x", padx=10)

            # Log
            frm_log = ttk.LabelFrame(self.root, text="Log")
            frm_log.pack(fill="both", expand=True, **pad)

            log_frame = ttk.Frame(frm_log)
            log_frame.pack(fill="both", expand=True, padx=10, pady=10)

            self.log_text = tk.Text(log_frame, wrap="word", height=12, state="disabled")
            self.log_text.pack(side="left", fill="both", expand=True)

            sb2 = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
            sb2.pack(side="right", fill="y")
            self.log_text.configure(yscrollcommand=sb2.set)

        def _set_running(self, running: bool) -> None:
            self.start_btn.configure(state=("disabled" if running else "normal"))
            self.cancel_btn.configure(state=("normal" if running else "disabled"))

        def _log(self, line: str) -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line.rstrip() + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        def _refresh_listbox(self) -> None:
            self.listbox.delete(0, "end")
            for p in self.msg_files:
                self.listbox.insert("end", str(p))
            self.count_label.configure(text=f"{len(self.msg_files)} file(s) selected")

        def add_files(self) -> None:
            from tkinter import filedialog
            files = filedialog.askopenfilenames(
                title="Select .msg files",
                filetypes=[("Outlook MSG", "*.msg"), ("All files", "*.*")],
            )
            if not files:
                return
            self.msg_files = dedupe_keep_order([*self.msg_files, *map(Path, files)])
            self._refresh_listbox()

        def add_folder(self) -> None:
            from tkinter import filedialog
            folder = filedialog.askdirectory(title="Select folder containing .msg files")
            if not folder:
                return
            folder_path = Path(folder)
            found = scan_msg_files(folder_path, recursive=self.recursive.get())
            self.msg_files = dedupe_keep_order([*self.msg_files, *found])
            self._refresh_listbox()
            self._log(f"Added folder: {folder_path} ({len(found)} .msg found)")

        def remove_selected(self) -> None:
            sel = list(self.listbox.curselection())
            if not sel:
                return
            keep = [p for i, p in enumerate(self.msg_files) if i not in set(sel)]
            self.msg_files = keep
            self._refresh_listbox()

        def clear_list(self) -> None:
            self.msg_files = []
            self._refresh_listbox()

        def choose_out_dir(self) -> None:
            from tkinter import filedialog
            folder = filedialog.askdirectory(title="Select output folder for PDFs")
            if not folder:
                return
            self.out_dir.set(folder)

        def start(self) -> None:
            if self._worker_thread and self._worker_thread.is_alive():
                return

            if not self.msg_files:
                messagebox.showwarning("No input", "Please add at least one .msg file or a folder.")
                return

            out_dir = Path(self.out_dir.get()).expanduser()
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Output folder error", f"Cannot create output folder:\n{out_dir}\n\n{e}")
                return

            self._cancel.clear()
            self._set_running(True)
            self.progress.configure(maximum=len(self.msg_files), value=0)
            self.status.configure(text="Running…")
            self._log("=== Extraction started ===")
            self._log(f"Output: {out_dir.resolve()}")
            self._log(f"Files: {len(self.msg_files)}")
            self._log("")

            files = list(self.msg_files)
            debug = self.debug.get()

            def worker():
                total_pdfs = 0
                for idx, msg_path in enumerate(files, start=1):
                    if self._cancel.is_set():
                        self._q.put(("log", "Canceled by user."))
                        self._q.put(("done", (idx - 1, total_pdfs, True)))
                        return
                    try:
                        self._q.put(("log", f"[...] {msg_path.name}"))
                        n = extract_pdfs_from_msg(
                            msg_path=msg_path,
                            out_dir=out_dir,
                            debug=debug,
                            log=lambda s: self._q.put(("log", s)),
                        )
                        total_pdfs += n
                        self._q.put(("log", f"[OK]  {msg_path.name}: extracted {n} PDF(s)"))
                    except Exception as e:
                        self._q.put(("log", f"[ERR] {msg_path.name}: {e}"))

                    self._q.put(("progress", idx))

                self._q.put(("done", (len(files), total_pdfs, False)))

            self._worker_thread = threading.Thread(target=worker, daemon=True)
            self._worker_thread.start()

        def cancel(self) -> None:
            self._cancel.set()
            self.status.configure(text="Canceling…")

        def _poll_queue(self) -> None:
            try:
                while True:
                    kind, payload = self._q.get_nowait()
                    if kind == "log":
                        self._log(str(payload))
                    elif kind == "progress":
                        self.progress.configure(value=int(payload))
                        self.status.configure(text=f"Processed {payload}/{len(self.msg_files)} file(s)…")
                    elif kind == "done":
                        processed, total_pdfs, canceled = payload  # type: ignore[misc]
                        self.progress.configure(value=processed)
                        self._log("")
                        self._log(f"=== Done. Extracted {total_pdfs} PDF(s). ===")
                        self.status.configure(
                            text=("Canceled." if canceled else f"Done. Extracted {total_pdfs} PDF(s).")
                        )
                        self._set_running(False)
            except queue.Empty:
                pass
            self.root.after(100, self._poll_queue)

    root = tk.Tk()
    # nicer ttk default on some platforms
    try:
        from tkinter import ttk
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    App(root)
    root.mainloop()


# ----------------------------
# Optional CLI (kept for convenience)
# If you run with args, it uses CLI; with no args, it starts GUI.
# ----------------------------

def run_cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract PDF attachments from Outlook .msg files.")
    parser.add_argument("--in", dest="in_dir", default="messages", help="Input folder with .msg files")
    parser.add_argument("--out", dest="out_dir", default="pdfs", help="Output folder for extracted PDFs")
    parser.add_argument("--recursive", action="store_true", help="Scan subfolders too")
    parser.add_argument("--debug", action="store_true", help="Print attachment debug info")
    args = parser.parse_args(argv)

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_dir.exists():
        raise SystemExit(f"Input folder not found: {in_dir.resolve()}")

    msg_files = scan_msg_files(in_dir, recursive=args.recursive)

    total_pdfs = 0
    for msg_path in msg_files:
        try:
            n = extract_pdfs_from_msg(msg_path, out_dir, debug=args.debug, log=print)
            total_pdfs += n
            print(f"[OK] {msg_path.name}: extracted {n} PDF(s)")
        except Exception as e:
            print(f"[ERR] {msg_path.name}: {e}")

    print(f"\nDone. Extracted {total_pdfs} PDF(s) into: {out_dir.resolve()}")


if __name__ == "__main__":
    import sys

    if getattr(sys, "frozen", False):  # packaged app
        run_gui()
    else:
        if len(sys.argv) > 1:
            run_cli()
        else:
            print("Starting GUI…")
            run_gui()

            