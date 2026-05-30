"""Seed a rich sample course (barista / pha chế) for the public landing page.

Idempotent: re-running updates the existing course (matched by slug) instead of
creating duplicates. The `content` column stores a JSON blob with the rich
landing-page fields (outcomes, instructor, reviews, FAQ, ...) that don't have
dedicated table columns.

Run:  uv run python scripts/seed_sample_course.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.database import engine  # noqa: E402
from app.models import (  # noqa: E402
    Course,
    CourseCategory,
    CourseStatus,
    Lesson,
    Section,
)
from app.utils import utcnow  # noqa: E402

SLUG = "lam-chu-ky-nang-pha-che"

CONTENT = {
    "eyebrow": "Khóa học bán chạy · Khai giảng hàng tháng",
    "level": "Cơ bản đến nâng cao",
    "language": "Tiếng Việt",
    "promo_duration": "2:45",
    "stats": [
        {"num": "4.200+", "label": "Học viên đã tham gia"},
        {"num": "120+", "label": "Công thức đồ uống"},
        {"num": "18", "label": "Chuyên gia chia sẻ"},
        {"num": "4.9 / 5", "label": "Đánh giá trung bình"},
    ],
    "outcomes": [
        {
            "icon": "coffee",
            "title": "Chiết xuất espresso chuẩn",
            "desc": "Hiểu tỉ lệ, độ mịn, lực nén và thời gian để có shot espresso ổn định mỗi lần.",
        },
        {
            "icon": "local_cafe",
            "title": "Đánh sữa & latte art",
            "desc": "Tạo microfoam mịn và thành thạo 8 mẫu latte art cơ bản dùng được trên line.",
        },
        {
            "icon": "blender",
            "title": "Đồ uống hiện đại",
            "desc": "Pha chế trà trái cây, đá xay, cold brew và các món signature theo mùa.",
        },
        {
            "icon": "science",
            "title": "Định lượng & công thức",
            "desc": "Chuẩn hóa công thức, tính cost từng ly và xây menu theo phân khúc khách.",
        },
        {
            "icon": "checklist",
            "title": "Quy trình quầy bar",
            "desc": "Set up quầy, vệ sinh dụng cụ và vận hành mượt trong giờ cao điểm.",
        },
        {
            "icon": "workspace_premium",
            "title": "Sẵn sàng đi làm",
            "desc": "Kỹ năng và sự tự tin để ứng tuyển vị trí barista hoặc mở quầy của riêng bạn.",
        },
    ],
    "requirements": [
        "Không cần kinh nghiệm pha chế trước đó — khóa học bắt đầu từ con số 0.",
        "Một máy pha hoặc dụng cụ pha thủ công (V60, French press) để thực hành.",
        "Tinh thần luyện tập đều đặn: mỗi bài kèm bài tập áp dụng ngay.",
    ],
    "audiences": [
        "Người muốn trở thành barista chuyên nghiệp.",
        "Chủ quán / sắp mở quán muốn tự chuẩn hóa menu và đào tạo nhân viên.",
        "Người yêu cà phê muốn pha ngon tại nhà.",
    ],
    "instructor": {
        "name": "Lê Quang Vinh",
        "role": "Head Barista · CoffeeTree · Vô địch Latte Art miền Nam 2022",
        "bio": [
            "Vinh có 10 năm đứng máy tại các quán specialty ở TP. HCM và Đà Lạt, "
            "đào tạo hơn 600 barista và là giám khảo nhiều cuộc thi pha chế khu vực.",
            "\"Pha chế ngon không phải năng khiếu — đó là quy trình lặp lại đúng. "
            "Khóa học đưa ra quy trình, việc của bạn là luyện tập.\"",
        ],
        "creds": [
            {"icon": "verified", "text": "Chứng chỉ SCA Barista Skills — Foundation + Intermediate."},
            {"icon": "emoji_events", "text": "Vô địch Latte Art Throwdown khu vực phía Nam 2022."},
            {"icon": "school", "text": "Giảng viên khách mời tại Vietnam Barista Camp 2023–2024."},
        ],
    },
    "reviews": [
        {
            "rating": 5,
            "text": "Mình từ tay ngang, sau 6 tuần đã xin được việc barista ở quán specialty. Phần đánh sữa và latte art cực kỳ chi tiết.",
            "name": "Nguyễn Thị Hà",
            "role": "Barista · Quận 7",
        },
        {
            "rating": 5,
            "text": "Học để chuẩn hóa menu cho quán mình. Phần định lượng & tính cost giúp mình tăng margin mà khách không nhận ra giá đổi.",
            "name": "Trần Minh Hoàng",
            "role": "Chủ Cà phê Sương Mai · Đà Lạt",
        },
        {
            "rating": 5,
            "text": "Giảng viên chữa bài tận tình, mỗi video quay cận tay rất dễ làm theo. Đáng tiền hơn nhiều khóa offline mình từng học.",
            "name": "Phạm Mai Anh",
            "role": "Học viên · Hà Nội",
        },
    ],
    "includes": [
        "38 bài học · hơn 12 giờ video",
        "Công thức & worksheet định lượng",
        "Cộng đồng học viên riêng",
        "Q&A trực tiếp hàng tháng",
        "Chứng chỉ hoàn thành",
        "Truy cập trọn đời",
    ],
    "faqs": [
        {
            "q": "Tôi chưa biết gì về pha chế, có theo được không?",
            "a": "Hoàn toàn được. Khóa học bắt đầu từ kiến thức nền tảng nhất về cà phê và dụng cụ, rồi mới nâng dần. Bạn không cần kinh nghiệm trước đó.",
        },
        {
            "q": "Tôi không có máy pha espresso thì sao?",
            "a": "Bạn vẫn học được phần lớn nội dung với dụng cụ pha thủ công. Các bài về espresso có hướng dẫn lựa chọn máy ở nhiều tầm giá để bạn thực hành khi sẵn sàng.",
        },
        {
            "q": "Khóa học có giúp tôi đi xin việc barista không?",
            "a": "Có. Module cuối tập trung vào quy trình quầy bar thực tế và mẹo phỏng vấn, kèm chứng chỉ hoàn thành để bạn đưa vào hồ sơ.",
        },
        {
            "q": "Tôi có được truy cập trọn đời không?",
            "a": "Có. Sau khi đăng ký, bạn xem lại không giới hạn và nhận mọi cập nhật nội dung trong tương lai miễn phí.",
        },
    ],
}

# (section title, description, [(lesson title, minutes, is_preview), ...])
CURRICULUM = [
    (
        "Nhập môn: cà phê & dụng cụ",
        "Hiểu về hạt, rang xay và làm quen bộ dụng cụ của một barista.",
        [
            ("Tổng quan thế giới cà phê specialty", 14, True),
            ("Phân biệt hạt, mức rang và hương vị", 18, True),
            ("Bộ dụng cụ barista cần có", 12, False),
            ("Vệ sinh & bảo quản dụng cụ", 10, False),
        ],
    ),
    (
        "Chiết xuất espresso",
        "Làm chủ shot espresso ổn định — nền tảng của mọi món cà phê.",
        [
            ("Nguyên lý chiết xuất & các biến số", 16, False),
            ("Chỉnh cối xay và độ mịn", 15, False),
            ("Nén (tamping) đúng kỹ thuật", 12, False),
            ("Đọc và sửa shot lỗi (chua / đắng)", 20, False),
            ("Thực hành: 10 shot liên tiếp ổn định", 18, False),
        ],
    ),
    (
        "Sữa & Latte Art",
        "Đánh microfoam mịn và tạo hình nghệ thuật trên ly.",
        [
            ("Chọn sữa & nguyên lý tạo bọt", 13, False),
            ("Kỹ thuật đánh microfoam", 17, False),
            ("Rót cơ bản: trái tim & tulip", 19, False),
            ("Rót nâng cao: rosetta & swan", 22, False),
        ],
    ),
    (
        "Đồ uống hiện đại & signature",
        "Mở rộng menu ngoài cà phê nóng truyền thống.",
        [
            ("Cold brew & cà phê lạnh", 15, False),
            ("Trà trái cây & đá xay", 16, False),
            ("Xây dựng món signature theo mùa", 18, False),
        ],
    ),
    (
        "Định lượng, công thức & menu",
        "Chuẩn hóa công thức và xây menu có lãi.",
        [
            ("Chuẩn hóa công thức & tỉ lệ", 14, False),
            ("Tính cost từng ly đồ uống", 16, False),
            ("Thiết kế menu theo phân khúc", 15, False),
            ("Worksheet: bảng định lượng quán", 10, False),
        ],
    ),
    (
        "Vận hành quầy bar & đi làm",
        "Quy trình quầy bar thực tế và sẵn sàng cho công việc.",
        [
            ("Set up quầy đầu ca", 12, False),
            ("Vận hành mượt giờ cao điểm", 17, False),
            ("Mẹo phỏng vấn vị trí barista", 13, False),
            ("Lộ trình phát triển nghề barista", 11, False),
        ],
    ),
]


def seed() -> None:
    with Session(engine) as session:
        # Category
        cat = session.exec(
            select(CourseCategory).where(CourseCategory.slug == "barista-san-pham")
        ).first()
        if cat is None:
            cat = CourseCategory(
                name="Barista & Sản phẩm",
                slug="barista-san-pham",
                description="Khóa học pha chế và phát triển sản phẩm đồ uống.",
            )
            session.add(cat)
            session.commit()
            session.refresh(cat)

        course = session.exec(select(Course).where(Course.slug == SLUG)).first()
        created = course is None
        if course is None:
            course = Course(course_code="PHA-CHE-101", slug=SLUG)

        course.name = "Làm chủ kỹ năng pha chế: Cà phê & đồ uống hiện đại"
        course.description = (
            "Từ tay ngang đến barista tự tin: chiết xuất espresso, đánh sữa & latte art, "
            "đồ uống hiện đại, định lượng và vận hành quầy bar — học theo nhịp của bạn, "
            "thực hành ngay trên từng bài."
        )
        course.content = json.dumps(CONTENT, ensure_ascii=False)
        course.thumbnail_url = None
        course.status = CourseStatus.published
        course.price = 1_990_000
        course.sale_price = 1_290_000
        course.updated_at = utcnow()
        course.categories = [cat]
        session.add(course)
        session.commit()
        session.refresh(course)

        # Reset curriculum so re-runs stay clean.
        for lesson in session.exec(
            select(Lesson).where(Lesson.course_id == course.id)
        ).all():
            session.delete(lesson)
        for section in session.exec(
            select(Section).where(Section.course_id == course.id)
        ).all():
            session.delete(section)
        session.commit()

        for s_pos, (title, desc, lessons) in enumerate(CURRICULUM):
            section = Section(
                course_id=course.id,
                title=title,
                description=desc,
                position=s_pos,
            )
            session.add(section)
            session.commit()
            session.refresh(section)
            for l_pos, (l_title, minutes, preview) in enumerate(lessons):
                session.add(
                    Lesson(
                        course_id=course.id,
                        section_id=section.id,
                        title=l_title,
                        duration_minutes=minutes,
                        position=l_pos,
                        is_preview=preview,
                        is_published=True,
                    )
                )
        session.commit()

        action = "Created" if created else "Updated"
        print(f"{action} course id={course.id} slug={course.slug}")
        print(f"  sections={len(CURRICULUM)} "
              f"lessons={sum(len(c[2]) for c in CURRICULUM)}")


if __name__ == "__main__":
    seed()
