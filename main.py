import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from database import db, create_document, get_documents
from schemas import Project, WageRate, Employee, TimesheetEntry, Submission

app = FastAPI(title="PrevailPay API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"name": "PrevailPay", "message": "Certified payroll & compliance API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# 1) Projects CRUD (basic endpoints)
class ProjectCreate(Project):
    pass

@app.post("/projects")
def create_project(project: ProjectCreate):
    project_id = create_document("project", project)
    return {"id": project_id}

@app.get("/projects")
def list_projects():
    return get_documents("project", {})

# 2) Employees (lightweight directory)
class EmployeeCreate(Employee):
    pass

@app.post("/employees")
def create_employee(emp: EmployeeCreate):
    emp_id = create_document("employee", emp)
    return {"id": emp_id}

@app.get("/employees")
def list_employees():
    return get_documents("employee", {})

# 3) Timesheets: CSV-like entries and manual entry
class TimesheetBulk(BaseModel):
    entries: List[TimesheetEntry]

@app.post("/timesheets/bulk")
def upload_timesheets(payload: TimesheetBulk):
    ids = []
    for entry in payload.entries:
        ids.append(create_document("timesheetentry", entry))
    return {"inserted": len(ids), "ids": ids}

@app.get("/timesheets")
def list_timesheets(project_id: str = None, week_ending: str = None):
    filt: Dict[str, Any] = {}
    if project_id:
        filt["project_id"] = project_id
    if week_ending:
        filt["week_ending"] = week_ending
    return get_documents("timesheetentry", filt)

# 4) Wage Engine & WH-347-like totals (simplified)

class GenerateRequest(BaseModel):
    project_id: str
    week_ending: str  # YYYY-MM-DD

@app.post("/submissions/generate")
def generate_submission(req: GenerateRequest):
    # Load project & rates
    projects = get_documents("project", {"_id": {"$exists": True}})
    proj = next((p for p in projects if str(p.get("_id")) == req.project_id), None)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    rates: List[Dict[str, Any]] = proj.get("wage_templates", [])

    # Load timesheets for that week
    rows = get_documents("timesheetentry", {"project_id": req.project_id, "week_ending": req.week_ending})

    # Build rate lookup
    rate_map: Dict[str, Dict[str, float]] = {}
    for r in rates:
        craft = r.get("craft")
        rate_map[craft] = {
            "base": float(r.get("base_rate", 0)),
            "fringe": float(r.get("fringe_rate", 0)),
            "apprentice_factor": float(r.get("apprentice_factor", 0.6)),
        }

    totals: Dict[str, float] = {
        "hours": 0.0,
        "base_pay": 0.0,
        "fringe": 0.0,
        "gross": 0.0,
    }
    warnings: List[str] = []

    for t in rows:
        craft = t.get("craft")
        hours = float(t.get("hours", 0))
        apprentice = bool(t.get("apprentice", False))
        if craft not in rate_map:
            warnings.append(f"Missing wage rate for craft '{craft}'")
            continue
        rm = rate_map[craft]
        base_rate = rm["base"] * (rm["apprentice_factor"] if apprentice else 1.0)
        fringe_rate = rm["fringe"]
        base_pay = base_rate * hours
        fringe_pay = fringe_rate * hours
        gross = base_pay + fringe_pay
        totals["hours"] += hours
        totals["base_pay"] += base_pay
        totals["fringe"] += fringe_pay
        totals["gross"] += gross

    sub = Submission(
        project_id=req.project_id,
        week_ending=req.week_ending,
        totals={k: round(v, 2) for k, v in totals.items()},
        warnings=warnings,
        status="generated",
    )
    sub_id = create_document("submission", sub)
    return {"id": sub_id, **sub.model_dump()}

class SignRequest(BaseModel):
    submission_id: str
    signer_name: str
    signer_title: str

@app.post("/submissions/sign")
def sign_submission(req: SignRequest):
    # Store a signature record as a new document for immutability
    sig = {
        "submission_id": req.submission_id,
        "signer_name": req.signer_name,
        "signer_title": req.signer_title,
        "signed_at": datetime.utcnow().isoformat(),
        "type": "statement_of_compliance"
    }
    sig_id = create_document("signature", sig)
    return {"signature_id": sig_id, "status": "signed"}

@app.get("/submissions")
def list_submissions(project_id: str = None, week_ending: str = None):
    filt: Dict[str, Any] = {}
    if project_id:
        filt["project_id"] = project_id
    if week_ending:
        filt["week_ending"] = week_ending
    return get_documents("submission", filt)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
