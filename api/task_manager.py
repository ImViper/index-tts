import os
import time
import threading
import uuid
import json
from typing import Dict, Optional, List, Literal
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


class TaskManager:
    """Manages TTS tasks"""
    def __init__(self, model_dir: str = "checkpoints", cfg_path: str = "checkpoints/config.yaml"):
        logger.info("Initializing TaskManager...")
        self.tasks: Dict[str, TTSTask] = {}
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
            tasks_data = {task_id: task.to_dict() for task_id, task in self.tasks.items()}
            try:
                with open(self.tasks_file, 'w') as f:
                    json.dump(tasks_data, f, indent=2)
                logger.info(f"Tasks saved to {self.tasks_file}")
            except Exception as e:
                logger.error(f"Failed to save tasks: {str(e)}")
    
    def _load_tasks(self):
        """Load tasks from file"""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, 'r') as f:
                    tasks_data = json.load(f)
                
                for task_id, task_data in tasks_data.items():
                    try:
                        self.tasks[task_id] = TTSTask.from_dict(task_data)
                    except Exception as e:
                        logger.error(f"Failed to load task {task_id}: {str(e)}")
                
                logger.info(f"Loaded {len(self.tasks)} tasks from {self.tasks_file}")
            except Exception as e:
                logger.error(f"Failed to load tasks: {str(e)}")
        else:
            logger.info(f"No tasks file found at {self.tasks_file}, starting with empty task list")
        
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
    
    def get_task(self, task_id: str) -> Optional[TTSTask]:
        """Get a task by its ID"""
        # Ensure we have the latest task list from file? <-- PROBLEM HERE
        # self._load_tasks() # <-- REMOVE THIS LINE
        
        with self.lock:
            task = self.tasks.get(task_id)
        if task:
            logger.info(f"Retrieved task {task_id} with status: {task.status}")
        else:
            logger.warning(f"Task {task_id} not found")
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
    
    def shutdown(self):
        """Shutdown the task manager"""
        logger.info("Shutting down task manager")
        self.running = False
        self.worker_thread.join(timeout=5)
        # Save tasks one last time before shutdown
        self._save_tasks()
        logger.info("Task manager shutdown complete")
