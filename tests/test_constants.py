from hoyo_assistant.core.constants import StatusCode


def test_status_code_success():
    assert hasattr(StatusCode, "SUCCESS")
    assert StatusCode.SUCCESS.value == 0
