import { marked } from 'marked'
import DOMPurify from 'dompurify'

// breaks：单个换行即 <br>，贴合手机上写菜谱的习惯
marked.setOptions({ gfm: true, breaks: true })

/** 将 Markdown 文本渲染为经过 XSS 消毒的安全 HTML */
export const renderMarkdown = (text: string | null | undefined): string => {
  if (!text) return ''
  const html = marked.parse(text, { async: false })
  return DOMPurify.sanitize(html)
}
