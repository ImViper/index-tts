import os
import time
import requests
import argparse
import shutil

# Parse command line arguments
parser = argparse.ArgumentParser(description="Test the IndexTTS API server")
parser.add_argument("--host", default="http://localhost:8000", help="API server host")
parser.add_argument("--prompt", default="sample_prompt.wav", help="Prompt audio file name")
parser.add_argument("--text", default="你好，这是一段测试文本", help="Text to synthesize")
args = parser.parse_args()

# API base URL
base_url = f"{args.host}/api/v1"

# Step 1: Check if the server is running
print("Testing API server health...")
try:
    response = requests.get(f"{base_url}/health")
    response.raise_for_status()
    print(f"Health check: {response.json()}")
except Exception as e:
    print(f"Error: {str(e)}")
    print("Make sure the API server is running.")
    exit(1)

# Step 2: Check available prompts
print("\nGetting available prompts...")
response = requests.get(f"{base_url}/tts/prompts")
prompts = response.json()["prompts"]
print(f"Available prompts: {prompts}")

# Step 3: Copy test prompt if needed
if args.prompt not in prompts and os.path.exists(f"tests/{args.prompt}"):
    print(f"\nCopying test prompt {args.prompt} to prompts directory...")
    os.makedirs("prompts", exist_ok=True)
    shutil.copy(f"tests/{args.prompt}", f"prompts/{args.prompt}")
    print(f"Copied {args.prompt} to prompts directory")

# Step 4: Create a TTS task
print("\nCreating TTS task...")
output_path = f"outputs/tasks/test_{int(time.time())}.wav"
task_data = {
    "text": args.text,
    "prompt_name": args.prompt,
    "output_path": output_path,
    "infer_mode": "普通推理"
}

response = requests.post(f"{base_url}/tts/tasks", json=task_data)
task = response.json()
task_id = task["task_id"]
print(f"Created task: {task}")

# Step 5: Poll task status until complete
print("\nPolling task status...")
max_polls = 60  # Maximum number of polls (5 minutes with 5-second interval)
poll_interval = 5  # Seconds between polls

for i in range(max_polls):
    response = requests.get(f"{base_url}/tts/tasks/{task_id}")
    status = response.json()
    print(f"Task status: {status}")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    print(f"Waiting {poll_interval} seconds...")
    time.sleep(poll_interval)

# Step 6: Check the result
if status["status"] == "completed":
    print(f"\nTask completed successfully!")
    print(f"Output file: {output_path}")
    if os.path.exists(output_path):
        print(f"File size: {os.path.getsize(output_path)} bytes")
    else:
        print("Warning: Output file not found")
else:
    print(f"\nTask did not complete successfully: {status}")
