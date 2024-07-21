from typing import Optional

from sqlalchemy import ForeignKey, String, Double
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STRING_LENGTH = 256


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(STRING_LENGTH))
    surname: Mapped[str] = mapped_column(String(STRING_LENGTH))
    lastname: Mapped[str] = mapped_column(String(STRING_LENGTH))
    age: Mapped[int]
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    last_seen: Mapped[Optional[float]] = mapped_column(Double())

    def __repr__(self) -> str:
        return f"Users(id={self.id!r}, name={self.name!r}, surname={self.surname!r}, lastname={self.lastname!r}, department_id={self.department_id!r}, age={self.age!r}), job_id={self.job_id}"


class Events(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    timestamp: Mapped[float] = mapped_column(Double())

    def __repr__(self) -> str:
        return f"Events(id={self.id!r}, user_id={self.user_id!r}, location_id={self.location_id!r}, timestamp={self.timestamp!r})"


class Images(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))    
    path: Mapped[str] = mapped_column(String(STRING_LENGTH))

    def __repr__(self) -> str:
        return f"Images(id={self.id!r}, user_id={self.user_id!r}, path={self.path!r})"


class Locations(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(STRING_LENGTH))

    def __repr__(self) -> str:
        return f"Locations(id={self.id!r}, title={self.title!r})"
    

class Departments(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(STRING_LENGTH))

    def __repr__(self) -> str:
        return f"Departments(id={self.id!r}, title={self.title!r})"


class Jobs(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(STRING_LENGTH))

    def __repr__(self) -> str:
        return f"Jobs(id={self.id!r}, title={self.title!r})"
