import datetime
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "telemetry")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=1,
        max_size=10,
    )
    yield
    if pool:
        await pool.close()


app = FastAPI(
    title="Telemetry API",
    description="Monitoring API for Smart House system",
    lifespan=lifespan,
)


class DeviceReadingResponse(BaseModel):
    id: str
    timestamp: datetime.datetime
    metric_name: str
    metric_value: float


class DeviceReadingsResponse(BaseModel):
    device_id: int
    readings: list[DeviceReadingResponse]
    total: int
    limit: int
    offset: int


class LatestDeviceReadingsResponse(BaseModel):
    device_id: int
    readings: list[DeviceReadingResponse]


def generate_sample_readings(
    device_id: int, count: int = 10
) -> list[DeviceReadingResponse]:
    readings = []
    base_time = datetime.datetime.now(datetime.timezone.utc)
    metrics = ["temperature", "humidity", "pressure", "motion", "light"]

    for i in range(count):
        reading = DeviceReadingResponse(
            id=str(uuid.uuid4()),
            timestamp=base_time - datetime.timedelta(minutes=i * 5),
            metric_name=metrics[i % len(metrics)],
            metric_value=20.0 + (i % 10),
        )
        readings.append(reading)

    return readings


@app.get(
    "/v1/devices/{device_id}/readings", response_model=DeviceReadingsResponse
)
async def get_device_readings(
    device_id: int,
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of readings to return"
    ),
    offset: int = Query(0, ge=0, description="Number of readings to skip"),
):
    """
    Retrieves readings/metrics for a specific device
    """
    if pool is None:
        raise HTTPException(
            status_code=500, detail="Database connection not available"
        )

    async with pool.acquire() as connection:
        device_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM devices WHERE id = $1)", device_id
        )
        if not device_exists:
            raise HTTPException(status_code=404, detail="Device not found")

    sample_readings = generate_sample_readings(device_id, limit)
    return DeviceReadingsResponse(
        device_id=device_id,
        readings=sample_readings,
        total=len(sample_readings),
        limit=limit,
        offset=offset,
    )


@app.get(
    "/v1/devices/{device_id}/readings/latest",
    response_model=LatestDeviceReadingsResponse,
)
async def get_latest_device_readings(device_id: int):
    """
    Retrieves the most recent readings for each metric of a device
    """
    if pool is None:
        raise HTTPException(
            status_code=500, detail="Database connection not available"
        )

    async with pool.acquire() as connection:
        device_exists = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM devices WHERE id = $1)", device_id
        )
        if not device_exists:
            raise HTTPException(status_code=404, detail="Device not found")

    sample_readings = generate_sample_readings(device_id, 5)
    return LatestDeviceReadingsResponse(
        device_id=device_id, readings=sample_readings
    )
