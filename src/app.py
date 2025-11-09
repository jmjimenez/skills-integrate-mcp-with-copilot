"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
import os

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .db import engine, Base, SessionLocal, get_db
from .models import Activity, Participant

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Seed data (same as previous in-memory dataset)
SEED_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.on_event("startup")
def startup_event():
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)

    # Seed DB if empty
    db = SessionLocal()
    try:
        existing = db.query(Activity).count()
        if existing == 0:
            for name, payload in SEED_ACTIVITIES.items():
                a = Activity(
                    name=name,
                    description=payload.get("description"),
                    schedule=payload.get("schedule"),
                    max_participants=payload.get("max_participants", 0)
                )
                db.add(a)
                db.flush()  # ensure a.id is available
                for email in payload.get("participants", []):
                    p = Participant(email=email, activity_id=a.id)
                    db.add(p)
            db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    activities = db.query(Activity).all()
    result = {}
    for a in activities:
        result[a.name] = {
            "description": a.description,
            "schedule": a.schedule,
            "max_participants": a.max_participants,
            "participants": [p.email for p in a.participants]
        }
    return result


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, db: Session = Depends(get_db)):
    """Sign up a student for an activity"""
    activity = db.query(Activity).filter(Activity.name == activity_name).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Check if participant exists efficiently
    existing_participant = db.query(Participant).filter(
        Participant.activity_id == activity.id,
        Participant.email == email
    ).first()
    if existing_participant:
        raise HTTPException(status_code=400, detail="Student is already signed up")

    # Validate capacity using a count query
    if activity.max_participants and db.query(Participant).filter(Participant.activity_id == activity.id).count() >= activity.max_participants:
        raise HTTPException(status_code=400, detail="Activity is at capacity")

    participant = Participant(email=email, activity_id=activity.id)
    try:
        db.add(participant)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Student is already signed up or constraint violation")
    except Exception:
        db.rollback()
        raise

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, db: Session = Depends(get_db)):
    """Unregister a student from an activity"""
    activity = db.query(Activity).filter(Activity.name == activity_name).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    participant = db.query(Participant).filter(
        Participant.activity_id == activity.id,
        Participant.email == email
    ).first()

    if not participant:
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    try:
        db.delete(participant)
        db.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}
    except Exception:
        db.rollback()
        raise
