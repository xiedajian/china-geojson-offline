# -*- coding: utf-8 -*-
"""通过 GitHub Git Data API 将本地 git 历史完整推送到远端（绕开被代理封锁的 HTTPS git 传输）。
用法: python push_via_api.py <repo_dir> <owner/repo> <token_file>
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

REPO_DIR, SLUG, TOKEN_FILE = sys.argv[1], sys.argv[2], sys.argv[3]
API = "https://api.github.com"
TOKEN = open(TOKEN_FILE, encoding="ascii").read().strip()
LOG = open(REPO_DIR + "/_api_push.log", "w", encoding="utf-8")


def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def git(*args):
    out = subprocess.run(("git", "-C", REPO_DIR) + args, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError("git " + " ".join(args) + " -> " + out.stderr.decode("utf-8", "replace"))
    return out.stdout


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{API}/repos/{SLUG}/{path}", data=data, method=method)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("User-Agent", "push-via-api")
    req.add_header("Content-Type", "application/json")
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code < 500:
                raise RuntimeError(f"HTTP {e.code} {path}: {detail}")
            last_err = RuntimeError(f"HTTP {e.code} {path}: {detail}")
        except Exception as e:
            last_err = e
        time.sleep(3 * (attempt + 1))
    raise last_err


# 远端必须为空仓库（refs 尚未建立）；Git Data API 不允许对空仓库建 blob，
# 需先用 Contents API（支持空仓库）创建一个引导提交，真实历史随后接在其后
base_sha = None
try:
    refs = api("GET", "git/refs/heads")
    if refs:
        sys.exit("FATAL: remote already has refs, abort to avoid history fork: " + json.dumps(refs)[:200])
except RuntimeError as e:
    if "409" not in str(e) and "404" not in str(e):
        raise
    boot = api("PUT", "contents/.bootstrap", {
        "message": "chore: repo bootstrap (Git Data API requires a non-empty repository)",
        "content": base64.b64encode(b"bootstrap\n").decode(),
    })
    base_sha = boot["commit"]["sha"]
    log(f"bootstrapped empty repo: commit {base_sha[:10]}")
log("OK, starting replay")

shas = git("rev-list", "--reverse", "main").decode().split()
log(f"local history: {len(shas)} commits")

uploaded = set()  # blob sha -> already on server
prev_api_sha = None

for ci, sha in enumerate(shas):
    # 提交元数据
    meta_raw = git("show", "-s", "--format=%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%B", sha).decode("utf-8")
    an, ae, ad, cn, ce, cd, msg = meta_raw.split("\x00", 6)
    # 完整文件树
    ls = git("ls-tree", "-r", sha).decode("utf-8").splitlines()
    tree_entries, new_blobs = [], 0
    for line in ls:
        meta, path = line.split("\t", 1)
        mode, typ, bsha = meta.split()
        path = path.replace('"', "")
        if typ != "blob":
            sys.exit(f"FATAL: non-blob entry {path}")
        if bsha not in uploaded:
            content = git("cat-file", "blob", bsha)
            res = api("POST", "git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"})
            if res["sha"] != bsha:
                raise RuntimeError(f"blob sha mismatch {path}: {res['sha']} != {bsha}")
            uploaded.add(bsha)
            new_blobs += 1
        tree_entries.append({"path": path, "mode": mode, "type": "blob", "sha": bsha})
    tree_res = api("POST", "git/trees", {"tree": tree_entries})
    commit_payload = {
        "message": msg.rstrip("\n"),
        "tree": tree_res["sha"],
        "parents": [base_sha] if base_sha and prev_api_sha is None else ([prev_api_sha] if prev_api_sha else []),
        "author": {"name": an, "email": ae, "date": ad},
        "committer": {"name": cn, "email": ce, "date": cd},
    }
    commit_res = api("POST", "git/commits", commit_payload)
    prev_api_sha = commit_res["sha"]
    log(f"[{ci+1}/{len(shas)}] {msg.splitlines()[0][:60]}  (+{new_blobs} blobs, total {len(uploaded)})  -> {prev_api_sha[:10]}")

# 引导提交已使 refs/heads/main 存在（指向 bootstrap），这里移动到真实历史顶端
try:
    api("PATCH", "git/refs/heads/main", {"sha": prev_api_sha, "force": False})
except RuntimeError:
    api("POST", "git/refs", {"ref": "refs/heads/main", "sha": prev_api_sha})
log(f"REF CREATED: refs/heads/main -> {prev_api_sha}")
log("PUSH_VIA_API_OK")
