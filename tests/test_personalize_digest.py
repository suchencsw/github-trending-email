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
    def test_analysis_shortlist_expands_each_domain_without_mutating_profile(self):
        original = copy.deepcopy(PROFILE)
        expanded = digest.candidate_profile(PROFILE, 2)
        self.assertEqual(expanded['projectLimit'], 90)
        self.assertEqual(sum(item['quota'] for item in expanded['categories']), 90)
        self.assertEqual(PROFILE, original)
        with self.assertRaises(ValueError):
            digest.candidate_profile(PROFILE, 4)

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
        self.assertEqual(counts['models'], 5)
        self.assertEqual(counts['hardware'], 1)
        self.assertEqual(counts['measurement'], 1)
        self.assertEqual(sum(counts.values()), 7)

    def test_all_nine_groups_and_supplements_have_at_most_five_final_items(self):
        self.assertEqual(len(PROFILE['categories']), 9)
        self.assertTrue(all(category['quota'] == 5 for category in PROFILE['categories']))
        self.assertEqual(PROFILE['projectLimit'], 45)
        for key in ('paperLimit', 'modelLimit', 'newsLimit'):
            self.assertEqual(PROFILE[key], 5)
        projects = [repo(f'lab/space-{i}', 'Astrodynamics and spacecraft simulation') for i in range(12)]
        groups, _ = digest.choose_projects(projects, PROFILE, {}, TODAY)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['id'], 'space_sim')
        self.assertEqual(len(groups[0]['projects']), 5)

    def test_space_sim_anchor_wins_over_generic_vision_robotics_and_creation_terms(self):
        samples = [
            ('CesiumGS/cesium', '3D globes and maps', 'space_sim'),
            ('lab/cesium-sensors', 'CesiumJS sensor simulator with computer vision, point cloud and lidar', 'space_sim'),
            ('iamaisim/ProjectAirSim', 'Unreal Engine drone robotics SLAM simulation engine', 'space_sim'),
            ('AVSLab/basilisk', 'Astrodynamics simulation framework', 'space_sim'),
            ('nasa/GMAT', 'General Mission Analysis Tool for lunar and deep space missions', 'space_sim'),
            ('lab/lunar', 'Planetary terrain and lunar rover with robotics, ROS2 and visual odometry', 'space_sim'),
            ('lab/sensors', 'Multi-sensor simulation and synthetic dataset generation using Unreal Engine', 'space_sim'),
        ]
        for name, description, category in samples:
            with self.subTest(name=name):
                ranked = digest.rank_project(repo(name, description), PROFILE)
                self.assertEqual(ranked['category'], category)
                self.assertTrue(ranked['reasons'])

    def test_generic_simulation_and_homonyms_do_not_become_space_projects(self):
        samples = [
            ('lab/engine', 'Physics simulation engine with Blender and animation'),
            ('lab/robot', 'Robotics drone simulator with ROS2'),
            ('lab/data', 'Synthetic dataset generation for image matching'),
            ('lab/basilisk', 'Basilisk game engine and animation toolkit'),
            ('lab/cesium', 'Cesium atomic clock precision measurement'),
            ('lab/gmat', 'GMAT exam preparation notebook'),
        ]
        for name, description in samples:
            with self.subTest(name=name):
                ranked = digest.rank_project(repo(name, description), PROFILE)
                self.assertTrue(ranked is None or ranked['category'] != 'space_sim')

    def test_space_group_stays_sparse_after_relevance_and_recent_delivery_filtering(self):
        projects = [repo('lab/fresh', 'Astrodynamics simulation framework'),
                    repo('lab/recent', 'Spacecraft orbital dynamics'),
                    repo('lab/unrelated', 'Planet wallpaper simulator')]
        groups, removed = digest.choose_projects(projects, PROFILE,
                                                 {'lastSent': {'lab/recent': TODAY.isoformat()}}, TODAY)
        self.assertEqual(removed, 1)
        self.assertEqual([p['title'] for g in groups for p in g['projects']], ['lab/fresh'])

    def test_seed_candidates_require_live_active_metadata_and_correct_attribution(self):
        seeds = ['lab/live', 'lab/stale', 'lab/archived', 'lab/fork', 'lab/missing-date']
        metadata = {
            'live': {'pushed_at': '2026-11-13T00:00:00Z'},
            'stale': {'pushed_at': '2020-01-01T00:00:00Z'},
            'archived': {'pushed_at': '2026-11-13T00:00:00Z', 'archived': True},
            'fork': {'pushed_at': '2026-11-13T00:00:00Z', 'fork': True},
            'missing-date': {},
        }
        def fake_fetch(url, token=None):
            name = url.rsplit('/', 1)[-1]
            return {'full_name': 'lab/' + name, 'description': 'Astrodynamics toolkit',
                    'todayStars': '9999', **metadata[name]}
        statuses = []
        with patch.object(digest, 'fetch_json', side_effect=fake_fetch) as fetch:
            projects = digest.seed_projects({**PROFILE, 'seedRepositories': seeds}, 'token', TODAY, statuses)
        self.assertEqual(fetch.call_count, len(seeds))
        self.assertEqual([project['title'] for project in projects], ['lab/live'])
        self.assertEqual(projects[0]['sources'], ['GitHub Repository'])
        self.assertIsNone(projects[0]['starsToday'])
        self.assertTrue(all(status['ok'] for status in statuses))
        groups, _ = digest.choose_projects(projects, PROFILE,
                                           {'lastSent': {'lab/live': TODAY.isoformat()}}, TODAY)
        self.assertEqual(groups, [])

    def test_one_seed_failure_does_not_discard_other_candidates(self):
        def fake_fetch(url, token=None):
            if url.endswith('/failed'):
                raise digest.FetchError('HTTP 503')
            return {'full_name': 'lab/live', 'description': 'Spacecraft dynamics toolkit',
                    'pushed_at': '2026-11-13T00:00:00Z'}
        statuses = []
        with patch.object(digest, 'fetch_json', side_effect=fake_fetch):
            projects = digest.seed_projects({'seedRepositories': ['lab/failed', 'lab/live']}, 'token', TODAY, statuses)
        self.assertEqual(len(projects), 1)
        self.assertEqual(sorted(status['ok'] for status in statuses), [False, True])

    def test_public_search_budget_preserves_all_nine_domains(self):
        statuses = []
        with patch.object(digest, 'fetch_json', return_value={'items': []}) as fetch:
            digest.search_projects(PROFILE, None, TODAY, statuses)
        self.assertEqual(fetch.call_count, 9)
        query_urls = [call.args[0] for call in fetch.call_args_list]
        self.assertTrue(any('astrodynamics' in url for url in query_urls))
        self.assertTrue(any('photonics' in url for url in query_urls))
        self.assertTrue(any('fpga' in url for url in query_urls))

    def test_repository_and_search_api_work_are_bounded(self):
        profile = {**PROFILE, 'searchQueries': PROFILE['searchQueries'] * 3,
                   'seedRepositories': [f'lab/tool-{i}' for i in range(20)]}
        with patch.object(digest, 'fetch_json', return_value={'items': []}) as fetch:
            digest.search_projects(profile, 'token', TODAY, [])
        self.assertEqual(fetch.call_count, 18)
        with patch.object(digest, 'fetch_json', side_effect=digest.FetchError('HTTP 503')) as fetch:
            digest.seed_projects(profile, 'token', TODAY, [])
        self.assertEqual(fetch.call_count, 8)

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
