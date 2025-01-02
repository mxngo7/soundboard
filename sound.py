import wave
import pyaudio
import wave
import numpy as np
import sys
import threading
import struct
import time
import sys

from typing import Any

class SoundMeta():
    def __init__(self, name: str, filepath: str) -> None:
        self.name: str = name
        self.filepath: str = filepath
        
class Sound():
    CHUNK_SIZE: int = 1024

    def __init__(self, filepath: str, output_device_index: int, volume: float, write_microphone_stream: bool, write_loopback_stream: bool) -> None:
        self.filepath: str = filepath
        self.output_device_index: int = output_device_index
        self.volume: int = max(min(volume, 1), 0)

        self.audio_playing: bool = False
        self.__paused: bool = False

        self.audio: pyaudio.PyAudio = None
        self.stream: pyaudio.Stream = None
        self.stream: pyaudio.Stream = None

        self.should_write_microphone_stream: bool = write_microphone_stream
        self.should_write_loopback_stream: bool = write_loopback_stream

    @property
    def is_paused(self) -> bool:
        return self.__paused
    
    def command_reader(self):
        while self.audio_playing:
            data: bytes = input().encode()

            try:
                command: int = struct.unpack("H", data[:struct.calcsize("H")])[0]
            except struct.error:
                continue

            match command:
                case 1:
                    self.toggle_play()
                case 2:
                    self.stop()
                case 3:
                    try:
                        volume: int = struct.unpack("HH", data)[1]
                    except struct.error:
                        continue
                    self.set_volume(volume / 100)
                case 4:
                    try:
                        write: bool = struct.unpack("H?", data)[1]
                    except struct.error:
                        continue
                    self.should_write_microphone_stream = write
                case 5:
                    try:
                        write: bool = struct.unpack("H?", data)[1]
                    except struct.error:
                        continue
                    self.should_write_loopback_stream = write

    def play(self) -> None:
        self.audio_playing = True
        threading.Thread(target = self.command_reader).start()

        wave_file: wave.Wave_read = wave.open(self.filepath, "rb")
        audio: pyaudio.PyAudio = pyaudio.PyAudio()

        sample_width: int = wave_file.getsampwidth()
        self.microphone_stream: pyaudio.Stream = audio.open(
            format = audio.get_format_from_width(sample_width),
            channels = wave_file.getnchannels(),
            rate = wave_file.getframerate(),
            output_device_index = self.output_device_index,
            output = True
        )

        self.loopback_stream: pyaudio.Stream = audio.open(
            format = audio.get_format_from_width(sample_width),
            channels = wave_file.getnchannels(),
            rate = wave_file.getframerate(),
            output = True
        )

        self.null_stream: pyaudio.Stream = audio.open(
            format = audio.get_format_from_width(sample_width),
            channels = wave_file.getnchannels(),
            rate = wave_file.getframerate(),
            output = True
        )

        data = wave_file.readframes(Sound.CHUNK_SIZE)

        start: float = time.time()

        while len(data) > 0 and self.audio_playing:
            progress: float = time.time() - start
            time_before_pause: float = time.time()
            was_paused: bool = self.is_paused

            sys.stdout.buffer.write(struct.pack("f?c", progress, self.is_paused, b"\n"))
            sys.stdout.flush()

            while self.is_paused:
                sys.stdout.buffer.write(struct.pack("f?c", progress, self.is_paused, b"\n"))
                sys.stdout.flush()

            if was_paused:
                time_paused: float = time.time() - time_before_pause
                start += time_paused

            data = self.update_volume(data)

            if self.should_write_loopback_stream:
                self.loopback_stream.write(data)

            if self.should_write_microphone_stream:
                self.microphone_stream.write(data)

            self.null_stream.write(self._update_volume(data, 0))

            data = wave_file.readframes(Sound.CHUNK_SIZE)

        self.stop()

    def stop(self) -> None:
        self.audio_playing = False

        if self.microphone_stream is not None:
            self.microphone_stream.stop_stream()
            self.microphone_stream.close()

        if self.loopback_stream is not None:
            self.loopback_stream.stop_stream()
            self.loopback_stream.close()

        if self.audio is not None:
            self.audio.terminate()

        self.microphone_stream = None
        self.loopback_stream = None
        self.audio = None

        sys.exit()

    def toggle_play(self) -> None:
        self.__paused = not self.is_paused

    def set_volume(self, volume: float) -> None:
        self.volume = max(min(volume, 1), 0)

    def update_volume(self, data) -> Any:
        audio_data = np.frombuffer(data, dtype = np.int16)
        audio_data = (audio_data * max(min(pow(self.volume, 3), 1), 0)).astype(np.int16)
        return audio_data.tobytes()
    
    def _update_volume(self, data, volume: float) -> Any:
        audio_data = np.frombuffer(data, dtype = np.int16)
        audio_data = (audio_data * max(min(pow(volume, 3), 1), 0)).astype(np.int16)
        return audio_data.tobytes()

    def set_position(self, wave_file: wave.Wave_read, percent: float) -> None:
        wave_file.setpos(round(max(min(percent, 1), 0) * wave_file.getnframes()))

if __name__ == "__main__":
    Sound(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), bool(sys.argv[4]), bool(sys.argv[5])).play()