"""
test_real_tools.py — 真实行为工具（open_url / send_email）测试

原则：绝不真实联网、绝不真开浏览器。
- webbrowser.open 用 monkeypatch 替换，捕获调用
- smtplib 用 monkeypatch 替换，捕获 send_message
- 真实凭据联调时人工跑（docs/week3/06 说明），不进自动化测试
"""

import smtplib
from email.message import EmailMessage

import pytest

from src import PermissionLevel, ToolRegistry
from src.real_tools import register_real_tools


class TestOpenUrl:
    def setup_method(self):
        self.registry = ToolRegistry()
        register_real_tools(self.registry)

    def test_01_registered_with_public_permission(self):
        schema = self.registry.get_schema("open_url")
        assert schema is not None
        assert schema.permission == PermissionLevel.PUBLIC

    def test_02_opens_url(self, monkeypatch):
        opened = {}
        monkeypatch.setattr("webbrowser.open", lambda u, new=0: opened.update(url=u) or True)
        r = self.registry.call("open_url", {"url": "https://www.example.com"})
        assert r.success
        assert r.result["opened"] == "https://www.example.com"
        assert opened["url"] == "https://www.example.com"

    def test_03_rejects_non_http_scheme(self, monkeypatch):
        monkeypatch.setattr("webbrowser.open", lambda *a, **k: True)
        for bad in ["javascript:alert(1)", "file:///etc/passwd", "ftp://x.com"]:
            r = self.registry.call("open_url", {"url": bad})
            assert not r.success
            assert "仅允许 http/https" in r.error

    def test_04_browser_missing(self, monkeypatch):
        monkeypatch.setattr("webbrowser.open", lambda *a, **k: False)
        r = self.registry.call("open_url", {"url": "https://www.example.com"})
        assert not r.success
        assert "浏览器" in r.error


class TestSendEmail:
    def setup_method(self):
        self.registry = ToolRegistry()
        register_real_tools(self.registry)

    def test_10_admin_permission_user_denied(self):
        """send_email 是 ADMIN 级：普通用户调用被拦（安全叙事的核心）。"""
        r = self.registry.call(
            "send_email", {"to": "a@b.com", "subject": "hi", "body": "test"}
        )
        assert not r.success
        assert "权限不足" in r.error

    def test_11_dry_run_builds_message_without_network(self):
        """干跑模式：ADMIN 提权后可调用，返回预览，全程无网络。"""
        r = self.registry.call(
            "send_email",
            {"to": ["a@b.com", "c@d.com"], "subject": "周报", "body": "内容"},
            user_level=PermissionLevel.ADMIN,
        )
        assert r.success
        assert r.result["dry_run"] is True
        assert r.result["to"] == ["a@b.com", "c@d.com"]
        assert r.result["subject"] == "周报"

    def test_12_invalid_recipient_rejected_even_in_dry_run(self):
        r = self.registry.call(
            "send_email", {"to": "not-an-email", "subject": "x", "body": "y"},
            user_level=PermissionLevel.ADMIN,
        )
        assert not r.success
        assert "收件人" in r.error

    def test_13_real_send_requires_credentials(self, monkeypatch):
        """真实发送缺凭据时给出明确报错，而不是把密码错误留在栈里。"""
        for var in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
            monkeypatch.delenv(var, raising=False)
        r = self.registry.call(
            "send_email",
            {"to": "a@b.com", "subject": "x", "body": "y", "dry_run": False},
            user_level=PermissionLevel.ADMIN,
        )
        assert not r.success
        assert "SMTP" in r.error

    def test_14_real_send_via_ssl(self, monkeypatch):
        """465 端口走 SMTP_SSL；捕获 send_message 验证邮件内容。"""
        sent = {}

        class FakeSMTP:
            def __init__(self, host, port, timeout=None):
                sent["smtp"] = f"{host}:{port}"
                sent["msg"] = None

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def login(self, u, p):
                sent["user"] = u

            def send_message(self, msg):
                sent["msg"] = msg

        monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
        r = self.registry.call(
            "send_email",
            {"to": "a@b.com", "subject": "测试", "body": "正文",
             "host": "smtp.test.com", "port": 465, "user": "me@test.com",
             "password": "authcode", "dry_run": False},
            user_level=PermissionLevel.ADMIN,
        )
        assert r.success and r.result["sent"] is True
        assert sent["smtp"] == "smtp.test.com:465"
        assert sent["user"] == "me@test.com"
        assert isinstance(sent["msg"], EmailMessage)
        assert sent["msg"]["Subject"] == "测试"

    def test_15_real_send_via_starttls(self, monkeypatch):
        """非 465 端口走 SMTP + STARTTLS。"""
        used = {}

        class FakeSMTP:
            def __init__(self, host, port, timeout=None):
                used["smtp"] = f"{host}:{port}"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                used["tls"] = True

            def login(self, u, p):
                pass

            def send_message(self, msg):
                pass

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        r = self.registry.call(
            "send_email",
            {"to": "a@b.com", "host": "smtp.test.com", "port": 587,
             "user": "me@test.com", "password": "x", "dry_run": False},
            user_level=PermissionLevel.ADMIN,
        )
        assert r.success
        assert used["smtp"] == "smtp.test.com:587" and used["tls"] is True

    def test_16_auth_failure_reported_friendly(self, monkeypatch):
        class FakeSMTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def login(self, u, p):
                raise smtplib.SMTPAuthenticationError(535, b"bad auth")

            def send_message(self, msg):
                pass

        monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
        r = self.registry.call(
            "send_email",
            {"to": "a@b.com", "host": "h", "port": 465,
             "user": "u", "password": "x", "dry_run": False},
            user_level=PermissionLevel.ADMIN,
        )
        assert not r.success
        assert "授权码" in r.error
