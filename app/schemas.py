"""Pydantic request/response models for the API."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# --- auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    employee_id: Optional[int] = None  # links a normal user to their HR record
    department: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    full_name: str
    role: str


class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    employee_id: Optional[int] = None
    department: Optional[str] = None


# --- chat ---
class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None


class Source(BaseModel):
    idx: int
    source: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    score: Optional[float] = None


class ChatResponse(BaseModel):
    conversation_id: int
    route: str
    answer: str
    sources: List[Source] = []
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    hallucination_blocked: bool = False


class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: datetime


class Message(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: List[Message] = []


# --- policies ---
class PolicyFile(BaseModel):
    id: int
    filename: str
    category: Optional[str] = None
    chunks: int
    size_bytes: int = 0
    status: str = "indexed"
    uploaded_by: Optional[str] = None
    uploaded_at: datetime


class PolicyStats(BaseModel):
    total_policies: int
    indexed_chunks: int
    queries_served: int
    accuracy_rate: float


# --- audit ---
class AuditEntry(BaseModel):
    id: int
    username: Optional[str] = None
    role: Optional[str] = None
    action: str
    question: Optional[str] = None
    route: Optional[str] = None
    sql: Optional[str] = None
    confidence: Optional[float] = None
    latency_ms: Optional[int] = None
    hallucination_blocked: bool
    status: str
    created_at: datetime


class AuditStats(BaseModel):
    events_today: int
    flagged_for_review: int
    avg_response_ms: Optional[int] = None
    verification_pass_rate: float


# --- employees (HR data) ---
class EmployeeCreate(BaseModel):
    EmployeeID: int
    EmployeeName: str
    Age: Optional[int] = None
    Gender: Optional[str] = None
    Location: Optional[str] = None
    Department: Optional[str] = None
    Role: Optional[str] = None
    YearsAtCompany: Optional[int] = None
    DateOfJoining: Optional[date] = None
    YearsInCurrentRole: Optional[int] = None
    EducationLevel: Optional[str] = None
    MonthlySalaryINR: Optional[int] = None
    WorkHoursPerWeek: Optional[int] = None
    ProjectsHandled: Optional[int] = None
    TrainingHoursLastYear: Optional[int] = None
    SickLeavesLastYear: Optional[int] = None
    OvertimeHoursLastMonth: Optional[int] = None
    ManagerRating: Optional[int] = None
    DisciplinaryNotices: Optional[int] = None
    PolicyViolationsLastYear: Optional[int] = None
    PerformanceRating: Optional[int] = None
    PromotionLast2Years: Optional[str] = None
    ComplianceRiskLevel: Optional[str] = None
    AttritionRisk: Optional[str] = None


class Employee(EmployeeCreate):
    pass


class EmployeeListResponse(BaseModel):
    total: int
    employees: List[Dict[str, Any]]
