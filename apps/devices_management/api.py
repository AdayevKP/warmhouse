import datetime
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from rabbitmq import rabbitmq_client
from http_client import smart_home_client
from sqlalchemy import (
    ARRAY,
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "devices")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DeviceModel(Base):  # type: ignore
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(Integer, unique=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    description = Column(Text)
    location = Column(String(255))
    connection_info = Column(JSON)
    tags = Column(ARRAY(String))
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await rabbitmq_client.connect()
    yield
    await rabbitmq_client.close()


class DeviceCreateRequest(BaseModel):
    name: str
    type: str
    connection_info: dict
    description: str | None = None
    location: str | None = None
    tags: list[str] | None = None


class DeviceUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    location: str | None = None
    connection_info: dict | None = None
    tags: list[str] | None = None


class DeviceResponse(BaseModel):
    id: int
    name: str
    type: str
    description: str | None = None
    location: str | None = None
    connection_info: dict | None = None
    tags: list[str] | None = None
    created_at: datetime.datetime


class ErrorResponse(BaseModel):
    error: str


app = FastAPI(
    title="Device Management API",
    description="API for device management in the Smart House system",
    lifespan=lifespan,
)


async def publish_device_created_event(device: DeviceModel):
    """Publish device created event to RabbitMQ"""
    device_data = {
        "id": device.id,
        "name": device.name,
        "type": device.type,
        "description": device.description,
        "location": device.location,
        "connection_info": device.connection_info,
        "tags": device.tags,
        "created_at": device.created_at.isoformat()
        if device.created_at
        else None,
    }
    await rabbitmq_client.publish_event("devices.created", device_data)


async def publish_device_updated_event(device: DeviceModel):
    """Publish device updated event to RabbitMQ"""
    device_data = {
        "id": device.id,
        "name": device.name,
        "type": device.type,
        "description": device.description,
        "location": device.location,
        "connection_info": device.connection_info,
        "tags": device.tags,
        "created_at": device.created_at.isoformat()
        if device.created_at
        else None,
    }
    await rabbitmq_client.publish_event("devices.updated", device_data)


async def publish_device_deleted_event(device_id: int):
    """Publish device deleted event to RabbitMQ"""
    device_data = {
        "id": device_id,
        "deletedAt": datetime.datetime.now().isoformat(),
    }
    await rabbitmq_client.publish_event("devices.deleted", device_data)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/v1/devices", response_model=list[DeviceResponse])
async def get_all_devices(
    type: str | None = None,
    location: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Retrieves all devices
    """
    query = db.query(DeviceModel)

    if type:
        query = query.filter(DeviceModel.type == type)

    if location:
        query = query.filter(DeviceModel.location == location)

    devices = query.all()

    return [
        DeviceResponse(
            id=device.id,
            name=device.name,
            type=device.type,
            description=device.description,
            location=device.location,
            connection_info=dict(device.connection_info),
            tags=device.tags,
            created_at=device.created_at,
        )
        for device in devices
    ]


@app.post("/v1/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    device_data: DeviceCreateRequest, db: Session = Depends(get_db)
):
    """
    Registers a new smart device
    """
    if device_data.type == "temperature_sensor":
        resp = await smart_home_client.create_sensor(
            {
                "name": device_data.name,
                "type": "temperature_sensor",
                "location": device_data.location,
                "unit": "C",
            }
        )
        external_id = resp["id"]
    else:
        external_id = None

    device = DeviceModel(
        name=device_data.name,
        type=device_data.type,
        description=device_data.description,
        location=device_data.location,
        connection_info=device_data.connection_info,
        tags=device_data.tags,
        external_id=external_id,
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    await publish_device_created_event(device)

    return DeviceResponse(
        id=device.id,
        name=device.name,
        type=device.type,
        description=device.description,
        location=device.location,
        connection_info=dict(device.connection_info),
        tags=device.tags,
        created_at=device.created_at,
    )


@app.get("/v1/devices/{device_id}", response_model=DeviceResponse)
async def get_device_by_id(device_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a specific device by its ID
    """
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse(
        id=device.id,
        name=device.name,
        type=device.type,
        description=device.description,
        location=device.location,
        connection_info=dict(device.connection_info),
        tags=device.tags,
        created_at=device.created_at,
    )


@app.put("/v1/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    device_data: DeviceUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Updates an existing device
    """
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.type == "temperature_sensor" and device.external_id:
        await smart_home_client.update_sensor(
            device.external_id, 
            {
                'name': device.name,    
                'location': device.location,
            }
        )

    if device_data.name is not None:
        device.name = device_data.name
    if device_data.description is not None:
        device.description = device_data.description
    if device_data.location is not None:
        device.location = device_data.location
    if device_data.connection_info is not None:
        device.connection_info = device_data.connection_info
    if device_data.tags is not None:
        device.tags = device_data.tags

    device.updated_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(device)

    await publish_device_updated_event(device)

    return DeviceResponse(
        id=device.id,
        name=device.name,
        type=device.type,
        description=device.description,
        location=device.location,
        connection_info=dict(device.connection_info),
        tags=device.tags,
        created_at=device.created_at,
    )


@app.delete("/v1/devices/{device_id}", response_model=dict[str, str])
async def delete_device(device_id: int, db: Session = Depends(get_db)):
    """
    Deletes a device
    """
    device = db.query(DeviceModel).filter(DeviceModel.id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.type == "temperature_sensor" and device.external_id:
        await smart_home_client.delete_sensor(
            device.external_id, 
        )

    db.delete(device)
    db.commit()

    await publish_device_deleted_event(device.id)

    return {"message": "Device deleted successfully"}
