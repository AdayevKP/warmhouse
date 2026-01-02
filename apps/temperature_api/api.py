import datetime
import random
from fastapi import FastAPI
import pydantic

app = FastAPI()


def _get_sensor_temperature() -> float:
    temperature = random.uniform(5.0, 40.0)
    return round(temperature, 2)


class TemperatureResponse(pydantic.BaseModel):
    value: float
    unit: str
    timestamp: datetime.datetime
    location: str
    status: str
    sensor_id: str
    sensor_type: str
    description: str


@app.get("/temperature")
async def get_temperature_by_location(location: str) -> TemperatureResponse:
    match location:
        case "Living Room":
            sensor_id = "1"
        case "Bedroom":
            sensor_id = "2"
        case "Kitchen":
            sensor_id = "3"
        case _:
            sensor_id = "0"

    return TemperatureResponse(
        value=_get_sensor_temperature(),
        unit="°C",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        location=location,
        status="active",
        sensor_id=sensor_id,
        sensor_type="thermometer",
        description="Indoor temperature sensor",
    )


@app.get("/temperature/{sensor_id}")
async def get_temperature_by_sesnor(sensor_id: str) -> TemperatureResponse:
    match sensor_id:
        case "1":
            location = "Living Room"
        case "2":
            location = "Bedroom"
        case "3":
            location = "Kitchen"
        case _:
            location = "Unknown"

    return TemperatureResponse(
        value=_get_sensor_temperature(),
        unit="°C",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        location=location,
        status="active",
        sensor_id=sensor_id,
        sensor_type="thermometer",
        description="Indoor temperature sensor",
    )
