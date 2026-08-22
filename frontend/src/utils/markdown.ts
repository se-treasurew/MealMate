import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 使用标准 Markdown 换行规则，避免把有序列表的换行解析成破坏列表结构的 <br>。
marked.setOptions({ gfm: true, breaks: false })

/** 将 Markdown 文本渲染为经过 XSS 消毒的安全 HTML */
export const renderMarkdown = (text: string | null | undefined): string => {
  if (!text) return ''
  const html = marked.parse(text, { async: false })
  return DOMPurify.sanitize(html)
}
