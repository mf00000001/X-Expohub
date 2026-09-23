/**
 * 判断一个字符串能否作为 <image> 的远程图片地址（http/https）。
 * 用于兜底脏数据：后端 cover_image / images 字段可能被填成乱码（如"我去饿"），
 * 直接渲染会被小程序拼成相对路径报 500，这里统一拦截走占位符。
 */
export function isHttpUrl(value: unknown): value is string {
  return typeof value === 'string' && /^https?:\/\//i.test(value)
}
