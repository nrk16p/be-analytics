from pydantic import BaseModel, field_validator
from datetime import date, datetime, timezone, timedelta
from typing import Optional

class DrivingDistanceBase(BaseModel):
    plate_number: str
    truck_number: str
    gps_vendor: str
    date: date
    distance: float
    created_at: Optional[datetime] = None

    # 🕒 Convert naive DB timestamp → UTC → Bangkok (+7)
    @field_validator("created_at", mode="before")
    @classmethod
    def convert_to_bangkok(cls, value):
        if isinstance(value, datetime):
            # If DB timestamp has no tzinfo (naive), assume it’s stored as UTC
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            bangkok_tz = timezone(timedelta(hours=7))
            return value.astimezone(bangkok_tz)
        return value

    class Config:
        orm_mode = True


class DrivingDistanceOut(DrivingDistanceBase):
    pass


class DrivingDistanceCreate(DrivingDistanceBase):
    pass
