"""Data Service Layer Mocking for Vexere

As this should already exist, this implementation is for design purposes only.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Data Service Layer", version="0.1.0")

# Fake in-memory data stores (replicate real data in production)
ORDERS = [
    {"order_id": 1, "user_id": 10, "status": "pending", "trip_id": 111, "departure_time": "2025-09-10T10:00:00"},
    {"order_id": 2, "user_id": 10, "status": "completed", "trip_id": 112, "departure_time": "2025-09-01T08:00:00"},
    {"order_id": 3, "user_id": 11, "status": "pending", "trip_id": 113, "departure_time": "2025-09-11T12:30:00"}
]

TRIPS = [
    {"route_id": "HCM-HN", "trip_id": 111, "operator": "Xe123", "depart": "2025-09-10T10:00:00"},
    {"route_id": "HCM-HN", "trip_id": 112, "operator": "Xe123", "depart": "2025-09-12T09:00:00"},
    {"route_id": "HCM-DN", "trip_id": 113, "operator": "Xe456", "depart": "2025-09-11T12:30:00"}
]

COMPLAINTS = []

class UpdateOrderTimeRequest(BaseModel):
    order_id: int
    new_time: str


class ComplaintResponse(BaseModel):
    order_id: int
    complaint: str
# These API endpoints should be there at the first place (optimized, documented),
# these endpoint are just for demonstration purposes

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/orders/{user_id}/pending")
def get_pending_orders(user_id: int):
    return [o for o in ORDERS if o["user_id"] == user_id and o["status"] == "pending"]

@app.get("/trips/{route_id}")
def get_trips(route_id: str):
    return [t for t in TRIPS if t["route_id"] == route_id]

@app.post("/orders/update_time")
def update_order_time(req: UpdateOrderTimeRequest):
    for o in ORDERS:
        if o["order_id"] == req.order_id:
            o["departure_time"] = req.new_time
            return {"updated": True, "order": o}
    raise HTTPException(status_code=404, detail="Order not found")

@app.delete("/orders/{order_id}")
def delete_order(order_id: int):
    for o in ORDERS:
        if o["order_id"] == order_id:
            ORDERS.remove(o)
            return {"deleted": True, "order_id": order_id}
    raise HTTPException(status_code=404, detail="Order not found")

@app.post("/complaint/{order_id}")
def create_complaint(order_id: int, complaint: str):
    for o in ORDERS:
        if o["order_id"] == order_id:
            # Here you would normally save the complaint to a database
            return ComplaintResponse(order_id=order_id, complaint=complaint)
    raise HTTPException(status_code=404, detail="Order not found")
