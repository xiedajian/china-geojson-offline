<script setup>
import * as echarts from 'echarts'
import { onMounted, onBeforeUnmount, ref } from 'vue'

const chartEl = ref(null)
const stack = ref([{ adcode: '100000', name: '全国' }])
const loading = ref(false)

let chart = null
let indexData = null
let nameMap = {}   // 当前层级：区域名 -> adcode

/** 请求数据集文件（vite publicDir 已指向 ../data，按需加载不进 bundle） */
async function loadJson(file) {
  const res = await fetch(`/${file}`)
  if (!res.ok) throw new Error(`加载失败: ${file}`)
  return res.json()
}

/** 用区域名生成稳定的伪随机值，让 visualMap 有颜色分层（示例数据） */
function pseudoValue(name) {
  let h = 0
  for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) % 1000
  return h
}

/** 渲染某个 adcode 的地图 */
async function show(adcode) {
  const node = indexData[adcode]
  if (!node) return
  loading.value = true
  try {
    const file = adcode === '100000' ? '100000_full.json' : node.file
    if (!file) return
    const data = await loadJson(file)
    echarts.registerMap(adcode, data)

    // 构建 当前层级区域名 -> adcode 的映射，供点击事件反查
    nameMap = {}
    node.children.forEach(c => {
      if (indexData[c]) nameMap[indexData[c].name] = c
    })

    const regions = data.features
      .map(f => f.properties?.name)
      .filter(Boolean)

    chart.setOption({
      title: { text: node.name, left: 'center', top: 14, textStyle: { fontSize: 18, color: '#333' } },
      tooltip: {
        trigger: 'item',
        formatter: p => `${p.name}<br/>示例值: ${p.value ?? '-'}${node.children.length ? '<br/><span style="color:#999">点击下钻</span>' : ''}`
      },
      visualMap: {
        min: 0, max: 1000, left: 16, bottom: 24,
        text: ['高', '低'], calculable: false,
        inRange: { color: ['#e0f3f8', '#74add1', '#2f5fa3'] }
      },
      series: [{
        type: 'map',
        map: adcode,
        roam: true,
        zoom: 1.05,
        label: { show: true, fontSize: 10, color: '#333' },
        itemStyle: { borderColor: '#fff', borderWidth: 0.6 },
        emphasis: {
          label: { fontSize: 12, fontWeight: 'bold' },
          itemStyle: { areaColor: '#ffd666' }
        },
        select: { disabled: true },
        data: regions.map(n => ({ name: n, value: pseudoValue(n) }))
      }]
    }, true)
  } finally {
    loading.value = false
  }
}

/** 点击区域 → 下钻 */
async function handleClick(params) {
  const ad = nameMap[params.name]
  if (!ad) return
  const node = indexData[ad]
  if (!node?.children?.length) return // 区县为终点
  stack.value.push({ adcode: ad, name: node.name })
  await show(ad)
}

/** 面包屑返回 */
async function backTo(i) {
  if (i === stack.value.length - 1) return
  stack.value = stack.value.slice(0, i + 1)
  await show(stack.value[i].adcode)
}

function resize() { chart?.resize() }

onMounted(async () => {
  indexData = await loadJson('index.json')
  chart = echarts.init(chartEl.value)
  chart.on('click', handleClick)
  window.addEventListener('resize', resize)
  await show('100000')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>

<template>
  <div class="page">
    <header class="topbar">
      <nav class="crumbs">
        <template v-for="(item, i) in stack" :key="item.adcode">
          <span v-if="i > 0" class="sep">›</span>
          <button
            class="crumb"
            :class="{ active: i === stack.length - 1 }"
            :disabled="i === stack.length - 1"
            @click="backTo(i)"
          >{{ item.name }}</button>
        </template>
      </nav>
      <span class="tip">点击区域下钻（直辖市：省 → 区）</span>
    </header>

    <div class="chart-wrap">
      <div v-show="loading" class="loading">加载中…</div>
      <div ref="chartEl" class="chart"></div>
    </div>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; height: 100%; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); z-index: 1;
}
.crumbs { display: flex; align-items: center; gap: 4px; }
.sep { color: #999; }
.crumb {
  border: none; background: none; cursor: pointer;
  font-size: 15px; color: #2f5fa3; padding: 4px 6px; border-radius: 4px;
}
.crumb:hover:not(:disabled) { background: #eef3fa; }
.crumb.active { color: #333; font-weight: 600; cursor: default; }
.tip { font-size: 12px; color: #aaa; }
.chart-wrap { position: relative; flex: 1; min-height: 0; }
.chart { width: 100%; height: 100%; }
.loading {
  position: absolute; inset: 0; display: flex; align-items: center;
  justify-content: center; font-size: 14px; color: #888; z-index: 2;
  background: rgba(245, 247, 250, 0.6);
}
</style>
