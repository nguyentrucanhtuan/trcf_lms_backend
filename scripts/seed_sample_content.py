"""Seed sample content for the public website: course categories, extra
courses, archive (content) categories, and articles.

Idempotent: matches existing rows by slug and updates them. Articles need an
author — uses the first admin user (falls back to the first user).

Run:  uv run python scripts/seed_sample_content.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.database import engine  # noqa: E402
from app.models import (  # noqa: E402
    Archive,
    ArchiveCategory,
    ArchiveStatus,
    Course,
    CourseCategory,
    CourseStatus,
    Lesson,
    PaymentMethod,
    Section,
    User,
    UserRole,
)
from app.utils import utcnow  # noqa: E402

# ---------------------------------------------------------------- categories
COURSE_CATEGORIES = [
    ("Vận hành", "van-hanh", "Set up, quy trình và vận hành quán hằng ngày."),
    ("Barista & Sản phẩm", "barista-san-pham", "Pha chế, định lượng và phát triển đồ uống."),
    ("Tài chính", "tai-chinh", "Dòng tiền, P&L và quản trị chi phí cho quán."),
    ("Nhân sự", "nhan-su", "Tuyển dụng, đào tạo và giữ chân nhân viên."),
    ("Marketing", "marketing", "Thương hiệu, nội dung và giữ chân khách."),
    ("Khởi nghiệp", "khoi-nghiep", "Chuẩn bị trước khi mở quán đầu tiên."),
]

PAYMENT_METHODS = [
    ("vnpay", "Cổng VNPay", "Internet Banking, ATM, QR Code · 40+ ngân hàng"),
    ("momo", "Ví Momo", "Thanh toán bằng ví Momo"),
    ("zalopay", "ZaloPay", "Hoàn 5% giá trị đơn hàng"),
    ("bank", "Chuyển khoản ngân hàng", "Chuyển khoản thủ công, kích hoạt trong 2 giờ"),
]

ARCHIVE_CATEGORIES = [
    ("Vận hành", "van-hanh"),
    ("Tài chính", "tai-chinh"),
    ("Nhân sự", "nhan-su"),
    ("Menu & sản phẩm", "menu-san-pham"),
    ("Marketing", "marketing"),
    ("Case study", "case-study"),
    ("Khởi nghiệp", "khoi-nghiep"),
]

# ------------------------------------------------------------------- courses
# (code, name, slug, category_slug, price, sale_price, description, [(section, [lessons])])
COURSES = [
    (
        "VAN-HANH-201",
        "Vận hành quán cà phê từ A đến Z",
        "van-hanh-quan-ca-phe-a-z",
        "van-hanh",
        3_900_000,
        2_900_000,
        "Lên ý tưởng, set up, vận hành và phát triển một quán cà phê có lãi — chương trình toàn diện cho người sắp mở và chủ quán đang vận hành.",
        [
            ("Định hình ý tưởng & mô hình", ["Phân tích 4 mô hình quán phổ biến", "Khảo sát khu vực & khách", "Định vị thương hiệu trong 1 câu"]),
            ("Mặt bằng & set up", ["Đọc hợp đồng thuê", "Layout quầy bar tối ưu", "Dự toán đầu tư"]),
            ("Vận hành hằng ngày", ["Quy trình mở & đóng ca", "Quản lý kho cơ bản", "Theo dõi doanh thu"]),
        ],
    ),
    (
        "TAI-CHINH-101",
        "Đọc báo cáo P&L cho chủ quán không chuyên",
        "doc-bao-cao-pl-cho-chu-quan",
        "tai-chinh",
        1_800_000,
        None,
        "Dòng tiền hằng ngày, P&L theo tuần, và cách dùng số liệu để ra quyết định nhanh — không cần biết kế toán.",
        [
            ("Nền tảng tài chính quán", ["Doanh thu, chi phí, lợi nhuận", "Dòng tiền vs lợi nhuận"]),
            ("Đọc P&L", ["Cấu trúc một bảng P&L", "5 dòng quan trọng nhất", "Ra quyết định từ số liệu"]),
        ],
    ),
    (
        "NHAN-SU-101",
        "Onboarding 30 ngày: đào tạo barista mới",
        "onboarding-30-ngay-dao-tao-barista",
        "nhan-su",
        1_200_000,
        None,
        "Quy trình tuyển, lộ trình 30 ngày, KPI và cách giữ chân nhân viên giỏi qua mùa cao điểm.",
        [
            ("Tuyển dụng", ["Viết tin tuyển dụng hiệu quả", "Phỏng vấn barista"]),
            ("Lộ trình 30 ngày", ["Tuần 1: làm quen & an toàn", "Tuần 2-3: kỹ năng pha chế", "Tuần 4: đánh giá & KPI"]),
        ],
    ),
    (
        "MKT-101",
        "Marketing cho quán cà phê nhỏ",
        "marketing-cho-quan-ca-phe-nho",
        "marketing",
        1_500_000,
        990_000,
        "Câu chuyện thương hiệu, social hằng tuần, chương trình loyalty đưa khách quay lại lần 3.",
        [
            ("Thương hiệu", ["Câu chuyện thương hiệu", "Bộ nhận diện tối thiểu"]),
            ("Nội dung & loyalty", ["Lịch nội dung 7 ngày", "Chương trình khách quen", "Đo lường hiệu quả"]),
        ],
    ),
    (
        "KHOI-NGHIEP-001",
        "Mở quán cà phê: 6 câu hỏi trước khi bắt đầu",
        "mo-quan-ca-phe-6-cau-hoi",
        "khoi-nghiep",
        0,
        None,
        "Mini-course miễn phí giúp bạn tự đánh giá ý tưởng quán trước khi đầu tư đồng vốn đầu tiên.",
        [
            ("6 câu hỏi quan trọng", ["Vì sao khách chọn bạn?", "Bạn có đủ vốn dự phòng?", "Mặt bằng có phù hợp?"]),
        ],
    ),
]

# ------------------------------------------------------------------ articles
_LONG_CONTENT = """
<p class="lead">Quán đầu tiên vừa có lãi 8 tháng. Khách quen, đội ngũ ổn định, social bắt đầu chạy. Một số chủ quán bắt đầu nghĩ đến chi nhánh thứ hai — và rất nhiều trong số đó <strong>đóng cửa cả hai</strong> sau 12 tháng.</p>
<p>Chúng tôi ngồi xuống với Hà — founder Cà phê Sương Mai (Đà Lạt) — để bóc tách 18 tháng từ quán đầu tiên đến chi nhánh thứ hai.</p>
<h2>Khi nào là "đủ chín" để mở chi nhánh thứ hai?</h2>
<p>Câu trả lời thẳng thắn của Hà: <strong>không phải khi quán bạn đông nhất, mà là khi quán bạn không cần bạn nữa</strong>. Hãy thử nghỉ 14 ngày liên tục — nếu doanh thu và chất lượng vẫn ổn, bạn đã chuẩn hóa thành công.</p>
<blockquote>"Khi tôi đi vắng 2 tuần mà quán vẫn chạy, tôi mới đi tìm mặt bằng thứ hai. Trước đó là cảm tính." — Hà, founder Cà phê Sương Mai</blockquote>
<h2>Những con số cần đọc trước</h2>
<p>Có ba con số Hà luôn nhìn trước khi ký hợp đồng: lợi nhuận liên tục ≥ 6 tháng, dòng tiền dự trữ ≥ 2.5× CAPEX, và tỷ lệ chi phí mặt bằng ≤ 35% doanh thu dự phóng.</p>
<h3>SOP cần có những gì?</h3>
<ul>
<li><strong>Sản phẩm:</strong> định lượng + quy trình pha cho từng món.</li>
<li><strong>Phục vụ:</strong> kịch bản đón khách, xử lý phàn nàn.</li>
<li><strong>Vệ sinh:</strong> checklist mở quán, giữa ca, đóng quán.</li>
<li><strong>Tài chính:</strong> đóng ca thu chi, đối chiếu cuối ngày.</li>
</ul>
<h2>Bài học rút ra</h2>
<p>Mở chi nhánh thứ hai là một bài kiểm tra mức độ <strong>hệ thống</strong> của quán đầu tiên — không phải một bài kiểm tra ý tưởng.</p>
"""

_SHORT_CONTENT = """
<p class="lead">{lead}</p>
<p>Bài viết này tổng hợp những gì áp dụng được ngay cho quán của bạn, dựa trên kinh nghiệm thực tế từ các chủ quán đang vận hành.</p>
<h2>Vấn đề thường gặp</h2>
<p>Phần lớn chủ quán nhỏ gặp khó ở khâu này vì thiếu một quy trình rõ ràng. Dưới đây là cách tiếp cận có hệ thống.</p>
<ul>
<li>Xác định đúng vấn đề trước khi tìm giải pháp.</li>
<li>Đo lường bằng số liệu, không bằng cảm tính.</li>
<li>Thử nghiệm nhỏ trước khi áp dụng toàn quán.</li>
</ul>
<h2>Kết luận</h2>
<p>Bắt đầu từ một thay đổi nhỏ tuần này, đo kết quả, rồi mở rộng. Đó là cách bền vững nhất.</p>
"""

# (title, slug, cat_slug, excerpt, content, read_min, views, days_ago)
ARTICLES = [
    (
        "Mở quán thứ hai sau 18 tháng: bài học từ Cà phê Sương Mai",
        "mo-quan-thu-hai-sau-18-thang",
        "case-study",
        "Khi nào nên mở chi nhánh thứ hai, làm sao để chi nhánh mới không kéo lùi chi nhánh đầu tiên, và những con số bạn cần đọc được trước khi ký mặt bằng tiếp theo.",
        _LONG_CONTENT,
        12, 3400, 9,
    ),
    (
        "Quán bạn đang lỗ ở đâu? Đọc P&L trong 5 phút",
        "quan-ban-dang-lo-o-dau-doc-pl",
        "tai-chinh",
        "Khung 5 dòng đơn giản để biết tháng vừa rồi quán bạn lời hay lỗ — không cần kế toán.",
        _SHORT_CONTENT.format(lead="Nhiều chủ quán không biết quán mình lời hay lỗ cho đến cuối quý. Đây là khung đọc P&L trong 5 phút."),
        8, 5200, 11,
    ),
    (
        "4 lý do khiến barista nghỉ trong 90 ngày đầu",
        "4-ly-do-barista-nghi-trong-90-ngay",
        "nhan-su",
        "Onboarding không rõ ràng, ca làm kiệt sức, không có lộ trình lên — và cách khắc phục.",
        _SHORT_CONTENT.format(lead="Tỷ lệ nghỉ việc cao trong 90 ngày đầu là dấu hiệu của vấn đề onboarding, không phải của nhân viên."),
        6, 3800, 15,
    ),
    (
        "Định lượng menu mùa hè: 12 món bán chạy theo nhiệt độ",
        "dinh-luong-menu-mua-he-12-mon",
        "menu-san-pham",
        "Khi trời nóng, hành vi gọi món đổi rất nhanh. Đây là cách 3 quán đã điều chỉnh menu trong 2 tuần.",
        _SHORT_CONTENT.format(lead="Nhiệt độ tăng 5°C có thể đổi hoàn toàn cơ cấu món bán ra. Hãy chuẩn bị menu mùa hè từ sớm."),
        9, 2600, 19,
    ),
    (
        "Quán nhỏ, social nhỏ: lịch nội dung 7 ngày cho 1 người",
        "lich-noi-dung-7-ngay-cho-1-nguoi",
        "marketing",
        "Bạn không có team. Đây là lịch 7 ngày, mỗi ngày 1 bài, ai cũng làm được — kèm template caption sẵn dùng.",
        _SHORT_CONTENT.format(lead="Không cần team marketing. Một người vẫn chạy được social đều đặn nếu có lịch nội dung rõ ràng."),
        7, 4100, 23,
    ),
    (
        "SOP & chuẩn hóa khi mở chi nhánh thứ 2",
        "sop-chuan-hoa-khi-mo-chi-nhanh-2",
        "van-hanh",
        "5 nhóm SOP tối thiểu và cách viết tài liệu mà nhân viên thực sự đọc — không phải chỉ đặt cho có.",
        _SHORT_CONTENT.format(lead="SOP không phải là tài liệu để cho có. Đây là 5 nhóm SOP tối thiểu và cách viết để nhân viên thực sự dùng."),
        10, 2900, 25,
    ),
    (
        "Mở quán cà phê 200 triệu: chi tiết từng đồng đầu tư",
        "mo-quan-ca-phe-200-trieu",
        "khoi-nghiep",
        "Bảng chi phí thực tế cho quán take-away 20m². Đầy đủ từ mặt bằng, máy, đến marketing 3 tháng đầu.",
        _SHORT_CONTENT.format(lead="200 triệu có đủ mở quán không? Đây là bảng chi phí chi tiết từng đồng cho một quán take-away."),
        11, 6100, 28,
    ),
    (
        "Mức lương barista 2026: dữ liệu từ 180 quán Việt Nam",
        "muc-luong-barista-2026",
        "nhan-su",
        "Tổng hợp lương cứng, thưởng theo doanh thu, chế độ làm thêm — 3 vùng TP. HCM, Hà Nội, Đà Nẵng.",
        _SHORT_CONTENT.format(lead="Trả lương bao nhiêu là hợp lý? Dữ liệu từ 180 quán cho bạn một mốc tham chiếu thực tế."),
        8, 4700, 33,
    ),
]


def _get_or_create_category(session, model, name, slug, description=None):
    cat = session.exec(select(model).where(model.slug == slug)).first()
    if cat is None:
        cat = model(name=name, slug=slug, description=description)
        session.add(cat)
    else:
        cat.name = name
        if description is not None:
            cat.description = description
        cat.updated_at = utcnow()
    return cat


def seed() -> None:
    with Session(engine) as session:
        # ---- author for articles ----
        author = session.exec(
            select(User).where(User.role == UserRole.admin)
        ).first() or session.exec(select(User)).first()
        if author is None:
            raise SystemExit("No user found — create an admin first.")

        # ---- payment methods ----
        for i, (code, name, desc) in enumerate(PAYMENT_METHODS):
            pm = session.exec(
                select(PaymentMethod).where(PaymentMethod.code == code)
            ).first()
            if pm is None:
                pm = PaymentMethod(code=code)
            pm.name = name
            pm.description = desc
            pm.is_active = True
            pm.display_order = i
            session.add(pm)
        session.commit()

        # ---- course categories ----
        course_cats: dict[str, CourseCategory] = {}
        for i, (name, slug, desc) in enumerate(COURSE_CATEGORIES):
            cat = _get_or_create_category(session, CourseCategory, name, slug, desc)
            cat.display_order = i
            cat.is_active = True
            course_cats[slug] = cat
        session.commit()
        for cat in course_cats.values():
            session.refresh(cat)

        # ---- archive (content) categories ----
        archive_cats: dict[str, ArchiveCategory] = {}
        for i, (name, slug) in enumerate(ARCHIVE_CATEGORIES):
            cat = _get_or_create_category(session, ArchiveCategory, name, slug)
            cat.display_order = i
            cat.is_active = True
            archive_cats[slug] = cat
        session.commit()
        for cat in archive_cats.values():
            session.refresh(cat)

        # ---- courses ----
        n_courses = 0
        for code, name, slug, cat_slug, price, sale, desc, sections in COURSES:
            course = session.exec(select(Course).where(Course.slug == slug)).first()
            if course is None:
                course = Course(course_code=code, slug=slug)
            course.name = name
            course.description = desc
            course.status = CourseStatus.published
            course.price = price
            course.sale_price = sale
            course.categories = [course_cats[cat_slug]]
            course.updated_at = utcnow()
            session.add(course)
            session.commit()
            session.refresh(course)

            # reset curriculum
            for l in session.exec(select(Lesson).where(Lesson.course_id == course.id)).all():
                session.delete(l)
            for s in session.exec(select(Section).where(Section.course_id == course.id)).all():
                session.delete(s)
            session.commit()
            for s_pos, (s_title, lessons) in enumerate(sections):
                section = Section(course_id=course.id, title=s_title, position=s_pos)
                session.add(section)
                session.commit()
                session.refresh(section)
                for l_pos, l_title in enumerate(lessons):
                    session.add(Lesson(
                        course_id=course.id, section_id=section.id, title=l_title,
                        duration_minutes=10 + l_pos * 4, position=l_pos,
                        is_preview=(s_pos == 0 and l_pos == 0), is_published=True,
                    ))
            session.commit()
            n_courses += 1

        # ---- articles ----
        now = datetime.now(timezone.utc)
        n_articles = 0
        for title, slug, cat_slug, excerpt, content, read_min, views, days_ago in ARTICLES:
            art = session.exec(select(Archive).where(Archive.slug == slug)).first()
            if art is None:
                art = Archive(slug=slug, author_id=author.id)
            art.title = title
            art.excerpt = excerpt
            art.content = content.strip()
            art.status = ArchiveStatus.published
            art.published_at = now - timedelta(days=days_ago)
            art.archive_category_id = archive_cats[cat_slug].id
            art.author_id = author.id
            art.view_count = views
            art.updated_at = utcnow()
            session.add(art)
            n_articles += 1
        session.commit()

        print(f"Payment methods:   {len(PAYMENT_METHODS)}")
        print(f"Course categories: {len(course_cats)}")
        print(f"Archive categories: {len(archive_cats)}")
        print(f"Courses upserted:  {n_courses}")
        print(f"Articles upserted: {n_articles}")
        print(f"Article author:    {author.email}")


if __name__ == "__main__":
    seed()
