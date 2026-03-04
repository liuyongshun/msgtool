"""
公众号内容生成模块

功能：
- 接收选题信息 + 用户输入的创作要求
- 使用 wechat_llm 配置调用 LLM 生成完整公众号文章（Markdown 格式）
- 支持将生成的文章同步到 Notion wechat 数据库
"""

import json
from datetime import datetime
from typing import Optional
import httpx

from ..config import get_config
from ..utils.logger import logger
from ..utils.notion_sync import get_notion_sync


class WechatContentGenerator:
    """公众号文章内容生成器"""

    # 公众号文章 Prompt 模板
    ARTICLE_PROMPT_TEMPLATE = """你是一位专注 AI 技术领域的公众号作者，文章风格：通俗易懂、干货满满、有实际价值，整体尽量弱化“AI味”，更贴近自然的人类写作。

【选题信息】
- 推荐标题：{suggested_title}
- 原始标题：{source_title}
- 原文摘要：{summary}
- 建议写作角度：{writing_angle}
- 来源：{source_type} - {source_url}

【用户创作要求】
{user_prompt}

【公众号方向】
AI技术分享、教程、开源软件、AI工具、AIGC创作等

【输出要求】
请生成一篇完整的公众号文章，满足以下结构和格式要求：
1. 一个吸引人的标题：放在文章最前面，使用 “### 标题内容” 作为一级标题
2. 引言：50-80 字，引起读者兴趣
3. 正文：结构清晰，分段展开，1200-2000 字
   - 使用 “#### 小节标题” 或 “##### 更小节标题” 划分章节
   - 可以包含一层级的无序列表（只使用 “- ” 开头的列表项）
   - 适当包含实际使用建议或操作步骤（尤其是教程/工具类内容）
4. 总结：80-120 字，点明核心价值
5. 互动引导：一句话，引导读者关注/收藏/留言

注意：
1. 全文必须使用 Markdown 格式，但只允许使用以下几种语法：
   - 标题：只允许使用 “### / #### / #####” 三种级别的标题
   - 列表：只允许一层级的无序列表（行首使用 “- ”）
   - 加粗：允许使用 **加粗** 强调重要概念
   其他 Markdown 语法（例如：表格、引用、代码块、行内代码、图片、链接别名等）一律不要使用。
2. 段落和列表项之间通过换行来控制格式；不要在同一行里堆叠多种复杂格式。
3. 全文禁止任何形式的表情：包括字符表情（如 :) :( ^_^）、文字表情、Emoji、图标等。
4. 降低“AI味”：
   - 避免或尽量少用明显的因果连接词堆叠，比如 “因此/由此可见/综上所述/总的来说/总之/首先/其次/另外/此外/最后”等。
   - 多用自然的口语化连接方式，让段落衔接看起来自然，不要像机器生成的总结。
5. 教程或工具讲解类内容：
   - 合理使用第一人称和第二人称，例如 “我通常会…”，“你可以这样做…”，“我们可以先…然后…”
   - 让读者感觉是在跟一位经验丰富的工程师对话，而不是在读官方文档。
6. 中文写作，适当保留必要的英文专业术语，但不要大段英文堆砌。
7. 不要出现 “本文”“笔者”“博主”等自指称呼，可以用更自然的表达方式。
8. 不要添加与内容无关的广告或推广语。"""

    def __init__(self):
        self.config = get_config()

    def _get_wechat_llm_config(self) -> Optional[dict]:
        """获取 wechat_llm 配置"""
        raw_config = self.config._config  # 直接访问原始配置
        return raw_config.get("wechat_llm")

    async def generate(
        self,
        topic: dict,
        user_prompt: str,
    ) -> dict:
        """
        生成公众号文章

        Args:
            topic: 选题数据（来自 wechat_topics JSON）
            user_prompt: 用户填写的创作要求

        Returns:
            {
                "success": bool,
                "title": str,          # 文章标题
                "content": str,        # Markdown 格式正文（含标题行）
                "error": str           # 出错时的错误信息
            }
        """
        wechat_llm = self._get_wechat_llm_config()
        provider = None
        if not wechat_llm or not wechat_llm.get("enabled"):
            # 降级使用普通 llm 配置
            llm = self.config.get_llm_config()
            if not llm or not llm.enabled:
                return {"success": False, "error": "LLM 未配置或未启用"}
            provider = getattr(llm, "provider", None)
            api_key = llm.api_key
            api_url = llm.api_url
            model_name = llm.model_name
            max_tokens = getattr(llm, "max_tokens", 4000) or 4000
            temperature = getattr(llm, "temperature", 0.7) or 0.7
        else:
            provider = wechat_llm.get("provider") or "deepseek"
            api_key = wechat_llm.get("api_key", "")
            api_url = wechat_llm.get("api_url", "")
            model_name = wechat_llm.get("model_name", "deepseek-chat")
            max_tokens = wechat_llm.get("max_tokens", 4000) or 4000
            temperature = wechat_llm.get("temperature", 0.7) or 0.7

        if not api_key:
            return {"success": False, "error": "wechat_llm 未配置 api_key"}

        prompt = self.ARTICLE_PROMPT_TEMPLATE.format(
            suggested_title=topic.get("suggested_title", ""),
            source_title=topic.get("source_title", ""),
            summary=topic.get("summary", ""),
            writing_angle=topic.get("writing_angle", ""),
            source_type=topic.get("source_type", ""),
            source_url=topic.get("source_url", ""),
            user_prompt=user_prompt.strip() if user_prompt.strip() else "无特殊要求，按建议角度创作即可",
        )

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # 根据 provider 选择不同的调用方式
                if provider == "gemini":
                    # Gemini generateContent API（使用 v1beta + x-goog-api-key 头，参考官方文档）
                    endpoint = api_url or f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    response = await client.post(
                        endpoint,
                        headers={
                            "x-goog-api-key": api_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "contents": [
                                {
                                    "parts": [
                                        {"text": prompt}
                                    ]
                                }
                            ],
                            "generationConfig": {
                                "maxOutputTokens": int(max_tokens),
                                "temperature": float(temperature),
                            },
                        },
                    )
                    response.raise_for_status()
                    resp_data = response.json()
                    # 把所有 candidate 的 text 拼接起来（通常只会有一个）
                    texts: list[str] = []
                    for cand in resp_data.get("candidates", []) or []:
                        content_obj = cand.get("content") or {}
                        for part in content_obj.get("parts", []) or []:
                            text = part.get("text")
                            if isinstance(text, str) and text.strip():
                                texts.append(text.strip())
                    if not texts:
                        raise ValueError("Gemini 返回内容为空，无法生成文章")
                    content = "\n\n".join(texts)
                else:
                    # 默认使用 OpenAI / DeepSeek 兼容的 Chat Completions 风格
                    response = await client.post(
                        api_url,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )
                    response.raise_for_status()
                    resp_data = response.json()
                    content = resp_data["choices"][0]["message"]["content"].strip()

                # 提取标题（第一个 # 行）
                title = topic.get("suggested_title", "公众号文章")
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        title = stripped[2:].strip()
                        break

                logger.info(f"公众号文章生成成功，标题：{title}")
                return {
                    "success": True,
                    "title": title,
                    "content": content,
                    "error": None,
                }

        except httpx.HTTPStatusError as e:
            error_msg = f"LLM 请求失败 (HTTP {e.response.status_code}): {e.response.text[:200]}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"生成文章失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def sync_to_notion(
        self,
        title: str,
        content: str,
        topic: dict,
        user_prompt: str,
    ) -> dict:
        """
        将生成的文章同步到 Notion wechat 数据库

        Args:
            title: 文章标题
            content: Markdown 正文内容
            topic: 选题数据（用于补充元信息）
            user_prompt: 用户输入的创作要求

        Returns:
            {"success": bool, "message": str, "notion_url": str}
        """
        try:
            notion_sync = get_notion_sync()
            if not notion_sync or not notion_sync.enabled:
                return {
                    "success": False,
                    "message": "Notion 同步未启用，请检查配置",
                }

            # 获取 wechat 数据库 ID（不使用 fallback，避免写入其他库）
            wechat_db_id = notion_sync.databases.get("wechat")
            if not wechat_db_id:
                return {
                    "success": False,
                    "message": "Notion wechat 数据库 ID 未配置，请在 sources.json 的 notion_sync.databases.wechat.database_id 中填写",
                }

            # 构建 Notion 页面属性
            # 正文内容超出 summary 字段限制，存到 Notion 的 rich_text 块中
            summary_preview = content[:500].replace("\n", " ") if content else ""

            properties = {
                "Title": {
                    "title": [{"text": {"content": title[:200]}}]
                },
                "Summary": {
                    "rich_text": [{"text": {"content": summary_preview}}]
                },
                "Source URL": {
                    "url": topic.get("source_url") or None
                },
                "Source Type": {
                    "select": {"name": "wechat"}
                },
                "Article Tag": {
                    "select": {"name": "公众号文章"}
                },
                "Published Date": {
                    "date": {"start": datetime.now().strftime("%Y-%m-%d")}
                },
            }

            # 移除 None 值的字段（避免 Notion API 报错）
            if not topic.get("source_url"):
                del properties["Source URL"]

            # 构建页面 children（正文块）
            children = _build_notion_content_blocks(title, content, topic, user_prompt)

            # 直接调用 Notion API 创建页面（不通过 ArticleItem，因格式不同）
            notion_sync._throttle()
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{notion_sync.api_base_url}/pages",
                    headers=notion_sync.headers,
                    json={
                        "parent": {"database_id": wechat_db_id},
                        "properties": properties,
                        "children": children,
                    },
                )

            if response.status_code in (200, 201):
                page_data = response.json()
                page_url = page_data.get("url", "")
                logger.info(f"公众号文章已同步到 Notion: {page_url}")
                return {
                    "success": True,
                    "message": "文章已成功同步到 Notion",
                    "notion_url": page_url,
                }
            else:
                error_body = response.text[:300]
                logger.error(f"Notion 同步失败 (HTTP {response.status_code}): {error_body}")
                return {
                    "success": False,
                    "message": f"Notion API 返回错误 ({response.status_code}): {error_body}",
                }

        except Exception as e:
            error_msg = f"Notion 同步异常: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}


def _build_notion_content_blocks(
    title: str, content: str, topic: dict, user_prompt: str
) -> list[dict]:
    """
    将 Markdown 文章内容拆分为 Notion blocks

    Notion API children 最多支持 100 个块，超出则截断
    """
    blocks = []

    # 元信息块
    meta_lines = [
        f"来源：{topic.get('source_type', '')} | {topic.get('feed_name', '')}",
        f"原始标题：{topic.get('source_title', '')}",
        f"原始链接：{topic.get('source_url', '')}",
        f"写作角度：{topic.get('writing_angle', '')}",
        f"用户创作要求：{user_prompt[:200] if user_prompt else '无'}",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": "\n".join(meta_lines)}}],
            "icon": {"emoji": "📝"},
            "color": "gray_background",
        },
    })
    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # 正文内容：为满足 Notion 对单个 rich_text.content ≤ 2000 字的限制，
    # 按长度切分为多个 markdown code block，每块最多 ~1900 字，保证 5000 字以内完整同步。
    if content:
        max_chunk_len = 1900  # 比 2000 略小，留一点安全余量
        text = content
        start = 0
        index = 0
        while start < len(text):
            if len(blocks) >= 98:  # 预留 2 个 meta 块，总数接近 100 时停止
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": "（内容已部分截断，超出 Notion 单页限制）"}
                        }]
                    },
                })
                break

            chunk = text[start:start + max_chunk_len]
            # 尽量在换行处截断，避免把 Markdown 语法劈开
            if start + max_chunk_len < len(text):
                last_newline = chunk.rfind("\n")
                if last_newline > 0:
                    chunk = chunk[:last_newline]
                    start += last_newline + 1
                else:
                    start += max_chunk_len
            else:
                start += max_chunk_len

            if not chunk.strip():
                continue

            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                    "language": "markdown",
                },
            })
            index += 1

    return blocks


# Notion 支持的代码语言列表（常用）
_NOTION_CODE_LANGS = {
    "python", "javascript", "typescript", "java", "c", "c++", "c#",
    "go", "rust", "bash", "shell", "json", "yaml", "toml", "markdown",
    "html", "css", "sql", "plain text",
}


# 全局单例
_generator: Optional["WechatContentGenerator"] = None


def get_wechat_content_generator() -> WechatContentGenerator:
    """获取全局内容生成器实例"""
    global _generator
    if _generator is None:
        _generator = WechatContentGenerator()
    return _generator
