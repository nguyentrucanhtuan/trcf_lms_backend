from app.models import Coupon, CouponType
from app.routers.coupons import compute_discount


def _coupon(discount_type: CouponType, value: int) -> Coupon:
    return Coupon(
        code="X",
        discount_type=discount_type,
        discount_value=value,
        is_active=True,
    )


def test_percent_basic():
    assert compute_discount(_coupon(CouponType.percent, 10), 1000) == 100


def test_percent_capped_at_100():
    assert compute_discount(_coupon(CouponType.percent, 250), 500) == 500


def test_percent_zero():
    assert compute_discount(_coupon(CouponType.percent, 0), 1000) == 0


def test_fixed_less_than_subtotal():
    assert compute_discount(_coupon(CouponType.fixed, 200), 500) == 200


def test_fixed_capped_at_subtotal():
    assert compute_discount(_coupon(CouponType.fixed, 9999), 500) == 500
