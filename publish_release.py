#!/usr/bin/env python3
"""Create/update the GitHub Release for the current mod version and upload the zip.

Why not the GitHub MCP: that connector only exposes repo/PR/issue tools.
Creating a Release and uploading assets needs the Releases REST API with a
token that has ``contents: write``, so this script talks to the API directly.

Usage:
    set GH_TOKEN=ghp_xxx        # Windows PowerShell: $env:GH_TOKEN = 'ghp_xxx'
    python publish_release.py --notes-file notes.md

Token is read from ``GH_TOKEN`` or ``GITHUB_TOKEN``; it is never written to
disk. The tag must already exist locally, because creating a Release for a
missing tag would make GitHub tag the default branch instead.
"""

from __future__ import print_function

import argparse
import json
import os
import re
import subprocess
import sys

try:
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 is not supported here
    sys.exit('publish_release.py needs Python 3 (build.py uses 2.7 bytecode only).')

API = 'https://api.github.com'
UPLOADS = 'https://uploads.github.com'
ROOT = os.path.dirname(os.path.abspath(__file__))


def read_version():
    path = os.path.join(ROOT, 'build.py')
    with open(path, encoding='utf-8') as fh:
        match = re.search(r"^MOD_VERSION\s*=\s*'([^']+)'", fh.read(), re.M)
    if not match:
        raise SystemExit('cannot find MOD_VERSION in build.py')
    return match.group(1)


def default_repo():
    try:
        url = subprocess.check_output(
            ['git', 'remote', 'get-url', 'origin'], cwd=ROOT
        ).decode('utf-8').strip()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit('cannot read git remote; pass --repo owner/name')
    match = re.search(r'github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$', url)
    if not match:
        raise SystemExit('origin is not a GitHub remote; pass --repo owner/name')
    return '%s/%s' % (match.group(1), match.group(2))


def call(method, url, token, payload=None, data=None, content_type=None,
         accept='application/vnd.github+json'):
    headers = {
        'Authorization': 'Bearer %s' % token,
        'Accept': accept,
        'User-Agent': 'streamer-mode-release',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if content_type:
        headers['Content-Type'] = content_type
    body = data
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')
        raise SystemExit('%s %s failed: HTTP %s\n%s' % (method, url, exc.code, detail))
    except URLError as exc:
        raise SystemExit('%s %s failed: %s' % (method, url, exc.reason))
    return json.loads(raw.decode('utf-8')) if raw else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', help='owner/name (default: origin remote)')
    parser.add_argument('--tag', help='release tag (default: v<MOD_VERSION>)')
    parser.add_argument('--title', help='release title (default: tag)')
    parser.add_argument('--notes', default='', help='release body text')
    parser.add_argument('--notes-file', help='read release body from this file')
    parser.add_argument('--asset', help='file to upload (default: build/<mod>_<ver>.zip)')
    parser.add_argument('--draft', action='store_true', help='create as draft')
    parser.add_argument('--prerelease', action='store_true')
    parser.add_argument('--clobber', action='store_true',
                        help='replace an already uploaded asset')
    args = parser.parse_args(argv)

    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise SystemExit('set GH_TOKEN (fine-grained token with Contents: read+write)')

    version = read_version()
    repo = args.repo or default_repo()
    tag = args.tag or 'v%s' % version
    title = args.title or 'Streamer Mode %s' % version
    asset = args.asset or os.path.join(
        ROOT, 'build', 'akemi.streamermode_%s.zip' % version)

    if not os.path.isfile(asset):
        raise SystemExit('%s not found; run `python build.py` first' % asset)

    try:
        subprocess.check_output(['git', 'rev-parse', '--verify', 'refs/tags/%s' % tag],
                                cwd=ROOT, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit('tag %s does not exist; create and push it first' % tag)

    body = args.notes
    if args.notes_file:
        with open(args.notes_file, encoding='utf-8') as fh:
            body = fh.read().strip()
    if not body:
        body = 'Streamer Mode %s' % version

    release = None
    try:
        release = call('GET', '%s/repos/%s/releases/tags/%s' % (API, repo, tag), token)
    except SystemExit as exc:
        if 'HTTP 404' not in str(exc):
            raise

    if release is None:
        try:
            call('GET', '%s/repos/%s/git/ref/tags/%s' % (API, repo, tag), token)
        except SystemExit as exc:
            if 'HTTP 404' not in str(exc):
                raise
            raise SystemExit('tag %s is not on the remote; run `git push origin %s` first'
                             % (tag, tag))

    if release is None:
        release = call('POST', '%s/repos/%s/releases' % (API, repo), token, payload={
            'tag_name': tag,
            'name': title,
            'body': body,
            'draft': args.draft,
            'prerelease': args.prerelease,
        })
        print('created release %s' % release['html_url'])
    else:
        release = call('PATCH', release['url'], token, payload={
            'name': title,
            'body': body,
            'draft': args.draft,
            'prerelease': args.prerelease,
        })
        print('updated release %s' % release['html_url'])

    name = os.path.basename(asset)
    assets = call('GET', '%s/repos/%s/releases/%s/assets' % (API, repo, release['id']), token)
    for existing in assets:
        if existing['name'] != name:
            continue
        if not args.clobber:
            raise SystemExit('asset %s already uploaded; pass --clobber to replace' % name)
        call('DELETE', existing['url'], token)
        print('deleted old asset %s' % name)

    with open(asset, 'rb') as fh:
        data = fh.read()
    uploaded = call(
        'POST',
        '%s/repos/%s/releases/%s/assets?name=%s' % (
            UPLOADS, repo, release['id'], quote(name)),
        token,
        data=data,
        content_type='application/zip',
    )
    print('uploaded %s (%d bytes)' % (uploaded['name'], uploaded['size']))
    print(release['html_url'])


if __name__ == '__main__':
    main()
