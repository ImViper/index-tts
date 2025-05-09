import os
import random
import asyncio
import time
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
import logging

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

lock = asyncio.Lock()

# Global for prompt index tracking
PROMPT_INDEX_FILE = "prompt_last_index.txt"  # Stores the last used prompt index, relative to project root
logger = logging.getLogger(__name__)

# Helper function to get the next prompt sequentially
def get_next_sequential_prompt_path() -> Optional[str]:
    # Construct path to prompt_last_index.txt in the project's root directory (one level up from 'api')
    project_root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    index_file_path = os.path.join(project_root_path, PROMPT_INDEX_FILE)
    
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    os.makedirs(prompts_dir, exist_ok=True) # Ensure prompts directory exists
    
    available_prompts = sorted([
        f for f in os.listdir(prompts_dir) 
        if f.lower().endswith(('.wav', '.mp3'))
    ])

    if not available_prompts:
        logger.warning("No prompts available in the prompts directory for sequential selection.")
        return None

    last_index = -1
    try:
        if os.path.exists(index_file_path):
            with open(index_file_path, "r") as f:
                content = f.read().strip()
                if content.isdigit():
                    last_index = int(content)
                else:
                    logger.warning(f"Content of {index_file_path} is not a digit: '{content}'. Resetting index.")
        else:
            logger.info(f"{index_file_path} not found. Will start from the beginning.")
    except Exception as e:
        logger.error(f"Error reading prompt index file {index_file_path}: {e}. Resetting index.")
        # Continue with last_index = -1, effectively starting from the beginning

    next_index = (last_index + 1) % len(available_prompts)

    try:
        with open(index_file_path, "w") as f:
            f.write(str(next_index))
    except Exception as e:
        logger.error(f"Error writing prompt index file {index_file_path}: {e}")
        # If writing fails, the next run might reuse the same prompt or an older index,
        # but the application should continue to function.

    selected_prompt_name = available_prompts[next_index]
    logger.info(f"Sequentially selected prompt: {selected_prompt_name} at index {next_index}")
    return os.path.join(prompts_dir, selected_prompt_name)


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
    
    # List all wav and mp3 files in the prompts directory
    prompts = [f for f in os.listdir("prompts") if f.lower().endswith(('.wav', '.mp3'))]
    
    return {"prompts": prompts}


@router.post("/tasks", response_model=TTSTaskResponse)
async def create_task(
    request: TTSTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager)
):
    async with lock:
        """Create a new TTS task"""
        # Determine prompt path
        prompt_path_to_use = None
        # Define prompts_dir for validation if user provides a prompt_path
        prompts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts"))

        if request.prompt_path:
            # User provided a specific prompt filename (relative to prompts directory)
            potential_path = os.path.join(prompts_dir, request.prompt_path)
            if os.path.isfile(potential_path) and potential_path.lower().endswith(('.wav', '.mp3')):
                prompt_path_to_use = potential_path
                logger.info(f"Using user-provided prompt: {prompt_path_to_use}")
            else:
                logger.warning(
                    f"User-provided prompt path '{request.prompt_path}' not found or invalid in '{prompts_dir}'. "
                    f"A prompt will be selected sequentially."
                )

        if not prompt_path_to_use:
            # No valid user prompt provided, or none provided at all, select sequentially
            prompt_path_to_use = get_next_sequential_prompt_path()
            if not prompt_path_to_use:
                logger.error("No prompt audio files available for sequential selection, and none were provided or valid.")
                raise HTTPException(
                    status_code=400,
                    detail="No prompt audio files found in the 'prompts' directory, and none could be automatically selected."
                )
            logger.info(f"Sequentially selected prompt: {prompt_path_to_use}")

        # Get available prompts
        prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
        prompts_dir = os.path.abspath(prompts_dir)
        os.makedirs(prompts_dir, exist_ok=True)

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
            prompt_path=prompt_path_to_use,
            output_path=final_output_path,
            infer_mode=request.infer_mode
        )

        return {"task_id": task_id, "status": TaskStatus.PENDING}


@router.post("/batch_tasks", response_model=BatchTTSTaskResponse)
async def create_batch_task(
    request: BatchTTSTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager)
):
    async with lock:
        logger.info(f"Received batch task creation request: {request}")
        # Determine the prompt path to be used for the entire batch
        prompt_path_for_batch = None
        prompts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts"))
        os.makedirs(prompts_dir, exist_ok=True) # Ensure prompts directory exists for validation

        if request.prompt_path:
            # User provided a specific prompt filename (relative to prompts directory)
            potential_path = os.path.join(prompts_dir, request.prompt_path)
            if os.path.isfile(potential_path) and potential_path.lower().endswith(('.wav', '.mp3')):
                prompt_path_for_batch = potential_path
                logger.info(f"Using user-provided prompt for batch: {prompt_path_for_batch}")
            else:
                logger.warning(
                    f"User-provided prompt path '{request.prompt_path}' for batch not found or invalid in '{prompts_dir}'. "
                    f"A single prompt will be selected sequentially for the entire batch."
                )

        if not prompt_path_for_batch:
            # No valid user prompt provided for the batch, or none provided at all, select one sequentially for the whole batch
            prompt_path_for_batch = get_next_sequential_prompt_path()
            if not prompt_path_for_batch:
                logger.error("No prompt audio files available for sequential selection for the batch, and none were provided or valid.")
                raise HTTPException(
                    status_code=400,
                    detail="No prompt audio files found in the 'prompts' directory for batch processing, and none could be automatically selected."
                )
            logger.info(f"Sequentially selected prompt for the entire batch: {prompt_path_for_batch}")

        # Validate output filenames
        output_directory = request.output_directory
        os.makedirs(output_directory, exist_ok=True)

        # Validate that all filenames in speeches have .wav or .mp3 extension
        invalid_filenames = [filename for filename in request.speeches.keys() if not filename.lower().endswith(('.wav', '.mp3'))]
        if invalid_filenames:
            raise HTTPException(
                status_code=400,
                detail=f"All filenames must end with .wav or .mp3 extension. Invalid filenames: {', '.join(invalid_filenames)}"
            )

        # Create the batch task
        task_id = task_manager.create_batch_task(
            speeches=request.speeches,
            prompt_path=prompt_path_for_batch,
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
