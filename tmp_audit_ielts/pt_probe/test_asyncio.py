import asyncio

async def _x():
    return 1

def test_a():
    assert asyncio.run(_x()) == 1

def test_b():
    assert True
