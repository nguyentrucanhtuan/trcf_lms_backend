"""Full smoke test for TRCF LMS API.

Usage:
    rm -f lms.db
    uv run fastapi dev --port 8765 &
    uv run python scripts/smoke_test.py
"""
import sqlite3
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8765"
DB_PATH = Path(__file__).resolve().parent.parent / "lms.db"
client = httpx.Client(base_url=BASE, timeout=10.0)

PASS, FAIL = 0, 0
failures: list[str] = []


def check(label: str, response: httpx.Response, expected: int, *, body_contains: str | None = None) -> bool:
    global PASS, FAIL
    ok = response.status_code == expected
    if ok and body_contains:
        ok = body_contains in response.text
    icon = "✓" if ok else "✗"
    print(f"  {icon} {label:55s} → {response.status_code} (want {expected})")
    if ok:
        PASS += 1
        return True
    FAIL += 1
    snippet = response.text[:120].replace("\n", " ")
    failures.append(f"{label}: HTTP {response.status_code} != {expected} | body: {snippet}")
    return False


def section(name: str) -> None:
    print(f"\n══ {name} ══")


def main() -> int:
    section("0. Bootstrap")
    r = client.get("/health")
    check("GET /health", r, 200)

    # Public registration as student → user 1
    r = client.post(
        "/auth/register",
        json={"email": "admin@trcf.vn", "password": "AdminPw123", "full_name": "Admin"},
    )
    check("POST /auth/register admin user", r, 201)
    # Manually promote to admin via direct DB (simulating ops bootstrap)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE user SET role='admin' WHERE id=1")
    conn.commit()
    conn.close()

    r = client.post(
        "/auth/register",
        json={"email": "alice@trcf.vn", "password": "AlicePw123", "full_name": "Alice"},
    )
    check("POST /auth/register student alice", r, 201)
    r = client.post(
        "/auth/register",
        json={"email": "bob@trcf.vn", "password": "BobPw12345", "full_name": "Bob"},
    )
    check("POST /auth/register student bob", r, 201)

    # Simulate clicked-verify links for alice + bob so VerifiedUserDep-gated routes work
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE user SET email_verified_at=CURRENT_TIMESTAMP WHERE id IN (2,3)")
    conn.commit()
    conn.close()

    # Logins (within /auth/login 5/min limit — careful)
    r = client.post("/auth/login", json={"email": "admin@trcf.vn", "password": "AdminPw123"})
    check("POST /auth/login admin", r, 200)
    admin_token = r.json()["access_token"]
    admin_refresh = r.json()["refresh_token"]

    r = client.post("/auth/login", json={"email": "alice@trcf.vn", "password": "AlicePw123"})
    check("POST /auth/login alice", r, 200)
    alice_token = r.json()["access_token"]

    r = client.post("/auth/login", json={"email": "bob@trcf.vn", "password": "BobPw12345"})
    check("POST /auth/login bob", r, 200)
    bob_token = r.json()["access_token"]

    H_ADMIN = {"Authorization": f"Bearer {admin_token}"}
    H_ALICE = {"Authorization": f"Bearer {alice_token}"}
    H_BOB = {"Authorization": f"Bearer {bob_token}"}

    section("1. /auth")
    check("POST /auth/login wrong password", client.post("/auth/login", json={"email": "alice@trcf.vn", "password": "wrong"}), 401)
    check("GET /auth/me as admin", client.get("/auth/me", headers=H_ADMIN), 200)
    check("GET /auth/me no token", client.get("/auth/me"), 401)
    check("POST /auth/refresh valid", client.post("/auth/refresh", json={"refresh_token": admin_refresh}), 200)
    check("POST /auth/refresh with access token", client.post("/auth/refresh", json={"refresh_token": admin_token}), 401)
    check("POST /auth/logout as admin", client.post("/auth/logout", headers=H_ADMIN), 204)
    # logout bumps token_version, so the cached admin_token is now invalid
    check("GET /auth/me after logout", client.get("/auth/me", headers=H_ADMIN), 401)
    r = client.post("/auth/login", json={"email": "admin@trcf.vn", "password": "AdminPw123"})
    admin_token = r.json()["access_token"]
    admin_refresh = r.json()["refresh_token"]
    H_ADMIN = {"Authorization": f"Bearer {admin_token}"}
    check("POST /auth/email-verify/request", client.post("/auth/email-verify/request", json={"email": "alice@trcf.vn"}), 204)
    check("POST /auth/email-verify/request unknown", client.post("/auth/email-verify/request", json={"email": "nobody@x.vn"}), 204)
    check("POST /auth/email-verify/confirm bad token", client.post("/auth/email-verify/confirm", json={"token": "bad"}), 401)
    check("POST /auth/password-reset/request", client.post("/auth/password-reset/request", json={"email": "alice@trcf.vn"}), 204)
    check("POST /auth/password-reset/confirm bad token", client.post("/auth/password-reset/confirm", json={"token": "bad", "new_password": "NewPass123"}), 401)

    section("2. /users (admin only)")
    check("GET /users/ no auth", client.get("/users/"), 401)
    check("GET /users/ as student", client.get("/users/", headers=H_ALICE), 403)
    check("GET /users/ as admin", client.get("/users/", headers=H_ADMIN), 200)
    check("GET /users/1 as admin", client.get("/users/1", headers=H_ADMIN), 200)
    r = client.post("/users/", json={"email": "teacher@trcf.vn", "password": "TeachPw123", "role": "teacher"}, headers=H_ADMIN)
    check("POST /users/ (teacher) as admin", r, 201)
    teacher_id = r.json()["id"]
    check("PATCH /users/{id} as admin", client.patch(f"/users/{teacher_id}", json={"is_active": False}, headers=H_ADMIN), 200)
    check("POST /users/ duplicate email", client.post("/users/", json={"email": "alice@trcf.vn", "password": "x12345678"}, headers=H_ADMIN), 409)
    check("DELETE /users/{teacher_id}", client.delete(f"/users/{teacher_id}", headers=H_ADMIN), 204)
    check("DELETE /users/1 (admin has student) → 409", client.delete("/users/1", headers=H_ADMIN), 409)

    section("3. /students")
    check("GET /students/ as student → 403", client.get("/students/", headers=H_ALICE), 403)
    check("GET /students/ as admin", client.get("/students/", headers=H_ADMIN), 200)
    check("GET /students/2 self (alice)", client.get("/students/2", headers=H_ALICE), 200)
    check("GET /students/3 other → 403", client.get("/students/3", headers=H_ALICE), 403)
    check("GET /students/3 as admin", client.get("/students/3", headers=H_ADMIN), 200)
    check("PATCH /students/2 as admin", client.patch("/students/2", json={"phone": "0901"}, headers=H_ADMIN), 200)

    section("4. /course-categories")
    check("GET /course-categories/ public", client.get("/course-categories/"), 200)
    check("POST /course-categories/ anon → 401", client.post("/course-categories/", json={"name": "X"}), 401)
    r = client.post("/course-categories/", json={"name": "Barista"}, headers=H_ADMIN)
    check("POST /course-categories/ admin", r, 201)
    cat_id = r.json()["id"]
    check("GET /course-categories/slug/barista", client.get("/course-categories/slug/barista"), 200)
    check("PATCH /course-categories/{id} admin", client.patch(f"/course-categories/{cat_id}", json={"display_order": 5}, headers=H_ADMIN), 200)

    section("5. /courses")
    check("GET /courses/ public", client.get("/courses/"), 200)
    r = client.post(
        "/courses/",
        json={"course_code": "BAR-01", "name": "Barista 101", "price": 2000000, "category_ids": [cat_id], "status": "published"},
        headers=H_ADMIN,
    )
    check("POST /courses/ admin with category", r, 201)
    course_id = r.json()["id"]
    check("POST /courses/ as student → 403", client.post("/courses/", json={"course_code": "X", "name": "X"}, headers=H_ALICE), 403)
    check("GET /courses/{id} public (tree)", client.get(f"/courses/{course_id}"), 200)
    check("GET /courses/slug/barista-101", client.get("/courses/slug/barista-101"), 200)
    check("GET /courses/?category_id filter", client.get(f"/courses/?category_id={cat_id}"), 200)
    check("PATCH /courses/{id}", client.patch(f"/courses/{course_id}", json={"sale_price": 1500000}, headers=H_ADMIN), 200)

    section("6. /sections + /lessons")
    r = client.post("/sections/", json={"course_id": course_id, "title": "Chương 1", "position": 1}, headers=H_ADMIN)
    check("POST /sections/", r, 201)
    section_id_ = r.json()["id"]
    r = client.post("/lessons/", json={"course_id": course_id, "section_id": section_id_, "title": "L1", "duration_minutes": 10}, headers=H_ADMIN)
    check("POST /lessons/ in section", r, 201)
    lesson1_id = r.json()["id"]
    r = client.post("/lessons/", json={"course_id": course_id, "section_id": section_id_, "title": "L2", "duration_minutes": 15}, headers=H_ADMIN)
    check("POST /lessons/ second", r, 201)
    lesson2_id = r.json()["id"]
    r = client.post("/lessons/", json={"course_id": course_id, "title": "Loose", "duration_minutes": 5}, headers=H_ADMIN)
    check("POST /lessons/ no section (loose)", r, 201)
    check("GET /sections/?course_id", client.get(f"/sections/?course_id={course_id}"), 200)
    check("GET /lessons/?course_id&no_section=true", client.get(f"/lessons/?course_id={course_id}&no_section=true"), 200)
    check("POST /lessons/ cross-course section → 422", client.post("/lessons/", json={"course_id": 999, "section_id": section_id_, "title": "X"}, headers=H_ADMIN), 422)

    section("7. /payment-methods")
    check("GET /payment-methods/ public", client.get("/payment-methods/"), 200)
    r = client.post("/payment-methods/", json={"code": "momo", "name": "Ví MoMo"}, headers=H_ADMIN)
    check("POST /payment-methods/", r, 201)
    pm_id = r.json()["id"]
    check("POST /payment-methods/ as student → 403", client.post("/payment-methods/", json={"code": "x", "name": "x"}, headers=H_ALICE), 403)

    section("8. /coupons")
    r = client.post("/coupons/", json={"code": "BARISTA25", "discount_type": "percent", "discount_value": 25, "max_uses": 5}, headers=H_ADMIN)
    check("POST /coupons/ percent 25", r, 201)
    check("POST /coupons/ percent>100 → 422", client.post("/coupons/", json={"code": "BAD", "discount_type": "percent", "discount_value": 150}, headers=H_ADMIN), 422)
    check("POST /coupons/validate", client.post("/coupons/validate", params={"code": "BARISTA25", "subtotal": 1000000}), 200)
    check("POST /coupons/validate unknown → 422", client.post("/coupons/validate", params={"code": "NOPE", "subtotal": 1000}), 422)
    check("GET /coupons/ as student → 403", client.get("/coupons/", headers=H_ALICE), 403)

    section("9. /orders")
    r = client.post(
        "/orders/",
        json={
            "student_id": 2,  # alice
            "payment_method_id": pm_id,
            "items": [{"course_id": course_id, "unit_price": 2000000}],
            "coupon_code": "BARISTA25",
        },
        headers=H_ALICE,
    )
    check("POST /orders/ as alice with coupon", r, 201)
    order_id = r.json()["id"]
    order_code = r.json()["order_code"]
    if r.status_code == 201:
        body = r.json()
        ok = body["subtotal_amount"] == 2000000 and body["discount_amount"] == 500000 and body["total_amount"] == 1500000
        print(f"  {'✓' if ok else '✗'} {'order amounts (subtotal/discount/total)':55s} → {body['subtotal_amount']}/{body['discount_amount']}/{body['total_amount']}")
        if ok:
            globals()["PASS"] += 1
        else:
            globals()["FAIL"] += 1
            failures.append(f"order amounts mismatch: {body}")
    check("POST /orders/ alice for bob → 403", client.post("/orders/", json={"student_id": 3, "payment_method_id": pm_id, "items": [{"course_id": course_id, "unit_price": 1000}]}, headers=H_ALICE), 403)
    check("GET /orders/ alice (forced filter)", client.get("/orders/", headers=H_ALICE), 200)
    check("GET /orders/{id} alice self", client.get(f"/orders/{order_id}", headers=H_ALICE), 200)
    check("GET /orders/{id} bob other → 403", client.get(f"/orders/{order_id}", headers=H_BOB), 403)
    check(f"GET /orders/code/{{code}}", client.get(f"/orders/code/{order_code}", headers=H_ALICE), 200)
    check("POST /orders/{id}/mark-paid as alice → 403", client.post(f"/orders/{order_id}/mark-paid", headers=H_ALICE), 403)
    check("POST /orders/{id}/mark-paid as admin", client.post(f"/orders/{order_id}/mark-paid", headers=H_ADMIN), 200)

    section("10. /enrollments (auto-created by mark-paid)")
    r = client.get("/enrollments/", headers=H_ALICE)
    check("GET /enrollments/ alice (forced self)", r, 200)
    if r.status_code == 200 and r.json()["total"] >= 1:
        print(f"  ✓ enrollment auto-created for alice/course {course_id}")
        globals()["PASS"] += 1
    else:
        print(f"  ✗ alice has no auto-enrollment after mark-paid")
        globals()["FAIL"] += 1
        failures.append("alice missing auto-enrollment")
    check("GET /enrollments/students/2/courses alice self", client.get("/enrollments/students/2/courses", headers=H_ALICE), 200)
    check("GET /enrollments/students/3/courses alice → 403", client.get("/enrollments/students/3/courses", headers=H_ALICE), 403)
    check("GET /enrollments/courses/{id}/students alice → 403", client.get(f"/enrollments/courses/{course_id}/students", headers=H_ALICE), 403)
    check("GET /enrollments/courses/{id}/students admin", client.get(f"/enrollments/courses/{course_id}/students", headers=H_ADMIN), 200)
    check("POST /enrollments/ admin manual", client.post("/enrollments/", json={"student_id": 3, "course_id": course_id}, headers=H_ADMIN), 201)

    section("11. /lesson-progress")
    r = client.post("/lesson-progress/", json={"student_id": 2, "lesson_id": lesson1_id, "seconds_watched": 600, "mark_completed": True}, headers=H_ALICE)
    check("POST /lesson-progress/ alice on lesson1", r, 200)
    check("POST /lesson-progress/ alice for bob → 403", client.post("/lesson-progress/", json={"student_id": 3, "lesson_id": lesson1_id, "seconds_watched": 100}, headers=H_ALICE), 403)
    check("GET /lesson-progress/?student_id=2 alice self", client.get("/lesson-progress/?student_id=2", headers=H_ALICE), 200)
    check("GET /lesson-progress/?student_id=3 alice → 403", client.get("/lesson-progress/?student_id=3", headers=H_ALICE), 403)
    check("GET /lesson-progress/students/2/courses/{id}/summary", client.get(f"/lesson-progress/students/2/courses/{course_id}/summary", headers=H_ALICE), 200)

    section("12. /reviews")
    # Create a 2nd course for the "not enrolled" test (bob has manual enrollment in course1)
    r = client.post("/courses/", json={"course_code": "OTHER", "name": "Other"}, headers=H_ADMIN)
    other_course_id = r.json()["id"]
    r = client.post("/reviews/", json={"student_id": 2, "course_id": course_id, "rating": 5, "title": "Hay!", "comment": "Tốt"}, headers=H_ALICE)
    check("POST /reviews/ alice (enrolled)", r, 201)
    check("POST /reviews/ duplicate → 409", client.post("/reviews/", json={"student_id": 2, "course_id": course_id, "rating": 3}, headers=H_ALICE), 409)
    check("POST /reviews/ bob not-enrolled (course2) → 403", client.post("/reviews/", json={"student_id": 3, "course_id": other_course_id, "rating": 5}, headers=H_BOB), 403)
    check("GET /reviews/?course_id public", client.get(f"/reviews/?course_id={course_id}"), 200)

    section("13. /certificates")
    check("POST auto-issue without complete → 409", client.post(f"/certificates/auto-issue/students/2/courses/{course_id}", headers=H_ALICE), 409)
    r = client.post("/lesson-progress/", json={"student_id": 2, "lesson_id": lesson2_id, "seconds_watched": 900, "mark_completed": True}, headers=H_ALICE)
    # Need lesson 3 (loose) too — let me complete it
    client.post("/lesson-progress/", json={"student_id": 2, "lesson_id": 3, "seconds_watched": 300, "mark_completed": True}, headers=H_ALICE)
    r = client.post(f"/certificates/auto-issue/students/2/courses/{course_id}", headers=H_ALICE)
    check("POST auto-issue after complete", r, 200)
    cert_code = r.json().get("certificate_code")
    if cert_code:
        check(f"GET /certificates/code/{{code}} public", client.get(f"/certificates/code/{cert_code}"), 200)
    check("POST auto-issue idempotent", client.post(f"/certificates/auto-issue/students/2/courses/{course_id}", headers=H_ALICE), 200)
    check("POST /certificates/ admin duplicate → 409", client.post("/certificates/", json={"student_id": 2, "course_id": course_id}, headers=H_ADMIN), 409)

    section("14. /archives + /archive-categories")
    r = client.post("/archive-categories/", json={"name": "Tin tức"}, headers=H_ADMIN)
    check("POST /archive-categories/", r, 201)
    arc_cat_id = r.json()["id"]
    r = client.post("/archives/", json={"title": "Bài viết test", "author_id": 1, "archive_category_id": arc_cat_id, "status": "published"}, headers=H_ADMIN)
    check("POST /archives/ published", r, 201)
    archive_id = r.json()["id"]
    check("GET /archives/ public", client.get("/archives/"), 200)
    check("GET /archives/{id} public", client.get(f"/archives/{archive_id}"), 200)
    check("PATCH /archives/{id} admin", client.patch(f"/archives/{archive_id}", json={"excerpt": "Tóm tắt"}, headers=H_ADMIN), 200)
    check("DELETE /archive-categories with archives → 409", client.delete(f"/archive-categories/{arc_cat_id}", headers=H_ADMIN), 409)

    section("15. /uploads")
    check("POST /uploads/ no auth → 401", client.post("/uploads/", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")}), 401)
    check("POST /uploads/ as student → 403", client.post("/uploads/", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")}, headers=H_ALICE), 403)
    check("POST /uploads/ .txt → 400", client.post("/uploads/", files={"file": ("a.txt", b"hi", "text/plain")}, headers=H_ADMIN), 400)
    r = client.post("/uploads/", files={"file": ("a.png", b"\x89PNG\r\n\x1a\nDATA", "image/png")}, headers=H_ADMIN)
    check("POST /uploads/ .png as admin", r, 201)
    if r.status_code == 201:
        url = r.json()["url"]
        fname = r.json()["filename"]
        check(f"GET static {url}", client.get(url), 200)
        check(f"DELETE /uploads/{fname}", client.delete(f"/uploads/{fname}", headers=H_ADMIN), 204)
    check("DELETE /uploads/.hidden → 400", client.delete("/uploads/.hidden", headers=H_ADMIN), 400)

    section("16. Cleanup deletes")
    check("DELETE /reviews/1 as alice self", client.delete("/reviews/1", headers=H_ALICE), 204)
    check("DELETE /lessons/{id} admin", client.delete(f"/lessons/{lesson1_id}", headers=H_ADMIN), 204)
    check("DELETE /sections/{id} admin", client.delete(f"/sections/{section_id_}", headers=H_ADMIN), 204)
    check("DELETE /courses/{id} → 409 (has enrollment/order_item)", client.delete(f"/courses/{course_id}", headers=H_ADMIN), 409)

    section("17. Rate limit")
    print("  (skipping /auth/login burst — would block subsequent tests)")
    print(f"  (current rate_limit env: respected by app, manual verify in earlier turn)")

    print("\n" + "═" * 70)
    print(f"  RESULT: {PASS} pass, {FAIL} fail")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
