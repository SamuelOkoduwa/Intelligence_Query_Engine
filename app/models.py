from datetime import datetime, timezone
from uuid6 import uuid7
from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid7()))
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    gender: Mapped[str] = mapped_column(String, nullable=False)
    gender_probability: Mapped[float] = mapped_column(Float, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    age_group: Mapped[str] = mapped_column(String, nullable=False)
    country_id: Mapped[str] = mapped_column(String(2), nullable=False)
    country_name: Mapped[str] = mapped_column(String, nullable=False)
    country_probability: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


Index("ix_profiles_gender", Profile.gender)
Index("ix_profiles_age_group", Profile.age_group)
Index("ix_profiles_country_id", Profile.country_id)
Index("ix_profiles_age", Profile.age)
Index("ix_profiles_gender_probability", Profile.gender_probability)
Index("ix_profiles_country_probability", Profile.country_probability)
Index("ix_profiles_created_at", Profile.created_at)
