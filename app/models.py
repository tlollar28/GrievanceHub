from pydantic import BaseModel

class ClockRingEvent(BaseModel):
    employee_name: str
    date: str
    event_type: str
    time: str
    code: str

class Assignment(BaseModel):
    employee_name: str
    date: str
    machine: str
    start_time: str
    end_time: str
    duration_minutes: int

class MachineRunSession(BaseModel):
    date: str
    machine: str
    start_time: str
    end_time: str
    duration_minutes: int

class CrossCraftFinding(BaseModel):
    date: str
    machine: str
    machine_start_time: str
    machine_end_time: str
    duration_minutes: int
    clerk_names: list[str]
    pse_names: list[str]
    mail_handler_names: list[str]
    clerk_count: int
    pse_count: int
    total_clerk_side_count: int
    mail_handler_count: int
    allowed_clerks: int
    required_mail_handlers: int
    status: str
    reason: str

class AssignmentInput(BaseModel):
    employee_name: str
    craft: str
    employee_type: str
    date: str
    code: str
    start_time: str
    end_time: str
    duration_minutes: int

