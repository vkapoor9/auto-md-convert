from __future__ import annotations

import tempfile
import unittest
from email import policy
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

from shared.convert import core


class EmailAttachmentConversionTests(unittest.TestCase):
    def convert_message(self, message):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "message.eml"
            path.write_bytes(message.as_bytes())
            with mock.patch.object(core, "_markitdown", return_value=None):
                return core.convert_file(path)

    def test_attachments_inside_related_body_are_not_lost(self):
        message = EmailMessage()
        message["Subject"] = "Related"
        message.set_content("Plain body")
        message.add_alternative("<p>HTML body</p>", subtype="html")
        html = message.get_payload()[1]
        html.add_related(b"attached text", maintype="text", subtype="plain",
                         filename="related.txt", disposition="attachment")
        meta, body = self.convert_message(message)
        self.assertEqual(body.strip(), "Plain body")
        self.assertEqual(len(meta["attachments"]), 1)
        self.assertEqual(meta["attachments"][0]["body"], "attached text")

    def test_text_attachment_uses_declared_charset(self):
        message = EmailMessage()
        message.set_content("body")
        message.add_attachment("café", charset="iso-8859-1", filename="notes.txt")
        meta, _ = self.convert_message(message)
        self.assertEqual(meta["attachments"][0]["body"].strip(), "café")

    def test_unknown_body_charset_does_not_silently_drop_body(self):
        message = EmailMessage()
        message.set_content("Important body")
        message.set_param("charset", "unknown-charset")
        _, body = self.convert_message(message)
        self.assertIn("Important body", body)

    def test_bad_attachment_does_not_hide_following_attachments(self):
        message = EmailMessage()
        message.set_content("body")
        message.add_attachment("first", filename="one.txt")
        message.add_attachment("second", filename="two.txt")
        original = core._attachment_bytes
        calls = 0

        def payload(part):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("malformed payload")
            return original(part)

        with mock.patch.object(core, "_attachment_bytes", side_effect=payload):
            meta, _ = self.convert_message(message)
        self.assertEqual(len(meta["attachments"]), 2)
        self.assertIn("malformed payload", meta["attachments"][0]["error"])
        self.assertEqual(meta["attachments"][1]["body"].strip(), "second")

    def test_depth_limit_is_visible_without_losing_outer_body(self):
        nested = EmailMessage()
        nested.set_content("nested")
        message = EmailMessage()
        message.set_content("outer")
        message.add_attachment(nested, filename="nested.eml")
        with mock.patch.object(core, "_MAX_NESTED_EMAIL_DEPTH", 0):
            meta, body = self.convert_message(message)
        self.assertEqual(body.strip(), "outer")
        self.assertIn("Maximum nested email depth", meta["attachments"][0]["error"])

    def test_html_email_headers_dates_and_no_attachments(self):
        message = EmailMessage()
        message["Subject"] = "Re: Status"
        message["From"] = "from@example.com"
        message["To"] = "to@example.com"
        message["Cc"] = "copy@example.com"
        message["Message-ID"] = "<audit@example.com>"
        message["Date"] = "Mon, 17 Aug 2026 09:14:22 -0400"
        message.set_content("<p>HTML body &amp; details</p>", subtype="html")
        meta, body = self.convert_message(message)
        self.assertEqual(meta["date_prefix"], "2026-08-17")
        self.assertEqual(core.build_filename(meta), "2026-08-17--status.md")
        self.assertIn("HTML body & details", body)
        output = core.render_markdown(meta, body)
        self.assertIn('cc: "copy@example.com"', output)
        self.assertIn('message_id: "<audit@example.com>"', output)
        self.assertNotIn("## Attachments", output)
        self.assertEqual(core._email_date_prefix("nonsense", "2026-08-18T01:00:00"), "2026-08-18")

    def test_unnamed_attachments_use_mime_type_and_names_are_sanitized(self):
        message = EmailMessage()
        message.set_content("body")
        message.add_attachment("unnamed text")
        message.add_attachment("named text", filename="C:\\outside\\notes.txt")
        nested = EmailMessage()
        nested.set_content("nested body")
        message.add_attachment(nested)
        meta, _ = self.convert_message(message)
        self.assertEqual(len(meta["attachments"]), 3)
        self.assertEqual(meta["attachments"][0]["body"].strip(), "unnamed text")
        self.assertEqual(meta["attachments"][1]["name"], "notes.txt")
        self.assertEqual(meta["attachments"][2]["body"].strip(), "nested body")

    def test_unreadable_attachment_has_visible_error(self):
        message = EmailMessage()
        message.set_content("body")
        message.add_attachment("bad", filename="bad.txt")
        with mock.patch.object(core, "_attachment_bytes", return_value=None):
            meta, body = self.convert_message(message)
        self.assertIn("payload could not be read", core.render_markdown(meta, body))

    def test_converts_file_and_nested_email_attachments_into_same_markdown(self) -> None:
        nested = EmailMessage(policy=policy.default)
        nested["Subject"] = "Forwarded details"
        nested["From"] = "sender@example.com"
        nested["To"] = "recipient@example.com"
        nested.set_content("Nested email body")
        nested.add_attachment("Nested attachment content", filename="nested.txt")

        message = EmailMessage(policy=policy.default)
        message["Subject"] = "Project update"
        message["From"] = "owner@example.com"
        message["To"] = "team@example.com"
        message.set_content("Original email body")
        message.add_attachment(
            b"%PDF-attachment-content",
            maintype="application",
            subtype="pdf",
            filename="report.pdf",
        )
        message.add_attachment(
            b"unknown-binary-content",
            maintype="application",
            subtype="octet-stream",
            filename="payload.bin",
        )
        message.add_attachment(nested, filename="forwarded.eml")

        def convert_attachment(path: Path) -> str | None:
            if path.suffix == ".pdf":
                self.assertEqual(path.read_bytes(), b"%PDF-attachment-content")
                return "Converted PDF content"
            if path.suffix == ".txt":
                return path.read_text(encoding="utf-8")
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            email_path = Path(temp_dir) / "message.eml"
            email_path.write_bytes(message.as_bytes())
            with mock.patch.object(core, "_convert_other", side_effect=convert_attachment):
                meta, body = core.convert_file(email_path)
                markdown = core.render_markdown(meta, body)

        self.assertIn("Original email body", markdown)
        self.assertIn("## Attachments", markdown)
        self.assertIn("### 1. report.pdf", markdown)
        self.assertIn("Converted PDF content", markdown)
        self.assertIn("### 2. payload.bin", markdown)
        self.assertIn("Conversion unavailable", markdown)
        self.assertIn("### 3. forwarded.eml", markdown)
        self.assertIn("#### Forwarded details", markdown)
        self.assertIn("Nested email body", markdown)
        self.assertIn("##### Attachments", markdown)
        self.assertIn("###### 1. nested.txt", markdown)
        self.assertIn("Nested attachment content", markdown)
        self.assertLess(markdown.index("Original email body"), markdown.index("## Attachments"))
        self.assertLess(markdown.index("### 1. report.pdf"), markdown.index("### 2. payload.bin"))
        self.assertLess(markdown.index("### 2. payload.bin"), markdown.index("### 3. forwarded.eml"))

    def test_converts_text_attachment_without_optional_dependencies(self) -> None:
        message = EmailMessage(policy=policy.default)
        message["Subject"] = "Text attachment"
        message.set_content("Email body")
        message.add_attachment("Plain attachment body", filename="notes.txt")

        with tempfile.TemporaryDirectory() as temp_dir:
            email_path = Path(temp_dir) / "message.eml"
            email_path.write_bytes(message.as_bytes())
            meta, body = core.convert_file(email_path)
            markdown = core.render_markdown(meta, body)

        self.assertIn("### 1. notes.txt", markdown)
        self.assertIn("Plain attachment body", markdown)


if __name__ == "__main__":
    unittest.main()