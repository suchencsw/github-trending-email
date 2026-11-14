import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / '.github' / 'actions' / 'send_email.py'
SPEC = importlib.util.spec_from_file_location('personalized_email', MODULE_PATH)
email = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(email)


class PersonalizedEmailTests(unittest.TestCase):
    def setUp(self):
        self.digest = {
            'date': '2026-11-14',
            'profileLabel': 'AI科研与工程生产力',
            'categories': [{
                'id': 'hardware', 'label': 'FPGA、硬件与嵌入式',
                'projects': [{
                    'title': 'example/fpga-agent',
                    'url': 'https://github.com/example/fpga-agent',
                    'description': 'An assistant for FPGA engineering.',
                    'stars': 1234, 'starsToday': None, 'language': 'Python',
                    'updatedAt': '2026-11-13T09:00:00Z',
                    'reasons': ['AI辅助FPGA设计'], 'sources': ['GitHub Search'],
                }],
            }],
            'papers': [], 'models': [], 'news': [],
            'sourceStatus': [], 'stats': {'candidates': 20, 'selected': 1},
        }

    def render(self):
        return email.format_email({'personalizedDigest': self.digest})

    def test_groups_matching_and_search_stars_are_clear(self):
        output = self.render()
        for expected in ('FPGA、硬件与嵌入式', 'AI辅助FPGA设计', '总 Stars 1,234', '来源：GitHub 领域搜索', 'An assistant for FPGA engineering.'):
            self.assertIn(expected, output)
        self.assertNotIn('今日新增 +', output)
        self.assertNotIn('Tech Trending Daily', output)
        self.assertNotIn('相关论文</h2>', output)
        self.assertNotIn('相关模型</h2>', output)
        self.assertNotIn('相关科技动态</h2>', output)

    def test_real_trending_increment_is_distinct_from_total(self):
        project = self.digest['categories'][0]['projects'][0]
        project['starsToday'] = 27
        project['sources'] = ['GitHub Trending', 'GitHub Search']
        output = self.render()
        self.assertIn('总 Stars 1,234 · 今日新增 +27', output)
        self.assertIn('来源：GitHub 热榜、GitHub 领域搜索', output)

    def test_external_text_and_unsafe_links_cannot_inject_html(self):
        attack = '<img src=x onerror=alert(1)>'
        self.digest['profileLabel'] = attack
        category = self.digest['categories'][0]
        category['label'] = attack
        project = category['projects'][0]
        for field in ('title', 'description', 'language', 'updatedAt'):
            project[field] = attack
        project['reasons'] = [attack]
        project['url'] = 'javascript:alert(1)'
        for key, url in (('papers', 'data:text/html,alert(1)'), ('models', 'file:///etc/passwd'), ('news', 'https://example.com/" onclick="alert(1)')):
            self.digest[key] = [{'title': attack, 'url': url, 'summary': attack, 'description': attack, 'reasons': [attack]}]
        output = self.render()
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', output)
        self.assertNotIn('<img', output)
        self.assertNotIn('<script', output)
        self.assertNotIn('href="javascript:', output)
        self.assertNotIn('href="data:', output)
        self.assertNotIn('href="file:', output)
        self.assertNotIn(' onclick="', output)

    def test_urls_require_safe_web_scheme_without_credentials(self):
        for value in ('javascript:alert(1)', '//example.com', 'https://user:secret@example.com/', 'https://example.com/\nattack', 'https://example.com\\evil', 'https://example.com:invalid/'):
            with self.subTest(value=value):
                self.assertIsNone(email._digest_url(value))
        self.assertEqual(email._digest_url('https://example.com/?a=1&b=2'), 'https://example.com/?a=1&amp;b=2')

    def test_failed_optional_source_has_public_status_without_diagnostics(self):
        self.digest['sourceStatus'] = [{
            'name': 'Hugging Face Models', 'ok': False,
            'message': 'token=SECRET; C:\\private\\credentials.json; unexpected exception',
        }, {'name': '/private/token=SECRET', 'ok': False, 'message': 'SECRET'}]
        output = self.render()
        self.assertIn('来源状态：Hugging Face 模型暂不可用', output)
        self.assertNotIn('SECRET', output)
        self.assertNotIn('credentials.json', output)
        self.assertNotIn('unexpected exception', output)
        self.digest['sourceStatus'] = None
        self.render()

    def test_optional_sections_appear_only_with_real_items(self):
        self.digest['papers'] = [{'title': 'Robot research', 'url': 'https://arxiv.org/abs/1234.56789', 'summary': 'Original abstract.', 'authors': ['Alice', 'Bob'], 'publishedAt': '2026-11-13'}]
        self.digest['models'] = [{'title': 'example/model', 'url': 'https://huggingface.co/example/model', 'likes': 12, 'downloads': 3000}]
        self.digest['news'] = [{'title': 'Simulation news', 'url': 'https://example.com/news', 'score': 42}]
        output = self.render()
        for expected in ('相关论文</h2>', 'Original abstract.', '作者：Alice、Bob', '相关模型</h2>', '下载 3,000', '喜欢 12', '相关科技动态</h2>', '社区热度 42'):
            self.assertIn(expected, output)

    def test_legacy_data_retains_legacy_renderer(self):
        output = email.format_email({})
        self.assertIn('Tech Trending Daily', output)
        self.assertNotIn('本期 0 个匹配项目', output)


if __name__ == '__main__':
    unittest.main()
