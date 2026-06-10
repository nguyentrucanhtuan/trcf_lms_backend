from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

import json

from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.utils import utcnow

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class UserRole(str, Enum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


class StudentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    graduated = "graduated"


class CourseStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class EnrollmentStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"
    completed = "completed"


class VideoType(str, Enum):
    """How a lesson's video_url should be interpreted by the player.

    ``auto`` detects the provider from the URL; the others force a provider
    so the player builds the correct embed even for unusual URL formats.
    """

    auto = "auto"
    youtube = "youtube"
    vimeo = "vimeo"
    drive = "drive"
    file = "file"


class PaymentStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"
    cancelled = "cancelled"


class CouponType(str, Enum):
    percent = "percent"
    fixed = "fixed"


class UserBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True, max_length=255)
    role: UserRole = UserRole.student
    is_active: bool = True


class User(UserBase, table=True):
    __tablename__ = "user"
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str = Field(max_length=255)
    password_changed_at: datetime | None = None
    token_version: int = Field(default=0)
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=255)


class UserUpdate(SQLModel):
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=255)


class UserPublic(UserBase):
    id: int
    email_verified_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StudentBase(SQLModel):
    student_code: str = Field(index=True, unique=True, max_length=32)
    full_name: str = Field(max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    gender: Gender = Gender.other
    address: str | None = Field(default=None, max_length=500)
    status: StudentStatus = StudentStatus.active
    enrollment_date: date | None = None


class Student(StudentBase, table=True):
    __tablename__ = "student"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StudentCreate(StudentBase):
    user_id: int


class StudentUpdate(SQLModel):
    student_code: str | None = None
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    address: str | None = None
    status: StudentStatus | None = None
    enrollment_date: date | None = None


class StudentPublic(StudentBase):
    id: int
    user_id: int
    # Email of the linked login account (User). Joined in the students router.
    email: str | None = None
    created_at: datetime
    updated_at: datetime


class CourseCategoryLink(SQLModel, table=True):
    __tablename__ = "course_category_link"
    course_id: int | None = Field(
        default=None, foreign_key="course.id", primary_key=True
    )
    course_category_id: int | None = Field(
        default=None, foreign_key="course_category.id", primary_key=True
    )


class CourseCategoryBase(SQLModel):
    name: str = Field(max_length=255)
    slug: str = Field(index=True, unique=True, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    display_order: int = 0
    is_active: bool = True
    thumbnail_url: str | None = Field(default=None, max_length=500)


class CourseCategory(CourseCategoryBase, table=True):
    __tablename__ = "course_category"
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    courses: list["Course"] = Relationship(
        back_populates="categories", link_model=CourseCategoryLink
    )


class CourseCategoryCreate(SQLModel):
    name: str = Field(max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    display_order: int = 0
    is_active: bool = True
    thumbnail_url: str | None = Field(default=None, max_length=500)


class CourseCategoryUpdate(SQLModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    display_order: int | None = None
    is_active: bool | None = None
    thumbnail_url: str | None = None


class CourseCategoryPublic(CourseCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime


class CourseCategoryBrief(SQLModel):
    id: int
    name: str
    slug: str
    thumbnail_url: str | None = None


class CourseBase(SQLModel):
    course_code: str = Field(index=True, unique=True, max_length=64)
    name: str = Field(max_length=255)
    slug: str = Field(index=True, unique=True, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)
    status: CourseStatus = CourseStatus.draft
    price: int = Field(default=0, ge=0)
    sale_price: int | None = Field(default=None, ge=0)


class Course(CourseBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    categories: list[CourseCategory] = Relationship(
        back_populates="courses", link_model=CourseCategoryLink
    )
    sections: list["Section"] = Relationship(back_populates="course")
    lessons: list["Lesson"] = Relationship(back_populates="course")


class CourseCreate(SQLModel):
    course_code: str = Field(max_length=64)
    name: str = Field(max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)
    status: CourseStatus = CourseStatus.draft
    price: int = Field(default=0, ge=0)
    sale_price: int | None = Field(default=None, ge=0)
    category_ids: list[int] | None = None


class CourseUpdate(SQLModel):
    course_code: str | None = None
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    content: str | None = None
    thumbnail_url: str | None = None
    status: CourseStatus | None = None
    price: int | None = Field(default=None, ge=0)
    sale_price: int | None = Field(default=None, ge=0)
    category_ids: list[int] | None = None


class CoursePublic(CourseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    categories: list[CourseCategoryBrief] = []


class SectionBase(SQLModel):
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    position: int = 0


class Section(SectionBase, table=True):
    __tablename__ = "section"
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    course: Course = Relationship(back_populates="sections")
    lessons: list["Lesson"] = Relationship(back_populates="section")


class SectionCreate(SectionBase):
    course_id: int


class SectionUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    position: int | None = None


class SectionPublic(SectionBase):
    id: int
    course_id: int
    created_at: datetime
    updated_at: datetime


class LessonBase(SQLModel):
    title: str = Field(max_length=255)
    content: str | None = None
    video_url: str | None = Field(default=None, max_length=1000)
    video_type: VideoType = VideoType.auto
    duration_minutes: int | None = Field(default=None, ge=0)
    position: int = 0
    is_preview: bool = False
    is_published: bool = True


class Lesson(LessonBase, table=True):
    __tablename__ = "lesson"
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    section_id: int | None = Field(
        default=None, foreign_key="section.id", index=True
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    course: Course = Relationship(back_populates="lessons")
    section: Section | None = Relationship(back_populates="lessons")


class LessonCreate(LessonBase):
    course_id: int
    section_id: int | None = None


class LessonUpdate(SQLModel):
    title: str | None = None
    content: str | None = None
    video_url: str | None = None
    video_type: VideoType | None = None
    duration_minutes: int | None = None
    position: int | None = None
    is_preview: bool | None = None
    is_published: bool | None = None
    section_id: int | None = None


class LessonPublic(LessonBase):
    id: int
    course_id: int
    section_id: int | None
    created_at: datetime
    updated_at: datetime


class LessonBrief(SQLModel):
    id: int
    title: str
    position: int
    duration_minutes: int | None = None
    is_preview: bool
    is_published: bool


class SectionWithLessons(SectionPublic):
    lessons: list[LessonBrief] = []


class CourseDetail(CoursePublic):
    sections: list[SectionWithLessons] = []
    lessons: list[LessonBrief] = []


class EnrollmentBase(SQLModel):
    status: EnrollmentStatus = EnrollmentStatus.active
    enrolled_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None


class Enrollment(EnrollmentBase, table=True):
    __tablename__ = "enrollment"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
    )
    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class EnrollmentCreate(EnrollmentBase):
    student_id: int
    course_id: int


class EnrollmentUpdate(SQLModel):
    status: EnrollmentStatus | None = None
    expires_at: datetime | None = None


class EnrollmentPublic(EnrollmentBase):
    id: int
    student_id: int
    course_id: int
    created_at: datetime
    updated_at: datetime


class PaymentMethodBase(SQLModel):
    code: str = Field(index=True, unique=True, max_length=64)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    display_order: int = 0


class PaymentMethod(PaymentMethodBase, table=True):
    __tablename__ = "payment_method"
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PaymentMethodCreate(PaymentMethodBase):
    pass


class PaymentMethodUpdate(SQLModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


class PaymentMethodPublic(PaymentMethodBase):
    id: int
    created_at: datetime
    updated_at: datetime


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"
    __table_args__ = (
        UniqueConstraint("order_id", "course_id", name="uq_order_item_order_course"),
    )
    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    unit_price: int = Field(ge=0)
    order: "Order" = Relationship(back_populates="items")


class OrderItemCreate(SQLModel):
    course_id: int


class OrderItemPublic(SQLModel):
    id: int
    order_id: int
    course_id: int
    unit_price: int


class OrderBase(SQLModel):
    notes: str | None = Field(default=None, max_length=1000)


class Order(OrderBase, table=True):
    __tablename__ = "order"
    id: int | None = Field(default=None, primary_key=True)
    order_code: str = Field(index=True, unique=True, max_length=64)
    student_id: int = Field(foreign_key="student.id", index=True)
    payment_method_id: int = Field(foreign_key="payment_method.id", index=True)
    payment_status: PaymentStatus = Field(default=PaymentStatus.pending, index=True)
    subtotal_amount: int = Field(default=0, ge=0)
    discount_amount: int = Field(default=0, ge=0)
    total_amount: int = Field(default=0, ge=0)
    coupon_id: int | None = Field(default=None, foreign_key="coupon.id", index=True)
    provider_txn_id: str | None = Field(default=None, max_length=255)
    provider_payload: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    paid_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    items: list[OrderItem] = Relationship(back_populates="order")


class OrderCreate(OrderBase):
    student_id: int
    payment_method_id: int
    items: list[OrderItemCreate] = Field(min_length=1)
    coupon_code: str | None = None


MAX_PROVIDER_PAYLOAD_BYTES = 16 * 1024


class OrderUpdate(SQLModel):
    payment_method_id: int | None = None
    payment_status: PaymentStatus | None = None
    provider_txn_id: str | None = None
    provider_payload: dict[str, Any] | None = None
    notes: str | None = None

    @field_validator("provider_payload")
    @classmethod
    def _cap_payload(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return v
        size = len(json.dumps(v, default=str).encode("utf-8"))
        if size > MAX_PROVIDER_PAYLOAD_BYTES:
            raise ValueError(
                f"provider_payload exceeds {MAX_PROVIDER_PAYLOAD_BYTES} bytes (got {size})"
            )
        return v


class OrderPublic(OrderBase):
    id: int
    order_code: str
    student_id: int
    payment_method_id: int
    payment_status: PaymentStatus
    subtotal_amount: int
    discount_amount: int
    total_amount: int
    coupon_id: int | None
    provider_txn_id: str | None
    provider_payload: dict[str, Any] | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemPublic] = []


class LessonProgressBase(SQLModel):
    seconds_watched: int = Field(default=0, ge=0)


class LessonProgress(LessonProgressBase, table=True):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),
    )
    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    lesson_id: int = Field(foreign_key="lesson.id", index=True)
    completed_at: datetime | None = None
    last_seen_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class LessonProgressUpsert(LessonProgressBase):
    student_id: int
    lesson_id: int
    mark_completed: bool = False


class LessonProgressPublic(LessonProgressBase):
    id: int
    student_id: int
    lesson_id: int
    completed_at: datetime | None
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class ArchiveCategoryBase(SQLModel):
    name: str = Field(max_length=255)
    slug: str = Field(index=True, unique=True, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    display_order: int = 0
    is_active: bool = True
    thumbnail_url: str | None = Field(default=None, max_length=500)


class ArchiveCategory(ArchiveCategoryBase, table=True):
    __tablename__ = "archive_category"
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ArchiveCategoryCreate(SQLModel):
    name: str = Field(max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    display_order: int = 0
    is_active: bool = True
    thumbnail_url: str | None = Field(default=None, max_length=500)


class ArchiveCategoryUpdate(SQLModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    display_order: int | None = None
    is_active: bool | None = None
    thumbnail_url: str | None = None


class ArchiveCategoryPublic(ArchiveCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ArchiveStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class ArchiveBase(SQLModel):
    title: str = Field(max_length=255)
    slug: str = Field(index=True, unique=True, max_length=255)
    excerpt: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)
    status: ArchiveStatus = ArchiveStatus.draft
    published_at: datetime | None = None


class Archive(ArchiveBase, table=True):
    __tablename__ = "archive"
    id: int | None = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="user.id", index=True)
    archive_category_id: int | None = Field(
        default=None, foreign_key="archive_category.id", index=True
    )
    view_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ArchiveCreate(SQLModel):
    title: str = Field(max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    excerpt: str | None = Field(default=None, max_length=1000)
    content: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)
    status: ArchiveStatus = ArchiveStatus.draft
    published_at: datetime | None = None
    author_id: int
    archive_category_id: int | None = None


class ArchiveUpdate(SQLModel):
    title: str | None = None
    slug: str | None = None
    excerpt: str | None = None
    content: str | None = None
    thumbnail_url: str | None = None
    status: ArchiveStatus | None = None
    published_at: datetime | None = None
    archive_category_id: int | None = None


class ArchivePublic(ArchiveBase):
    id: int
    author_id: int
    archive_category_id: int | None
    view_count: int
    created_at: datetime
    updated_at: datetime


class CouponBase(SQLModel):
    code: str = Field(index=True, unique=True, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    discount_type: CouponType
    discount_value: int = Field(ge=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    is_active: bool = True


class Coupon(CouponBase, table=True):
    __tablename__ = "coupon"
    id: int | None = Field(default=None, primary_key=True)
    used_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CouponCreate(CouponBase):
    pass


class CouponUpdate(SQLModel):
    code: str | None = None
    description: str | None = None
    discount_type: CouponType | None = None
    discount_value: int | None = Field(default=None, ge=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_uses: int | None = None
    is_active: bool | None = None


class CouponPublic(CouponBase):
    id: int
    used_count: int
    created_at: datetime
    updated_at: datetime


class ReviewBase(SQLModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=255)
    comment: str | None = Field(default=None, max_length=2000)
    is_published: bool = True


class Review(ReviewBase, table=True):
    __tablename__ = "review"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_review_student_course"),
    )
    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ReviewCreate(ReviewBase):
    student_id: int
    course_id: int


class ReviewUpdate(SQLModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = None
    comment: str | None = None
    is_published: bool | None = None


class ReviewPublic(ReviewBase):
    id: int
    student_id: int
    course_id: int
    created_at: datetime
    updated_at: datetime


class CertificateBase(SQLModel):
    notes: str | None = Field(default=None, max_length=500)


class Certificate(CertificateBase, table=True):
    __tablename__ = "certificate"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_certificate_student_course"),
    )
    id: int | None = Field(default=None, primary_key=True)
    certificate_code: str = Field(index=True, unique=True, max_length=64)
    student_id: int = Field(foreign_key="student.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    issued_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CertificateCreate(CertificateBase):
    student_id: int
    course_id: int


class CertificatePublic(CertificateBase):
    id: int
    certificate_code: str
    student_id: int
    course_id: int
    issued_at: datetime
    created_at: datetime
    updated_at: datetime
