from sqlmodel import Session, select
from app.core.db import engine
from app.models import Camera

with Session(engine) as session:
    # Check if we already have a camera
    if not session.exec(select(Camera)).first():
        cam = Camera(camera_name="Ayala Highway Cam", channel_id=1)
        session.add(cam)
        session.commit()
        print("✅ Dummy camera seeded successfully!")
    else:
        print("Camera already exists.")