"""Collect and rank an evidence-linked research engineering digest.

Uses public metadata and editable keyword rules, not model-generated claims.
State is staged separately; the delivery workflow saves it only after SMTP succeeds.
"""

import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


BEIJING = timezone(timedelta(hours=8))


class FetchError(RuntimeError):
    """A public, credential-free description of a failed source."""


def fetch_json(url, token=None, timeout=15):
    headers = {'User-Agent': 'research-engineering-digest/1.0', 'Accept': 'application/json'}
    if token and urlparse(url).hostname == 'api.github.com':
        headers.update({'Authorization': f'Bearer {token}',
                        'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28'})
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and not attempt:
                time.sleep(2)
                continue
            raise FetchError(f'HTTP {exc.code}') from None
        except (URLError, TimeoutError, OSError, ValueError):
            if not attempt:
                time.sleep(1)
                continue
            raise FetchError('请求超时或数据不可用') from None


def numeric(value):
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or '').strip().lower().replace(',', '')
    match = re.search(r'(\d+(?:\.\d+)?)\s*([km]?)', text)
    if not match:
        return 0
    scale = {'': 1, 'k': 1000, 'm': 1000000}[match.group(2)]
    return int(float(match.group(1)) * scale)


def normalized(text):
    return re.sub(r'\s+', ' ', re.sub(r'[-_/]+', ' ', str(text or '').lower())).strip()


def has_term(text, term):
    needle = normalized(term)
    if not needle:
        return False
    # Short acronyms such as AI, MCP, RTL and CAD must match whole tokens.
    return bool(re.search(r'(?<![a-z0-9])' + re.escape(needle) + r'(?![a-z0-9])', text))


def parse_time(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
    except (TypeError, ValueError):
        return None


def project_from_metadata(raw, source):
    name = raw.get('full_name') or raw.get('title') or ''
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', name):
        return None
    project = {
        'title': name, 'url': f'https://github.com/{name}',
        'description': str(raw.get('description') or ''),
        'stars': numeric(raw.get('stargazers_count', raw.get('stars'))),
        'starsToday': None, 'language': raw.get('language') or '',
        'updatedAt': raw.get('pushed_at') or raw.get('updatedAt') or '',
        'topics': [str(topic) for topic in raw.get('topics', []) if isinstance(topic, str)]
                  if isinstance(raw.get('topics'), list) else [], 'sources': [source],
    }
    # API search metadata does not report daily star gains. Never invent them.
    if source == 'GitHub Trending':
        today = raw.get('todayStars')
        if today is not None and str(today).strip():
            project['starsToday'] = numeric(today)
    return project


def merge_projects(projects):
    merged = {}
    for project in projects:
        if not project:
            continue
        key = project['title'].lower()
        if key not in merged:
            merged[key] = dict(project)
            continue
        target = merged[key]
        target['sources'] = sorted(set(target['sources']) | set(project['sources']))
        target['stars'] = max(target['stars'], project['stars'])
        for field in ('description', 'language', 'updatedAt', 'topics'):
            if project.get(field):
                target[field] = project[field]
        if project.get('starsToday') is not None:
            target['starsToday'] = project['starsToday']
    return list(merged.values())


def content_matches(text, profile):
    text = normalized(text)
    if any(has_term(text, term) for term in profile.get('excludeTerms', [])):
        return []
    ai_match = any(has_term(text, term) for term in profile.get('aiTerms', []))
    tool_match = any(has_term(text, term) for term in profile.get('toolTerms', []))
    matches = []
    for category in profile['categories']:
        required = category.get('requiredAnyTerms', [])
        if required and not any(has_term(text, term) for term in required):
            continue
        terms = [(term, weight) for term, weight in category['terms'].items() if has_term(text, term)]
        base = sum(weight for _, weight in terms)
        if not terms:
            continue
        # AI + engineering utility is preferred, while useful specialist tools
        # remain eligible even if their author does not advertise them as AI.
        score = base + (3 if ai_match else 0) + (1 if tool_match else 0)
        if score < category.get('minimumScore', 5):
            continue
        evidence = ', '.join(term for term, _ in sorted(terms, key=lambda pair: -pair[1])[:3])
        reasons = [f'兴趣关键词匹配：{evidence}']
        if ai_match and category['id'] not in ('models', 'ai_tools'):
            reasons.append('元数据同时包含AI或大模型相关关键词')
        matches.append((category['id'], score, reasons))
    specialist = {'hardware', 'measurement', 'creative_sim', 'vision_3d', 'embodied', 'space_sim'}
    # A narrowly identified domain wins over a long list of generic AI/vision/
    # robotics terms. Priority is configured only alongside an explicit gate.
    priorities = {category['id']: category.get('priority', 0)
                  if category.get('requiredAnyTerms') else 0 for category in profile['categories']}
    return sorted(matches, key=lambda item: (-priorities[item[0]], -item[1], item[0] not in specialist))


def rank_project(project, profile, now=None):
    now = now or datetime.now(timezone.utc)
    text = ' '.join([project['title'], project.get('description', ''),
                     ' '.join(project.get('topics', []))])
    matches = content_matches(text, profile)
    if not matches:
        return None
    category, relevance, reasons = matches[0]
    recency = 0
    updated = parse_time(project.get('updatedAt'))
    if updated:
        age = (now - updated).total_seconds() / 86400
        recency = 2 if 0 <= age <= 7 else (1 if 0 <= age <= 30 else 0)
    popularity = min(3, math.log10(1 + project['stars']))
    trend_boost = min(2, math.log10(1 + (project.get('starsToday') or 0)))
    return {**project, 'category': category, 'score': round(relevance + recency + popularity + trend_boost, 2),
            'reasons': reasons}


def seen_recently(key, state, today, days):
    try:
        sent = date.fromisoformat(state.get('lastSent', {}).get(key.lower(), ''))
        age = (today - sent).days
        return 0 <= age < days
    except (TypeError, ValueError):
        return False


def choose_projects(projects, profile, state, today=None):
    today = today or datetime.now(BEIJING).date()
    now = datetime.combine(today, datetime.min.time(), tzinfo=BEIJING).astimezone(timezone.utc)
    ranked = []
    duplicate_count = 0
    for project in merge_projects(projects):
        candidate = rank_project(project, profile, now)
        if not candidate:
            continue
        if seen_recently(project['title'], state, today, profile.get('deduplicateDays', 7)):
            duplicate_count += 1
            continue
        ranked.append(candidate)
    ranked.sort(key=lambda repo: (-repo['score'], repo['title'].lower()))
    remaining = profile.get('projectLimit', 18)
    groups = []
    for category in profile['categories']:
        matches = [repo for repo in ranked if repo['category'] == category['id']]
        chosen = matches[:min(category['quota'], remaining)]
        remaining -= len(chosen)
        if chosen:
            groups.append({'id': category['id'], 'label': category['label'], 'projects': chosen})
    return groups, duplicate_count


def next_state(previous, categories, today):
    cutoff = today - timedelta(days=35)
    entries = {}
    for key, value in previous.get('lastSent', {}).items():
        try:
            if cutoff <= date.fromisoformat(value) <= today:
                entries[key.lower()] = value
        except (TypeError, ValueError):
            continue
    for category in categories:
        for project in category['projects']:
            entries[project['title'].lower()] = today.isoformat()
    return {'version': 1, 'lastSent': entries}


def candidate_profile(profile, multiplier=1):
    """Expand each domain before the document analysis makes the final selection."""
    if multiplier not in (1, 2, 3):
        raise ValueError('Candidate multiplier must be 1, 2 or 3.')
    expanded = deepcopy(profile)
    expanded['projectLimit'] = profile.get('projectLimit', 18) * multiplier
    for category in expanded['categories']:
        category['quota'] *= multiplier
    return expanded


def load_input(path, statuses):
    if not path.exists():
        statuses.append({'name': 'GitHub Trending', 'ok': False,
                         'message': '热榜输入不可用；本期使用领域搜索补充'})
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, OSError):
        statuses.append({'name': 'GitHub Trending', 'ok': False,
                         'message': '热榜输入格式无效；本期使用领域搜索补充'})
        return {}
    groups = data.get('githubTrending', {})
    if not isinstance(groups, dict):
        data['githubTrending'] = groups = {}
    count = sum(len(value) for value in groups.values() if isinstance(value, list)) if isinstance(groups, dict) else 0
    statuses.append({'name': 'GitHub Trending', 'ok': bool(count),
                     'message': f'收到{count}条热榜记录' if count else '热榜未返回项目；本期使用领域搜索补充'})
    return data


def search_projects(profile, token, today, statuses):
    active_since = (today - timedelta(days=profile.get('activeWithinDays', 180))).isoformat()
    queries = profile.get('searchQueries', [])[:18]
    if not token:
        # Preserve specialist domains, rather than spending the public quota
        # on several overlapping AI tooling searches.
        public_labels = profile.get('publicSearchLabels')
        if public_labels:
            queries = [query for query in queries if query['label'] in public_labels]
        queries = queries[:9]
        statuses.append({'name': 'GitHub Search 配额', 'ok': False,
                         'message': '未设置GitHub令牌，本次缩减搜索数量以遵守公开接口限额'})

    def search(query):
        parameters = {'q': f"{query['query']} pushed:>={active_since} archived:false fork:false",
                      'sort': query.get('sort', 'updated'), 'order': 'desc', 'per_page': 25}
        payload = fetch_json('https://api.github.com/search/repositories?' + urlencode(parameters), token)
        if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
            raise FetchError('接口返回格式无效')
        projects = [project_from_metadata(repo, 'GitHub Search') for repo in payload['items']
                    if not repo.get('archived') and not repo.get('fork')]
        return projects, bool(payload.get('incomplete_results'))

    results = []
    # Two concurrent requests keep well below authenticated search limits.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(search, query): query for query in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                projects, incomplete = future.result()
                results.extend(projects)
                statuses.append({'name': 'GitHub Search · ' + query['label'], 'ok': not incomplete,
                                 'message': f'获取{len(projects)}条候选' + ('，接口提示结果不完整' if incomplete else '')})
            except FetchError as exc:
                statuses.append({'name': 'GitHub Search · ' + query['label'], 'ok': False,
                                 'message': str(exc) + '；其他来源继续运行'})
    return results


def seed_projects(profile, token, today, statuses):
    """Read a bounded watchlist as candidates, never as forced recommendations."""
    repositories = list(dict.fromkeys(profile.get('seedRepositories', [])))[:8]
    if not repositories:
        return []
    cutoff = today - timedelta(days=profile.get('activeWithinDays', 180))

    def inspect(name):
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', name):
            raise FetchError('仓库名称无效')
        raw = fetch_json('https://api.github.com/repos/' + name, token)
        if not isinstance(raw, dict) or not raw.get('full_name'):
            raise FetchError('接口返回格式无效')
        pushed = parse_time(raw.get('pushed_at'))
        if raw.get('archived') or raw.get('fork') or not pushed or pushed.date() < cutoff:
            return None
        return project_from_metadata(raw, 'GitHub Repository')

    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(inspect, name): name for name in repositories}
        for future in as_completed(futures):
            name = futures[future]
            try:
                project = future.result()
                if project:
                    results.append(project)
                statuses.append({'name': 'GitHub Repository · ' + name, 'ok': True,
                                 'message': '获取最新仓库元数据，继续参与相关性及去重筛选' if project
                                            else '未满足近期活跃或非归档/非复刻要求，略过候选'})
            except FetchError as exc:
                statuses.append({'name': 'GitHub Repository · ' + name, 'ok': False,
                                 'message': str(exc) + '；其他来源继续运行'})
    return results


def supplemental_data(data, statuses):
    """Reuse upstream results; retrieve missing channels from official APIs."""
    sources = {
        'papers': ('Hugging Face Papers', data.get('aiPapers'),
                   'https://huggingface.co/api/daily_papers?limit=50'),
        'models': ('Hugging Face Models', data.get('huggingFaceModels'),
                   'https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=50&full=true'),
        'news': ('Hacker News', data.get('hackerNewsStories'),
                 'https://hn.algolia.com/api/v1/search_by_date?' + urlencode({
                     'query': 'AI', 'tags': 'story', 'hitsPerPage': 50,
                     'numericFilters': f'created_at_i>{int(time.time()) - 3 * 86400},points>10'})),
    }
    result = {}
    pending = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        for key, (label, existing, url) in sources.items():
            if isinstance(existing, list) and existing and key != 'models':
                result[key] = existing
                statuses.append({'name': label, 'ok': True, 'message': f'使用上游采集的{len(existing)}条记录'})
            else:
                result[key] = existing if isinstance(existing, list) else []
                pending[executor.submit(fetch_json, url)] = (key, label)
        for future in as_completed(pending):
            key, label = pending[future]
            try:
                payload = future.result()
                if key == 'news' and isinstance(payload, dict):
                    payload = payload.get('hits')
                if not isinstance(payload, list):
                    raise FetchError('接口返回格式无效')
                if key == 'models':
                    for model in payload:
                        if isinstance(model, dict):
                            model['_trendingCandidate'] = True
                    result[key] = payload + result[key]
                else:
                    result[key] = payload
                statuses.append({'name': label, 'ok': True,
                                 'message': f'获取{len(payload)}条候选' + ('，并合并上游模型结果' if key == 'models' else '')})
            except FetchError as exc:
                statuses.append({'name': label, 'ok': False, 'message': str(exc) + '；本期略过此来源'})
    return result


def safe_url(value):
    value = str(value or '')
    parsed = urlparse(value)
    return value if parsed.scheme in ('https', 'http') and parsed.netloc else ''


def pick_supplements(items, kind, profile, today=None):
    today = today or datetime.now(BEIJING).date()
    ranked = []
    seen = set()
    for raw in items:
        raw = raw or {}
        if not isinstance(raw, dict):
            continue
        if kind == 'papers':
            paper = raw.get('paper', raw)
            if not isinstance(paper, dict):
                continue
            title = paper.get('title', '')
            summary = paper.get('summary') or paper.get('abstract') or ''
            identifier = paper.get('id')
            url = raw.get('url') or raw.get('link') or paper.get('url') or (f'https://huggingface.co/papers/{identifier}' if identifier else '')
            published = raw.get('publishedAt') or paper.get('publishedAt') or raw.get('publishedDate') or ''
            timestamp = parse_time(published)
            if timestamp and (today - timestamp.date()).days > 14:
                continue
            authors = paper.get('authors') or []
            item = {'title': title, 'url': safe_url(url), 'summary': summary[:900],
                    'authors': [author.get('name', '') if isinstance(author, dict) else str(author)
                                for author in authors[:5]],
                    'publishedAt': published}
            text = f'{title} {summary}'
            popularity = numeric(paper.get('upvotes', raw.get('likes')))
        elif kind == 'models':
            title = raw.get('modelId') or raw.get('id') or raw.get('title') or ''
            tags = raw.get('tags') or []
            tags = [str(tag) for tag in tags] if isinstance(tags, list) else []
            pipeline = raw.get('pipeline_tag') or ''
            description = raw.get('description') or pipeline
            url = raw.get('link') or (f'https://huggingface.co/{title}' if title else '')
            item = {'title': title, 'url': safe_url(url), 'description': description,
                    'likes': numeric(raw.get('likes')), 'downloads': numeric(raw.get('downloads'))}
            text = ' '.join([title, description, pipeline, ' '.join(tags)])
            # A model's actual task gives stronger evidence than its name alone.
            if pipeline == 'text-generation':
                text += ' large language model'
            elif pipeline == 'image-text-to-text':
                text += ' multimodal vision language'
            elif pipeline in ('depth-estimation', 'image-to-3d', 'text-to-3d'):
                text += ' computer vision 3d generation'
            modified = parse_time(raw.get('lastModified') or raw.get('last_modified'))
            if modified and (today - modified.date()).days > profile.get('activeWithinDays', 180):
                continue
            popularity = numeric(raw.get('likes'))
        else:
            title = raw.get('title') or raw.get('story_title') or ''
            url = raw.get('url') or raw.get('link') or ''
            identifier = raw.get('objectID') or raw.get('id')
            if not url and identifier:
                url = f'https://news.ycombinator.com/item?id={identifier}'
            item = {'title': title, 'url': safe_url(url), 'score': numeric(raw.get('points', raw.get('score')))}
            text = title + ' ' + str(raw.get('story_text') or '')
            popularity = item['score']
        if not item['title'] or not item['url'] or item['url'] in seen:
            continue
        matches = content_matches(text, profile)
        if not matches:
            continue
        seen.add(item['url'])
        item['reasons'] = matches[0][2]
        freshness = 3 if kind == 'models' and raw.get('_trendingCandidate') else 0
        if kind == 'models' and pipeline:
            item['reasons'].append(f'模型任务：{pipeline}')
        ranked.append((matches[0][1] + freshness + min(3, math.log10(1 + popularity)), item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['title']))
    limit = profile.get({'papers': 'paperLimit', 'models': 'modelLimit', 'news': 'newsLimit'}[kind], 4)
    return [item for _, item in ranked[:limit]]


def build_digest(data, searches, supplements, profile, state, statuses, today=None):
    today = today or datetime.now(BEIJING).date()
    candidates = list(searches)
    groups = data.get('githubTrending') or {}
    for repos in groups.values() if isinstance(groups, dict) else []:
        if isinstance(repos, list):
            candidates.extend(project_from_metadata(repo, 'GitHub Trending') for repo in repos
                              if isinstance(repo, dict))
    candidates = merge_projects(candidates)
    categories, deduplicated = choose_projects(candidates, profile, state, today)
    projects = [project for category in categories for project in category['projects']]
    if not projects:
        raise ValueError('未找到未在近期发送过的相关项目；停止发送空日报。')
    digest = {
        'date': today.isoformat(), 'profileLabel': profile['profileLabel'],
        'categories': categories,
        'papers': pick_supplements(supplements.get('papers', []), 'papers', profile, today),
        'models': pick_supplements(supplements.get('models', []), 'models', profile, today),
        'news': pick_supplements(supplements.get('news', []), 'news', profile, today),
        'sourceStatus': sorted(statuses, key=lambda entry: entry['name']),
        'stats': {'candidates': len(candidates), 'selected': len(projects), 'deduplicated': deduplicated},
    }
    # Retain the original action contract so existing validation/consumers work.
    legacy = [{'title': project['title'], 'link': '/' + project['title'],
               'description': project['description'], 'language': project['language'],
               'stars': str(project['stars']),
               'todayStars': str(project['starsToday']) if project['starsToday'] is not None else ''}
              for project in projects]
    return {'githubTrending': {'personalized': legacy}, 'personalizedDigest': digest}, next_state(state, categories, today)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('output/trending.json'))
    parser.add_argument('--output', type=Path, default=Path('output/personalized.json'))
    parser.add_argument('--state', type=Path, default=Path('.github/personalization-state.json'))
    parser.add_argument('--state-output', type=Path, default=Path('output/next-personalization-state.json'))
    parser.add_argument('--profile', type=Path, default=Path('config/interests.json'))
    parser.add_argument('--candidate-multiplier', type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args(argv)
    if args.state.resolve() == args.state_output.resolve():
        raise ValueError('待提交状态必须写入独立文件；原始去重状态只能在成功发信后保存。')
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    state = json.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else {'version': 1, 'lastSent': {}}
    if not isinstance(state, dict) or not isinstance(state.get('lastSent'), dict):
        raise ValueError('去重状态格式无效；停止运行以避免重复发送。')
    today = datetime.now(BEIJING).date()
    statuses = []
    upstream = load_input(args.input, statuses)
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    with ThreadPoolExecutor(max_workers=3) as executor:
        searches_future = executor.submit(search_projects, profile, token, today, statuses)
        seeds_future = executor.submit(seed_projects, profile, token, today, statuses)
        supplements_future = executor.submit(supplemental_data, upstream, statuses)
        searches = searches_future.result() + seeds_future.result()
        supplements = supplements_future.result()
    digest, updated_state = build_digest(upstream, searches, supplements,
                                         candidate_profile(profile, args.candidate_multiplier),
                                         state, statuses, today)
    for destination, value in ((args.output, digest), (args.state_output, updated_state)):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Personalized digest: {digest['personalizedDigest']['stats']['selected']} projects from "
          f"{digest['personalizedDigest']['stats']['candidates']} candidates.")
    print('Delivery state staged; original state was not changed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
