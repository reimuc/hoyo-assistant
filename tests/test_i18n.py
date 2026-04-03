from hoyo_assistant.core import i18n


def test_i18n_fallback_key():
    # request a key that doesn't exist, expect key returned
    assert i18n.t("this.key.does.not.exist") == "this.key.does.not.exist"


def test_i18n_existing_key():
    # pick a key known to exist in locales (based on project locales files)
    # ensure it doesn't raise and returns a string
    res = i18n.t("cli.task.server_help_title")
    assert isinstance(res, str)
