# send_email.py
import argparse
import base64
import html
import json
import os
from pathlib import Path
import random
import re
import string
import sys
from datetime import datetime
from urllib.parse import urlsplit

try:
    import yagmail
except ImportError:
    yagmail = None

def send_email(username, password, recipient, subject, body):
    if yagmail is None:
        raise RuntimeError('Install yagmail before sending email.')

    host = os.getenv('SMTP_HOST') or 'smtp.gmail.com'
    try:
        port = int(os.getenv('SMTP_PORT') or '465')
    except ValueError:
        raise ValueError('SMTP_PORT must be an integer.') from None
    if not 1 <= port <= 65535:
        raise ValueError('SMTP_PORT must be between 1 and 65535.')
    smtp_ssl = parse_bool(os.getenv('SMTP_SSL') or 'true')
    smtp_starttls = parse_bool(os.getenv('SMTP_STARTTLS') or 'false')
    if smtp_ssl and smtp_starttls:
        raise ValueError('SMTP_SSL and SMTP_STARTTLS cannot both be enabled.')

    print("Sending email...")
    yag = yagmail.SMTP(
        username, password, host=host, port=port,
        smtp_ssl=smtp_ssl, smtp_starttls=smtp_starttls,
    )
    try:
        result = yag.send(to=recipient, subject=subject, contents=body, prettify_html=False)
        if result is False:
            raise RuntimeError('SMTP did not confirm email delivery.')
    finally:
        yag.close()
    print('Email sent successfully')

def uid():
    """Generate unique id to prevent Gmail pattern detection"""
    return ''.join(random.choices(string.ascii_lowercase, k=4))

def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

def _extract_remote_jobs_date(path):
    match = re.search(r'daily_remote_jobs_(\d{4}-\d{2}-\d{2})\.md$', path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), '%Y-%m-%d').date()
    except ValueError:
        return None

def _find_latest_remote_jobs_report(report_path):
    requested_path = Path(report_path) if report_path else None
    search_dirs = []

    if requested_path:
        search_dirs.append(requested_path.parent)

    repo_remote_jobs_dir = Path.cwd() / 'remote-jobs'
    search_dirs.append(repo_remote_jobs_dir)

    for directory in dict.fromkeys(search_dirs):
        if not directory.exists():
            continue

        reports = []
        for candidate in directory.glob('daily_remote_jobs_*.md'):
            report_date = _extract_remote_jobs_date(candidate)
            if report_date is not None:
                reports.append((report_date, candidate))

        if reports:
            return max(reports, key=lambda item: item[0])[1]

    return None

def load_remote_jobs_report(report_path):
    if not report_path:
        latest_report = _find_latest_remote_jobs_report(report_path)
        if latest_report is None:
            return {
                'status': 'missing',
                'message': '未提供远程岗位报告路径。',
                'path': '',
            }
        report_path = str(latest_report)

    path = Path(report_path)
    if not path.exists():
        latest_report = _find_latest_remote_jobs_report(report_path)
        if latest_report is not None and latest_report != path:
            path = latest_report
        else:
            return {
                'status': 'missing',
                'message': f'未找到远程岗位报告：{path}',
                'path': str(path),
            }

    content = path.read_text(encoding='utf-8').strip()
    title = path.stem.replace('_', ' ')
    for line in content.splitlines():
        if line.startswith('主题：'):
            title = line.replace('主题：', '', 1).strip()
            break

    report = {
        'status': 'ready',
        'title': title,
        'path': str(path),
        'content': content,
    }
    requested_path = Path(report_path)
    if requested_path != path:
        report['requested_path'] = str(requested_path)
        report['fallback_message'] = f'已自动使用最近可用报告：{path.name}'

    return report

def render_remote_jobs_report(report):
    lines = report.get('content', '').splitlines()
    parts = [
        f'<div style="background:#2f2f2f;padding:24px;border-radius:10px;margin:24px 0;color:#f3f4f6;" id="remote-{uid()}">',
        f'<h2 style="color:#f9fafb;margin:0 0 8px 0;font-size:28px;line-height:1.3;">{html.escape(report.get("title", "每日远程岗位推荐"))}</h2>',
        '<p style="color:#d1d5db;margin:0 0 20px 0;font-size:14px;line-height:1.7;">以下内容来自每日远程开发岗位搜索 automation 同步的当日报告。</p>',
    ]

    fallback_message = report.get('fallback_message')
    if fallback_message:
        parts.append(
            f'<p style="margin:0 0 18px 0;padding:10px 12px;background:#111827;border-left:4px solid #60a5fa;color:#bfdbfe;font-size:13px;line-height:1.6;border-radius:6px;">'
            f'{html.escape(fallback_message)}'
            '</p>',
        )

    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            parts.append('</ul>')
            in_list = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith('主题：'):
            close_list()
            continue

        if line.startswith('## '):
            close_list()
            parts.append(
                f'<h3 style="color:#f9fafb;margin:28px 0 18px 0;font-size:24px;line-height:1.35;">'
                f'{html.escape(line[3:])}'
                '</h3>',
            )
            continue

        if re.match(r'^\d+\.\s+', line):
            close_list()
            parts.append(
                f'<p style="margin:0 0 12px 0;color:#f3f4f6;font-size:22px;font-weight:800;line-height:1.55;">'
                f'{html.escape(line)}'
                '</p>',
            )
            continue

        if line.startswith('- '):
            if not in_list:
                parts.append(
                    '<ul style="margin:0 0 18px 28px;padding:0;color:#d1d5db;line-height:1.8;font-size:18px;">',
                )
                in_list = True
            bullet_text = html.escape(line[2:].strip())
            bullet_text = re.sub(
                r'(https?://[^\s<]+)',
                r'<a href="\1" style="color:#60a5fa;text-decoration:underline;">\1</a>',
                bullet_text,
            )
            parts.append(f'<li style="margin:0 0 10px 0;">{bullet_text}</li>')
            continue

        close_list()
        parts.append(
            f'<p style="margin:10px 0 16px 0;color:#d1d5db;font-size:18px;line-height:1.8;">'
            f'{html.escape(line)}'
            '</p>',
        )

    close_list()
    parts.append('</div>')
    return ''.join(parts)

def render_remote_jobs_warning(report):
    message = html.escape(report.get('message', '远程岗位报告暂不可用。'))
    path = report.get('path', '')
    path_hint = ''
    if path:
        path_hint = f'<p style="margin:8px 0 0 0;color:#7f1d1d;font-size:12px;">预期路径：{html.escape(path)}</p>'

    return (
        f'<div style="background:#fef2f2;padding:18px;border-radius:8px;margin:20px 0;border-left:5px solid #dc2626;" id="remote-missing-{uid()}">'
        '<h2 style="color:#991b1b;margin:0 0 8px 0;">💼 远程岗位报告未同步</h2>'
        f'<p style="color:#7f1d1d;margin:0;line-height:1.7;">{message}</p>'
        f'{path_hint}'
        '</div>'
    )

def get_github_all_repos(gh):
    candidates = [
        gh.get('all'),
        gh.get('All'),
        gh.get(''),
    ]
    for repos in candidates:
        if isinstance(repos, list):
            return repos

    return []

def _digest_text(value, limit=None):
    text = ' '.join(str(value if value is not None else '').split())
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + '…'
    return html.escape(text, quote=True)


def _digest_url(value):
    """Allow web links only; never turn scraped values into executable markup."""
    if not isinstance(value, str) or not value:
        return None
    if any(ord(char) < 33 or ord(char) == 127 for char in value) or '\\' in value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        parsed.port
    except ValueError:
        return None
    return html.escape(value, quote=True)


def _digest_link(item):
    title = _digest_text(item.get('title') or '未命名条目', 150)
    url = _digest_url(item.get('url'))
    if url:
        return f'<a href="{url}" style="color:#1d4ed8;text-decoration:none;word-break:break-word;">{title}</a>'
    return title


def _digest_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(str(value).replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    return f'{max(0, number):,}'


def _digest_reasons(item):
    reasons = item.get('reasons') or []
    if not isinstance(reasons, list):
        return ''
    labels = [_digest_text(reason, 80) for reason in reasons[:2] if reason]
    if not labels:
        return ''
    return '<p style="margin:8px 0;color:#166534;font-size:13px;line-height:1.6;">匹配方向：' + '；'.join(labels) + '</p>'


def _digest_source_labels(values):
    labels = {
        'github trending': 'GitHub 热榜', 'github_trending': 'GitHub 热榜',
        'trending': 'GitHub 热榜', 'github search': 'GitHub 领域搜索',
        'github_search': 'GitHub 领域搜索', 'search': 'GitHub 领域搜索',
        'github repository': 'GitHub 仓库资料', 'github_repository': 'GitHub 仓库资料',
        'hugging face': 'Hugging Face', 'huggingface': 'Hugging Face',
        'hugging face models': 'Hugging Face 模型', 'huggingface models': 'Hugging Face 模型',
        'hf models': 'Hugging Face 模型', 'huggingface_models': 'Hugging Face 模型',
        'hugging face papers': 'Hugging Face 论文', 'huggingface papers': 'Hugging Face 论文',
        'hf papers': 'Hugging Face 论文', 'huggingface_papers': 'Hugging Face 论文',
        'hacker news': 'Hacker News', 'hacker_news': 'Hacker News', 'hn': 'Hacker News',
        'arxiv': 'arXiv',
    }
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        label = labels.get(str(value).strip().lower())
        if label and label not in result:
            result.append(label)
    return result


def _digest_section(title, cards):
    return '<h2 style="margin:24px 0 12px;color:#111827;font-size:19px;line-height:1.5;">' + _digest_text(title, 100) + '</h2>' + ''.join(cards)


def _digest_card(parts):
    return '<div style="margin:0 0 12px;padding:16px;border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;">' + ''.join(parts) + '</div>'


def _analysis_text(value, limit):
    """Render only expected prose, never response objects or diagnostics."""
    if isinstance(value, list):
        value = '；'.join(item for item in value if isinstance(item, str))
    return _digest_text(value, limit) if isinstance(value, str) else ''


def _project_document_analysis(project):
    """Return a document analysis card only when reading actually succeeded."""
    analysis = project.get('llmAnalysis')
    if not isinstance(analysis, dict) or analysis.get('status') != 'analyzed':
        return ''
    documents = analysis.get('documentsRead')
    if isinstance(documents, bool) or not isinstance(documents, int) or documents < 1:
        return ''
    # The analysis validator requests a complete functional summary within
    # this bound, so ordinary output is rendered without losing capabilities.
    summary = _analysis_text(analysis.get('summary'), 200)
    if not summary:
        return ''
    parts = [
        '<p style="margin:0;color:#374151;line-height:1.7;word-break:break-word;"><strong>项目简介：</strong>' + summary + '</p>',
    ]
    details = []
    for field, label, limit, fallback in (
        ('useCase', '对你的用途', 140, '资料不足，暂未确定具体接入方式。'),
        ('requirements', '使用条件', 280, '文档未明确，请查看项目说明。'),
        ('limitations', '限制与待确认', 120, '尚未运行验证，实际效果需自行测试。'),
    ):
        text = _analysis_text(analysis.get(field), limit) or fallback
        details.append('<strong>' + label + '：</strong>' + text)
    parts.append('<p style="margin:7px 0 0;color:#374151;font-size:13px;line-height:1.7;word-break:break-word;">' + '<br>'.join(details) + '</p>')
    evidence = analysis.get('evidence')
    citations = []
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            url = _digest_url(item.get('url'))
            quote = _analysis_text(item.get('quote'), 60)
            if not url or not quote:
                continue
            citations.append('<a href="' + url + '" style="color:#1d4ed8;text-decoration:none;">文档依据 ' + str(len(citations) + 1) + '</a>：&ldquo;' + quote + '&rdquo;')
            if len(citations) == 2:
                break
    evidence_note = 'AI 文档分析 · 已读取 ' + str(documents) + ' 份 README / 仓库文档片段'
    if citations:
        evidence_note += '<br>' + '<br>'.join(citations)
    parts.append('<p style="margin:9px 0 0;color:#6b7280;font-size:12px;line-height:1.7;word-break:break-word;">' + evidence_note + '</p>')
    return ''.join(parts)


def render_personalized_digest(digest):
    """Render source metadata and, when present, evidence-linked AI analyses."""
    if not isinstance(digest, dict):
        raise ValueError('personalizedDigest must be a JSON object.')
    categories = digest.get('categories') or []
    if not isinstance(categories, list):
        categories = []
    project_count = 0
    analysis_status = digest.get('analysisStatus')
    analysis_status = analysis_status if isinstance(analysis_status, dict) else {}
    analysis_enabled = analysis_status.get('enabled') is True
    analyzed_count = 0
    fallback_count = 0
    sections = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        projects = category.get('projects') or []
        if not isinstance(projects, list):
            continue
        projects = [project for project in projects if isinstance(project, dict)][:5]
        project_count += len(projects)
        cards = []
        for project in projects:
            parts = ['<h3 style="margin:0 0 8px;font-size:16px;line-height:1.5;">' + _digest_link(project) + '</h3>']
            document_analysis = _project_document_analysis(project)
            if document_analysis:
                analyzed_count += 1
                parts.append(document_analysis)
            else:
                if analysis_enabled or isinstance(project.get('llmAnalysis'), dict):
                    fallback_count += 1
                    parts.append('<p style="margin:0 0 8px;color:#92400e;font-size:12px;line-height:1.6;">本项未完成文档分析，仅按关键词初筛。</p>')
                if project.get('description'):
                    parts.append('<p style="margin:0;color:#374151;line-height:1.7;word-break:break-word;"><strong>项目简介：</strong>' + _digest_text(project['description'], 260) + '</p>')
            parts.append(_digest_reasons(project))
            metadata = []
            stars = _digest_number(project.get('stars'))
            today = _digest_number(project.get('starsToday'))
            if stars is not None:
                metadata.append('总 Stars ' + stars)
            if today is not None:
                metadata.append('今日新增 +' + today)
            if project.get('language'):
                metadata.append('语言：' + _digest_text(project['language'], 35))
            if project.get('updatedAt'):
                metadata.append('更新：' + _digest_text(str(project['updatedAt'])[:10]))
            sources = _digest_source_labels(project.get('sources'))
            if sources:
                metadata.append('来源：' + '、'.join(sources))
            if metadata:
                parts.append('<p style="margin:10px 0 0;color:#6b7280;font-size:12px;line-height:1.8;">' + ' · '.join(metadata) + '</p>')
            cards.append(_digest_card(parts))
        if cards:
            sections.append(_digest_section(category.get('label') or '相关项目', cards))
    if not sections:
        sections.append('<p style="line-height:1.8;color:#4b5563;">本期暂未找到符合关注方向的新项目。</p>')

    for key, heading in (('papers', '相关论文'), ('models', '相关模型'), ('news', '相关科技动态')):
        items = digest.get(key) or []
        if not isinstance(items, list):
            continue
        cards = []
        for item in [item for item in items if isinstance(item, dict)][:5]:
            parts = ['<h3 style="margin:0 0 8px;font-size:16px;line-height:1.5;">' + _digest_link(item) + '</h3>']
            description = item.get('summary') if key == 'papers' else item.get('description')
            if description:
                parts.append('<p style="margin:0;color:#374151;line-height:1.7;word-break:break-word;">' + _digest_text(description, 230) + '</p>')
            parts.append(_digest_reasons(item))
            metadata = []
            if key == 'papers':
                authors = item.get('authors') or []
                if isinstance(authors, list) and authors:
                    metadata.append('作者：' + _digest_text('、'.join(str(author) for author in authors[:3]), 100))
                if item.get('publishedAt'):
                    metadata.append('发表：' + _digest_text(str(item['publishedAt'])[:10]))
            elif key == 'models':
                for field, label in (('downloads', '下载'), ('likes', '喜欢')):
                    number = _digest_number(item.get(field))
                    if number is not None:
                        metadata.append(label + ' ' + number)
            else:
                score = _digest_number(item.get('score'))
                if score is not None:
                    metadata.append('社区热度 ' + score)
            if metadata:
                parts.append('<p style="margin:10px 0 0;color:#6b7280;font-size:12px;line-height:1.8;">' + ' · '.join(metadata) + '</p>')
            cards.append(_digest_card(parts))
        if cards:
            sections.append(_digest_section(heading, cards))

    statuses = digest.get('sourceStatus') or []
    failures = [status for status in statuses if isinstance(status, dict) and status.get('ok') is False] if isinstance(statuses, list) else []
    source_note = ''
    if failures:
        names = _digest_source_labels([status.get('name', '') for status in failures])
        label = '、'.join(names) if names else '部分来源'
        # Collector messages may contain diagnostics: publish only fixed status text.
        source_note = '<p style="margin:12px 0 0;color:#92400e;font-size:12px;line-height:1.7;">来源状态：' + label + '暂不可用，本期展示已成功获取的内容。</p>'
    if analysis_enabled or analyzed_count or fallback_count:
        introduction = '本期 ' + str(project_count) + ' 个匹配项目，其中 ' + str(analyzed_count) + ' 个完成 AI 文档分析。'
        if fallback_count:
            introduction += str(fallback_count) + ' 个仅按关键词初筛，已单独标注。'
        introduction += '每组最多 5 项，宁缺毋滥。论文、模型与科技动态仍基于来源信息筛选，介绍和摘要保留原文。'
        analysis_note = '项目中文分析依据实际读取的 README 与仓库文档片段生成，文档依据可点击核对；未运行项目或验证作者宣称的效果。'
        model = _analysis_text(analysis_status.get('model'), 100)
        if model:
            analysis_note += ' 分析模型：' + model + '。'
    else:
        introduction = '本期 ' + str(project_count) + ' 个匹配项目。每组最多 5 项，宁缺毋滥。按兴趣主题筛选与去重；项目介绍和论文摘要保留原文。'
        analysis_note = '匹配方向依据你关注的主题与关键词生成，供快速筛选；具体能力与使用条件请查看原链接。'
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 科研与工程日报</title></head>'
        '<body style="margin:0;padding:0;background:#f3f4f6;color:#1f2937;font-family:Arial,\'Microsoft YaHei\',sans-serif;font-size:14px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;"><tr><td align="center" style="padding:16px 8px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:700px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;"><tr><td style="padding:24px 18px;">'
        '<p style="margin:0 0 8px;color:#6b7280;font-size:12px;">' + _digest_text(digest.get('date'), 30) + '</p>'
        '<h1 style="margin:0;color:#111827;font-size:25px;line-height:1.5;">' + _digest_text(digest.get('profileLabel') or 'AI 科研与工程生产力', 80) + '</h1>'
        '<p style="margin:12px 0 20px;color:#4b5563;line-height:1.8;">' + introduction + '</p>'
        + ''.join(sections) +
        '<div style="margin-top:24px;padding-top:14px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px;line-height:1.8;">'
        '<p style="margin:0;">总 Stars 为累计收藏数；今日新增仅在 GitHub 热榜提供数据时显示。领域搜索补充项目可能没有今日增量。</p>'
        '<p style="margin:6px 0 0;">' + analysis_note + '</p>'
        + source_note + '</div></td></tr></table></td></tr></table></body></html>'
    )


def format_email(data, remote_jobs_report=None):
    if 'personalizedDigest' in data:
        return render_personalized_digest(data['personalizedDigest'])
    html = f'''<html><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#fafafa;">
<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:30px;border-radius:12px;margin-bottom:20px;">
<h1 style="color:#fff;text-align:center;margin:0;">🔥 Tech Trending Daily</h1>
<p style="color:#e0e0e0;text-align:center;margin:10px 0 0 0;">{uid()}</p>
</div>'''

    # GitHub Trending - All languages with detailed cards
    if 'githubTrending' in data:
        gh = data['githubTrending']
        all_repos = get_github_all_repos(gh)
        
        if all_repos:
            html += f'<div style="background:#24292e;padding:20px;border-radius:8px;margin-bottom:15px;" id="gh-{uid()}">'
            html += '<h2 style="color:#fff;margin:0 0 15px 0;">📦 GitHub Trending - All</h2>'
            for i, r in enumerate(all_repos[:10]):
                desc = (r.get("description","") or "")[:70]
                html += f'<div style="background:#{"2d333b" if i%2==0 else "22272e"};padding:12px;margin:5px 0;border-radius:4px;border-left:3px solid #58a6ff;">'
                html += f'<a href="https://github.com{r["link"]}" style="color:#58a6ff;font-weight:bold;text-decoration:none;">{r["title"]}</a>'
                html += f'<span style="color:#8b949e;float:right;">⭐{r["stars"]} | +{r["todayStars"]}</span>'
                html += f'<p style="color:#8b949e;margin:5px 0 0 0;font-size:13px;">{desc}</p></div>'
            html += '</div>'
        
        # Other languages - also detailed
        lang_colors = {'typescript':'#3178c6','python':'#3572A5','go':'#00ADD8','rust':'#dea584','javascript':'#f1e05a'}
        for lang in sorted([k for k in gh.keys() if k and k.lower() not in ['all', '']])[:3]:
            repos = gh[lang][:10]
            color = lang_colors.get(lang.lower(),'#6e7681')
            html += f'<div style="background:#1a1a2e;padding:15px;border-radius:8px;margin-bottom:10px;border-top:3px solid {color};" id="lang-{uid()}">'
            html += f'<h3 style="color:{color};margin:0 0 10px 0;">📦 {lang.capitalize()}</h3>'
            for i, r in enumerate(repos):
                desc = (r.get("description","") or "")[:60]
                html += f'<div style="padding:10px;margin:5px 0;background:#{"252540" if i%2==0 else "1e1e35"};border-radius:4px;">'
                html += f'<a href="https://github.com{r["link"]}" style="color:#e0e0e0;text-decoration:none;font-weight:bold;">{r["title"]}</a>'
                html += f'<span style="color:{color};float:right;">⭐{r["stars"]} | +{r["todayStars"]}</span>'
                if desc:
                    html += f'<p style="color:#888;margin:5px 0 0 0;font-size:12px;">{desc}</p>'
                html += '</div>'
            html += '</div>'

    # HuggingFace - orange theme
    models = data.get('huggingFaceModels', [])
    if models:
        html += f'<div style="background:#fff3e0;padding:20px;border-radius:8px;margin:20px 0;border-left:5px solid #ff9800;" id="hf-{uid()}">'
        html += '<h2 style="color:#e65100;margin:0 0 15px 0;">🤖 HuggingFace Hot Models</h2>'
        html += '<table style="width:100%;border-collapse:collapse;">'
        html += '<tr style="background:#ffe0b2;"><th style="padding:10px;text-align:left;">Model</th><th style="padding:10px;">Downloads</th><th style="padding:10px;">Likes</th></tr>'
        for i, m in enumerate(models[:10]):
            bg = '#fff8e1' if i%2==0 else '#fff3e0'
            html += f'<tr style="background:{bg};"><td style="padding:8px;"><a href="{m["link"]}" style="color:#e65100;">{m["modelId"]}</a></td><td style="padding:8px;text-align:center;">{m.get("downloads",0):,}</td><td style="padding:8px;text-align:center;">❤️{m.get("likes",0)}</td></tr>'
        html += '</table></div>'

    # Hacker News - distinct orange cards
    stories = data.get('hackerNewsStories', [])
    if stories:
        html += f'<div style="background:#fff5f0;padding:20px;border-radius:8px;margin:20px 0;" id="hn-{uid()}">'
        html += '<h2 style="color:#ff6600;margin:0 0 15px 0;border-bottom:2px solid #ff6600;padding-bottom:10px;">📰 Hacker News Top Stories</h2>'
        for i, s in enumerate(stories[:10]):
            html += f'<article style="padding:10px;margin:8px 0;background:#{"fffaf5" if i%2==0 else "fff0e5"};border-radius:4px;">'
            html += f'<a href="{s["link"]}" style="color:#ff6600;font-size:15px;text-decoration:none;font-weight:500;">{s["title"]}</a>'
            html += f'<footer style="color:#828282;font-size:12px;margin-top:5px;">▲{s["score"]} pts by {s["by"]} | {s.get("descendants",0)} comments</footer></article>'
        html += '</div>'

    # Dev.to - purple theme
    articles = data.get('devToArticles', [])
    if articles:
        html += f'<div style="background:#f3e5f5;padding:20px;border-radius:8px;margin:20px 0;" id="dev-{uid()}">'
        html += '<h2 style="color:#7b1fa2;margin:0 0 15px 0;">📝 Dev.to Popular Articles</h2>'
        html += '<ul style="list-style:none;padding:0;margin:0;">'
        for a in articles[:10]:
            html += f'<li style="padding:10px;border-bottom:1px dashed #ce93d8;"><a href="{a["url"]}" style="color:#7b1fa2;text-decoration:none;">{a["title"]}</a> <small style="color:#9c27b0;">by {a["user"]["name"]} • ❤️{a.get("publicReactionsCount",0)}</small></li>'
        html += '</ul></div>'

    # AI Papers - deep purple
    papers = data.get('aiPapers', [])
    if papers:
        html += f'<div style="background:#ede7f6;padding:20px;border-radius:8px;margin:20px 0;" id="paper-{uid()}">'
        html += '<h2 style="color:#512da8;margin:0 0 15px 0;">📄 Latest AI Research Papers</h2>'
        html += '<ol style="padding-left:20px;margin:0;">'
        for p in papers[:10]:
            authors = ", ".join(p.get("authors",[])[:2])
            html += f'<li style="padding:8px 0;color:#5e35b1;"><a href="{p["url"]}" style="color:#512da8;text-decoration:none;">{p["title"]}</a><br/><small style="color:#7e57c2;">{authors} • ❤️{p.get("likes",0)}</small></li>'
        html += '</ol></div>'

    # Indie Revenue - green theme with detailed cards including links and descriptions
    revenues = data.get('indieRevenue', [])
    if revenues:
        html += f'<div style="background:#e8f5e9;padding:20px;border-radius:8px;margin:20px 0;" id="indie-{uid()}">'
        html += '<h2 style="color:#2e7d32;margin:0 0 15px 0;">💰 Indie Hackers Revenue Report</h2>'
        for i, r in enumerate(revenues[:10]):
            url = r.get("url", "")
            desc = r.get("description", "")[:80]
            founders = ", ".join(r.get("founders", [])[:2]) if r.get("founders") else ""
            bg = '#f1f8e9' if i%2==0 else '#e8f5e9'
            html += f'<div style="background:{bg};padding:15px;margin:8px 0;border-radius:6px;border-left:4px solid #4caf50;">'
            html += f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            html += f'<span style="background:#4caf50;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;">#{r.get("rank","-")}</span>'
            html += f'<span style="color:#2e7d32;font-weight:bold;font-size:16px;">${r.get("mrr",0):,.0f}/mo</span>'
            html += '</div>'
            if url:
                html += f'<h3 style="margin:10px 0 5px 0;"><a href="{url}" style="color:#1b5e20;text-decoration:none;">{r["name"]} ↗</a></h3>'
            else:
                html += f'<h3 style="margin:10px 0 5px 0;color:#1b5e20;">{r["name"]}</h3>'
            if desc:
                html += f'<p style="color:#558b2f;margin:5px 0;font-size:13px;">{desc}</p>'
            html += f'<div style="display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:#689f38;">'
            html += f'<span>ARR: ${r.get("arr",0):,.0f}</span>'
            if founders:
                html += f'<span>👤 {founders}</span>'
            html += '</div></div>'
        html += '</div>'

    if remote_jobs_report:
        if remote_jobs_report.get('status') == 'ready':
            html += render_remote_jobs_report(remote_jobs_report)
        else:
            html += render_remote_jobs_warning(remote_jobs_report)

    html += f'<p style="text-align:center;color:#999;font-size:12px;margin-top:30px;">Generated by Tech Trending Daily 🚀 [{uid()}]</p>'
    html += '</body></html>'
    return html

def main(argv=None):
    parser = argparse.ArgumentParser(description='Render or send a trending digest.')
    # Keep the original positional interface for existing callers. New workflows
    # pass credentials through environment variables instead of process arguments.
    for name in ('username', 'password', 'recipient', 'subject', 'data_base64',
                 'enable_remote_jobs', 'remote_jobs_path'):
        parser.add_argument(name, nargs='?')
    parser.add_argument('--dry-run', action='store_true', help='Write HTML without sending email.')
    parser.add_argument('--output', default=os.getenv('EMAIL_PREVIEW_PATH') or 'output/digest-preview.html')
    args = parser.parse_args(argv)

    username = args.username or os.getenv('SMTP_USERNAME', '')
    password = args.password or os.getenv('SMTP_PASSWORD', '')
    recipient = args.recipient or os.getenv('SMTP_TO', '')
    subject = args.subject or os.getenv('EMAIL_SUBJECT') or 'Tech Trending Daily'
    data_file = os.getenv('TRENDING_DATA_FILE')
    data_base64 = args.data_base64 or os.getenv('TRENDING_DATA', '')
    if data_file:
        data = json.loads(Path(data_file).read_text(encoding='utf-8'))
    elif data_base64:
        try:
            decoded_bytes = base64.b64decode(data_base64, altchars=b'-_', validate=True)
            data = json.loads(decoded_bytes.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ValueError('TRENDING_DATA must contain base64-encoded JSON.') from None
    else:
        raise ValueError('Set TRENDING_DATA_FILE or TRENDING_DATA before rendering a digest.')
    if not isinstance(data, dict):
        raise ValueError('Trending data must be a JSON object.')

    enable_remote_jobs = parse_bool(
        args.enable_remote_jobs if args.enable_remote_jobs is not None
        else os.getenv('ENABLE_REMOTE_JOBS')
    )
    remote_jobs_path = (
        args.remote_jobs_path if args.remote_jobs_path is not None
        else os.getenv('REMOTE_JOBS_REPORT_PATH', '')
    )
    remote_jobs_report = None
    if enable_remote_jobs:
        remote_jobs_report = load_remote_jobs_report(remote_jobs_path)
        print(f"Remote jobs report status: {remote_jobs_report['status']}")

    content = format_email(data, remote_jobs_report)
    
    content_size = len(content.encode('utf-8'))
    print(f"Email HTML size: {content_size} bytes ({content_size/1024:.1f} KB)")
    if args.dry_run:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding='utf-8')
        print(f'Dry run complete. Preview: {output_path}')
        return 0

    missing = [name for name, value in (
        ('SMTP_USERNAME', username), ('SMTP_PASSWORD', password), ('SMTP_TO', recipient)
    ) if not value]
    if missing:
        raise ValueError('Missing email settings: ' + ', '.join(missing))
    send_email(username, password, recipient, subject, content)
    return 0


if __name__ == '__main__':
    sys.exit(main())
