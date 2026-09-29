"""paperqa 的错误类型。

每个错误自带 HTTP 状态码，API 层直接用它构造响应，不用在路由里写
一张"异常 -> 状态码"的映射表——那种表迟早会和异常定义漂移。
`status_code` 之外不携带任何展示细节，避免把上游响应正文透给客户端。
"""


class PaperQAError(RuntimeError):
    status_code = 502


class InvalidRequest(PaperQAError):
    status_code = 422


class NotFound(PaperQAError):
    status_code = 404


class AmbiguousDocument(PaperQAError):
    status_code = 409


class AccessDenied(PaperQAError):
    status_code = 403


class UpstreamError(PaperQAError):
    pass


class LocationError(PaperQAError):
    status_code = 422
