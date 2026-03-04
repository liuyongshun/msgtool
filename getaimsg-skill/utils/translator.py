"""
翻译工具模块 - 使用大模型API翻译文本
"""

import re
import asyncio
import httpx
from typing import Optional
from config import get_config


def has_chinese(text: str) -> bool:
    """
    检测文本是否包含中文字符
    
    Args:
        text: 要检测的文本
        
    Returns:
        如果包含中文返回True，否则返回False
    """
    if not text:
        return False
    
    # 使用正则表达式检测中文字符
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))


async def translate_text(
    text: str,
    target_language: str = "中文",
    source_language: Optional[str] = None
) -> str:
    """
    使用大模型API翻译文本
    
    Args:
        text: 要翻译的文本
        target_language: 目标语言（默认：中文）
        source_language: 源语言（自动检测）
        
    Returns:
        翻译后的文本，如果翻译失败返回原文
    """
    if not text or not text.strip():
        return text
    
    # 如果已经包含中文，不需要翻译
    if has_chinese(text):
        return text
    
    # 获取配置
    config = get_config()
    llm_config = config.get_llm_config()
    
    if not llm_config or not llm_config.enabled or not llm_config.api_key:
        # 如果没有配置或未启用，返回原文
        return text
    
    try:
        # 构建翻译提示词
        if source_language:
            prompt = f"请将以下{source_language}文本翻译成{target_language}，只返回翻译结果，不要添加任何解释：\n\n{text}"
        else:
            prompt = f"请将以下文本翻译成{target_language}，只返回翻译结果，不要添加任何解释：\n\n{text}"
        
        # 调用API（减少超时时间，快速失败）
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {llm_config.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": llm_config.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": llm_config.temperature,
                "max_tokens": llm_config.max_tokens
            }
            
            response = await client.post(
                llm_config.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 提取翻译结果
            if "choices" in result and len(result["choices"]) > 0:
                translated_text = result["choices"][0]["message"]["content"].strip()
                # 清理可能的引号或其他格式
                translated_text = translated_text.strip('"').strip("'").strip()
                return translated_text
            else:
                return text
                
    except httpx.HTTPError as e:
        # 翻译失败时静默返回原文，避免影响主流程
        return text
    except Exception as e:
        # 翻译失败时静默返回原文，避免影响主流程
        return text


async def translate_article_item(
    title: str,
    summary: str
) -> tuple[str, str]:
    """
    翻译文章的标题和摘要（并发执行以提高效率）
    
    **重要优化**：
    - 翻译前先裁剪summary到350字符，避免浪费token
    - 翻译后再裁剪到300字符，防止翻译膨胀
    
    Args:
        title: 文章标题
        summary: 文章摘要
        
    Returns:
        (翻译后的标题, 翻译后的摘要) - summary保证不超过300字符
    """
    # 检查是否需要翻译
    title_has_chinese = has_chinese(title)
    summary_has_chinese = has_chinese(summary)
    
    # 【关键优化1】翻译前先裁剪summary，避免浪费token翻译过长内容
    # 留350字符空间，考虑翻译后可能膨胀到300字符
    if len(summary) > 350:
        summary = summary[:350].rsplit(" ", 1)[0] + "..."
    
    # 【关键优化2】如果原文已经是中文且超长，直接裁剪到300（不会进入翻译流程）
    if summary_has_chinese and len(summary) > 300:
        summary = summary[:300].rsplit(" ", 1)[0] + "..."
    
    translated_title = title
    translated_summary = summary
    
    # 如果需要翻译，并发执行以提高效率
    if not title_has_chinese and not summary_has_chinese:
        # 两个都需要翻译，并发执行
        title_task = translate_text(title)
        summary_task = translate_text(summary)
        translated_title, translated_summary = await asyncio.gather(
            title_task, summary_task, return_exceptions=True
        )
        # 处理异常情况
        if isinstance(translated_title, Exception):
            translated_title = title
        if isinstance(translated_summary, Exception):
            translated_summary = summary
    elif not title_has_chinese:
        # 只翻译标题
        translated_title = await translate_text(title) or title
    elif not summary_has_chinese:
        # 只翻译摘要
        translated_summary = await translate_text(summary) or summary
    
    # 【最终保护】翻译后再次确保不超过300字符（防止翻译膨胀）
    if len(translated_summary) > 300:
        translated_summary = translated_summary[:300].rsplit(" ", 1)[0] + "..."
    
    return translated_title, translated_summary
