from datetime import datetime

from app.models import SysHealthHourlyBase, SysHealthRawBase


class SysHealthRawRead(SysHealthRawBase):
    sys_health_id: int
    created_at: datetime


class SysHealthHourlyRead(SysHealthHourlyBase):
    hourly_id: int
    hour_start: datetime
    sample_count: int
