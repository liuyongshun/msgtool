"""
公众号选题评估模块

功能：
- 读取当日 output/daily/YYYYMMDD/ 下的 RSS + HackerNews 数据
- 使用 LLM 批量评估每条内容是否值得发布为公众号文章
- 公众号方向：AI技术分享、教程、开源软件、AI工具、AIGC创作等
- 结果写入 output/daily/YYYYMMDD/wechat_topics_TIMESTAMP.json
"""

import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx

from ..config import get_config
from ..utils.logger import logger


# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent.parent


class WechatTopicEvaluator:
    """公众号选题评估器"""

    # 公众号内容方向描述（用于 Prompt）
    WECHAT_DIRECTIONS = [
        "AI技术分享与深度解析",
        "AI工具教程与使用指南",
        "开源软件与开发框架介绍",
        "AIGC创作工具与技巧",
        "AI行业热点与动态",
        "大模型进展与评测",
    ]

    def __init__(self):
        self.config = get_config()
        self.output_base = BASE_DIR / "output" / "daily"

    def _get_today_dir(self, date_str: Optional[str] = None) -> Path:
        """获取当日输出目录（格式 YYYY-MM-DD，与 OutputManager 保持一致）"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        return self.output_base / date_str

    def _load_hackernews_items(self, date_str: str) -> list[dict]:
        """读取当日 HackerNews 数据"""
        daily_dir = self._get_today_dir(date_str)
        items = []

        hn_files = sorted(daily_dir.glob("hackernews_*.json"), reverse=True)
        seen_urls = set()

        for file in hn_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("items", []):
                    url = item.get("source_url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        items.append({
                            "id": item.get("id", str(uuid.uuid4())),
                            "title": item.get("title", ""),
                            "summary": item.get("summary", ""),
                            "source_url": url,
                            "source_type": "hackernews",
                            "score": item.get("score", 0),
                            "ai_score": item.get("ai_score", 0),
                        })
            except Exception as e:
                logger.warning(f"读取 HackerNews 文件 {file.name} 失败: {e}")

        return items

    def _load_rss_items(self, date_str: str) -> list[dict]:
        """读取当日 RSS 数据"""
        daily_dir = self._get_today_dir(date_str)
        items = []

        rss_files = sorted(daily_dir.glob("rss_*.json"), reverse=True)
        seen_urls = set()

        for file in rss_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for feed_url, feed_data in data.get("feeds", {}).items():
                    if not isinstance(feed_data, dict):
                        continue
                    feed_name = feed_data.get("feed_name", feed_url)
                    for item in feed_data.get("items", []):
                        url = item.get("link", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            items.append({
                                "id": str(uuid.uuid4()),
                                "title": item.get("title", ""),
                                "summary": item.get("summary", "")[:300],
                                "source_url": url,
                                "source_type": "rss",
                                "feed_name": feed_name,
                                "ai_score": item.get("ai_score", 0),
                            })
            except Exception as e:
                logger.warning(f"读取 RSS 文件 {file.name} 失败: {e}")

        return items

    async def _evaluate_batch(
        self, items: list[dict], batch_size: int = 10
    ) -> list[dict]:
        """
        批量调用 LLM 评估选题价值

        返回每条的评估结果：selected, wechat_score, suggested_title, reason, writing_angle
        """
        llm_config = self.config.get_llm_config()
        if not llm_config or not llm_config.enabled or not llm_config.api_key:
            logger.warning("LLM 未配置或未启用，跳过选题评估")
            return []

        directions_str = "\n".join(f"- {d}" for d in self.WECHAT_DIRECTIONS)
        results = []

        # 分批处理（默认每批10条，降低单次请求长度，减少超时/解析失败概率）
        total_batches = (len(items) + batch_size - 1) // batch_size
        for batch_idx in range(total_batches):
            batch = items[batch_idx * batch_size: (batch_idx + 1) * batch_size]

            # 构建 items 列表给 LLM
            items_str = ""
            for i, item in enumerate(batch):
                title = item.get("title", "")
                summary = item.get("summary", "")[:200]
                items_str += f'{i + 1}. ID: "{item["id"]}"\n   标题: {title}\n   摘要: {summary}\n\n'

            prompt = f"""你是一个专注于 AI 技术的公众号编辑，负责筛选和评估当天的技术资讯，判断哪些内容适合发布为公众号文章。

公众号定位方向（只能从以下方向挑选内容）：
{directions_str}

下面是今天的文章列表，请逐条评估是否值得发布为公众号文章。

评估标准：
1. 内容必须与 AI 技术方向强相关
2. 有实用价值：教程、工具介绍、开源项目更容易被读者喜爱
3. 有时效性：最新进展、新发布的工具/模型
4. 避免过于学术或难以通俗化的内容

文章列表：
{items_str}

请以 JSON 数组格式返回评估结果，每个元素包含：
- id: 原文章 ID（与输入对应）
- selected: 是否推荐（true/false）
- wechat_score: 推荐分数（0.0-1.0，1.0表示非常推荐）
- suggested_title: 为公众号建议的中文标题（简洁吸引人，15字以内），不推荐则为空字符串
- reason: 推荐或不推荐的理由（30字以内）
- writing_angle: 建议的写作角度（如"工具测评"、"入门教程"、"技术解析"等，不推荐则为空字符串）

只返回 JSON 数组，不要有任何其他内容。"""

            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        llm_config.api_url,
                        headers={
                            "Authorization": f"Bearer {llm_config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": llm_config.model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 2000,
                            "temperature": 0.3,
                        },
                    )
                    response.raise_for_status()
                    resp_data = response.json()
                    content = resp_data["choices"][0]["message"]["content"].strip()

                    # 提取 JSON 数组
                    if "```" in content:
                        import re
                        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", content)
                        if match:
                            content = match.group(1).strip()

                    batch_results = json.loads(content)
                    if isinstance(batch_results, list):
                        results.extend(batch_results)

                    logger.info(
                        f"批次 {batch_idx + 1}/{total_batches} 评估完成，"
                        f"共 {len(batch)} 条，获得 {len(batch_results)} 条结果"
                    )

            except Exception as e:
                logger.error(f"批次 {batch_idx + 1} LLM 评估失败: {e}")
                # 失败时跳过该批次

            # 避免过快请求
            if batch_idx < total_batches - 1:
                await asyncio.sleep(1)

        return results

    async def evaluate(self, date_str: Optional[str] = None) -> dict:
        """
        执行选题评估并保存结果

        Args:
            date_str: 日期字符串 YYYYMMDD，默认为今天

        Returns:
            评估结果字典
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        daily_dir = self._get_today_dir(date_str)
        if not daily_dir.exists():
            logger.warning(f"当日数据目录不存在: {daily_dir}")
            return {"error": f"数据目录不存在: {daily_dir}", "topics": []}

        # 读取数据
        logger.info(f"开始读取 {date_str} 的 RSS 和 HackerNews 数据...")
        hn_items = self._load_hackernews_items(date_str)
        rss_items = self._load_rss_items(date_str)
        all_items = hn_items + rss_items

        logger.info(
            f"共读取 {len(all_items)} 条数据 "
            f"（HackerNews: {len(hn_items)}, RSS: {len(rss_items)}）"
        )

        if not all_items:
            logger.warning("没有可评估的数据")
            result = {
                "generated_at": datetime.now().isoformat(),
                "source_date": date_str,
                "total_evaluated": 0,
                "selected_count": 0,
                "topics": [],
            }
            self._save_result(result, date_str)
            return result

        # 创建 id -> item 的映射
        id_to_item = {item["id"]: item for item in all_items}

        # LLM 批量评估
        logger.info("开始 LLM 批量评估选题价值...")
        eval_results = await self._evaluate_batch(all_items)

        # 合并评估结果与原始数据，筛选出推荐的选题
        topics = []
        for eval_item in eval_results:
            item_id = eval_item.get("id", "")
            if not eval_item.get("selected", False):
                continue

            original = id_to_item.get(item_id)
            if not original:
                continue

            wechat_score = float(eval_item.get("wechat_score", 0.0))
            topics.append({
                "id": item_id,
                "suggested_title": eval_item.get("suggested_title", ""),
                "source_title": original.get("title", ""),
                "source_url": original.get("source_url", ""),
                "source_type": original.get("source_type", ""),
                "feed_name": original.get("feed_name", ""),
                "summary": original.get("summary", ""),
                "reason": eval_item.get("reason", ""),
                "writing_angle": eval_item.get("writing_angle", ""),
                "wechat_score": wechat_score,
            })

        # 按评分降序排序
        topics.sort(key=lambda x: x["wechat_score"], reverse=True)

        result = {
            "generated_at": datetime.now().isoformat(),
            "source_date": date_str,
            "total_evaluated": len(all_items),
            "selected_count": len(topics),
            "topics": topics,
        }

        self._save_result(result, date_str)
        logger.info(
            f"选题评估完成：共评估 {len(all_items)} 条，"
            f"筛选出 {len(topics)} 条推荐选题"
        )
        return result

    def _save_result(self, result: dict, date_str: str) -> Path:
        """保存评估结果到文件"""
        daily_dir = self._get_today_dir(date_str)
        daily_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = daily_dir / f"wechat_topics_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"选题评估结果已保存: {output_file}")
        return output_file

    def load_latest_topics(self, date_str: Optional[str] = None) -> Optional[dict]:
        """
        加载最新的选题评估结果

        Args:
            date_str: 日期字符串 YYYYMMDD，默认为今天

        Returns:
            最新的选题结果，或 None
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        daily_dir = self._get_today_dir(date_str)
        if not daily_dir.exists():
            return None

        topic_files = sorted(daily_dir.glob("wechat_topics_*.json"), reverse=True)
        if not topic_files:
            return None

        try:
            with open(topic_files[0], "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取选题文件失败: {e}")
            return None


# 全局单例
_evaluator: Optional[WechatTopicEvaluator] = None


def get_wechat_topic_evaluator() -> WechatTopicEvaluator:
    """获取全局选题评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = WechatTopicEvaluator()
    return _evaluator
