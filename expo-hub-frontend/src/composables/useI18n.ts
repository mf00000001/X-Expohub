import { ref } from 'vue'

type Locale = 'zh' | 'en'

const currentLocale = ref<Locale>((localStorage.getItem('locale') as Locale) || 'zh')

const messages: Record<string, Record<string, string>> = {
  home: { zh: '首页', en: 'Home' },
  exhibitions: { zh: '全部展会', en: 'Exhibitions' },
  products: { zh: '展品', en: 'Products' },
  procurements: { zh: '采购需求', en: 'Procurements' },
  dashboard: { zh: '管理后台', en: 'Dashboard' },
  messages: { zh: '消息', en: 'Messages' },
  profile: { zh: '个人中心', en: 'Profile' },
  login: { zh: '登录', en: 'Login' },
  logout: { zh: '退出', en: 'Logout' },
  register: { zh: '注册', en: 'Register' },
  search: { zh: '搜索', en: 'Search' },
  viewAll: { zh: '查看全部', en: 'View All' },
  noData: { zh: '暂无数据', en: 'No Data' },
  loading: { zh: '加载中...', en: 'Loading...' },
  create: { zh: '创建', en: 'Create' },
  edit: { zh: '编辑', en: 'Edit' },
  delete: { zh: '删除', en: 'Delete' },
  cancel: { zh: '取消', en: 'Cancel' },
  confirm: { zh: '确认', en: 'Confirm' },
  save: { zh: '保存', en: 'Save' },
  approve: { zh: '通过', en: 'Approve' },
  reject: { zh: '驳回', en: 'Reject' },
  back: { zh: '返回', en: 'Back' },
  contact: { zh: '联系', en: 'Contact' },
  company: { zh: '公司', en: 'Company' },
  position: { zh: '职位', en: 'Position' },
  bio: { zh: '简介', en: 'Bio' },
  booths: { zh: '展位', en: 'Booths' },
  productList: { zh: '展品列表', en: 'Product List' },
  companyInfo: { zh: '公司信息', en: 'Company Info' },
  stats: { zh: '统计数据', en: 'Statistics' },
  totalProducts: { zh: '展品总数', en: 'Total Products' },
  totalBooths: { zh: '展位数量', en: 'Total Booths' },
  matchCount: { zh: '匹配次数', en: 'Match Count' },
  startConversation: { zh: '发起对话', en: 'Start Conversation' },
  exhibitorProfile: { zh: '展商主页', en: 'Exhibitor Profile' },
  pendingReview: { zh: '待审核', en: 'Pending Review' },
  userManagement: { zh: '用户管理', en: 'User Management' },
  pendingCount: { zh: '待审核展商', en: 'Pending Exhibitors' },
  location: { zh: '地点', en: 'Location' },
  date: { zh: '日期', en: 'Date' },
  status: { zh: '状态', en: 'Status' },
  role: { zh: '角色', en: 'Role' },
}

export function useI18n() {
  const locale = currentLocale

  function t(key: string, fallback?: string): string {
    const entry = messages[key]
    if (entry && entry[locale.value]) return entry[locale.value]
    return fallback || key
  }

  function toggleLocale() {
    locale.value = locale.value === 'zh' ? 'en' : 'zh'
    localStorage.setItem('locale', locale.value)
  }

  // Pick the right field based on locale (e.g., name vs name_en)
  function pick(obj: Record<string, any> | null | undefined, fieldBase: string): string {
    if (!obj) return ''
    if (locale.value === 'en') {
      const enField = `${fieldBase}_en`
      if (obj[enField]) return obj[enField]
    }
    return obj[fieldBase] || ''
  }

  return { locale, t, toggleLocale, pick }
}
