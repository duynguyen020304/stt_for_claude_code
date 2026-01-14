# Sherpa-ONNX Server Implementation Plan

## Overview

Create a new STT server using sherpa-onnx that matches the API input/output of the existing `server_chunkformer_model.py`, but uses the `csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20` Vietnamese model.

**Target Model:** https://huggingface.co/csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20

---

## API Compatibility Requirements

The new server must maintain API compatibility with the existing ChunkFormer server:

### Endpoints (must match exactly)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Root endpoint with API information |
| GET | `/health` | Health check and model status |
| POST | `/transcribe` | File upload transcription |
| WS | `/transcribe/ws` | WebSocket streaming transcription |

### Response Format (must match)

```json
{
  "text": "transcribed text here",
  "segments": [
    {
      "decode": "text segment",
      "start": 0.0,
      "end": 1.5
    }
  ]
}
```

---

## Model Architecture Analysis

### Sherpa-ONNX Vietnamese Model Details

| Property | Value |
|----------|-------|
| **Model ID** | `csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20` |
| **Architecture** | Zipformer Encoder + Transducer (Decoder/Joiner) |
| **Model Type** | Transducer (NOT CTC) |
| **Training Data** | ~70,000 hours Vietnamese audio |
| **Vocabulary** | 2000 BPE tokens |
| **Model Files** | encoder.onnx, decoder.onnx, joiner.onnx, tokens.txt |
| **Total Size** | ~258 MB |

### Key Differences from ChunkFormer

| Aspect | ChunkFormer | Sherpa-ONNX (new) |
|--------|-------------|-------------------|
| Framework | PyTorch | ONNX Runtime |
| Model Loading | `from_pretrained()` (Hugging Face) | Local file paths only |
| Long-form Audio | `endless_decode()` with chunking | Manual chunking or single decode |
| Timestamps | Built-in segment timestamps | Token-level timestamps only |
| Streaming | Native support | Limited (metadata issues) |
| Dependencies | torch, torchaudio, chunkformer | sherpa-onnx only |

---

## Implementation Plan

### Phase 1: Model Service Layer

**File:** `stt_server/sherpa_onnx_service.py`

Create a `SherpaONNXService` singleton class that:

1. **Handles model initialization**
   - Downloads model from Hugging Face on first run (if not present)
   - Uses `OfflineRecognizer.from_transducer()` (not CTC)
   - Configurable threads (default: 4), device (cpu/cuda)

2. **Implements transcription methods**
   - `transcribe(audio_path, return_timestamps=True)` - Single file
   - Returns format matching ChunkFormer: `{text, segments}`

3. **Handles timestamps conversion**
   - Sherpa-ONNX provides token-level timestamps
   - Need to convert to word/segment-level timestamps
   - Algorithm: Group tokens by words, calculate start/end times

```python
# Skeleton structure
class SherpaONNXService:
    _instance = None
    _recognizer = None

    async def get_model(self):
        # Lazy load model on first request

    async def transcribe(self, audio_path, return_timestamps=True):
        # 1. Load audio using sherpa_onnx.read_wave()
        # 2. Create stream, accept waveform
        # 3. Decode stream
        # 4. Get result with timestamps
        # 5. Convert to ChunkFormer-compatible format
```

### Phase 2: FastAPI Server

**File:** `stt_server/server_sherpa_onnx.py`

Create server with identical endpoints to existing server:

```python
# Configuration
SHERPA_ONNX_MODEL = "csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20"
MODEL_DIR = "./models/sherpa-onnx-vi"
NUM_THREADS = 4
DEVICE = "cpu"  # or "cuda"

# Endpoints
@app.get("/")              # API information
@app.get("/health")        # Health check
@app.post("/transcribe")   # File transcription
@app.websocket("/transcribe/ws")  # WebSocket streaming
```

### Phase 3: Timestamp Conversion Logic

Sherpa-ONNX returns token-level timestamps, but ChunkFormer returns segment-level. Need conversion:

```python
def convert_timestamps_to_segments(text: str, timestamps: List[float]) -> List[dict]:
    """
    Convert token timestamps to segment format.

    Input:  text="xin chào", timestamps=[0.52, 0.98]
    Output: [{"decode": "xin chào", "start": 0.0, "end": 0.98}]
    """
    words = text.split()
    segments = []

    for i, word in enumerate(words):
        start = timestamps[i-1] if i > 0 else 0.0
        end = timestamps[i] if i < len(timestamps) else timestamps[-1]
        segments.append({
            "decode": word,
            "start": start,
            "end": end
        })

    return segments
```

### Phase 4: Audio Format Handling

Reuse existing audio conversion logic:

- Accept: WAV, MP3, M4A, FLAC, OGG
- Convert non-WAV to WAV using pydub
- Ensure 16kHz, mono, 16-bit PCM

### Phase 5: WebSocket Support

For WebSocket endpoint, two approaches:

**Option A: Simple (recommended)**
- Treat each message as independent audio chunk
- Transcribe each chunk separately
- No context between chunks

**Option B: Advanced (later)**
- Accumulate audio chunks in a buffer
- Process when silence detected or buffer full
- Requires VAD (Voice Activity Detection)

---

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `SHERPA_ONNX_MODEL` | `csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20` | Hugging Face model ID |
| `MODEL_DIR` | `./models/sherpa-onnx-vi` | Local model cache directory |
| `NUM_THREADS` | `4` | CPU threads for inference |
| `DEVICE` | `cpu` | Execution provider (cpu/cuda) |
| `SAMPLE_RATE` | `16000` | Required audio sample rate |
| `HOST` | `localhost` | Server host |
| `PORT` | `8001` | Server port (different from ChunkFormer) |

---

## Model Download Strategy

### Automatic Download on First Run

```python
def ensure_model_downloaded(model_id: str, local_dir: str) -> str:
    """Download model from Hugging Face if not present."""
    if Path(local_dir).exists():
        return local_dir

    print(f"Downloading model {model_id}...")
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=model_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False
    )
```

### Required Files

After download, verify these files exist:
- `encoder-epoch-12-avg-8.onnx` (~249 MB)
- `decoder-epoch-12-avg-8.onnx` (~5 MB)
- `joiner-epoch-12-avg-8.onnx` (~4 MB)
- `tokens.txt` (~26 KB)

---

## Dependencies

### New Requirements

```txt
# Add to requirements.txt
sherpa-onnx>=1.10.0
huggingface-hub>=0.20.0

# Existing (keep)
fastapi
uvicorn
pydub
pydantic
python-multipart
```

---

## File Structure

```
stt_server/
├── server_chunkformer_model.py    # Existing ChunkFormer server
├── server_sherpa_onnx.py          # NEW: Sherpa-ONNX server
├── sherpa_onnx_service.py         # NEW: Service layer
├── requirements.txt               # Update with sherpa-onnx
└── models/
    └── sherpa-onnx-vi/            # Auto-downloaded model
        ├── encoder-epoch-12-avg-8.onnx
        ├── decoder-epoch-12-avg-8.onnx
        ├── joiner-epoch-12-avg-8.onnx
        └── tokens.txt
```

---

## Implementation Steps

### Step 1: Create Service Layer
- [ ] Create `sherpa_onnx_service.py`
- [ ] Implement `SherpaONNXService` singleton
- [ ] Add model download logic
- [ ] Implement `transcribe()` method
- [ ] Add timestamp conversion

### Step 2: Create Server
- [ ] Create `server_sherpa_onnx.py`
- [ ] Implement all 4 endpoints matching ChunkFormer API
- [ ] Add audio format conversion
- [ ] Add error handling

### Step 3: WebSocket Support
- [ ] Implement `/transcribe/ws` endpoint
- [ ] Handle base64 audio data
- [ ] Return transcription results

### Step 4: Testing
- [ ] Test with sample audio files
- [ ] Verify API compatibility
- [ ] Test health endpoint
- [ ] Test WebSocket connection

### Step 5: Documentation
- [ ] Update CLAUDE.md with new server info
- [ ] Add startup instructions
- [ ] Document any differences from ChunkFormer

---

## Key Implementation Details

### 1. Model Initialization

```python
import sherpa_onnx

recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=os.path.join(model_dir, "encoder-epoch-12-avg-8.onnx"),
    decoder=os.path.join(model_dir, "decoder-epoch-12-avg-8.onnx"),
    joiner=os.path.join(model_dir, "joiner-epoch-12-avg-8.onnx"),
    tokens=os.path.join(model_dir, "tokens.txt"),
    num_threads=4,
    sample_rate=16000,
    feature_dim=80,
    decoding_method="greedy_search",
    provider="cpu"
)
```

### 2. Audio Loading

Sherpa-ONNX has a built-in WAV reader:

```python
import sherpa_onnx

# Returns normalized float32 numpy array
audio = sherpa_onnx.read_wave(audio_path)
```

### 3. Transcription Flow

```python
# Create stream
stream = recognizer.create_stream()

# Accept audio (must be float32, 16kHz)
stream.accept_waveform(16000, audio)

# Decode
recognizer.decode_stream(stream)

# Get result
result = recognizer.get_result(stream)

# Access text and timestamps
text = result.text
timestamps = result.timestamps  # End time for each token
```

### 4. Response Format Conversion

```python
def format_response(text: str, timestamps: List[float]) -> dict:
    """Format response to match ChunkFormer API."""
    segments = convert_timestamps_to_segments(text, timestamps)
    return {
        "text": text,
        "segments": segments
    }
```

---

## Known Limitations

1. **No streaming endpoint for continuous audio**
   - Sherpa-ONNX OnlineRecognizer has metadata issues with this model
   - WebSocket will treat each message as independent chunk
   - Consider adding VAD later for better UX

2. **Timestamp granularity**
   - Sherpa-ONNX provides token-level timestamps
   - We approximate word/segment timestamps from tokens
   - Less precise than ChunkFormer's native segments

3. **No long-form optimization**
   - ChunkFormer has `endless_decode()` for hours-long audio
   - Sherpa-ONNX processes entire file at once
   - May have memory issues with very long files (>30 min)

---

## Testing Plan

### Unit Tests
- [ ] Model initialization
- [ ] Timestamp conversion
- [ ] Audio loading

### Integration Tests
- [ ] POST /transcribe with WAV file
- [ ] POST /transcribe with MP3 file (conversion)
- [ ] WebSocket transcription
- [ ] Health check endpoint

### Compatibility Tests
- [ ] Compare output format with ChunkFormer
- [ ] Test with existing desktop client
- [ ] Verify response JSON structure

---

## Rollout Strategy

1. **Phase 1:** Implement server on port 8001 (doesn't conflict)
2. **Phase 2:** Test with sample audio files
3. **Phase 3:** Test with desktop client (update server URL)
4. **Phase 4:** Benchmark performance vs ChunkFormer
5. **Phase 5:** Decide on migration strategy

---

## Estimated Complexity

| Component | Complexity | Time |
|-----------|------------|------|
| Service Layer | Medium | 2-3 hours |
| FastAPI Server | Low | 1-2 hours |
| Timestamp Logic | Low | 1 hour |
| WebSocket | Medium | 2 hours |
| Testing | Medium | 2 hours |
| **Total** | | **8-10 hours** |

---

## Open Questions

1. **Port allocation:** Use 8001 or make configurable?
2. **Model caching:** Cache downloaded model between runs?
3. **Error handling:** Match ChunkFormer error responses exactly?
4. **WebSocket behavior:** Independent chunks or accumulated buffer?

---

## References

- **Sherpa-ONNX GitHub:** https://github.com/k2-fsa/sherpa-onnx
- **Sherpa-ONNX Docs:** https://k2-fsa.github.io/sherpa-onnx/
- **Vietnamese Model:** https://huggingface.co/csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20
- **Existing Server:** `stt_server/server_chunkformer_model.py`
