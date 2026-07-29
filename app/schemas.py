"""Pydantic request/response models for the API."""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# --- auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    """Self-registration for staff already in the HR system. Identity comes
    entirely from the company address — name, employee_id and department are
    read from the HR record, never accepted from the client."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class InviteAcceptRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class InvitePreview(BaseModel):
    company_email: str
    full_name: str


class RoleUpdateRequest(BaseModel):
    role: Literal["admin", "employee"]


class UserSummary(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    is_active: bool = True
    created_at: datetime


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
    employee_id: Optional[str] = None
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
    company: Optional[str] = None  # issuing organisation of the policy document
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
    """A new hire. `EmployeeID` and `Email` are allocated by the server, so
    neither is accepted here; the personal address is where the onboarding
    invitation is sent."""
    FullName: str = Field(min_length=1, max_length=255)
    PersonalEmail: EmailStr
    Role: Optional[str] = None
    Department: Optional[str] = None
    Location: Optional[str] = None
    DateOfJoining: Optional[date] = None
    ManagerID: Optional[str] = None
    ManagerName: Optional[str] = None
    CasualLeaveBalance: Optional[int] = None
    CasualLeaveUsed: Optional[int] = None
    SickLeaveBalance: Optional[int] = None
    SickLeaveUsed: Optional[int] = None
    EarnedLeaveBalance: Optional[int] = None
    EarnedLeaveUsed: Optional[int] = None
    LastAppraisalDate: Optional[date] = None
    NextAppraisalDate: Optional[date] = None
    POSHTrainingCompleted: Optional[str] = None
    POSHTrainingDate: Optional[date] = None
    PerformanceRating: Optional[str] = None
    AnnualCTC_INR: Optional[int] = None
    EmploymentType: Optional[str] = None


class Employee(BaseModel):
    """An employee as stored. Permissive on purpose: the HR table is reference
    data and its shape may vary between deployments."""
    EmployeeID: str
    FullName: str
    Email: Optional[str] = None
    Status: str = "active"

    model_config = {"extra": "allow"}


class EmployeeListResponse(BaseModel):
    total: int
    employees: List[Dict[str, Any]]
