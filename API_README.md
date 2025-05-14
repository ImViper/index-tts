# IndexTTS API Server

This is an API server for IndexTTS that implements the interfaces described in the API documentation.

## Setup

1. Install the required dependencies:

```bash
# Install IndexTTS dependencies
pip install -r requirements.txt

# Install API server dependencies
pip install -r requirements_api.txt
```

2. Place your reference audio files in the `prompts` directory:

```bash
mkdir -p prompts
# Copy your .wav files to the prompts directory
```

## Running the API Server

Start the API server with:

```bash
python api_server.py
```

The server will run on `http://0.0.0.0:51046` by default.

## API Documentation

Once the server is running, you can access the API documentation at:

- Swagger UI: `http://localhost:51046/docs`
- ReDoc: `http://localhost:51046/redoc`

## API Endpoints

The following endpoints are available:

- `GET /api/v1/health` - Health check
- `GET /api/v1/tts/prompts` - Get available prompt audio files
- `POST /api/v1/tts/tasks` - Create a new TTS task
- `GET /api/v1/tts/tasks/{task_id}` - Get task status

## Usage Example

1. Check available prompts:

```bash
curl -X GET http://localhost:8000/api/v1/tts/prompts
```

2. Create a TTS task:

```bash
curl -X POST http://localhost:8000/api/v1/tts/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，这是一段测试文本",
    "prompt_name": "sample_prompt.wav",
    "output_path": "outputs/tasks/test.wav",
    "infer_mode": "普通推理"
  }'
```

3. Check task status:

```bash
curl -X GET http://localhost:8000/api/v1/tts/tasks/task_1709123456_0
```
