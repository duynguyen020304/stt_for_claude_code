# Audio Transcription Server - Test Results

## Summary

Tested the ChunkFormer-based audio transcription server with 10 Vietnamese audio samples.

**Date:** 2025-01-13
**Model:** khanhld/chunkformer-ctc-large-vie
**Device:** CPU

## Issue Found and Fixed

### Problem
The server failed with an error when trying to transcribe audio:
```
OSError: libtorch_cuda.so: cannot open shared object file: No such file or directory
```

**Root Cause:** The `torchaudio` package (2.9.1) was installed with CUDA support, but the system doesn't have CUDA libraries installed. This caused torchaudio to fail during import when trying to load CUDA dependencies.

**Solution:** Reinstalled `torchaudio` with CPU-only version:
```bash
pip uninstall torchaudio -y
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**Fixed Version:** `torchaudio==2.9.1+cpu` (matching the CPU-only `torch==2.9.1+cpu`)

## Test Results

All 10 audio samples were successfully transcribed:

| File | Transcription (Vietnamese) |
|------|---------------------------|
| sample_0000.wav | thế mà hôm nay lại nghe em gái nhắc đến |
| sample_0001.wav | các vấn đề y học chuyên khoa hoặc ứng |
| sample_0002.wav | không được về nhà ăn tết thì là năm |
| sample_0003.wav | lại hai bên nên cũng oải lắm nhưng vẫn |
| sample_0004.wav | ai cho phép em uống nhiều rượu như vậy |
| sample_0005.wav | mẹ xem mẹ tôi chỉ động viên rồi dặn dò |
| sample_0006.wav | nó sẽ đem lại cho con hạnh phúc mãi |
| sample_0007.wav | đàn ông là thế chơi với nhau thân thiết |
| sample_0008.wav | mà các bạn để máy ở một vị trí rất là cô |
| sample_0009.wav | mới rồi em gặp mẹ con kiều liên ở chợ |

## API Usage

### Start Server
```bash
python server.py
```

### Endpoints

**POST /transcribe**
```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "audio=@audio_samples/sample_0000.wav"
```

**Response format:**
```json
{
  "text": "thế mà hôm nay lại nghe em gái nhắc đến",
  "segments": [
    {
      "decode": "thế mà hôm nay lại nghe em gái nhắc đến",
      "start": "00:00:00:320",
      "end": "00:00:02:000"
    }
  ]
}
```

### API Documentation
Available at: http://localhost:8000/docs

## System Configuration

- **Python:** 3.12.12
- **PyTorch:** 2.9.1+cpu
- **TorchAudio:** 2.9.1+cpu (fixed)
- **ChunkFormer:** 1.2.2
- **FastAPI:** Latest
- **Platform:** Linux (CPU-only)

## Conclusion

The server is now working correctly after fixing the torchaudio dependency issue. All test samples were transcribed successfully with reasonable quality Vietnamese text output.
