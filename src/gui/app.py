from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from src.audio.audio_recorder import AudioRecorder
from src.stt.speech_recognizer import SpeechRecognizer
from src.utils.config import load_audio_config, load_stt_config


class SttGuiApp:

    def __init__(self, root: tk.Tk, config_path: str = "config/stt.yaml") -> None:
        self.root = root
        self.root.title("Voice Writing Robot - STT")
        self.root.geometry("700x500")
        self.root.minsize(500, 350)
        self._result_queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._recorder: AudioRecorder | None = None
        self._recognizer: SpeechRecognizer | None = None
        self._build_ui()
        self.root.after_idle(lambda: self._load_models(config_path))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.status_var = tk.StringVar(value="Loading models, please wait...")
        ttk.Label(main_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(0, 8))
        dev_frame = ttk.Frame(main_frame)
        dev_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(dev_frame, text="Microphone:").pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="default")
        self.device_combo = ttk.Combobox(dev_frame, textvariable=self.device_var, values=["default"], state="readonly", width=50)
        self.device_combo.pack(side=tk.LEFT, padx=(6, 0))
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 8))
        self.record_btn = ttk.Button(btn_frame, text="Start Recording", command=self._toggle_recording)
        self.record_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.record_btn.configure(state=tk.DISABLED)
        self.copy_btn = ttk.Button(btn_frame, text="Copy Text", command=self._copy_text)
        self.copy_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.clear_btn = ttk.Button(btn_frame, text="Clear", command=self._clear_text)
        self.clear_btn.pack(side=tk.LEFT)
        self.text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Microsoft YaHei", 11), state=tk.DISABLED)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.info_var = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.info_var, foreground="gray").pack(anchor=tk.W, pady=(4, 0))

    def _load_models(self, config_path: str) -> None:
        try:
            config_file = Path(config_path)
            audio_config = load_audio_config(config_file)
            stt_config = load_stt_config(config_file)
            self._recorder = AudioRecorder(audio_config)
            self._recognizer = SpeechRecognizer(stt_config)
            self._refresh_device_list()
            self.record_btn.configure(state=tk.NORMAL)
            self.status_var.set("Ready. Click Start Recording and speak.")
            self.info_var.set(f"STT model: {stt_config.model_size} | device: {stt_config.device} | compute: {stt_config.compute_type}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load models: {exc}")
            self.status_var.set("Error loading models.")

    def _refresh_device_list(self) -> None:
        try:
            devices = AudioRecorder.list_input_devices()
            names = [f'{d["index"]}: {d["name"]}' for d in devices]
            if not names:
                names = ["default"]
            self.device_combo.configure(values=names)
            if self.device_var.get() == "default" and names:
                self.device_var.set(names[0])
        except Exception:
            pass

    def _toggle_recording(self) -> None:
        if self._running:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        if self._recorder is None or self._recognizer is None:
            return
        device_sel = self.device_var.get()
        device_idx = _parse_device_index(device_sel)
        old = self._recorder.config.__dict__
        self._recorder.config = self._recorder.config.__class__(**{**old, "device": device_idx})
        self._running = True
        self._stop_event.clear()
        self.record_btn.configure(text="Stop Recording")
        self.status_var.set("Waiting for speech...")
        self._worker = threading.Thread(target=self._record_loop, daemon=True)
        self._worker.start()
        self._poll_queue()

    def _stop_recording(self) -> None:
        self._stop_event.set()
        self._running = False
        self.record_btn.configure(text="Start Recording", state=tk.DISABLED)
        self.status_var.set("Stopping... please wait.")

    def _record_loop(self) -> None:
        assert self._recorder is not None
        assert self._recognizer is not None

        def on_status(msg: str) -> None:
            self._result_queue.put(f"__STATUS__{msg}")

        try:
            audio = self._recorder.listen_once(on_status=on_status, stop_event=self._stop_event)
            if audio.size == 0:
                self._result_queue.put("__DONE__")
                return
            text = self._recognizer.transcribe(audio)
            if text:
                self._result_queue.put(text)
        except Exception as exc:
            self._result_queue.put(f"[Error] {exc}")
        self._result_queue.put("__DONE__")

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._result_queue.get_nowait()
                if msg == "__DONE__":
                    self.record_btn.configure(text="Start Recording", state=tk.NORMAL)
                    self.status_var.set("Ready. Click Start Recording and speak.")
                    self._worker = None
                    self._running = False
                    return
                if msg.startswith("__STATUS__"):
                    self.status_var.set(msg[len("__STATUS__"):])
                    continue
                self._append_text(msg)
        except queue.Empty:
            pass
        if self._running:
            self.root.after(100, self._poll_queue)

    def _append_text(self, text: str) -> None:
        self.text_area.configure(state=tk.NORMAL)
        if self.text_area.index("end-1c") != "1.0":
            self.text_area.insert(tk.END, "\n")
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.configure(state=tk.DISABLED)

    def _copy_text(self) -> None:
        text = self.text_area.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.info_var.set("Text copied to clipboard.")
            self.root.after(3000, lambda: self.info_var.set(""))

    def _clear_text(self) -> None:
        self.text_area.configure(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        self.text_area.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        self._stop_event.set()
        self._running = False
        self.root.destroy()


def _parse_device_index(selection: str) -> int | None:
    if selection == "default":
        return None
    if ":" in selection:
        try:
            return int(selection.split(":")[0])
        except ValueError:
            return None
    return None


def run_gui(config_path: str = "config/stt.yaml") -> None:
    root = tk.Tk()
    SttGuiApp(root, config_path)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
