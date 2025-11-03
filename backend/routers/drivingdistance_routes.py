from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import date, timedelta, timezone
from pydantic import BaseModel
import logging

from ..models.drivingdistance import DrivingDistance
from ..schemas.drivingdistance import DrivingDistanceCreate, DrivingDistanceOut
from ..database import get_db
from ..auth import verify_token

router = APIRouter(
    prefix="/drivingdistance",
    tags=["drivingdistance"],
    dependencies=[Depends(verify_token)]
)

# 🧭 Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drivingdistance")

# ✅ Define Bangkok timezone
BKK_TZ = timezone(timedelta(hours=7))


# ============================================================================
# 🧱 DB Dependency Wrapper
# ============================================================================
def get_main_db():
    yield from get_db("DB_MAIN")


# ============================================================================
# 🧱 BULK INSERT ENDPOINT
# ============================================================================
@router.post("/bulk", response_model=List[DrivingDistanceOut])
def create_large_bulk_records(
    payload: List[DrivingDistanceCreate],
    db: Session = Depends(get_main_db),
):
    total = len(payload)
    if total == 0:
        raise HTTPException(status_code=400, detail="No records provided.")

    logger.info(f"🚚 Starting bulk insert of {total} records...")

    batch_size = 2000
    inserted_records = []

    try:
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch = payload[start:end]
            logger.info(f"🧩 Inserting records {start + 1} to {end}...")

            records = [DrivingDistance(**r.dict()) for r in batch]
            db.bulk_save_objects(records)
            db.commit()

            last_batch = (
                db.query(DrivingDistance)
                .order_by(DrivingDistance.id.desc())
                .limit(len(batch))
                .all()
            )
            inserted_records = last_batch + inserted_records

        logger.info(f"✅ Bulk insert completed: {total} records.")
        return list(reversed(inserted_records))

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Bulk insert failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database insert failed: {e}")


# ============================================================================
# 🔍 FILTER MODEL
# ============================================================================
class DrivingDistanceFilter(BaseModel):
    plate_number: Optional[List[str]] = None
    start_at: Optional[date] = None
    end_at: Optional[date] = None
    limit: int = 500


# ============================================================================
# 🔍 POST FILTER ENDPOINT
# ============================================================================
@router.post("/filter", response_model=List[DrivingDistanceOut])
def filter_driving_distance(
    payload: DrivingDistanceFilter,
    db: Session = Depends(get_main_db),
):
    logger.info(f"📥 Payload filter: {payload}")

    query = db.query(DrivingDistance)
    filters = []

    if payload.plate_number:
        filters.append(DrivingDistance.plate_number.in_(payload.plate_number))
    if payload.start_at and payload.end_at:
        filters.append(and_(DrivingDistance.date >= payload.start_at, DrivingDistance.date <= payload.end_at))
    elif payload.start_at:
        filters.append(DrivingDistance.date >= payload.start_at)
    elif payload.end_at:
        filters.append(DrivingDistance.date <= payload.end_at)

    if filters:
        query = query.filter(*filters)

    records = query.order_by(DrivingDistance.date.asc()).limit(payload.limit).all()
    if not records:
        raise HTTPException(status_code=404, detail="No matching records found")

    for record in records:
        if record.created_at:
            record.created_at = record.created_at.replace(tzinfo=timezone.utc).astimezone(BKK_TZ)

    logger.info(f"✅ Found {len(records)} records.")
    return records


# ============================================================================
# 🌐 GET FILTER ENDPOINT
# ============================================================================
@router.get("/", response_model=List[DrivingDistanceOut])
def get_driving_distance_records(
    plate_number: Optional[List[str]] = Query(None),
    start_at: Optional[date] = Query(None),
    end_at: Optional[date] = Query(None),
    limit: int = Query(500),
    db: Session = Depends(get_main_db),
):
    logger.info(f"📥 Query - plates: {plate_number}, start: {start_at}, end: {end_at}")

    query = db.query(DrivingDistance)
    filters = []

    if plate_number:
        filters.append(DrivingDistance.plate_number.in_(plate_number))
    if start_at and end_at:
        filters.append(and_(DrivingDistance.date >= start_at, DrivingDistance.date <= end_at))
    elif start_at:
        filters.append(DrivingDistance.date >= start_at)
    elif end_at:
        filters.append(DrivingDistance.date <= end_at)

    if filters:
        query = query.filter(*filters)

    records = query.order_by(DrivingDistance.date.asc()).limit(limit).all()
    if not records:
        raise HTTPException(status_code=404, detail="No matching records found")

    for record in records:
        if record.created_at:
            record.created_at = record.created_at.replace(tzinfo=timezone.utc).astimezone(BKK_TZ)

    logger.info(f"✅ Found {len(records)} records.")
    return records


# ============================================================================
# 📊 SUMMARIZE DISTANCE ENDPOINT
# ============================================================================
@router.post("/sumdistance")
def summarize_distance(
    payload: DrivingDistanceFilter,
    db: Session = Depends(get_main_db),
):
    logger.info(f"📊 Summarizing distance for: {payload.plate_number}, period: {payload.start_at} → {payload.end_at}")

    query = db.query(
        DrivingDistance.plate_number.label("plate_number"),
        func.sum(DrivingDistance.distance).label("total_distance")
    )

    filters = []
    if payload.plate_number:
        filters.append(DrivingDistance.plate_number.in_(payload.plate_number))
    if payload.start_at and payload.end_at:
        filters.append(and_(DrivingDistance.date >= payload.start_at, DrivingDistance.date <= payload.end_at))
    elif payload.start_at:
        filters.append(DrivingDistance.date >= payload.start_at)
    elif payload.end_at:
        filters.append(DrivingDistance.date <= payload.end_at)

    if filters:
        query = query.filter(*filters)

    results = query.group_by(DrivingDistance.plate_number).order_by(DrivingDistance.plate_number.asc()).all()
    if not results:
        raise HTTPException(status_code=404, detail="No records found for summary")

    summary = [
        {
            "plate_number": r.plate_number,
            "total_distance": float(r.total_distance or 0),
            "start_at": payload.start_at,
            "end_at": payload.end_at,
        }
        for r in results
    ]

    logger.info(f"✅ Summary generated for {len(summary)} plates.")
    return {"period": f"{payload.start_at} → {payload.end_at}", "summary": summary}


# ============================================================================
# 🚚 GET UNIQUE PLATES
# ============================================================================
@router.get("/platenumber")
def get_unique_plate_numbers(
    db: Session = Depends(get_main_db),
):
    logger.info("📋 Fetching unique plate numbers...")

    try:
        plates = (
            db.query(DrivingDistance.plate_number)
            .distinct()
            .order_by(DrivingDistance.plate_number.asc())
            .all()
        )

        unique_plates = [p[0] for p in plates if p[0]]

        if not unique_plates:
            raise HTTPException(status_code=404, detail="No plate numbers found")

        logger.info(f"✅ Found {len(unique_plates)} unique plate numbers.")
        return {"count": len(unique_plates), "plates": unique_plates}

    except Exception as e:
        logger.error(f"❌ Failed to fetch plate numbers: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving plate numbers: {e}")
