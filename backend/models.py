from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# The life of a parcel, in order
PARCEL_STATUSES = [
    "booked",       # sender created it, got the QR label
    "dropped_off",  # scanned in at the origin box / station
    "matched",      # assigned to a bus departure
    "loaded",       # driver/agent scanned it onto the bus
    "in_transit",   # bus departed
    "arrived",      # scanned at destination box
    "collected",    # receiver picked it up with their code -> credits are issued
]


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(20))  # sender | driver | agent | admin
    business_name: Mapped[str | None] = mapped_column(String(160))


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    origin_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    destination_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    distance_km: Mapped[float] = mapped_column(Float)

    origin: Mapped[Station] = relationship(foreign_keys=[origin_id])
    destination: Mapped[Station] = relationship(foreign_keys=[destination_id])


class Departure(Base):
    __tablename__ = "departures"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"))
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrives_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity_kg: Mapped[float] = mapped_column(Float)  # free luggage space declared by the operator
    booked_kg: Mapped[float] = mapped_column(Float, default=0)

    route: Mapped[Route] = relationship()
    operator: Mapped[Operator] = relationship()


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # printed on the QR label, e.g. GL-482913
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    receiver_name: Mapped[str] = mapped_column(String(120))
    receiver_phone: Mapped[str] = mapped_column(String(32))
    origin_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    destination_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    weight_kg: Mapped[float] = mapped_column(Float)
    size: Mapped[str] = mapped_column(String(2))  # S | M | L
    content_type: Mapped[str] = mapped_column(String(40))
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="booked")
    departure_id: Mapped[int | None] = mapped_column(ForeignKey("departures.id"))
    pickup_code: Mapped[str] = mapped_column(String(8))  # one-time code the receiver uses
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sender: Mapped[User] = relationship()
    origin: Mapped[Station] = relationship(foreign_keys=[origin_id])
    destination: Mapped[Station] = relationship(foreign_keys=[destination_id])
    departure: Mapped[Departure | None] = relationship()
    events: Mapped[list["ParcelEvent"]] = relationship(
        back_populates="parcel", order_by="ParcelEvent.created_at"
    )


class ParcelEvent(Base):
    """One row per scan / status change = the chain of custody."""

    __tablename__ = "parcel_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"))
    status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    parcel: Mapped[Parcel] = relationship(back_populates="events")


class CreditEntry(Base):
    """Ledger: credits are only ever added/subtracted by rows here (auditable)."""

    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey("parcels.id"))
    entry_type: Mapped[str] = mapped_column(String(10))  # earn | redeem
    co2_avoided_kg: Mapped[float] = mapped_column(Float, default=0)
    credits: Mapped[int] = mapped_column(Integer)  # positive for earn, negative for redeem
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """Simulated SMS/Viber/WhatsApp messages, shown in an in-app log for the demo."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey("parcels.id"))
    recipient_phone: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(12), default="sms")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
