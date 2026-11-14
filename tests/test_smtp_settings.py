import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


def load_send_email_module():
    path = Path(__file__).resolve().parents[1] / '.github' / 'actions' / 'send_email.py'
    spec = importlib.util.spec_from_file_location('smtp_settings_send_email', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmtpSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_send_email_module()

    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ, {}, clear=True))
        self.smtp = mock.Mock()
        self.client = self.smtp.return_value
        self.client.send.return_value = {}
        self.enterContext(mock.patch.object(
            self.module, 'yagmail', types.SimpleNamespace(SMTP=self.smtp)
        ))

    def send_example(self):
        self.module.send_email('sender@example.com', 'test-secret',
                               'recipient@example.com', 'Digest', '<p>Example</p>')

    def test_default_gmail_uses_ssl_and_closes_connection(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.send_example()

        self.smtp.assert_called_once_with(
            'sender@example.com', 'test-secret', host='smtp.gmail.com', port=465,
            smtp_ssl=True, smtp_starttls=False,
        )
        self.client.close.assert_called_once_with()
        self.assertNotIn('test-secret', output.getvalue())

    def test_provider_host_and_starttls_are_explicit(self):
        os.environ.update({
            'SMTP_HOST': 'smtp.example.com', 'SMTP_PORT': '587',
            'SMTP_SSL': 'false', 'SMTP_STARTTLS': 'true',
        })
        self.send_example()

        self.smtp.assert_called_once_with(
            'sender@example.com', 'test-secret', host='smtp.example.com', port=587,
            smtp_ssl=False, smtp_starttls=True,
        )

    def test_conflicting_tls_settings_fail_before_connection(self):
        os.environ['SMTP_STARTTLS'] = 'true'

        with self.assertRaisesRegex(ValueError, 'cannot both be enabled'):
            self.send_example()

        self.smtp.assert_not_called()

    def test_failed_delivery_is_not_reported_as_success(self):
        self.client.send.return_value = False

        with self.assertRaisesRegex(RuntimeError, 'did not confirm'):
            self.send_example()

        self.client.close.assert_called_once_with()

    def test_dry_run_uses_json_file_without_credentials_or_smtp(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / 'trending.json'
            preview_path = Path(directory) / 'preview' / 'digest.html'
            input_path.write_text(json.dumps({'githubTrending': {}}), encoding='utf-8')
            os.environ['TRENDING_DATA_FILE'] = str(input_path)

            result = self.module.main(['--dry-run', '--output', str(preview_path)])

            self.assertEqual(result, 0)
            self.assertIn('Tech Trending Daily', preview_path.read_text(encoding='utf-8'))
            self.smtp.assert_not_called()

    def test_environment_credentials_and_base64_input_are_supported(self):
        os.environ.update({
            'SMTP_USERNAME': 'sender@example.com',
            'SMTP_PASSWORD': 'test-secret',
            'SMTP_TO': 'recipient@example.com',
            'EMAIL_SUBJECT': 'Daily Digest',
            'TRENDING_DATA': base64.b64encode(b'{"githubTrending":{}}').decode('ascii'),
        })

        self.assertEqual(self.module.main([]), 0)

        self.client.send.assert_called_once()
        self.assertEqual(self.client.send.call_args.kwargs['to'], 'recipient@example.com')
        self.assertEqual(self.client.send.call_args.kwargs['subject'], 'Daily Digest')

    def test_language_only_data_is_not_presented_as_all_languages(self):
        repository = {
            'title': 'example/python-project', 'link': '/example/python-project',
            'description': 'A Python repository', 'stars': '123', 'todayStars': '4',
        }

        content = self.module.format_email({'githubTrending': {'python': [repository]}})

        self.assertNotIn('GitHub Trending - All', content)
        self.assertEqual(content.count('example/python-project</a>'), 1)


if __name__ == '__main__':
    unittest.main()
