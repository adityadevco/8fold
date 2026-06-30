import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cdt.core.normalize import (
    normalize_country, normalize_date, normalize_email, normalize_phone, normalize_skill,
)


def test_normalize_phone_indian_10_digit():
    assert normalize_phone("9876543210") == "+919876543210"


def test_normalize_phone_with_plus_and_punctuation():
    assert normalize_phone("+1 (415) 555-0199") == "+14155550199"


def test_normalize_phone_garbage():
    assert normalize_phone("abc") is None
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_normalize_email():
    assert normalize_email("Foo@Bar.com") == "foo@bar.com"
    assert normalize_email("not-an-email") is None
    assert normalize_email("priya.nair@") is None


def test_normalize_date_formats():
    assert normalize_date("2022-06-01") == "2022-06"
    assert normalize_date("06/2022") == "2022-06"
    assert normalize_date("June 2022") == "2022-06"
    assert normalize_date("present") == "present"
    assert normalize_date(None) is None
    assert normalize_date("garbage") is None


def test_normalize_skill_aliases():
    assert normalize_skill("py") == "Python"
    assert normalize_skill("ReactJS") == "React"
    assert normalize_skill("Some Niche Tool") == "Some Niche Tool"


def test_normalize_country():
    assert normalize_country("India") == "IN"
    assert normalize_country("us") == "US"
    assert normalize_country("Narnia") is None
