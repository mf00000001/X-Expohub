/**
 * 输入校验：拦截联系方式、金额等信息
 * 展前撮合平台禁止线上沟通价格和联系方式
 */
const phonePatterns = [
  /1[3-9]\d{9}/, /1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}/,
  /\+?86[\s-]?1[3-9]\d{9}/,
  /\d{3}[\s-]?\d{4}[\s-]?\d{4}/,  // 138 1234 5678
  /\d{11,}/,  // any 11+ digit sequence = likely a phone number
  /[一八壹捌](\s|-)?[三叁三四肆四五伍五六陆六七柒七八捌八九玖九](?:\d|[零一二三四五六七八九壹贰叁肆伍陆柒捌玖拾]){8,}/,
]
const wechatPatterns = [
  /(微|薇|维)信[:\s：]*\w+/i, /wechat[:\s：]*\w+/i, /vx?[:\s：]*\w+/i,
  /加\s*v/i, /微信/,
]
const qqPatterns = [
  /qq[:\s：]*\d{5,}/i, /扣扣[:\s：]*\d+/i, /企鹅[:\s：]*\d+/i,
]
const emailPatterns = [
  /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/,
  /[a-zA-Z0-9]+[\s]*艾特[\s]*[a-zA-Z0-9]+[\s]*点[\s]*[a-zA-Z]+/,
]
const moneyPatterns = [
  /[¥￥]\s*\d+/, /\d+[\s]*(元|块|万|w|W|rmb|RMB)/,
  /(零|一|二|三|四|五|六|七|八|九|十|百|千|万|两|壹|贰|叁|肆|伍|陆|柒|捌|玖|拾|佰|仟|萬){3,}[元块]/,
  /\d+[\s]*k\b/i, /\d+[\s]*张\b/,
]

const allPatterns: { re: RegExp; label: string }[] = [
  ...phonePatterns.map(re => ({ re, label: '手机号' })),
  ...wechatPatterns.map(re => ({ re, label: '微信' })),
  ...qqPatterns.map(re => ({ re, label: 'QQ' })),
  ...emailPatterns.map(re => ({ re, label: '邮箱' })),
  ...moneyPatterns.map(re => ({ re, label: '金额' })),
]

export function validateInput(value: string): { valid: boolean; reason: string } {
  if (!value) return { valid: true, reason: '' }
  for (const { re, label } of allPatterns) {
    if (re.test(value)) {
      return { valid: false, reason: `输入内容疑似包含${label}信息。平台仅用于展前匹配，请于展会现场沟通。` }
    }
  }
  return { valid: true, reason: '' }
}
