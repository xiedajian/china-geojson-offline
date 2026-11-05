# china-geojson-offline · 中国行政区划 GeoJSON 离线数据集

完全离线的中国行政区划 GeoJSON 数据集：**全国 → 省 → 市 → 区县**四级齐备，
附带**一键更新脚本**与一个 **ECharts 下钻演示**。数据本身与渲染引擎无关，
可直接用于 ECharts、Leaflet、MapLibre GL、OpenLayers、D3 等任意支持 GeoJSON 的引擎。

[在线演示（ECharts 下钻）](#演示echarts-下钻) · [数据结构](#数据结构) · [一键更新](#一键更新数据)

## 数据概览

| 指标 | 数值 |
|---|---|
| 行政区划节点 | **3238 个**（1 全国 + 34 省级 + 363 市级 + 2840 区县） |
| GeoJSON 文件 | 365 个（另含下钻索引 `index.json`） |
| 坐标系 | GCJ-02（火星坐标系，与高德/腾讯地图一致） |
| 数据来源 | [阿里 DataV.GeoAtlas](https://datav.aliyun.com/portal/school/atlas/area_selector) `areas_v3` 接口 |
| 边界完整性 | 全国图含**九段线/南海诸岛**，符合中国地图合规要求 |
| 运行时依赖 | 0（数据是纯 JSON；更新脚本仅需 Python 3.8+ 标准库） |

## 数据结构

```
data/
├── 100000_full.json        # 全国：features 为 34 个省级区域（画全国图只需这一个文件）
├── 100000.json             # 中国国界轮廓（单条边界，含九段线）
├── 110000.json ... 820000.json   # 34 个省级文件：features 为下辖市级区域
├── cities/
│   └── 440100.json ...     # 329 个市级文件：features 为下辖区县（下钻终点）
└── index.json              # 下钻索引：3238 个节点的查找表（见下）
```

`index.json` 每个节点的结构（adcode 即文件名，正好用于动态加载）：

```json
{
  "440000": { "name": "广东省", "level": "province",
              "file": "440000.json",          "children": ["440100", ...] },
  "440100": { "name": "广州市", "level": "city",
              "file": "cities/440100.json",   "children": ["440103", ...] }
}
```

- **直辖市**（京津沪渝）：省级文件直接挂区（`level: "district"`），下钻为两级
- **台湾**（710000）：仅省级轮廓，无下级；港澳含区级
- **省直辖县级市**（济源、仙桃等）：可显示，无下级
- 全部 3238 个节点均收录于 `index.json`，任意层级的名称都可反查 adcode

## 一键更新数据

行政区划变更（撤县设区、新设地级市等）后，重新执行即可增量更新——
已下载且有效的文件自动跳过，只拉取缺失/新增的部分：

```bash
python scripts/fetch_data.py            # 增量更新（推荐）
python scripts/fetch_data.py --force    # 全量重新下载
python scripts/fetch_data.py --out 其他目录
```

脚本仅用标准库（`urllib` + `ThreadPoolExecutor`，16 线程并发，断点续传），
无需 `pip install` 任何东西。全量下载约 360 个文件、25MB，1~2 分钟跑完。

## 在线演示

| 地址 | 说明 |
|---|---|
| **https://china-geojson-offline.pages.dev** | Cloudflare Pages（主演示地址） |
| **https://xiedajian.github.io/china-geojson-offline/** | GitHub Pages（随仓库走） |

演示内容：ECharts 点击「省 → 市 → 区」逐级下钻 + 面包屑返回，直观验证数据完整性。

## 演示代码（ECharts 下钻）

`src/App.vue` 是一个 ~150 行的 Vue 3 演示：点击省→市→区逐级下钻、
面包屑返回、visualMap 着色。**它只是数据集的用法示例，不是项目主体。**

```bash
npm install
npm run dev        # http://localhost:5173
```

核心逻辑三句话：

1. 用 `index.json` 把「区域名 → adcode → 文件路径」串起来
2. 点击区域时按需 `fetch` 对应 GeoJSON，`echarts.registerMap(adcode, data)`
3. 区县 `children` 为空即下钻终点

## 在其他引擎中使用

GeoJSON 是标准格式，任何引擎都是「加载文件 → 注册/添加数据源」两步：

```js
// MapLibre GL / Mapbox GL（注意：底图用 WGS-84 时需先做 GCJ-02 转坐标纠偏）
map.addSource('gz', { type: 'geojson', data: 'data/cities/440100.json' });

// Leaflet
fetch('data/440000.json').then(r => r.json())
  .then(gj => L.geoJSON(gj).addTo(map));

// OpenLayers
vectorSource.addFeatures(new GeoJSON().readFeatures(await (await fetch('data/100000_full.json')).json()));
```

## 坐标系说明（重要）

本数据集为 **GCJ-02** 坐标（DataV 标准）。叠加展示时：

- 底图用高德/腾讯地图 → 直接对齐，无需转换
- 底图用 OpenStreetMap / Mapbox / 天地图（WGS-84 / CGCS2000）→ 需先做 GCJ-02→WGS-84 纠偏，否则边界偏移约 100~700 米
- 展示纯边界（无底图，如本演示）→ 无所谓坐标系

## 许可

- 代码：MIT
- 数据：来自阿里 DataV.GeoAtlas 公开接口，版权归原始数据方所有，使用时请遵循[国家统计局行政区划代码标准](http://www.stats.gov.cn/sj/tjbz/)与地图出版合规要求
