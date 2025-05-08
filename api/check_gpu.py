import torch

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA version built with PyTorch: {torch.version.cuda}")
    print(f"Number of GPUs: {torch.cuda.device_count()}")
    if torch.cuda.device_count() > 0:
        print(f"Current GPU index: {torch.cuda.current_device()}")
        print(f"GPU name: {torch.cuda.get_device_name(torch.cuda.current_device())}")
else:
    print("CUDA is not available. PyTorch cannot use your GPU.")

# Check for MPS (Apple Silicon GPU) as well, just in case
if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    print("MPS (Apple Silicon GPU) is available.")
else:
    print("MPS (Apple Silicon GPU) is not available or not configured.")
