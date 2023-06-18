import pytest
from pathlib import Path
from ssm import SSM


@pytest.fixture
def read_file():
    return Path("../embrace/resources/ECS_HW.ssm")


def test_read_correct_file(read_file):  # Asserts that reading a known correct file does not raise an exception
    error = None
    try:
        with SSM(read_file) as file:
            print(file)
            file.__check_compliance__()

    except Exception as error:
        pass
    assert error is None


def test_create_basic_file():
    pass