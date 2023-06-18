import http.server
import ssl


# TODO Create a Handler that only serves on a single path. In the future, we'll extend that,
# so the same app will implement different webhooks. Notice that the GenericWebhookConfig
# yaml already supports that.

class Handler(http.server.BaseHTTPRequestHandler):
    pass