from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship

# -----------------------------------------
# 1. USER MANAGEMENT (RBAC) - Table 4.0
# -----------------------------------------
class UserBase(SQLModel):
    username: str = Field(unique=True, index=True)
    first_name: str
    last_name: str
    role: str

class User(UserBase, table=True):
    user_id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # sa_column_kwargs ensures SQLite auto-updates this timestamp whenever the row is modified
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)}
    )
    password_changed_at: Optional[datetime] = Field(default=None)
    last_login: Optional[datetime] = Field(default=None)

    # Relationships
    verified_detections: list["DetectionLog"] = Relationship(
        back_populates="verified_by", 
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.verified_by_id"}
    )
    closed_detections: list["DetectionLog"] = Relationship(
        back_populates="closed_by", 
        sa_relationship_kwargs={"foreign_keys": "DetectionLog.closed_by_id"}
    )

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    password_changed_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class UserUpdate(SQLModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserUpdatePassword(SQLModel):
    old_password: str
    new_password: str

class UserResetPassword(SQLModel):
    new_password: str

# -----------------------------------------
# 2. CAMERA MANAGEMENT - Table 5.0
# -----------------------------------------
class CameraBase(SQLModel):
    camera_name: str = Field(unique=True)
    channel_id: int = Field(unique=True)

class Camera(CameraBase, table=True):
    camera_id: Optional[int] = Field(default=None, primary_key=True)
    connection_status: str = Field(default="Disconnected") 
    ai_status: str = Field(default="Inactive") 
    is_enabled: bool = Field(default=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)}
    )

    # Relationships
    detections: list["DetectionLog"] = Relationship(back_populates="camera")

class CameraCreate(CameraBase):
    pass

class CameraRead(CameraBase):
    camera_id: int
    connection_status: str
    ai_status: str
    is_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

class CameraUpdate(SQLModel):
    camera_name: Optional[str] = None
    channel_id: Optional[int] = None
    is_enabled: Optional[bool] = None
    is_active: Optional[bool] = None

# ==========================================
# 3. DETECTION LOGS (HITL Workflow) - Table 6.0
# ==========================================
class DetectionLogBase(SQLModel):
    camera_id: int = Field(foreign_key="camera.camera_id", index=True)
    detected_at: datetime
    snapshot_path: str
    confidence_score: float

class DetectionLog(DetectionLogBase, table=True):
    log_id: Optional[int] = Field(default=None, primary_key=True)
    
    # We redeclare detected_at here to tell SQLite to index it
    detected_at: datetime = Field(index=True) 
    
    detection_status: str = Field(default="Unverified", index=True) 
    
    # Audit Trail
    verified_by_id: Optional[int] = Field(default=None, foreign_key="user.user_id")
    verified_at: Optional[datetime] = Field(default=None)
    closed_by_id: Optional[int] = Field(default=None, foreign_key="user.user_id")
    closed_at: Optional[datetime] = Field(default=None)

    # Relationships
    camera: Optional[Camera] = Relationship(back_populates="detections")
    verified_by: Optional[User] = Relationship(
        back_populates="verified_detections", 
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.verified_by_id]"}
    )
    closed_by: Optional[User] = Relationship(
        back_populates="closed_detections", 
        sa_relationship_kwargs={"foreign_keys": "[DetectionLog.closed_by_id]"}
    )

class DetectionLogCreate(DetectionLogBase):
    pass 

class DetectionLogRead(DetectionLogBase):
    log_id: int
    detection_status: str
    verified_by_id: Optional[int] = None
    verified_at: Optional[datetime] = None
    closed_by_id: Optional[int] = None
    closed_at: Optional[datetime] = None


# -----------------------------------------
# 4. SYSTEM HEALTH RAW - Table 7.0
# -----------------------------------------
class SystemHealthRawBase(SQLModel):
    cpu_usage: float
    gpu_usage: float
    ram_usage: float
    gpu_temperature: float

class SystemHealthRaw(SystemHealthRawBase, table=True):
    sys_health_id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

class SystemHealthRawRead(SystemHealthRawBase):
    sys_health_id: int
    created_at: datetime

# -----------------------------------------
# 5. SYSTEM HEALTH HOURLY - Table 8.0
# -----------------------------------------
class SystemHealthHourlyBase(SQLModel):
    avg_cpu_usage: float
    avg_gpu_usage: float
    avg_ram_usage: float
    peak_gpu_temp: float

class SystemHealthHourly(SystemHealthHourlyBase, table=True):
    hourly_sys_health_id: Optional[int] = Field(default=None, primary_key=True)
    created_at_hour: datetime = Field(unique=True, index=True)

class SystemHealthHourlyRead(SystemHealthHourlyBase):
    hourly_sys_health_id: int
    created_at_hour: datetime
