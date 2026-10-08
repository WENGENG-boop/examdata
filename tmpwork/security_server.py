"""临时 ASGI 入口：真实 app + 安全层，供 uvicorn 起真服务做端到端验证（跑完即弃）。

主代理接入 app.py 之后本文件即可删除；这里只是为了在 app.py 尚未改动的前提下，
用真实 HTTP 验证 security.py。
"""

from examdata.api.app import app
from examdata.api.security import install_security

install_security(app)
