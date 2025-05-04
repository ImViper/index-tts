from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TTSTaskRequest(BaseModel):
    """Request model for creating a TTS task"""
    text: str = Field(..., description="Text to be converted to speech")
    output_path: str = Field(..., description="Output directory path for the generated audio file")
    infer_mode: Optional[Literal["普通推理", "批次推理"]] = Field("普通推理", description="Inference mode")


class TTSTaskResponse(BaseModel):
    """Response model for a TTS task creation"""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")


class TTSTaskStatusResponse(BaseModel):
    """Response model for a TTS task status"""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status: pending/processing/completed/failed")
    output_path: str = Field(..., description="Output file path")
    process_time: Optional[float] = Field(None, description="Processing time in seconds")
    error: Optional[str] = Field(None, description="Error message if task failed")


class PromptsResponse(BaseModel):
    """Response model for available prompts"""
    prompts: List[str] = Field(..., description="List of available prompt audio files")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service status")
