from datetime import datetime

from app.models import SystemHealthHourlyBase, SystemHealthRawBase


class SystemHealthRawRead(SystemHealthRawBase):
    sys_health_id: int
    created_at: datetime


class SystemHealthHourlyRead(SystemHealthHourlyBase):
    hourly_sys_health_id: int
    created_at_hour: datetime
