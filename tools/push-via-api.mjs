#!/usr/bin/env node
// Push commits through the GitHub REST API instead of `git push`.
//
// Why this exists: on some networks `github.com:443` accepts the TCP connection
// and then resets the HTTPS one, so `git push` dies after a long timeout while
// `api.github.com` keeps working. This walks the same commits the way the git
// wire protocol would - blobs, trees, commits, then the ref - over the API.
//
// The commit objects are rebuilt with the original author *and* committer, so a
// commit made in UTC comes out with the same SHA. GitHub normalises the
// committer date to +0000, though, so a commit made in another time zone gets a
// new SHA even though its tree is identical. When that happens this tool moves
// the local branch onto the new commit, so the two sides stay in step and the
// working tree does not change at all.
//
//   node tools/push-via-api.mjs                  # dry run, shows what would go
//   node tools/push-via-api.mjs --yes            # actually push
//   node tools/push-via-api.mjs --yes --tag v0.3.0
//
// Token: $GH_TOKEN / $GITHUB_TOKEN, else whatever `git credential fill` has
// stored for github.com. Nothing is written to disk.

import { execFileSync } from 'node:child_process';
import { Buffer } from 'node:buffer';
import process from 'node:process';

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const opt = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const REMOTE = opt('--remote', 'origin');
const BRANCH = opt('--branch', 'main');
const TAG = opt('--tag', '');
const YES = flag('--yes');
const NO_ADOPT = flag('--no-adopt');
const VERBOSE = flag('--verbose');
const API = 'https://api.github.com';

function git(...a) {
  return execFileSync('git', a, { encoding: 'utf8', maxBuffer: 64 << 20 }).trim();
}
function gitBuf(...a) {
  return execFileSync('git', a, { maxBuffer: 256 << 20 });
}
function die(msg) {
  console.error('✗ ' + msg);
  process.exit(1);
}

// ---------------------------------------------------------------- credentials
function token() {
  if (process.env.GH_TOKEN) return process.env.GH_TOKEN.trim();
  if (process.env.GITHUB_TOKEN) return process.env.GITHUB_TOKEN.trim();
  try {
    const out = execFileSync('git', ['credential', 'fill'], {
      input: 'protocol=https\nhost=github.com\n\n',
      encoding: 'utf8',
    });
    const m = out.match(/^password=(.+)$/m);
    if (m) return m[1].trim();
  } catch {}
  die('找不到 token：设置 GH_TOKEN，或用 git credential 存一份 github.com 的凭据');
}
const TOKEN = token();

async function api(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: {
      Authorization: 'token ' + TOKEN,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'mousecam-push-via-api',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${method} ${path} -> ${res.status} ${text.slice(0, 300)}`);
  }
  return text ? JSON.parse(text) : {};
}

// ------------------------------------------------------------------- the repo
function slug() {
  const url = git('remote', 'get-url', REMOTE);
  // handles https://github.com/o/r(.git), https://gh-proxy.com/https://github.com/o/r
  const m = url.match(/github\.com[/:]+([^/]+)\/([^/]+?)(?:\.git)?$/);
  if (!m) die(`无法从 ${url} 解析出 owner/repo`);
  return `${m[1]}/${m[2]}`;
}

const REPO = slug();

function remoteHead() {
  // ls-remote works over the read-only mirror, so it is a reliable view of the
  // remote even when git push cannot reach github.com
  const out = git('ls-remote', REMOTE, `refs/heads/${BRANCH}`);
  if (!out) return null;
  return out.split(/\s+/)[0];
}

// ------------------------------------------------------------ git object read
// One commit, read straight out of the object store so the message and the
// identities are byte-for-byte what git recorded.
function readCommit(sha) {
  const raw = gitBuf('cat-file', 'commit', sha).toString('utf8');
  const split = raw.indexOf('\n\n');
  const headers = raw.slice(0, split).split('\n');
  const message = raw.slice(split + 2);

  const people = {};
  for (const line of headers) {
    if (line.startsWith('author ')) people.author = parsePerson(line.slice(7));
    if (line.startsWith('committer ')) people.committer = parsePerson(line.slice(10));
  }
  return { message, ...people };
}

// "Name <mail> 1699999999 +0800" -> { name, email, date: ISO }
function parsePerson(s) {
  const m = s.match(/^(.*?)\s*<(.+?)>\s*(\d+)\s*([+-]\d{4})$/);
  if (!m) return { name: s, email: '', date: new Date().toISOString() };
  const [, name, email, secs, tz] = m;
  const sign = tz[0] === '-' ? -1 : 1;
  const offMin = sign * (Number(tz.slice(1, 3)) * 60 + Number(tz.slice(3, 5)));
  const d = new Date((Number(secs) + offMin * 60) * 1000);
  return { name, email, date: d.toISOString().replace(/\.\d{3}Z$/, 'Z') };
}

// name-status between two trees, not between a commit and its parent: a merge
// commit has no single-parent diff, so the changes it resolved would otherwise
// be lost and the branch would be pushed missing them.
// -z keeps paths with spaces intact.
function changedFiles(from, sha) {
  const out = gitBuf('diff-tree', '--no-commit-id', '-r', '--name-status', '-z', from, sha);
  const parts = out.toString('utf8').split('\0').filter((x) => x.length);
  const rows = [];
  for (let i = 0; i < parts.length; ) {
    const status = parts[i++];
    if (status.startsWith('R') || status.startsWith('C')) {
      rows.push({ status, from: parts[i++], path: parts[i++] });
    } else {
      rows.push({ status, path: parts[i++] });
    }
  }
  return rows;
}

function modeOf(sha, path) {
  const out = git('ls-tree', sha, '--', path);
  const m = out.match(/^(\d{6}) /);
  return m ? m[1] : '100644';
}

// ----------------------------------------------------------------- variables
const head = remoteHead();
const localHead = git('rev-parse', BRANCH);
if (!head) die(`远端没有 ${BRANCH} 分支`);

if (head === localHead) {
  console.log(`✓ 已经是最新：${BRANCH} 在 ${localHead.slice(0, 8)}`);
  if (TAG) await pushTag();
  process.exit(0);
}

// fast-forward only: if the remote has work we do not, refuse rather than rewrite
try {
  git('merge-base', '--is-ancestor', head, localHead);
} catch {
  die(`远端 ${BRANCH}（${head.slice(0, 8)}）不在本地历史里，先 git pull；这个工具不做强推`);
}

const commits = git('rev-list', '--reverse', `${head}..${localHead}`).split('\n').filter(Boolean);
console.log(`仓库   ${REPO}`);
console.log(`远端   ${BRANCH} @ ${head.slice(0, 8)}`);
console.log(`本地   ${BRANCH} @ ${localHead.slice(0, 8)}`);
console.log(`提交   ${commits.length} 个`);
for (const c of commits) {
  console.log(`  ${c.slice(0, 8)}  ${git('log', '-1', '--format=%s', c)}`);
}

if (!YES) {
  console.log('\n这是预演。加 --yes 才会真的推送。');
  process.exit(0);
}

// -------------------------------------------------------------------- upload
let parent = head;
let parentTree = (await api('GET', `/repos/${REPO}/git/commits/${parent}`)).tree.sha;
let rewritten = 0;
let deleted = 0;
let created = 0;
// local commit -> the commit the server now has for it, so a merge can point at
// both of its parents after they have been rewritten.
const rewrittenShas = new Map();
let prev = head;

for (const sha of commits) {
  const { message, author, committer } = readCommit(sha);
  const rows = changedFiles(prev, sha);
  const entries = [];

  for (const row of rows) {
    if (row.status.startsWith('R') || row.status.startsWith('C')) {
      // a rename removes the old path as well as adding the new one
      entries.push({ path: row.from, mode: '100644', type: 'blob', sha: null });
      deleted++;
    }
    if (row.status.startsWith('D')) {
      entries.push({ path: row.path, mode: '100644', type: 'blob', sha: null });
      deleted++;
      continue;
    }
    const blob = await api('POST', `/repos/${REPO}/git/blobs`, {
      content: gitBuf('cat-file', 'blob', `${sha}:${row.path}`).toString('base64'),
      encoding: 'base64',
    });
    entries.push({ path: row.path, mode: modeOf(sha, row.path), type: 'blob', sha: blob.sha });
    created++;
  }

  const tree = await api('POST', `/repos/${REPO}/git/trees`, { base_tree: parentTree, tree: entries });
  // Every parent of the original commit, not just the first: a merge that lost
  // its second parent is a different commit and, worse, a different tree.
  const localParents = git('rev-list', '--parents', '-n', '1', sha).split(' ').slice(1);
  const parents = localParents.map((p) => rewrittenShas.get(p) || p);
  const commit = await api('POST', `/repos/${REPO}/git/commits`, {
    message,
    tree: tree.sha,
    parents,
    author,
    committer,
  });
  rewrittenShas.set(sha, commit.sha);
  prev = sha;

  const same = commit.sha === sha;
  if (!same) rewritten++;
  console.log(`  → ${commit.sha.slice(0, 8)}  ${same ? 'SHA 一致' : 'SHA 变了（服务端重建）'}  ${message.split('\n')[0]}`);
  parent = commit.sha;
  parentTree = tree.sha;
}

await api('PATCH', `/repos/${REPO}/git/refs/heads/${BRANCH}`, { sha: parent });

console.log(`\n✓ 已推送 ${commits.length} 个提交到 ${REPO}:${BRANCH}`);
console.log(`  blob ${created} 个，删除 ${deleted} 个，SHA 变化 ${rewritten} 个`);

if (!rewritten) {
  console.log('  本地与远端 SHA 一致');
} else if (NO_ADOPT) {
  console.log('\n服务端重建了提交，本地需要手动对齐：');
  console.log(`  git fetch ${REMOTE} && git reset --hard ${REMOTE}/${BRANCH}`);
} else if (git('status', '--porcelain')) {
  console.log('\n服务端重建了提交，但工作区有未提交的改动，没有动本地：');
  console.log(`  git fetch ${REMOTE} && git reset --hard ${REMOTE}/${BRANCH}`);
} else {
  // The tree is byte-identical; only the committer's time zone differs, so
  // moving the branch onto the new commit leaves every file untouched.
  git('fetch', REMOTE, BRANCH);
  git('reset', '--hard', `${REMOTE}/${BRANCH}`);
  console.log(`✓ 本地已对齐到 ${git('rev-parse', '--short', BRANCH)}（文件内容未变）`);
}

if (TAG) await pushTag();

// ----------------------------------------------------------------------- tag
async function pushTag() {
  const check = git('tag', '-l', TAG);
  if (!check) die(`本地没有 tag ${TAG}`);
  const existing = await fetch(`${API}/repos/${REPO}/git/ref/tags/${TAG}`, {
    headers: { Authorization: 'token ' + TOKEN, 'User-Agent': 'mousecam-push-via-api' },
  });
  if (existing.ok) {
    console.log(`✓ tag ${TAG} 已存在于远端`);
    return;
  }
  const target = git('rev-parse', `${TAG}^{commit}`);
  const type = git('cat-file', '-t', TAG);
  if (type === 'tag') {
    const raw = gitBuf('cat-file', 'tag', TAG).toString('utf8');
    const body = raw.slice(raw.indexOf('\n\n') + 2);
    const obj = await api('POST', `/repos/${REPO}/git/tags`, {
      tag: TAG,
      message: body,
      object: target,
      type: 'commit',
    });
    await api('POST', `/repos/${REPO}/git/refs`, { ref: `refs/tags/${TAG}`, sha: obj.sha });
  } else {
    await api('POST', `/repos/${REPO}/git/refs`, { ref: `refs/tags/${TAG}`, sha: target });
  }
  console.log(`✓ tag ${TAG} 已推送`);
}
