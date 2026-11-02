/**
 * 品类 → 分类占位图（public/categories/<slug>.png）
 *
 * 为什么需要：
 * 名录 67,357 件展品里只有 751 件有真实图，其余全靠兜底。纯「深蓝渐变 + 首字水印」
 * 不破图但整页一个样，看不出品类差异。这里把后端的中文品类（常常是
 * 「机床工具,模具制造」这种逗号多值串）映射到 16 个 slug，由
 * scripts/gen_category_covers.py 生成 800×600 的几何母题缩略图；
 * 没有映射的落到 _default.png。
 *
 * 约定：
 * - 只做纯映射，不发请求、不读 DOM，SSR / 单测都能直接调用；
 * - 入参既可以是 slug（machine-tool），也可以是裸品类名（机床工具）或
 *   逗号多值串（机床工具,模具制造），还能直接吞下 `/categories/x.png`；
 * - 永远返回可用字符串：无法识别时返回 _default.png，绝不返回空串。
 */

/** 与 scripts/gen_category_covers.py 的 CATEGORIES 键一一对应（含 _default） */
export const CATEGORY_SLUGS = [
  'machine-tool',
  'mold-die',
  'general-machinery',
  'instruments',
  'electronics',
  'auto-parts',
  'home-appliance',
  'photonics',
  'semiconductor',
  'robotics',
  'energy',
  'aerospace',
  'medical-device',
  'diagnostics',
  'rehab',
  'materials',
] as const

export type CategorySlug = (typeof CATEGORY_SLUGS)[number]
export type CategoryImageSlug = CategorySlug | '_default'

/** 兜底图：没有任何品类线索时使用 */
export const DEFAULT_CATEGORY_SLUG: CategoryImageSlug = '_default'

/** 分类图所在目录（相对 public，Vite 直接以站点根提供） */
const BASE_DIR = '/categories'

/**
 * 裸品类名 → slug 的精确表。
 * 只放「后端真实出现过的完整品类名」，多值串里的逗号片段也能命中。
 */
const NAME_TO_SLUG: Record<string, CategoryImageSlug> = {
  机床工具: 'machine-tool',
  数控机床: 'machine-tool',
  机床: 'machine-tool',
  模具制造: 'mold-die',
  模具: 'mold-die',
  通用机械: 'general-machinery',
  重型机械: 'general-machinery',
  工程机械: 'general-machinery',
  机械制造: 'general-machinery',
  仪器仪表: 'instruments',
  仪表仪器: 'instruments',
  '3C电子': 'electronics',
  '3C': 'electronics',
  消费电子: 'electronics',
  汽车: 'auto-parts',
  '汽车/汽车零部件': 'auto-parts',
  家用电器: 'home-appliance',
  光电: 'photonics',
  光学: 'photonics',
  半导体: 'semiconductor',
  '半导体与集成电路': 'semiconductor',
  人工智能: 'robotics',
  人工智能与机器人: 'robotics',
  智能制造与自动化: 'robotics',
  新能源: 'energy',
  新型电力: 'energy',
  电力能源: 'energy',
  清洁能源: 'energy',
  航空航天: 'aerospace',
  低空经济与商业航天: 'aerospace',
  医疗器械: 'medical-device',
  医疗器械制造: 'medical-device',
  医疗设备: 'medical-device',
  诊断试剂: 'diagnostics',
  康复理疗设备: 'rehab',
  康养结合: 'rehab',
  新材料: 'materials',
  高分子材料: 'materials',
  金属材料: 'materials',
  原材料: 'materials',
}

/**
 * 关键词兜底：按数组顺序判定，越靠前越具体。
 * 命中规则是「品类串包含关键词」，因此「机床工具,模具制造」会先命中 machine-tool。
 */
const KEYWORD_RULES: ReadonlyArray<readonly [CategoryImageSlug, readonly string[]]> = [
  ['diagnostics', ['诊断试剂', '体外诊断', '试剂', '生化分析', '免疫分析', '血球', '培养皿', '样本采集']],
  [
    'medical-device',
    [
      '医疗', '医用', '器械', '手术', '病床', '监护', '内窥镜', '超声', '灭菌', '消毒', '护理',
      '医院', '健康', '敷料', '敷贴', '绷带', '口罩', '防护', '吻合器', '输液', '插管', '导管',
      '心电', '血压', '体温', '血氧', '血糖', '葡萄糖', '离心机', '医械', '牙科', '口腔', '眼科',
      '骨科', '义齿', '医学', '治疗', '体检', '慢病', '雾化', '探头', '图像显示', '垫单', '隔离',
      '管路', '呼吸', '麻醉', '注射', '缝合', '穿刺', '引流', '吸引', '除颤', '急救', '心肺',
      '复苏', '矫形', '固定器', '影像', 'X射线', '磁共振', '体层摄影', '采血', '喉罩', '牵开',
      '补片', '止血', '负压', '氧气', '输氧', '鼻氧', '电极', '刺激器', '多普勒', '透视', '活检',
      '妇科', '产科', '耳鼻喉', '中医', '针灸', '吸痰', '供氧', '抢救', '担架', '轮椅车', '尿管',
      '手套', '创口贴', '夹板', '固定带', '外固定', '样本', '支具', '纱布', '棉签', '缝线',
    ],
  ],
  ['rehab', ['康复', '理疗', '康养', '养老', '适老', '助行', '轮椅', '按摩', '关节训练', '牵引', '健身', '康体', '穴位', '磁疗', '步态', '训练']],
  ['semiconductor', ['半导体', '集成电路', '芯片', '晶圆', '封装测试', '光刻', 'EDA']],
  ['photonics', ['光电', '光学', '激光', '镜头', '光纤', '光通信', '摄像', '红外', '光谱', '滤光', '镜片']],
  ['robotics', ['机器人', '人工智能', '智能制造', '自动化', '视觉', '算法', '协作臂', '自动化设备']],
  ['aerospace', ['航空航天', '航空', '航天', '低空', '无人机', '卫星', '飞行器', '火箭']],
  [
    'energy',
    ['新能源', '电力', '能源', '电池', '储能', '光伏', '风电', '充电桩', '充电', '逆变', '节能', '碳中和'],
  ],
  [
    'electronics',
    ['电子', '3C', '元器件', '线路板', 'PCB', '电源', '连接线', '通讯', '通信', '显示屏', '传感器件',
      '主板', '物联网', 'IOT', '电路', '开关', '线缆', '接插件'],
  ],
  ['auto-parts', ['汽车', '车辆', '轮胎', '摩托', '汽配', '车灯', '底盘', '电动车']],
  ['home-appliance', ['家电', '家用电器', '空调', '冰箱', '洗衣机', '厨电', '风扇', '小家电', '热水器']],
  [
    'machine-tool',
    ['机床', '数控', '车床', '铣床', '磨床', '加工中心', '刨槽', '钻床', '冲床', '精密制造', '精密',
      '机加工', '折弯', '刀具', '3D打印', '打印设备', '激光切割', '工具'],
  ],
  ['mold-die', ['模具', '注塑', '冲压', '型腔', '压铸', '挤出']],
  ['instruments', ['仪表', '仪器', '传感器', '测量', '计量', '检测', '试验机', '探伤', '探测', '测试']],
  [
    'materials',
    ['材料', '高分子', '金属', '塑料', '橡胶', '复合材料', '化工', '包装', '涂料', '胶带', '粘合',
      '硅胶', '树脂', '塑胶'],
  ],
  [
    'general-machinery',
    ['机械', '泵', '阀', '减速机', '轴承', '液压', '起重', '压缩机', '电机', '五金', '齿轮', '推杆',
      '传动', '工装', '夹具', '组装设备', '输送', '电动'],
  ],
]

const SLUG_SET = new Set<string>([...CATEGORY_SLUGS, DEFAULT_CATEGORY_SLUG])

/**
 * 把任意品类输入收敛成图片 slug。
 * @param slugOrName slug / 品类名 / 逗号多值串 / `/categories/x.png`，允许空
 */
export function categorySlug(slugOrName?: string | null): CategoryImageSlug {
  const raw = (slugOrName ?? '').toString().trim()
  if (!raw) return DEFAULT_CATEGORY_SLUG

  // 已经是一个图片路径 / slug（大小写不敏感）
  const lastSegment = raw.split(/[\\/]/).pop() ?? ''
  const head = lastSegment.replace(/\.png$/i, '').trim().toLowerCase()
  if (SLUG_SET.has(head)) return head as CategoryImageSlug

  // 精确名字（含逗号多值串逐段）
  const parts = raw.split(/[,，;；、|]/).map((s) => s.trim()).filter(Boolean)
  for (const part of parts) {
    const hit = NAME_TO_SLUG[part]
    if (hit) return hit
  }

  // 关键词（对整串判定，保持规则表的优先级）
  for (const [slug, words] of KEYWORD_RULES) {
    if (words.some((w) => raw.includes(w))) return slug
  }
  return DEFAULT_CATEGORY_SLUG
}

/**
 * 品类占位图地址：`/categories/<slug>.png`，无法识别时 `/categories/_default.png`。
 *
 * 用法：
 * ```ts
 * categoryImage('机床工具,模具制造') // '/categories/machine-tool.png'
 * categoryImage('不是品类')          // '/categories/_default.png'
 * ```
 */
export function categoryImage(slugOrName?: string | null): string {
  return `${BASE_DIR}/${categorySlug(slugOrName)}.png`
}

export default categoryImage
