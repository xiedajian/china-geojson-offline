# -*- coding: utf-8 -*-
"""
china-geojson-offline · 一键更新数据集
=====================================
从阿里 DataV.GeoAtlas (areas_v3) 拉取全国行政区划 GeoJSON，
写入项目 data/ 目录，并重建 index.json 下钻索引。

用法:
    python scripts/fetch_data.py                 # 增量更新（已有文件跳过）
    python scripts/fetch_data.py --force         # 全量重新下载
    python scripts/fetch_data.py --out 其他目录   # 自定义输出目录

仅依赖 Python 3.8+ 标准库，无需安装任何包。
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = "https://geo.datav.aliyun.com/areas_v3/bound/{}.json"

# 34 个省级行政区 adcode（含港澳台）
PROVINCE_CODES = [
    "110000", "120000", "130000", "140000", "150000",
    "210000", "220000", "230000", "310000", "320000",
    "330000", "340000", "350000", "360000", "370000",
    "410000", "420000", "430000", "440000", "450000",
    "460000", "500000", "510000", "520000", "530000",
    "540000", "610000", "620000", "630000", "640000",
    "650000", "710000", "810000", "820000",
]

UA = {"User-Agent": "china-geojson-offline/1.0"}


def fetch(adcode: str, dest: str, force: bool):
    """下载 adcode 的边界 GeoJSON：优先 _full 版（含子级），404 则回退普通版。
    成功返回 (dict, used_full)；文件已存在且非 force 时跳过返回 (None, None)。"""
    if not force and os.path.exists(dest) and os.path.getsize(dest) > 500:
        with open(dest, encoding="utf-8") as f:
            return json.load(f), None
    for suffix in ("_full", ""):
        try:
            req = urllib.request.Request(BASE.format(adcode + suffix), headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            if data.get("features"):
                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
                return data, (suffix == "_full")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            time.sleep(0.3)
    return None, None


def main():
    ap = argparse.ArgumentParser(description="一键更新中国 GeoJSON 离线数据集")
    ap.add_argument("--out", default=None, help="输出目录（默认: 仓库根目录/data）")
    ap.add_argument("--workers", type=int, default=16, help="并发线程数（默认 16）")
    ap.add_argument("--force", action="store_true", help="强制重新下载全部文件")
    args = ap.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.abspath(args.out) if args.out else os.path.join(repo_root, "data")
    city_dir = os.path.join(out_dir, "cities")
    os.makedirs(city_dir, exist_ok=True)

    index = {"100000": {"name": "中国", "level": "country",
                        "file": "100000_full.json", "children": []}}
    failed = []

    # 1) 全国（含全部省级边界与九段线）
    print("[1/3] 下载全国边界 100000_full.json ...")
    china, _ = fetch("100000", os.path.join(out_dir, "100000_full.json"), args.force)
    if china is None:
        sys.exit("× 全国边界下载失败，请检查网络后重试")

    # 2) 省级 + 市级
    print("[2/3] 下载 34 个省级行政区及其下辖市 ...")
    for code in PROVINCE_CODES:
        data, used_full = fetch(code, os.path.join(out_dir, f"{code}.json"), args.force)
        if data is None:
            failed.append(code)
            print(f"  × {code} 下载失败")
            continue
        node = index.setdefault(code, {"name": None, "level": "province",
                                       "file": f"{code}.json", "children": []})
        children = []
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            ad, name = p.get("adcode"), p.get("name")
            if not ad or str(ad) == code:
                continue
            if p.get("level") == "district":  # 直辖市：省级下直接挂区
                index[str(ad)] = {"name": name, "level": "district",
                                  "parent": code, "file": None, "children": []}
            else:
                index[str(ad)] = {"name": name, "level": "city", "parent": code,
                                  "file": f"cities/{ad}.json", "children": []}
                child_data, _ = fetch(str(ad), os.path.join(city_dir, f"{ad}.json"),
                                      args.force)
                if child_data is None:
                    failed.append(str(ad))
                    index[str(ad)]["file"] = None
                else:
                    for ft in child_data.get("features", []):
                        cp = ft.get("properties", {})
                        cad = cp.get("adcode")
                        if not cad:
                            continue
                        # 区县也要建索引节点，否则演示层「市→区」无法点击
                        index.setdefault(str(cad), {
                            "name": cp.get("name"), "level": "district",
                            "parent": str(ad), "file": None, "children": []})
                        index[str(ad)]["children"].append(str(cad))
            children.append(str(ad))
        node["children"] = children
        index["100000"]["children"].append(code)  # 全国层的下钻子级

    # 从全国数据补齐省级名称
    for feat in china["features"]:
        p = feat["properties"]
        if p.get("adcode") and str(p["adcode"]) in index:
            index[str(p["adcode"])]["name"] = p.get("name")

    # 3) 写索引
    print("[3/3] 生成下钻索引 index.json ...")
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    n_prov = sum(1 for v in index.values() if v["level"] == "province")
    n_city = sum(1 for v in index.values() if v["level"] == "city")
    n_dist = sum(1 for v in index.values() if v["level"] == "district")
    print(f"\n√ 完成: {n_prov} 省 / {n_city} 市 / {n_dist} 区（直辖市直挂）, "
          f"索引节点 {len(index)} 个")
    if failed:
        print(f"× 以下 {len(failed)} 个 adcode 下载失败: {','.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
