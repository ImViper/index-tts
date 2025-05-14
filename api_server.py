import os
import sys
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Add the current directory to the path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import our API modules
from api.routes import router, set_task_manager
from api.task_manager import TaskManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_server")

# Create FastAPI app
app = FastAPI(
    title="IndexTTS API",
    description="API for IndexTTS - An Industrial-Level Controllable and Efficient Zero-Shot Text-To-Speech System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include our API router
app.include_router(router)

# Create task manager instance
task_manager = None


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    global task_manager
    
    # Create necessary directories
    os.makedirs("prompts", exist_ok=True)
    os.makedirs("outputs/tasks", exist_ok=True)
    
    # Initialize task manager
    logger.info("Initializing task manager...")
    task_manager = TaskManager()
    # Share the task manager instance with routes.py
    set_task_manager(task_manager)
    logger.info("Task manager initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    global task_manager
    if task_manager:
        logger.info("Shutting down task manager...")
        task_manager.shutdown()
        logger.info("Task manager shutdown complete")


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=51046,
        reload=True
    )
