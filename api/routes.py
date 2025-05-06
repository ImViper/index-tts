import os
import random
import time
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends

from .models import (
    TTSTaskRequest,
    TTSTaskResponse,
    TTSTaskStatusResponse,
    PromptsResponse,
    HealthResponse,
    BatchTTSTaskRequest,
    BatchTTSTaskResponse,
    BatchTTSTaskStatusResponse
)
from .task_manager import TaskManager, TaskStatus

# Create API router
router = APIRouter(prefix="/api/tts")

# Global task manager instance that will be set by api_server.py
_task_manager = None


def set_task_manager(task_manager_instance: TaskManager):
    """Set the global task manager instance"""
    global _task_manager
    _task_manager = task_manager_instance


def get_task_manager() -> TaskManager:
    """Get the global task manager instance"""
    global _task_manager
    if _task_manager is None:
        # This should not happen as the task_manager should be set by api_server.py
        # But as a fallback, we'll create a new one
        _task_manager = TaskManager()
    return _task_manager


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/prompts", response_model=PromptsResponse)
async def get_prompts():
    """Get available prompt audio files"""
    # Ensure prompts directory exists
    os.makedirs("prompts", exist_ok=True)
    
    # List all wav files in the prompts directory
    prompts = [f for f in os.listdir("prompts") if f.endswith(".wav")]
    
    return {"prompts": prompts}


@router.post("/tasks", response_model=TTSTaskResponse)
async def create_task(
    request: TTSTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager)
):
    """Create a new TTS task"""
    # Get available prompts
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    # H:\Code\index-tts\prompts
    os.makedirs(prompts_dir, exist_ok=True)
    available_prompts = [f for f in os.listdir(prompts_dir) if f.lower().endswith(".wav")]

    if not available_prompts:
        raise HTTPException(
            status_code=400,
            detail="No prompt audio files found in the 'prompts' directory."
        )

    # Randomly select a prompt
    selected_prompt_name = random.choice(available_prompts)
    prompt_path = os.path.join(prompts_dir, selected_prompt_name)

    # Generate a timestamp-based filename
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    generated_filename = f"{timestamp}.wav"
    
    # Use the requested output path directly without adding an output folder
    output_dir = request.output_path
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, generated_filename)

    # Create the task
    task_id = task_manager.create_task(
        text=request.text,
        prompt_path=prompt_path,
        output_path=final_output_path,
        infer_mode=request.infer_mode
    )

    return {"task_id": task_id, "status": TaskStatus.PENDING}


@router.post("/batch_tasks", response_model=BatchTTSTaskResponse)
async def create_batch_task(
    request: BatchTTSTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager)
):
    """Create a new batch TTS task"""
    # Get available prompts
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    os.makedirs(prompts_dir, exist_ok=True)
    available_prompts = [f for f in os.listdir(prompts_dir) if f.lower().endswith(".wav")]

    if not available_prompts:
        raise HTTPException(
            status_code=400,
            detail="No prompt audio files found in the 'prompts' directory."
        )

    # Use specified prompt or randomly select one
    if request.prompt_path:
        # Check if the specified prompt exists
        if not os.path.exists(request.prompt_path):
            # Check if it's just a filename without path
            potential_path = os.path.join(prompts_dir, request.prompt_path)
            if os.path.exists(potential_path):
                prompt_path = potential_path
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Specified prompt '{request.prompt_path}' not found."
                )
        else:
            prompt_path = request.prompt_path
    else:
        # Randomly select a prompt
        selected_prompt_name = random.choice(available_prompts)
        prompt_path = os.path.join(prompts_dir, selected_prompt_name)

    # Ensure output directory exists
    output_directory = request.output_directory
    os.makedirs(output_directory, exist_ok=True)

    # Validate that all filenames in speeches have .wav extension
    invalid_filenames = [filename for filename in request.speeches.keys() if not filename.lower().endswith('.wav')]
    if invalid_filenames:
        raise HTTPException(
            status_code=400,
            detail=f"All filenames must end with .wav extension. Invalid filenames: {', '.join(invalid_filenames)}"
        )

    # Create the batch task
    task_id = task_manager.create_batch_task(
        speeches=request.speeches,
        prompt_path=prompt_path,
        output_directory=output_directory,
        infer_mode=request.infer_mode
    )

    return {
        "task_id": task_id, 
        "status": TaskStatus.PENDING,
        "total_files": len(request.speeches)
    }


@router.get("/tasks/{task_id}", response_model=None)
async def get_task_status(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager)
):
    """Get the status of a TTS task"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task with ID '{task_id}' not found"
        )
    
    # Check if it's a batch task or regular task
    if hasattr(task, 'total_files'):  # It's a batch task
        response = {
            "task_id": task.task_id,
            "status": task.status,
            "output_directory": task.output_directory,
            "total_files": task.total_files,
            "processed_files": task.processed_files
        }
        
        # Add process_time if available
        if task.process_time is not None:
            response["process_time"] = task.process_time
        
        # Add errors if any
        if task.errors:
            response["errors"] = task.errors
        
        return BatchTTSTaskStatusResponse(**response)
    else:  # It's a regular task
        response = {
            "task_id": task.task_id,
            "status": task.status,
            "output_path": task.output_path,
        }
        
        # Add process_time if available
        if task.process_time is not None:
            response["process_time"] = task.process_time
        
        # Add error if task failed
        if task.status == TaskStatus.FAILED and task.error:
            response["error"] = task.error
        
        return TTSTaskStatusResponse(**response)
