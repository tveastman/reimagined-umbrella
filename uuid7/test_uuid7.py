from unittest.mock import patch
from uuid import UUID
from typing import Iterable

import pytest
import uuid7


class MockIntReturner:
    def __init__(self, responses: list[int]):
        self.responses = list(reversed(responses))

    def __call__(self, _: int | None = None) -> int:
        return self.responses.pop()


def test_generate():
    generator = uuid7.UUIDv7Generator()
    generator.unix_time_ns_func = lambda: 1685940240093527761
    generator.randbits_func = lambda x: 258941218144316131

    result = generator()
    assert result == UUID("018889de-7edd-7871-8397-f1aa7d32eae3")


def test_increment_rand_b():
    generator = uuid7.UUIDv7Generator()
    generator.unix_time_ns_func = lambda: 1685940240093527761
    generator.randbits_func = MockIntReturner([258941218144316131, 2])

    first = generator()
    second = generator()
    assert first == UUID("018889de-7edd-7871-8397-f1aa7d32eae3")
    # This uuid is numerically just "3" more
    assert second == UUID("018889de-7edd-7871-8397-f1aa7d32eae6")


def test_overflow_rand_b():
    generator = uuid7.UUIDv7Generator()
    generator.unix_time_ns_func = MockIntReturner([0, 0, 1_000_000])
    LARGEST_POSSIBLE_RAND_B = (1 << 63) - 1
    generator.randbits_func = MockIntReturner([LARGEST_POSSIBLE_RAND_B, 1, 15])

    first_uuid = generator()
    assert first_uuid == UUID("00000000-0000-7000-ffff-ffffffffffff")
    print(f"{first_uuid=}")

    with patch("time.sleep") as mock_sleep:
        with pytest.warns(UserWarning):
            result = generator()
    mock_sleep.assert_called_with(uuid7.SLEEP_TIME)
    assert result == UUID("00000000-0001-7000-8000-00000000000f")
