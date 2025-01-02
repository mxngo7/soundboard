import subprocess
import struct
import os

from sound import SoundMeta

class Soundboard():
    def __init__(self, output_device: int | None):
        self.output_device: int | None = output_device

        if self.output_device is None:
            raise Exception("CABLE was not detected")
        
        self.sounds: list[SoundMeta] = []

        for sound in os.listdir("./data/sounds"):
            extension: tuple[str, str] = os.path.splitext(sound)
            if extension[1] == ".wav":
                self.sounds.append(SoundMeta(extension[0], f"./data/sounds/{sound}"))

        self.active_sounds: list[subprocess.Popen] = []

    def play_sound(self, filepath: str, volume: float, write_microphone_stream: bool, write_loopback_stream: bool) -> subprocess.Popen:
        sound: subprocess.Popen = subprocess.Popen(args = ["py", "sound.py", filepath, str(self.output_device), str(max(min(volume, 1), 0)), str(write_microphone_stream), str(write_loopback_stream)], stdin = subprocess.PIPE, stdout = subprocess.PIPE)
        self.active_sounds.append(sound)
        return sound
    
    def get_index_by_sound(self, sound: subprocess.Popen) -> int | None:
        for index, active_sound in enumerate(self.active_sounds):
            if sound is active_sound:
                return index

    def get_progress(self, sound: subprocess.Popen) -> tuple[float, bool]:
        index: int | None = self.get_index_by_sound(sound)

        if index is None:
            return False
        
        sound: subprocess.Popen = self.active_sounds[index]

        if sound.stdout is not None:
            try:
                data: tuple[float, bool, bytes] = struct.unpack("f?c", sound.stdout.readline())
            except struct.error:
                return 0, False

            return data[0], data[1]
        else:
            return 0, False
    
    def stop_all_sounds(self) -> None:
        for sound in self.active_sounds:
            sound.stdin.write(struct.pack("Hc", 2, b"\n"))
            sound.stdin.flush()

        self.active_sounds.clear()

    def toggle_play(self, sound: subprocess.Popen) -> None:
        index: int | None = self.get_index_by_sound(sound)

        if index is None:
            return
        
        sound.stdin.write(struct.pack("Hc", 1, b"\n"))
        sound.stdin.flush()

    def set_volume(self, sound: subprocess.Popen, percent: int) -> None:
        index: int | None = self.get_index_by_sound(sound)

        if index is None:
            return
        
        sound.stdin.write(struct.pack("HHc", 3, percent, b"\n"))
        sound.stdin.flush()

    def set_write_microphone_stream(self, sound: subprocess.Popen, write: bool) -> None:
        index: int | None = self.get_index_by_sound(sound)

        if index is None:
            return
        
        sound.stdin.write(struct.pack("H?c", 4, write, b"\n"))
        sound.stdin.flush()

    def set_write_loopback_stream(self, sound: subprocess.Popen, write: bool) -> None:
        index: int | None = self.get_index_by_sound(sound)

        if index is None:
            return
        
        sound.stdin.write(struct.pack("H?c", 5, write, b"\n"))
        sound.stdin.flush()
    
    def stop_sound(self, sound: subprocess.Popen) -> None:
        index: int | None = self.get_index_by_sound(sound)

        if index is None:
            return
        
        sound.stdin.write(struct.pack("Hc", 2, b"\n"))
        sound.stdin.flush()

        self.active_sounds.remove(sound)
