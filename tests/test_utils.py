from app.utils import slugify, utcnow


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_vietnamese():
    assert slugify("Cà phê Đặc biệt") == "ca-phe-dac-biet"


def test_slugify_strips_punctuation_and_collapses_dashes():
    assert slugify("  ---  Foo! @# Bar  ") == "foo-bar"


def test_slugify_empty_when_no_alphanumerics():
    assert slugify("!!!  ???") == ""


def test_utcnow_is_naive_utc():
    now = utcnow()
    assert now.tzinfo is None
