import customtkinter as ctk
import sv_ttk
import wave
import threading
import subprocess
import time
import tkinter as tk
import sounddevice
import os
import shutil
import re
import yt_dlp
import sys
import pywinstyles
import keyboard

from typing import Any
from tkinter.filedialog import askopenfilenames
from tkinter.messagebox import askyesnocancel, showerror, showinfo
from soundboard import Soundboard
from tkinter import ttk
from PIL import Image, ImageTk
from pydub import AudioSegment
from sound import SoundMeta

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Soundboard")
        self.geometry("1200x800")
        self.resizable(False, False)
        self.iconbitmap("data/assets/icon.ico")

        if not os.path.exists("data/sounds"):
            os.mkdir("data/sounds")

        self.font: str = "Poppins"
        
        self.cable_device: str | None = None
        self.cable_device_index: int | None = None
        
        for index, device in enumerate(sounddevice.query_devices()):
            if "CABLE Input" in device["name"]:
                self.cable_device = device["name"]
                self.cable_device_index = index
                break

        if self.cable_device is None or self.cable_device_index is None:
            raise Exception("CABLE Input not found")

        self.soundboard: Soundboard = Soundboard(self.cable_device_index)
        self.current_y: float = 0.01

        self.playing_sounds: list[list[subprocess.Popen, wave.Wave_read, SoundMeta, ttk.Frame, ttk.Button, bool, int, bool, bool, ttk.Progressbar, ttk.Label, ttk.Scale]] = []
        
        self.delete_image = ImageTk.PhotoImage(Image.open("data/assets/delete.png"), (32, 32))
        self.pause_image = ImageTk.PhotoImage(Image.open("data/assets/pause.png"), (32, 32))
        self.resume_image = ImageTk.PhotoImage(Image.open("data/assets/resume.png"), (32, 32))
        self.close_image = ImageTk.PhotoImage(Image.open("data/assets/close.png"), (32, 32))
        self.headphones_image = ImageTk.PhotoImage(Image.open("data/assets/headphones.png"), (32, 32))
        self.headphones_off_image = ImageTk.PhotoImage(Image.open("data/assets/headphones_off.png"), (32, 32))
        self.mic_image = ImageTk.PhotoImage(Image.open("data/assets/mic.png"), (32, 32))
        self.mic_off_image = ImageTk.PhotoImage(Image.open("data/assets/mic_off.png"), (32, 32))
        self.volume_image = ImageTk.PhotoImage(Image.open("data/assets/volume.png"), (32, 32))
        self.add_image = ImageTk.PhotoImage(Image.open("data/assets/add.png"), (32, 32))
        self.volume_down_image = ImageTk.PhotoImage(Image.open("data/assets/volume_down.png"), (32, 32))
        self.no_sound_image = ImageTk.PhotoImage(Image.open("data/assets/no_sound.png"), (32, 32))
        self.help_image = ImageTk.PhotoImage(Image.open("data/assets/help.png"), (32, 32))

        self.should_write_microphone_stream: bool = True
        self.should_write_loopback_stream: bool = True

        self.sidebar_sounds: list[tuple[ttk.Button, ttk.Button]] = []

        threading.Thread(target = self.update_progress_bars, daemon = True).start()

        self.load_widgets()
        self.setup_hotkeys()

    def setup_hotkeys(self) -> None:
        keyboard.add_hotkey("ctrl+alt+0", self.stop_sounds, suppress = True)
        keyboard.add_hotkey("ctrl+alt+-", self.decrease_all_volumes, suppress = True)
        keyboard.add_hotkey("ctrl+alt+plus", self.increase_all_volumes, suppress = True)

        for i in range(1, 10):
            hotkey = f"ctrl+alt+{i}"

            try:
                sound: SoundMeta = self.soundboard.sounds[i - 1]
                keyboard.add_hotkey(hotkey, self.play_sound, args = (sound, ), suppress = True)
            except IndexError:
                break
    
    def decrease_all_volumes(self):
        updated_default_volume: int = max(min(self.default_volume.get() + 1, 100), 0)
        self.default_volume.set(updated_default_volume)

        for sound in self.playing_sounds:
            volume: int = max(min(sound[6] - 1, 100), 0)
            self.set_volume(sound[0], max(min(volume, 100), 0), sound[10])
            sound[11].set(volume)

    def increase_all_volumes(self):
        updated_default_volume: int = max(min(self.default_volume.get() - 1, 100), 0)
        self.default_volume.set(updated_default_volume)

        for sound in self.playing_sounds:
            volume: int = max(min(sound[6] + 1, 100), 0)
            self.set_volume(sound[0], max(min(volume, 100), 0), sound[10])
            sound[11].set(volume)

    def update_progress_bars(self) -> None:
        while True:
            if len(self.playing_sounds) == 0:
                time.sleep(1)

            sound_index: int = -1
            for sound, wave_file, metadata, frame, button, paused, volume, write_microphone, write_loopback, progress_bar, volume_image, volume_slider in self.playing_sounds:
                sound_index += 1
                duration: float = wave_file.getnframes() / wave_file.getframerate()
                progress: tuple[float, bool] = self.soundboard.get_progress(sound)

                for index, playing_sound in enumerate(self.playing_sounds):
                    if sound is playing_sound[0]:
                        self.playing_sounds[index][5] = progress[1]

                        try:
                            self.playing_sounds[index][4].configure(image = self.resume_image if progress[1] else self.pause_image)
                        except Exception:
                            ...
                        break

                try:
                    if round(progress[0]) >= round(duration):
                        frame.destroy()

                        try:
                            self.playing_sounds.pop(sound_index)
                        except IndexError:
                            ...
                        self.update_playing_sounds()
                        continue
                    if round(progress[0]) != 0:
                        progress_bar["value"] = round(progress[0])
                    #     progress_bar.set(progress[0])
                except Exception:
                    continue

    def update_playing_sounds(self) -> None:
        self.current_y = 0.01

        new_playing_sounds = []

        for process, wave_file, sound, widget, button, paused, volume, write_microphone, write_loopback, progress_bar, volume_image, volume_slider in self.playing_sounds:
            widget.destroy()
            process_widget = self.new_sound(wave_file, sound, False, process, volume, write_microphone, write_loopback)
            new_playing_sounds.append([process_widget[0], wave_file, sound, process_widget[1], process_widget[2], paused, volume, write_microphone, write_loopback, process_widget[6], process_widget[7], process_widget[8]])

        self.playing_sounds.clear()
        self.playing_sounds.extend(new_playing_sounds)

        if len(self.playing_sounds) == 0:
            self.no_sounds_playing_label: ttk.Label = ttk.Label(self, text = "No sounds playing...", background = "#242424", font = (self.font, 16))
            self.no_sounds_playing_label.place(relx = 0.645, rely = 0.475, anchor = ctk.CENTER)
        else:
            self.no_sounds_playing_label.destroy()

    def stop_sound(self, process: subprocess.Popen) -> None:
        playing_sound: list[subprocess.Popen, wave.Wave_read, SoundMeta, ttk.Frame] | None = None

        index = 0
        for sound in self.playing_sounds:
            if sound[0] is process:
                playing_sound = self.playing_sounds[index]
                break

            index += 1

        if playing_sound is None:
            return
        
        self.playing_sounds[index][3].destroy()
        self.playing_sounds.pop(index)

        if playing_sound is None:
            return
        
        self.soundboard.stop_sound(process)
        self.update_playing_sounds()

    def stop_sounds(self) -> None:
        for sound in self.playing_sounds:
            sound[3].destroy()

        self.playing_sounds.clear()

        self.soundboard.stop_all_sounds()
        self.update_playing_sounds()

    def set_volume(self, sound: subprocess.Popen, volume: int, label: ttk.Label) -> None:
        self.soundboard.set_volume(sound, volume)

        index = 0
        for playing_sound in self.playing_sounds:
            if playing_sound[0] is sound:
                self.playing_sounds[index][6] = volume
                break

            index += 1

        if volume == 0:
            label.configure(image = self.no_sound_image)
        elif volume >= 50:
            label.configure(image = self.volume_image)
        elif volume < 50:
            label.configure(image = self.volume_down_image)

    def set_write_microphone_stream(self, sound: subprocess.Popen, write: bool, button: ttk.Checkbutton) -> None:
        self.soundboard.set_write_microphone_stream(sound, write)

        index = 0
        for playing_sound in self.playing_sounds:
            if playing_sound[0] is sound:
                self.playing_sounds[index][7] = write
                break

            index += 1

        if write:
            button.configure(image = self.mic_image)
        else:
            button.configure(image = self.mic_off_image)

    def set_write_loopback_stream(self, sound: subprocess.Popen, write: bool, button: ttk.Checkbutton) -> None:
        self.soundboard.set_write_loopback_stream(sound, write)

        index = 0
        for playing_sound in self.playing_sounds:
            if playing_sound[0] is sound:
                self.playing_sounds[index][8] = write
                break

            index += 1

        if write:
            button.configure(image = self.headphones_image)
        else:
            button.configure(image = self.headphones_off_image)

    def new_sound(self, wave_file: wave.Wave_read, sound: SoundMeta, play: bool = True, previous_process: subprocess.Popen | None = None, previous_volume: int = 100, previous_microphone: bool = True, previous_loopback: bool = True) -> tuple[subprocess.Popen, ttk.Frame, ttk.Button, int, bool, bool, ttk.Progressbar]:
        duration: float = wave_file.getnframes() / wave_file.getframerate()

        frame: ttk.Frame = ttk.Frame(self, width = 825, height = 50)
        # self.duration_progress: ttk.Scale = ttk.Scale(frame, length = 200, to = duration)
        self.duration_progress: ttk.Progressbar = ttk.Progressbar(frame, length = 200, maximum = duration)

        sound_process: subprocess.Popen | None = None
        
        if play:
            sound_process = self.soundboard.play_sound(sound.filepath, 0.5, previous_microphone, previous_loopback)

        name: str = sound.name

        if len(name) > 30:
            name = f"{name[:30]}..."

        label = ttk.Label(frame, text = name, font = (self.font, 10))
        label.place(relx = 0.02, rely = 0.5, anchor = ctk.W)

        self.duration_progress.place(relx = 0.87, rely = 0.5, anchor = ctk.E)

        write_microphone: tk.BooleanVar = tk.BooleanVar(self)
        write_microphone_button: ttk.Checkbutton = ttk.Checkbutton(frame, image = self.mic_image, variable = write_microphone, takefocus = False)
        write_microphone_button.place(relx = 0.38, rely = 0.5, anchor = tk.E)
        write_microphone.trace_add("write", lambda *args: self.set_write_microphone_stream(sound_process or previous_process, write_microphone.get(), write_microphone_button))
        write_microphone.set(previous_microphone)

        write_loopback: tk.BooleanVar = tk.BooleanVar(self)
        write_loopback_button: ttk.Checkbutton = ttk.Checkbutton(frame, image = self.headphones_image, variable = write_loopback, takefocus = False)
        write_loopback_button.place(relx = 0.45, rely = 0.5, anchor = tk.E)
        write_loopback.trace_add("write", lambda *args: self.set_write_loopback_stream(sound_process or previous_process, write_loopback.get(), write_loopback_button))
        write_loopback.set(previous_loopback)
        
        volume_image: ttk.Label = ttk.Label(frame, image = self.volume_image)
        volume_image.place(relx = 0.615, rely = 0.5, anchor = ctk.E)

        volume = tk.IntVar(self)
        volume_slider: ttk.Scale = ttk.Scale(frame, variable = volume, from_ = 0, to = 100, takefocus = False)
        volume.trace_add("write", lambda *args: self.set_volume(sound_process or previous_process, volume.get(), volume_image))
        volume.set(previous_volume)
        volume_slider.place(relx = 0.58, rely = 0.5, anchor = ctk.E)

        paused: bool = False
        for playing_sound in self.playing_sounds:
            if playing_sound[0] is (sound_process or previous_process):
                paused = playing_sound[5]
                break

        pause_button: ttk.Button = ttk.Button(frame, takefocus = False, image = self.resume_image if paused else self.pause_image, padding = "0 0 0 0", command = lambda: self.soundboard.toggle_play(sound_process or previous_process))
        pause_button.place(relx = 0.935, rely = 0.5, anchor = ctk.E)

        stop_button: ttk.Button = ttk.Button(frame, style = "Accent.TButton", takefocus = False, image = self.close_image, padding = "0 0 0 0", command = lambda: self.stop_sound(sound_process or previous_process))
        stop_button.place(relx = 0.99, rely = 0.5, anchor = ctk.E)

        frame.place(relx = 0.99, rely = self.current_y, anchor = ctk.NE)

        self.current_y += 0.07

        return sound_process if sound_process is not None else previous_process, frame, pause_button, volume.get(), write_microphone.get(), write_loopback.get(), self.duration_progress, volume_image, volume_slider

    def play_sound(self, sound: SoundMeta) -> None:
        if len(self.playing_sounds) >= 14:
            return
        
        if len(self.playing_sounds) == 0:
            self.no_sounds_playing_label.destroy()
        
        wave_file: wave.Wave_read = wave.open(sound.filepath, "rb")
        process_widget: ttk.Frame = self.new_sound(wave_file, sound, previous_volume = 100 - self.default_volume.get(), previous_microphone = self.should_write_microphone_stream, previous_loopback = self.should_write_loopback_stream)

        self.playing_sounds.append([process_widget[0], wave_file, sound, process_widget[1], process_widget[2], False, process_widget[3], process_widget[4], process_widget[5], process_widget[6], process_widget[7], process_widget[8]])

    def delete_sound(self, sound: SoundMeta) -> None:
        result: bool = askyesnocancel("Delete Sound", f"Are you sure you would like to delete {sound.name}?")

        if not result:
            return
        
        try:
            os.remove(sound.filepath)
        except PermissionError:
            return showerror("File in use", "Please wait for the sound to be finished")
            
        self.soundboard.sounds.remove(sound)

        for widget_1, widget_2 in self.sidebar_sounds:
            widget_1.destroy()
            widget_2.destroy()

        self.sidebar_sounds.clear()

        rely: int = 1

        for idx, sound in enumerate(self.soundboard.sounds):
            name: str = sound.name

            if len(name) > 30:
                name = f"{name[:30]}..."

            sound_widget = ttk.Button(self.sidebar_content_frame, text = name, takefocus = False, command = lambda sound = sound: self.play_sound(sound))
            sound_widget.grid(row = idx + 1, column = 0, padx = 10, pady = 5, sticky = "ew")

            delete_button = ttk.Button(self.sidebar_content_frame, image = self.delete_image, padding = "0 0 0 0", takefocus = False, command = lambda sound = sound: self.delete_sound(sound))
            delete_button.grid(row = idx + 1, column = 1, padx = 0, pady = 5, sticky = "ew")

            self.sidebar_sounds.append((sound_widget, delete_button))

            rely += 1

    def toggle_write_loopback_stream(self, value: bool) -> None:
        self.should_write_loopback_stream = value

        if value:
            self.write_loopback_stream_button.configure(image = self.headphones_image)
        else:
            self.write_loopback_stream_button.configure(image = self.headphones_off_image)

    def toggle_write_microphone_stream(self, value: bool) -> None:
        self.should_write_microphone_stream = value

        if value:
            self.write_microphone_stream_button.configure(image = self.mic_image)
        else:
            self.write_microphone_stream_button.configure(image = self.mic_off_image)

    def set_new_input_device(self, value: str) -> None:
        devices: list[str] = [device["name"] for device in sounddevice.query_devices()]

        try:
            index: int = devices.index(value)
        except ValueError:
            return

        self.soundboard.output_device = index

    def export_mp3_to_wav(self, filepath: str) -> str:
        path: str = f"./data/sounds/{os.path.splitext(os.path.split(filepath)[-1])[0]}.wav"

        sound: Any = AudioSegment.from_mp3(filepath)
        sound.export(path, format = "wav")

        return path
    
    def upload_audio(self) -> None:
        paths: tuple[str, ...] = askopenfilenames(filetypes = [("MPEG Audio Layer 3", ".mp3"), ("Waveform Audio File", ".wav")])
        
        if not paths:
            return
        
        for path in paths:
            if os.path.splitext(path)[1] == ".wav":
                shutil.copy2(path, "./data/sounds")
            else:
                path = self.export_mp3_to_wav(path)

            self.soundboard.sounds.append(SoundMeta(os.path.splitext(os.path.split(path)[-1])[0], path))

        for widget_1, widget_2 in self.sidebar_sounds:
            widget_1.destroy()
            widget_2.destroy()

        self.sidebar_sounds.clear()

        rely: int = 1

        for idx, sound in enumerate(self.soundboard.sounds):
            name: str = sound.name

            if len(name) > 30:
                name = f"{name[:30]}..."

            sound_widget = ttk.Button(self.sidebar_content_frame, text = name, takefocus = False, command = lambda sound = sound: self.play_sound(sound))
            sound_widget.grid(row = idx + 1, column = 0, padx = 10, pady = 5, sticky = "ew")

            delete_button = ttk.Button(self.sidebar_content_frame, image = self.delete_image, padding = "0 0 0 0", takefocus = False, command = lambda sound = sound: self.delete_sound(sound))
            delete_button.grid(row = idx + 1, column = 1, padx = 0, pady = 5, sticky = "ew")

            self.sidebar_sounds.append((sound_widget, delete_button))

            rely += 1

    def update_settings_volume_label(self) -> None:
        value: int = 100 - self.default_volume.get()
        
        if value == 0:
            self.volume_label.configure(image = self.no_sound_image)
        elif value >= 50:
            self.volume_label.configure(image = self.volume_image)
        elif value < 50:
            self.volume_label.configure(image = self.volume_down_image)

    def import_from_youtube(self) -> None:
        expression: str = r"(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
        clipboard_content: str = self.clipboard_get()

        result: re.Match[str] | None = re.match(expression, clipboard_content)
        
        if result is None:
            return showerror("Invalid Link", "Failed to parse YouTube link. Please copy the link you would like to import.")
            
        showinfo("Download ready", f"Press \"Ok\" to begin download.")

        options = {
            "outtmpl": "data/sounds/%(title)s.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            title: str = ydl.extract_info(clipboard_content, False)["title"]
            path: str = f"data/sounds/{title}.wav"

            if os.path.exists(path):
                return showerror("File already exists", "The sound you are trying to download already exists. ")
            
            ydl.download([clipboard_content])

        showinfo("Audio downloaded", f"\"{title}\" was successfully downloaded.")

        self.soundboard.sounds.append(SoundMeta(os.path.splitext(os.path.split(path)[-1])[0], path))

        for widget_1, widget_2 in self.sidebar_sounds:
            widget_1.destroy()
            widget_2.destroy()

        self.sidebar_sounds.clear()

        rely: int = 1

        for idx, sound in enumerate(self.soundboard.sounds):
            name: str = sound.name

            if len(name) > 30:
                name = f"{name[:30]}..."

            sound_widget = ttk.Button(self.sidebar_content_frame, text = name, takefocus = False, command = lambda sound = sound: self.play_sound(sound))
            sound_widget.grid(row = idx + 1, column = 0, padx = 10, pady = 5, sticky = "ew")

            delete_button = ttk.Button(self.sidebar_content_frame, image = self.delete_image, padding = "0 0 0 0", takefocus = False, command = lambda sound = sound: self.delete_sound(sound))
            delete_button.grid(row = idx + 1, column = 1, padx = 0, pady = 5, sticky = "ew")

            self.sidebar_sounds.append((sound_widget, delete_button))

            rely += 1

    def load_widgets(self) -> None:
        for widget_1, widget_2 in self.sidebar_sounds:
            widget_1.destroy()
            widget_2.destroy()

        self.sidebar: ttk.Frame = ttk.Frame(self, width = 322, height = 600)
        self.sidebar.place(relx = 0.005, rely = 0.005, anchor = ctk.NW)

        self.canvas: tk.Canvas = tk.Canvas(self.sidebar, width = 322, height = 600)
        self.canvas.pack(side = ctk.LEFT, fill = ctk.BOTH, expand = True)

        self.sidebar_scrollbar: ttk.Scrollbar = ttk.Scrollbar(self.sidebar, orient = ctk.VERTICAL, command = self.canvas.yview)
        self.sidebar_scrollbar.pack(fill = ctk.Y, side = ctk.RIGHT, expand = True)

        self.canvas.configure(yscrollcommand = self.sidebar_scrollbar.set)

        self.sidebar_content_frame = ttk.Frame(self.canvas, width = 322, height = 600)
        self.sidebar_content_frame.place(relx = 0.5, rely = 0.5, anchor = ctk.CENTER)

        self.canvas.create_window((0, 0), window = self.sidebar_content_frame, anchor = ctk.NW)
        self.sidebar_content_frame.grid_rowconfigure(0, minsize = 40)
        self.sidebar_content_frame.grid_columnconfigure(0, minsize = 290)

        self.stop_sounds_button = ttk.Button(self.sidebar_content_frame, text = "Stop All Sounds", takefocus = False, style = "Accent.TButton", command = self.stop_sounds)
        self.stop_sounds_button.grid(row = 0, column = 0, padx = 10, pady = 10, sticky = "ew")

        self.upload_sound_button_small = ttk.Button(self.sidebar_content_frame, image = self.add_image, padding = "0 0 0 0", takefocus = False, command = self.upload_audio)
        self.upload_sound_button_small.grid(row = 0, column = 1, padx = 0, pady = 5, sticky = "ew")

        rely: int = 1

        self.sidebar_sounds.clear()

        for idx, sound in enumerate(self.soundboard.sounds):
            name: str = sound.name

            if len(name) > 30:
                name = f"{name[:30]}..."

            sound_widget = ttk.Button(self.sidebar_content_frame, text = name, takefocus = False, command = lambda sound = sound: self.play_sound(sound))
            sound_widget.grid(row = idx + 1, column = 0, padx = 10, pady = 5, sticky = "ew")

            delete_button = ttk.Button(self.sidebar_content_frame, image = self.delete_image, padding = "0 0 0 0", takefocus = False, command = lambda sound = sound: self.delete_sound(sound))
            delete_button.grid(row = idx + 1, column = 1, padx = 0, pady = 5, sticky = "ew")

            self.sidebar_sounds.append((sound_widget, delete_button))

            rely += 1

        self.sidebar_content_frame.update_idletasks()
        self.canvas.config(scrollregion = self.canvas.bbox("all"))

        self.settings_panel: ttk.Frame = ttk.Frame(self, width = 350, height = 180)
        self.settings_panel.place(relx = 0.005, rely = 0.99, anchor = ctk.SW)

        self.upload_sound_button: ttk.Button = ttk.Button(self.settings_panel, text = "Upload Audio", style = "Accent.TButton", takefocus = False, command = self.upload_audio)
        self.upload_sound_button.place(relx = 0.03, rely = 0.05, anchor = ctk.NW)

        self.import_from_youtube_button: ttk.Button = ttk.Button(self.settings_panel, text = "Import from YouTube", takefocus = False, command = lambda: threading.Thread(target = self.import_from_youtube).start())
        self.import_from_youtube_button.place(relx = 0.03, rely = 0.275, anchor = ctk.NW)
        
        self.input_device: tk.StringVar = tk.StringVar(self)
        self.input_device.trace_add("write", lambda *args: self.set_new_input_device(self.input_device.get()))
        self.input_device_select: ttk.Combobox = ttk.Combobox(self.settings_panel, textvariable = self.input_device, values = [device["name"] for device in sounddevice.query_devices()], takefocus = False, width = 20)
        self.input_device_select.place(relx = 0.97, rely = 0.05, anchor = ctk.NE)
        self.input_device.set(self.cable_device)

        ttk.Label(self.settings_panel, text = "Input Device", font = (self.font, 10)).place(relx = 0.78, rely = 0.25, anchor = ctk.NE)

        self.write_microphone_stream: tk.BooleanVar = tk.BooleanVar(self)
        self.write_microphone_stream.trace_add("write", lambda *args: self.toggle_write_microphone_stream(self.write_microphone_stream.get()))
        self.write_microphone_stream_button: ttk.Checkbutton = ttk.Checkbutton(self.settings_panel, image = self.mic_image, variable = self.write_microphone_stream, takefocus = False)
        self.write_microphone_stream_button.place(relx = 0.03, rely = 0.7, anchor = ctk.SW)
        self.write_microphone_stream.set(True)

        ttk.Label(self.settings_panel, text = "Default", font = (self.font, 10)).place(relx = 0.2, rely = 0.6735, anchor = ctk.SW)
        
        self.write_loopback_stream: tk.BooleanVar = tk.BooleanVar(self)
        self.write_loopback_stream.trace_add("write", lambda *args: self.toggle_write_loopback_stream(self.write_loopback_stream.get()))
        self.write_loopback_stream_button: ttk.Checkbutton = ttk.Checkbutton(self.settings_panel, image = self.headphones_image, variable = self.write_loopback_stream, takefocus = False)
        self.write_loopback_stream_button.place(relx = 0.03, rely = 0.9, anchor = ctk.SW)
        self.write_loopback_stream.set(True)

        ttk.Label(self.settings_panel, text = "Default", font = (self.font, 10)).place(relx = 0.21, rely = 0.8835, anchor = ctk.SW)
        
        self.default_volume: tk.IntVar = tk.IntVar(self)
        self.default_volume.trace_add("write", lambda *args: self.update_settings_volume_label())
        self.default_volume_scale: ttk.Scale = ttk.Scale(self.settings_panel, variable = self.default_volume, from_ = 0, to = 100, length = 80, orient = ctk.VERTICAL, takefocus = False)
        self.default_volume_scale.place(relx = 0.95, rely = 0.75, anchor = ctk.SE)

        ttk.Label(self.settings_panel, text = "Default", font = (self.font, 10)).place(relx = 0.73, rely = 0.95, anchor = ctk.SW)

        self.volume_label: ttk.Label = ttk.Label(self.settings_panel, image = self.volume_image)
        self.volume_label.place(relx = 0.88, rely = 0.95, anchor = ctk.SW)

        help_info: str = """Ctrl+Alt+1-9 -> Play corresponding sound
Ctrl+Alt+0 -> Stop all sounds
Ctrl+Alt+Plus -> Increase all volumes (including default)
Ctrl+Alt+Minus -> Decrease all volumes (including default)"""

        self.help_button: ttk.Button = ttk.Button(self.settings_panel, image = self.help_image, takefocus = False, padding = "0 0 0 0", command = lambda: threading.Thread(target = showinfo, args = ("Help", help_info)).start())
        self.help_button.place(relx = 0.75, rely = 0.75, anchor = ctk.SW)

        self.no_sounds_playing_label: ttk.Label = ttk.Label(self, text = "No sounds playing...", background = "#242424", font = (self.font, 16))
        self.no_sounds_playing_label.place(relx = 0.645, rely = 0.475, anchor = ctk.CENTER)

def use_dark_theme(root):
    sv_ttk.use_dark_theme(root)

    version = sys.getwindowsversion()

    if version.major == 10 and version.build >= 22000:
        pywinstyles.change_header_color(root, "#1c1c1c")
    elif version.major == 10:
        pywinstyles.apply_style(root, "dark")
        root.wm_attributes("-alpha", 0.99)
        root.wm_attributes("-alpha", 1)

if __name__ == "__main__":
    app = App()
    use_dark_theme(app)

    app.mainloop()