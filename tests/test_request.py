import asyncio

from hoyo_assistant.core.request import HttpClient, MockResponse


def test_mock_response_json_text_read():
    loop = asyncio.new_event_loop()
    try:

        async def _run():
            data = {"a": 1}
            m = MockResponse(data)
            j = await m.json()
            assert j == data
            txt = await m.text()
            assert isinstance(txt, str)
            b = await m.read()
            assert isinstance(b, bytes)

        loop.run_until_complete(_run())
    finally:
        loop.close()


def test_httpclient_freeze_and_cache():
    c = HttpClient()
    # freeze simple structures
    a = c._freeze({"x": [1, 2]})
    assert isinstance(a, tuple)
    # cache behaviour: set cache directly and then ensure MockResponse returned
    auth_scope = {"cookie": "", "authorization": ""}
    key = ("http://example", c._freeze({}), c._freeze(auth_scope))
    c.cache[key] = {"ok": True}
    loop = asyncio.new_event_loop()
    try:

        async def _run():
            resp = await c.get("http://example")
            # since cache hit, should be MockResponse
            assert isinstance(resp, MockResponse)
            j = await resp.json()
            assert j == {"ok": True}

        loop.run_until_complete(_run())
    finally:
        loop.close()
