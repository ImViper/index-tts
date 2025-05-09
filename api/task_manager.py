import os
import time
import threading
import uuid
import json
from typing import Dict, Optional, List, Literal, Any
from enum import Enum
import logging
import traceback

from indextts.infer import IndexTTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("task_manager")


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TTSTask:
    """Represents a TTS task"""
    def __init__(self, task_id: str, text: str, prompt_path: str, output_path: str, 
                 infer_mode: Literal["普通推理", "批次推理"] = "普通推理"):
        self.task_id = task_id
        self.text = text
        self.prompt_path = prompt_path
        self.output_path = output_path
        self.infer_mode = infer_mode
        self.status = TaskStatus.PENDING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.error: Optional[str] = None
        
    @property
    def process_time(self) -> Optional[float]:
        """Calculate processing time in seconds"""
        if self.start_time is None:
            return None
        if self.end_time is None:
            return None
        return round(self.end_time - self.start_time, 2)
    
    def to_dict(self) -> dict:
        """Convert task to dictionary for serialization"""
        return {
            "task_id": self.task_id,
            "text": self.text,
            "prompt_path": self.prompt_path,
            "output_path": self.output_path,
            "infer_mode": self.infer_mode,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TTSTask':
        """Create task from dictionary"""
        task = cls(
            task_id=data["task_id"],
            text=data["text"],
            prompt_path=data["prompt_path"],
            output_path=data["output_path"],
            infer_mode=data["infer_mode"]
        )
        task.status = data["status"]
        task.start_time = data["start_time"]
        task.end_time = data["end_time"]
        task.error = data["error"]
        return task


class BatchTTSTask:
    """Represents a batch TTS task"""
    def __init__(self, task_id: str, speeches: Dict[str, str], prompt_path: str, output_directory: str, 
                 infer_mode: Literal["普通推理", "批次推理"] = "普通推理"):
        self.task_id = task_id
        self.speeches = speeches
        self.prompt_path = prompt_path
        self.output_directory = output_directory
        self.infer_mode = infer_mode
        self.status = TaskStatus.PENDING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.total_files = len(speeches)
        self.processed_files = 0
        self.errors: List[Dict[str, str]] = []
        
    @property
    def process_time(self) -> Optional[float]:
        """Calculate processing time in seconds"""
        if self.start_time is None:
            return None
        if self.end_time is None:
            return None
        return round(self.end_time - self.start_time, 2)
    
    def to_dict(self) -> dict:
        """Convert task to dictionary for serialization"""
        return {
            "task_id": self.task_id,
            "speeches": self.speeches,
            "prompt_path": self.prompt_path,
            "output_directory": self.output_directory,
            "infer_mode": self.infer_mode,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "errors": self.errors,
            "task_type": "batch"  # Add a type field to distinguish from regular tasks
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BatchTTSTask':
        """Create task from dictionary"""
        task = cls(
            task_id=data["task_id"],
            speeches=data["speeches"],
            prompt_path=data["prompt_path"],
            output_directory=data["output_directory"],
            infer_mode=data["infer_mode"]
        )
        task.status = data["status"]
        task.start_time = data["start_time"]
        task.end_time = data["end_time"]
        task.total_files = data["total_files"]
        task.processed_files = data["processed_files"]
        task.errors = data["errors"]
        return task


class TaskManager:
    """Manages TTS tasks"""
    def __init__(self, model_dir: str = "checkpoints", cfg_path: str = "checkpoints/config.yaml"):
        logger.info("Initializing TaskManager...")
        self.tasks: Dict[str, Any] = {}  # Changed to Any to support both task types
        self.model_dir = model_dir
        self.cfg_path = cfg_path
        self.tts_model: Optional[IndexTTS] = None
        self.lock = threading.Lock()
        self.tasks_file = "outputs/tasks.json"
        
        # Ensure tasks directory exists
        os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
        
        # Load existing tasks from file
        self._load_tasks()
        
        # Initialize model early to avoid delays later
        try:
            logger.info("Pre-initializing TTS model...")
            self._initialize_model()
            logger.info("TTS model pre-initialization successful")
        except Exception as e:
            logger.warning(f"TTS model pre-initialization failed: {str(e)}")
            # Continue even if model initialization fails here, we'll retry later
        
        # Start worker thread
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info("TaskManager initialized, worker thread started")
    
    def _save_tasks(self):
        """Save tasks to file"""
        with self.lock:
            tasks_data = {}
            for task_id, task in self.tasks.items():
                tasks_data[task_id] = task.to_dict()
            try:
                with open(self.tasks_file, 'w') as f:
                    json.dump(tasks_data, f, indent=2)
                logger.info(f"Tasks saved to {self.tasks_file}")
            except Exception as e:
                logger.error(f"Error saving tasks: {str(e)}")
    
    def _load_tasks(self):
        """Load tasks from file"""
        if not os.path.exists(self.tasks_file):
            logger.info(f"Tasks file {self.tasks_file} not found, starting with empty tasks")
            return
        
        try:
            with open(self.tasks_file, 'r') as f:
                tasks_data = json.load(f)
            
            for task_id, task_data in tasks_data.items():
                # Check if this is a batch task or regular task
                if task_data.get("task_type") == "batch":
                    self.tasks[task_id] = BatchTTSTask.from_dict(task_data)
                else:
                    self.tasks[task_id] = TTSTask.from_dict(task_data)
                    
            logger.info(f"Loaded {len(self.tasks)} tasks from {self.tasks_file}")
        except Exception as e:
            logger.error(f"Error loading tasks: {str(e)}")
            # Start with empty tasks if loading fails
            self.tasks = {}
    
    def _initialize_model(self):
        """Initialize the TTS model if not already initialized"""
        if self.tts_model is None:
            logger.info("Initializing TTS model...")
            try:
                self.tts_model = IndexTTS(
                    model_dir=self.model_dir,
                    cfg_path=self.cfg_path
                )
                logger.info("TTS model initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize TTS model: {str(e)}")
                logger.error(traceback.format_exc())
                raise
    
    def create_task(self, text: str, prompt_path: str, output_path: str, 
                    infer_mode: Literal["普通推理", "批次推理"] = "普通推理") -> str:
        """Create a new TTS task and return its ID"""
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate a unique task ID
        task_id = f"task_{int(time.time())}_{len(self.tasks)}"
        
        # Create and store the task
        task = TTSTask(task_id, text, prompt_path, output_path, infer_mode)
        with self.lock:
            self.tasks[task_id] = task
        
        # Save tasks to file
        self._save_tasks()
        
        logger.info(f"Created task {task_id} for text: {text[:30]}...")
        return task_id
    
    def create_batch_task(self, speeches: Dict[str, str], prompt_path: str, output_directory: str,
                          infer_mode: Literal["普通推理", "批次推理"] = "普通推理") -> str:
        """Create a new batch TTS task and return its ID"""
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Create a new task
        task = BatchTTSTask(
            task_id=task_id,
            speeches=speeches,
            prompt_path=prompt_path,
            output_directory=output_directory,
            infer_mode=infer_mode
        )
        
        # Add task to the tasks dictionary
        with self.lock:
            self.tasks[task_id] = task
        
        # Save tasks to file
        self._save_tasks()
        
        logger.info(f"Created batch task {task_id} with {len(speeches)} files")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Any]:
        """Get a task by its ID"""
        with self.lock:
            task = self.tasks.get(task_id)
        
        if task is None:
            logger.warning(f"Task {task_id} not found")
            return None
        
        return task
    
    def _worker(self):
        """Worker thread that processes tasks"""
        logger.info("Worker thread started")
        
        # Print debugging info about thread and process
        import threading
        import os
        logger.info(f"Worker thread ID: {threading.get_ident()}")
        logger.info(f"Worker process ID: {os.getpid()}")
        
        while self.running:
            try:
                # Find the next pending task
                next_task = None
                task_to_save = None # Temporary variable to hold the task needing save
                with self.lock:
                    for task in self.tasks.values():
                        if task.status == TaskStatus.PENDING:
                            logger.info(f"Found pending task {task.task_id}, changing to PROCESSING")
                            task.status = TaskStatus.PROCESSING
                            next_task = task
                            task_to_save = task # Mark this task for saving
                            break
                
                # Save updated status outside the lock if a task was updated
                if task_to_save:
                    self._save_tasks() # <-- MOVE SAVE CALL HERE

                # Process the task if one was found
                if next_task:
                    logger.info(f"Processing task {next_task.task_id}")
                    # Check if it's a batch task or regular task
                    if isinstance(next_task, BatchTTSTask):
                        self._process_batch_task(next_task)
                    else:
                        self._process_task(next_task)
                else:
                    # Sleep for a short time if no tasks are pending
                    time.sleep(1.0)
            except Exception as e:
                logger.error(f"Error in worker thread: {str(e)}")
                logger.error(traceback.format_exc())
                time.sleep(5.0)  # Sleep longer after an error
    
    def _process_task(self, task: TTSTask):
        """Process a TTS task"""
        logger.info(f"Processing task {task.task_id}")
        try:
            # Initialize the model if needed
            self._initialize_model()
            
            # Record start time
            task.start_time = time.time()
            self._save_tasks()  # Save updated state
            
            # Log task details
            logger.info(f"Task {task.task_id} details:")
            logger.info(f"  Text: {task.text[:50]}...")
            logger.info(f"  Prompt: {task.prompt_path}")
            logger.info(f"  Output: {task.output_path}")
            logger.info(f"  Mode: {task.infer_mode}")
            
            # Process the task based on inference mode
            if task.infer_mode == "普通推理":
                logger.info(f"Using regular inference for task {task.task_id}")
                self.tts_model.infer(
                    audio_prompt=task.prompt_path,
                    text=task.text,
                    output_path=task.output_path
                )
            else:  # 批次推理
                logger.info(f"Using fast inference for task {task.task_id}")
                self.tts_model.infer_fast(
                    audio_prompt=task.prompt_path,
                    text=task.text,
                    output_path=task.output_path
                )
            
            # Record end time and update status
            task.end_time = time.time()
            task.status = TaskStatus.COMPLETED
            logger.info(f"Task {task.task_id} completed successfully in {task.process_time} seconds")
            
        except Exception as e:
            # Handle errors
            logger.error(f"Task {task.task_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
        
        # Save updated task state
        self._save_tasks()
    
    def _process_batch_task(self, task: BatchTTSTask):
        """Process a batch TTS task"""
        logger.info(f"Processing batch task {task.task_id} with {task.total_files} files")
        try:
            # Initialize the model if needed
            self._initialize_model()
            
            # Record start time
            task.start_time = time.time()
            self._save_tasks()  # Save updated state
            
            # Log task details
            logger.info(f"Batch task {task.task_id} details:")
            logger.info(f"  Files: {task.total_files}")
            logger.info(f"  Prompt: {task.prompt_path}")
            logger.info(f"  Output directory: {task.output_directory}")
            logger.info(f"  Mode: {task.infer_mode}")
            
            # Ensure output directory exists
            os.makedirs(task.output_directory, exist_ok=True)
            
            # Process each file in the batch sequentially
            for filename, text in task.speeches.items():
                try:
                    # Construct full output path
                    output_path = os.path.join(task.output_directory, filename)
                    
                    logger.info(f"Processing file {filename} ({task.processed_files + 1}/{task.total_files})")
                    logger.info(f"  Text: {text[:50]}...")
                    
                    # Process the file based on inference mode
                    if task.infer_mode == "普通推理":
                        logger.info(f"Using regular inference for file {filename}")
                        logger.info(f"DEBUG: Full text being passed to tts_model.infer for {filename}: '{text}'")
                        self.tts_model.infer(
                            audio_prompt=task.prompt_path,
                            text=text,
                            output_path=output_path
                        )
                    else:  # 批次推理
                        logger.info(f"Using fast inference for file {filename}")
                        self.tts_model.infer_fast(
                            audio_prompt=task.prompt_path,
                            text=text,
                            output_path=output_path
                        )
                    
                    # Increment processed files counter
                    task.processed_files += 1
                    # Save state after each file to track progress
                    self._save_tasks()
                    
                except Exception as e:
                    # Handle errors for individual file
                    error_msg = str(e)
                    logger.error(f"Error processing file {filename}: {error_msg}")
                    task.errors.append({"filename": filename, "error": error_msg})
                    # Continue with next file despite error
            
            # Record end time and update status
            task.end_time = time.time()
            
            # If all files processed successfully or with some errors
            if task.processed_files == task.total_files:
                task.status = TaskStatus.COMPLETED
                logger.info(f"Batch task {task.task_id} completed successfully in {task.process_time} seconds")
            elif task.processed_files > 0:
                # Some files processed but not all
                task.status = TaskStatus.COMPLETED
                logger.info(f"Batch task {task.task_id} completed with {len(task.errors)} errors in {task.process_time} seconds")
            else:
                # No files processed successfully
                task.status = TaskStatus.FAILED
                logger.error(f"Batch task {task.task_id} failed completely in {task.process_time} seconds")
            
        except Exception as e:
            # Handle errors for the entire batch task
            logger.error(f"Batch task {task.task_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            task.errors.append({"filename": "batch_process", "error": str(e)})
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
        
        # Save updated task state
        self._save_tasks()
    
    def shutdown(self):
        """Shutdown the task manager"""
        logger.info("Shutting down task manager")
        self.running = False
        self.worker_thread.join(timeout=5)
        # Save tasks one last time before shutdown
        self._save_tasks()
        logger.info("Task manager shutdown complete")
