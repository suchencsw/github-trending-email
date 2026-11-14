import base64
import importlib.util
import json
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    'prepare_digest',
    Path(__file__).parents[1] / '.github/actions/prepare_digest.py',
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def encode(data):
    return base64.b64encode(json.dumps(data).encode()).decode()


class PrepareDigestTests(unittest.TestCase):
    def test_rejects_empty_collection_instead_of_sending_blank_email(self):
        with self.assertRaisesRegex(ValueError, 'No GitHub projects'):
            MODULE.decode_digest(encode({'githubTrending': {'all': []}}))

    def test_accepts_language_specific_projects_without_all_language_group(self):
        data = {'githubTrending': {'python': [{'title': 'owner/repo', 'link': '/owner/repo'}]}}
        decoded, count = MODULE.decode_digest(encode(data))
        self.assertEqual(decoded, data)
        self.assertEqual(count, 1)

    def test_rejects_malformed_collector_output(self):
        for value in ('', 'not base64', encode({'githubTrending': {'all': 'All'}})):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.decode_digest(value)


if __name__ == '__main__':
    unittest.main()
