"""
Database Schemas for PrevailPay

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class Company(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class WageRate(BaseModel):
    craft: str = Field(..., description="Craft/classification name, e.g., Electrician")
    base_rate: float = Field(..., ge=0, description="Base hourly rate")
    fringe_rate: float = Field(0, ge=0, description="Hourly fringe amount")
    apprentice_factor: Optional[float] = Field(0.6, ge=0, le=1, description="Multiplier for apprentice base pay (e.g., 0.6)")

class Project(BaseModel):
    name: str
    agency: Optional[str] = Field(None, description="Contracting agency/owner")
    county: Optional[str] = None
    state: Optional[str] = None
    project_number: Optional[str] = None
    address: Optional[str] = None
    wage_templates: List[WageRate] = Field(default_factory=list, description="Craft wage/fringe rates for this project")
    apprentice_required_ratio: Optional[str] = Field(None, description="Optional note like 1:5")

class Employee(BaseModel):
    name: str
    last_four_ssn: Optional[str] = Field(None, description="Last four digits for WH-347")
    classification: Optional[str] = None

class TimesheetEntry(BaseModel):
    project_id: str
    employee_name: str
    date: str  # YYYY-MM-DD
    craft: str
    hours: float = Field(..., ge=0)
    apprentice: bool = False
    week_ending: str = Field(..., description="Week ending date YYYY-MM-DD for grouping")

class Submission(BaseModel):
    project_id: str
    week_ending: str
    totals: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    signer_name: Optional[str] = None
    signer_title: Optional[str] = None
    signed_at: Optional[str] = None
    status: str = Field("generated", description="generated | signed")
