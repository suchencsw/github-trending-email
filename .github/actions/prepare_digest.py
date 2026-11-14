"""Validate action output before rendering or sending a digest."""

import argparse
import base64
import json
import os
from pathlib import Path


def decode_digest(encoded, allow_empty=False):
    try:
        data = json.loads(base64.b64decode(encoded, validate=True).decode('utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ValueError('The collector returned invalid digest data.') from exc
    if not isinstance(data, dict) or not isinstance(data.get('githubTrending'), dict):
        raise ValueError('The collector returned no GitHub project groups.')
    count = 0
    for repos in data['githubTrending'].values():
        if not isinstance(repos, list):
            raise ValueError('A GitHub project group is not a list.')
        for repo in repos:
            if not isinstance(repo, dict) or not repo.get('title') or not repo.get('link'):
                raise ValueError('A GitHub project is missing its name or link.')
        count += len(repos)
    if not count and not allow_empty:
        raise ValueError('No GitHub projects were collected; email will not be sent.')
    return data, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-empty', action='store_true')
    args = parser.parse_args()
    data, count = decode_digest(os.environ.get('TRENDING_DATA', ''), args.allow_empty)
    destination = Path('output/trending.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    print(f'Validated {count} collected GitHub project entries.')


if __name__ == '__main__':
    main()
