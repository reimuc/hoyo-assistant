class CookieError(Exception):
    def __init__(self, info):
        self.info = info

    def __str__(self):
        return str(self.info)


class StokenError(Exception):
    def __init__(self, info):
        self.info = info

    def __str__(self):
        return str(self.info)


class CaptchaError(Exception):
    def __init__(self, info):
        self.info = info

    def __str__(self):
        return str(self.info)
