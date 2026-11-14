import copy
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / '.github' / 'actions' / 'send_email.py'
SPEC = importlib.util.spec_from_file_location('llm_email', MODULE_PATH)
email = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(email)


class LLMEmailTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            'title': 'lab/fpga-agent', 'url': 'https://github.com/lab/fpga-agent',
            'description': 'Original metadata description.',
            'stars': 100, 'sources': ['GitHub Search'],
            'reasons': ['兴趣关键词匹配：FPGA'],
            'llmAnalysis': {
                'status': 'analyzed', 'summary': '通过智能体辅助设计 FPGA 逻辑。',
                'useCase': '可用于整理你的 Verilog 仿真与调试流程。',
                'requirements': '需要 Python 与兼容的 FPGA 工具链。',
                'limitations': '文档未给出精密测量场景的性能数据。',
                'relevanceScore': 82, 'documentsRead': 2,
                'evidence': [{
                    'url': 'https://github.com/lab/fpga-agent/blob/main/README.md',
                    'quote': 'Run Verilog simulations with an agent.',
                }],
            },
        }
        self.digest = {
            'date': '2026-11-14', 'profileLabel': 'AI科研与工程生产力',
            'categories': [{'id': 'hardware', 'label': 'FPGA与嵌入式', 'projects': [self.project]}],
            'analysisStatus': {'enabled': True, 'model': 'deepseek-ai/example', 'analyzed': 25, 'failed': 2},
            'papers': [], 'models': [], 'news': [], 'sourceStatus': [],
        }

    def render(self):
        return email.format_email({'personalizedDigest': self.digest})

    def test_completed_reading_shows_specific_use_and_citations(self):
        output = self.render()
        for expected in ('AI 文档分析 · 已读取 2 份 README / 仓库文档',
                         '通过智能体辅助设计 FPGA 逻辑。', '对你的用途',
                         '可用于整理你的 Verilog 仿真与调试流程。', '使用条件',
                         '限制与待确认', '文档依据 1', 'Run Verilog simulations with an agent.',
                         '其中 1 个完成 AI 文档分析', '未运行项目或验证作者宣称的效果',
                         '分析模型：deepseek-ai/example'):
            self.assertIn(expected, output)
        self.assertNotIn('Original metadata description.', output)
        self.assertNotIn('项目介绍和论文摘要保留原文', output)
        self.assertNotIn('其中 25 个', output)

    def test_fallback_is_distinct_and_uses_fixed_message_not_diagnostics(self):
        failed = copy.deepcopy(self.project)
        failed['title'] = 'lab/fallback'
        failed['llmAnalysis'] = {'status': 'unavailable', 'error': 'SECRET path=/private/key'}
        self.digest['categories'][0]['projects'].append(failed)
        output = self.render()
        self.assertIn('本期 2 个匹配项目，其中 1 个完成 AI 文档分析', output)
        self.assertIn('1 个仅按关键词初筛，已单独标注', output)
        self.assertIn('本项未完成文档分析，仅按关键词初筛', output)
        self.assertIn('Original metadata description.', output)
        self.assertNotIn('SECRET', output)
        self.assertNotIn('/private/key', output)

    def test_model_content_and_all_citations_are_escaped(self):
        attack = '<img src=x onerror="alert(1)">'
        analysis = self.project['llmAnalysis']
        for field in ('summary', 'useCase', 'requirements', 'limitations'):
            analysis[field] = attack
        analysis['evidence'] = [
            {'url': 'javascript:alert(1)', 'quote': 'UNSAFE QUOTE'},
            {'url': 'https://github.com/lab/fpga-agent/blob/main/README.md?x=" onclick="alert(1)', 'quote': attack},
            {'url': 'https://github.com/lab/fpga-agent/blob/main/docs/setup.md', 'quote': attack},
        ]
        self.digest['analysisStatus']['model'] = attack
        output = self.render()
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;', output)
        self.assertNotIn('<img', output)
        self.assertNotIn('href="javascript:', output)
        self.assertNotIn(' onclick="', output)
        self.assertNotIn('UNSAFE QUOTE', output)

    def test_invalid_read_counts_never_claim_document_review(self):
        for count in (0, -1, True, '2', None):
            with self.subTest(count=count):
                self.project['llmAnalysis']['documentsRead'] = count
                output = self.render()
                self.assertNotIn('AI 文档分析 · 已读取', output)
                self.assertIn('其中 0 个完成 AI 文档分析', output)
                self.assertIn('本项未完成文档分析，仅按关键词初筛', output)

    def test_missing_analysis_details_are_unknown_not_invented(self):
        analysis = self.project['llmAnalysis']
        for field in ('useCase', 'requirements', 'limitations'):
            analysis.pop(field)
        output = self.render()
        for expected in ('资料不足，暂未确定具体接入方式', '文档未明确，请查看项目说明',
                         '尚未运行验证，实际效果需自行测试'):
            self.assertIn(expected, output)

    def test_supplements_remain_labeled_as_source_metadata(self):
        self.digest['papers'] = [{'title': 'Paper', 'url': 'https://arxiv.org/abs/1234.56789', 'summary': 'Original paper abstract.'}]
        output = self.render()
        self.assertIn('论文、模型与科技动态仍基于来源信息筛选，介绍和摘要保留原文', output)
        self.assertIn('Original paper abstract.', output)

    def test_plain_digest_retains_original_behavior(self):
        self.digest.pop('analysisStatus')
        self.project.pop('llmAnalysis')
        output = self.render()
        self.assertIn('项目介绍和论文摘要保留原文', output)
        self.assertIn('Original metadata description.', output)
        self.assertNotIn('本项未完成文档分析', output)


if __name__ == '__main__':
    unittest.main()
