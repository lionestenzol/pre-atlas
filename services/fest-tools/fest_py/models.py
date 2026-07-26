from pydantic import BaseModel, ConfigDict
from typing import Optional


class Festival(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    path: str
    status: str
    progress: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PhaseProgress(BaseModel):
    model_config = ConfigDict(extra="allow")
    total: int = 0
    completed: int = 0
    in_progress: int = 0
    blocked: int = 0
    pending: int = 0
    percentage: int = 0
    time_spent_minutes: int = 0


class Phase(BaseModel):
    model_config = ConfigDict(extra="allow")
    phase_id: str
    phase_name: str
    progress: PhaseProgress


class ProgressReport(BaseModel):
    model_config = ConfigDict(extra="allow")
    festival_name: str
    overall: PhaseProgress
    phases: list[Phase] = []


class NextTask(BaseModel):
    model_config = ConfigDict(extra="allow")
    task: Optional[dict] = None
    reason: Optional[str] = None
    festival_complete: bool = False
