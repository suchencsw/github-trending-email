import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('personalize_digest', ROOT / 'scripts/personalize_digest.py')
digest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(digest)
PROFILE = json.loads((ROOT / 'config/interests.json').read_text(encoding='utf-8'))
TODAY = date(2026, 11, 14)


def repo(name, description, stars=100, source='GitHub Search', **extra):
    return digest.project_from_metadata({'full_name': name, 'description': description,
                                         'stargazers_count': stars, **extra}, source)


class PersonalizeDigestTests(unittest.TestCase):
    def test_multidisciplinary_engineering_matches_have_evidence(self):
        samples = [
            ('lab/paper', 'AI research assistant for literature review', 'research'),
            ('lab/code', 'coding agent with agent skills and MCP', 'ai_tools'),
            ('lab/vision', '3D reconstruction and image matching toolkit', 'vision_3d'),
            ('lab/robot', 'embodied robot learning and ROS2', 'embodied'),
            ('lab/cad', 'AI text-to-CAD and SolidWorks automation', 'creative_sim'),
            ('lab/chip', 'LLM-assisted Verilog and FPGA circuit design', 'hardware'),
            ('lab/optical', 'precision measurement and interferometry tools', 'measurement'),
        ]
        for name, description, category in samples:
            with self.subTest(name=name):
                ranked = digest.rank_project(repo(name, description), PROFILE)
                self.assertEqual(ranked['category'], category)
                self.assertTrue(ranked['reasons'][0].startswith('兴趣关键词匹配：'))

    def test_specialist_ties_keep_blender_mcp_in_creative_group(self):
        ranked = digest.rank_project(repo('lab/blender-mcp', 'Blender MCP tools'), PROFILE)
        self.assertEqual(ranked['category'], 'creative_sim')

    def test_short_acronyms_do_not_match_substrings_or_weak_hype(self):
        for description in ['A paid catalog of domain names', 'Social plugin for music fans',
                            'AI startup funding news', 'LLM stock trading bot']:
            with self.subTest(description=description):
                self.assertIsNone(digest.rank_project(repo('lab/example', description), PROFILE))

    def test_daily_gain_requires_actual_trending_source(self):
        searched = repo('lab/eda', 'FPGA toolkit', todayStars='999')
        trending = repo('lab/eda', 'FPGA toolkit', source='GitHub Trending', todayStars='1,234 stars today')
        merged = digest.merge_projects([searched, trending, searched])[0]
        self.assertIsNone(searched['starsToday'])
        self.assertEqual(merged['starsToday'], 1234)
        self.assertEqual(set(merged['sources']), {'GitHub Search', 'GitHub Trending'})
        self.assertEqual(digest.numeric('2.5k'), 2500)

    def test_seven_day_dedup_does_not_modify_delivery_state(self):
        state = {'lastSent': {'lab/recent': '2026-11-08', 'lab/expired': '2026-11-07'}}
        original = copy.deepcopy(state)
        groups, removed = digest.choose_projects([
            repo('lab/recent', 'FPGA tooling'), repo('lab/expired', 'FPGA tooling')], PROFILE, state, TODAY)
        self.assertEqual(removed, 1)
        self.assertEqual([p['title'] for g in groups for p in g['projects']], ['lab/expired'])
        staged = digest.next_state(state, groups, TODAY)
        self.assertEqual(state, original)
        self.assertEqual(staged['lastSent']['lab/expired'], TODAY.isoformat())

    def test_per_domain_quotas_prevent_llm_flooding(self):
        projects = [repo(f'lab/llm-{i}', 'large language model inference toolkit', stars=100000) for i in range(40)]
        projects += [repo('lab/fpga', 'FPGA Verilog circuit design'),
                     repo('lab/optic', 'photonics and interferometry tools')]
        groups, _ = digest.choose_projects(projects, PROFILE, {}, TODAY)
        counts = {group['id']: len(group['projects']) for group in groups}
        self.assertEqual(counts['models'], 2)
        self.assertEqual(counts['hardware'], 1)
        self.assertEqual(counts['measurement'], 1)
        self.assertEqual(sum(counts.values()), 4)

    def test_empty_relevant_pool_stops_instead_of_filling_old_items(self):
        with self.assertRaisesRegex(ValueError, '未找到'):
            digest.build_digest({}, [repo('lab/old', 'FPGA tools')], {}, PROFILE,
                                {'lastSent': {'lab/old': TODAY.isoformat()}}, [], TODAY)

    def test_legacy_contract_and_search_attribution_are_preserved(self):
        output, state = digest.build_digest({}, [repo('lab/chip', 'Verilog FPGA toolkit')], {}, PROFILE, {}, [], TODAY)
        project = output['personalizedDigest']['categories'][0]['projects'][0]
        self.assertEqual(project['sources'], ['GitHub Search'])
        self.assertIsNone(project['starsToday'])
        self.assertEqual(output['githubTrending']['personalized'][0]['todayStars'], '')
        self.assertEqual(state['lastSent']['lab/chip'], TODAY.isoformat())

    def test_invalid_or_missing_upstream_input_allows_search_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'missing.json'
            statuses = []
            self.assertEqual(digest.load_input(path, statuses), {})
            self.assertFalse(statuses[0]['ok'])
            path.write_text('{"githubTrending": "invalid"}', encoding='utf-8')
            loaded = digest.load_input(path, statuses)
            output, _ = digest.build_digest(loaded, [repo('lab/fpga', 'FPGA tool')], {}, PROFILE, {}, statuses, TODAY)
            self.assertEqual(output['personalizedDigest']['stats']['selected'], 1)

    def test_partial_sources_fail_without_losing_good_searches(self):
        def fake_fetch(url, token=None):
            if 'research' in url:
                raise digest.FetchError('HTTP 503')
            return {'items': [{'full_name': 'lab/fpga', 'description': 'FPGA tool', 'stargazers_count': 20}]}
        profile = {**PROFILE, 'searchQueries': PROFILE['searchQueries'][:2]}
        statuses = []
        with patch.object(digest, 'fetch_json', side_effect=fake_fetch):
            projects = digest.search_projects(profile, 'test-token', TODAY, statuses)
        self.assertEqual(len(projects), 1)
        self.assertEqual(sorted(item['ok'] for item in statuses), [False, True])
        self.assertNotIn('test-token', json.dumps(statuses))

    def test_upstream_papers_shape_and_relevance(self):
        papers = [{'title': 'Embodied robot learning with simulation', 'url': 'https://example.org/paper',
                   'abstract': 'A robotics and sim2real framework', 'authors': ['A'], 'publishedDate': '2026-11-13'},
                  {'title': 'AI startup funding', 'url': 'https://example.org/funding'},
                  {'paper': None}]
        chosen = digest.pick_supplements(papers, 'papers', PROFILE, TODAY)
        self.assertEqual([item['title'] for item in chosen], ['Embodied robot learning with simulation'])
        self.assertIn('robotics', chosen[0]['summary'])

    def test_models_use_real_tasks_and_reject_stale_metadata(self):
        models = [{'modelId': 'lab/fresh', 'pipeline_tag': 'text-generation', '_trendingCandidate': True,
                   'lastModified': '2026-11-13', 'likes': 10},
                  {'id': 'lab/old', 'pipeline_tag': 'text-generation', 'lastModified': '2024-01-01', 'likes': 10000}]
        chosen = digest.pick_supplements(models, 'models', PROFILE, TODAY)
        self.assertEqual([item['title'] for item in chosen], ['lab/fresh'])
        self.assertNotIn('multimodal', ' '.join(chosen[0]['reasons']))
        self.assertIn('模型任务：text-generation', chosen[0]['reasons'])

    def test_models_get_trend_supplement_while_reusing_papers_news(self):
        upstream = {'huggingFaceModels': [{'modelId': 'lab/popular'}],
                    'aiPapers': [{'title': 'paper'}], 'hackerNewsStories': [{'title': 'news'}]}
        statuses = []
        with patch.object(digest, 'fetch_json', return_value=[{'id': 'lab/trending'}]) as fetch:
            result = digest.supplemental_data(upstream, statuses)
        fetch.assert_called_once()
        self.assertEqual([item.get('id') or item.get('modelId') for item in result['models']],
                         ['lab/trending', 'lab/popular'])
        self.assertEqual(result['papers'], upstream['aiPapers'])

    def test_state_output_cannot_overwrite_live_state(self):
        with self.assertRaisesRegex(ValueError, '独立文件'):
            digest.main(['--state', 'same.json', '--state-output', 'same.json'])


if __name__ == '__main__':
    unittest.main()
