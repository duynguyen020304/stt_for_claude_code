import sounddevice as sd
import numpy as np
import threading
from pathlib import Path


class AudioRingBuffer:
    """Thread-safe ring buffer for audio PCM data."""

    def __init__(self, buffer_size_samples: int, channels: int = 1):
        self.buffer_size = buffer_size_samples
        self.channels = channels
        self.buffer = np.zeros((buffer_size_samples, channels), dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.count = 0
        self.lock = threading.Lock()

    def write(self, data: np.ndarray) -> int:
        n_samples = len(data)
        with self.lock:
            available = self.buffer_size - self.count
            writable = min(n_samples, available)
            if writable == 0:
                return 0

            end_pos = self.write_pos + writable
            if end_pos <= self.buffer_size:
                self.buffer[self.write_pos:end_pos] = data[:writable]
            else:
                first_part = self.buffer_size - self.write_pos
                self.buffer[self.write_pos:] = data[:first_part]
                self.buffer[:end_pos - self.buffer_size] = data[first_part:writable]

            self.write_pos = end_pos % self.buffer_size
            self.count += writable
            return writable

    def read_all(self) -> np.ndarray:
        with self.lock:
            if self.count == 0:
                return np.zeros((0, self.channels), dtype=np.float32)

            result = np.zeros((self.count, self.channels), dtype=np.float32)
            end_pos = self.read_pos + self.count

            if end_pos <= self.buffer_size:
                result[:] = self.buffer[self.read_pos:end_pos]
            else:
                first_part = self.buffer_size - self.read_pos
                result[:first_part] = self.buffer[self.read_pos:]
                result[first_part:] = self.buffer[:end_pos - self.buffer_size]

            self.read_pos = end_pos % self.buffer_size
            self.count = 0
            return result


class AudioRecorder:
    """Real-time audio recorder with ring buffer."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        buffer_duration: int = 30,
        blocksize: int = 2048
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_duration = buffer_duration
        self.blocksize = blocksize

        buffer_size = sample_rate * buffer_duration
        self.ring_buffer = AudioRingBuffer(buffer_size, channels)

        self.is_recording = False
        self.stream = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio callback status: {status}")
        self.ring_buffer.write(indata)

    def start(self):
        if self.is_recording:
            return

        self.ring_buffer = AudioRingBuffer(
            self.sample_rate * self.buffer_duration,
            self.channels
        )

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self._audio_callback,
            blocksize=self.blocksize,
            dtype=np.float32
        )
        self.stream.start()
        self.is_recording = True
        print("Recording started")

    def stop(self) -> np.ndarray:
        if not self.is_recording:
            return np.zeros((0, self.channels), dtype=np.float32)

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.is_recording = False
        print("Recording stopped")

        return self.ring_buffer.read_all()

    def save_to_wav(self, audio: np.ndarray, filename: str):
        import soundfile as sf
        sf.write(filename, audio, self.sample_rate, subtype='PCM_16')
        print(f"Saved to {filename}")
