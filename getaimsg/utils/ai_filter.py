"""
AI 筛选工具模块 - 使用大模型批量判断文章标题是否与AI相关

功能: 批量处理文章标题，使用LLM判断是否与AI/机器学习相关
使用场景: Hacker News 等数据源的标题筛选
"""

import json
import re
import asyncio
from typing import Optional, TypedDict, Any
import httpx
from config import get_config
from utils.logger import logger


class TitleClassificationResult(TypedDict):
    """标题分类结果"""
    id: str  # 文章ID或临时标识
    score: float  # AI相关性评分 0.0-1.0
    keep: bool  # 是否保留
    reason: Optional[str]  # 判断理由（可选）


async def classify_titles_batch(
    titles: list[tuple[str, str]],  # [(id, title), ...]
    batch_size: int = 25  # 批次大小，减小以避免JSON截断
) -> list[TitleClassificationResult]:
    """
    批量分类文章标题，判断是否与AI相关
    
    Args:
        titles: 标题列表，格式为 [(id, title), ...]
        batch_size: 每批处理的标题数量（默认50）
        
    Returns:
        分类结果列表，每个结果包含 id, score, keep, reason
    """
    if not titles:
        return []
    
    # 获取LLM配置
    config = get_config()
    llm_config = config.get_llm_config()
    
    if not llm_config or not llm_config.enabled or not llm_config.api_key:
        logger.warning("LLM未配置或未启用，跳过AI筛选")
        # 如果LLM未配置，返回默认结果（全部保留）
        return [
            TitleClassificationResult(
                id=item_id,
                score=0.5,
                keep=True,
                reason="LLM未配置，默认保留"
            )
            for item_id, _ in titles
        ]
    
    results = []
    total_batches = (len(titles) + batch_size - 1) // batch_size
    
    # 分批处理
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        logger.info(f"处理批次 {batch_num}/{total_batches} ({len(batch)} 个标题)...")
        
        # 添加重试机制
        max_retries = 2
        batch_results = None
        
        for retry in range(max_retries + 1):
            try:
                batch_results = await _classify_single_batch(batch, llm_config)
                break  # 成功则退出重试循环
            except Exception as e:
                if retry < max_retries:
                    wait_time = (retry + 1) * 2  # 递增等待时间：2秒、4秒
                    logger.warning(
                        f"批次 {batch_num} 处理失败，{wait_time}秒后重试 ({retry + 1}/{max_retries}): {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"批次 {batch_num} 处理失败，已达到最大重试次数，使用默认结果")
                    batch_results = _create_default_results(batch)
        
        if batch_results:
            results.extend(batch_results)
        
        # 避免请求过快，增加延迟
        if i + batch_size < len(titles):
            await asyncio.sleep(0.5)  # 减少到0.5秒延迟，提高速度
    
    logger.info(f"AI筛选完成: 共处理 {len(titles)} 个标题，返回 {len(results)} 个结果")
    return results


async def _classify_single_batch(
    batch: list[tuple[str, str]],
    llm_config: Any  # LLMConfig
) -> list[TitleClassificationResult]:
    """
    处理单批标题分类
    
    Args:
        batch: 标题批次，格式为 [(id, title), ...]
        llm_config: LLM配置对象
        
    Returns:
        分类结果列表
    """
    # 构建输入数据
    items_data = [
        {"id": item_id, "title": title}
        for item_id, title in batch
    ]
    
    # 构建提示词
    system_prompt = """你是一个AI资讯筛选助手。你的任务是判断文章标题是否与AI/机器学习/大模型相关。

判断标准：
- 与AI/机器学习/大模型/LLM/GPT/Claude/Gemini/Transformer/NLP/计算机视觉/智能体/生成式AI等明显相关 → 保留
- 与AI基础设施相关（算力、训练框架、推理引擎等）→ 保留
- 纯Web开发/数据库/硬件但与AI无关 → 不保留
- 边界模糊的标题，如果与AI有潜在关联 → 可以保留

请只返回JSON数组，不要添加任何解释。格式：
[
  {"id": "1", "score": 0.95, "keep": true, "reason": "明确提到GPT模型"},
  {"id": "2", "score": 0.15, "keep": false, "reason": "数据库与AI无关"}
]

score范围：0.0-1.0，表示AI相关性程度
keep：true表示保留，false表示不保留
reason：简要说明判断理由（1-2句话）"""

    user_prompt = f"""请判断以下{len(batch)}个文章标题是否与AI相关：

{json.dumps(items_data, ensure_ascii=False, indent=2)}

请返回JSON数组，每个元素对应一个标题的判断结果。"""
    
    try:
        # 超时设置：减少超时时间，提高响应速度
        timeout = httpx.Timeout(45.0, connect=10.0)  # 从60秒减少到45秒
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {
                "Authorization": f"Bearer {llm_config.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": llm_config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,  # 降低温度以获得更稳定的结果
                "max_tokens": min(llm_config.max_tokens, 2000)  # 限制输出长度
            }
            
            # 日志工具目前只支持 info/warning/error，这里使用 info 代替 debug
            logger.info(f"发送AI筛选请求: URL={llm_config.api_url}, batch_size={len(batch)}")
            
            response = await client.post(
                llm_config.api_url,
                headers=headers,
                json=payload
            )
            
            # 详细记录响应状态
            logger.info(f"AI筛选响应状态: {response.status_code}")
            
            # 如果状态码不是2xx，抛出异常以便重试
            if response.status_code >= 400:
                error_body = response.text[:500]  # 只取前500字符
                error_msg = (
                    f"AI筛选API返回错误: status={response.status_code}, "
                    f"url={llm_config.api_url}, error={error_body}"
                )
                logger.error(error_msg)
                # 抛出异常以便外层重试机制捕获
                response.raise_for_status()  # 这会抛出HTTPStatusError
            
            response.raise_for_status()
            result = response.json()
            
            # 提取回复内容
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                
                # 尝试提取JSON（可能包含markdown代码块）
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # 解析JSON - 增强的容错处理
                try:
                    content_cleaned = content.strip()
                    
                    # 修复策略1: 确保以 ] 结尾
                    if not content_cleaned.endswith("]"):
                        # 找到最后一个完整的 }
                        last_brace = content_cleaned.rfind("}")
                        if last_brace > 0:
                            # 检查这个位置之前的内容是否形成有效的JSON
                            before_brace = content_cleaned[:last_brace]
                            # 简单检查：确保有匹配的 {
                            open_braces = before_brace.count("{")
                            close_braces = before_brace.count("}")
                            if open_braces > close_braces:  # 有未闭合的 {
                                # 找到最后一个完整的对象
                                content_cleaned = content_cleaned[:last_brace + 1] + "\n]"
                                logger.warning("检测到不完整的JSON数组，尝试修复...")
                    
                    # 修复策略2: 处理被截断的字符串值
                    # 如果最后一个对象中的字符串被截断，尝试移除最后一个不完整的对象
                    try:
                        parsed_results = json.loads(content_cleaned)
                    except json.JSONDecodeError as parse_error:
                        # 如果还是失败，尝试更激进的修复
                        error_msg = str(parse_error)
                        if "Unterminated string" in error_msg or "Expecting" in error_msg:
                            # 找到最后一个完整的 }, 或 \n}
                            last_complete_obj = max(
                                content_cleaned.rfind("},"),
                                content_cleaned.rfind("\n}"),
                                content_cleaned.rfind("}")
                            )
                            if last_complete_obj > 10:  # 确保有足够的内容
                                # 移除最后一个不完整的对象
                                fixed_content = content_cleaned[:last_complete_obj + 1]
                                if not fixed_content.endswith("]"):
                                    fixed_content += "\n]"
                                parsed_results = json.loads(fixed_content)
                                logger.warning("使用修复后的JSON（移除了不完整的对象）")
                            else:
                                raise parse_error
                        else:
                            raise parse_error
                    
                    # 验证和转换结果
                    validated_results = []
                    for item in parsed_results:
                        if isinstance(item, dict) and "id" in item:
                            validated_results.append(
                                TitleClassificationResult(
                                    id=str(item.get("id", "")),
                                    score=float(item.get("score", 0.5)),
                                    keep=bool(item.get("keep", True)),
                                    reason=item.get("reason")
                                )
                            )
                    
                    # 如果解析出的结果少于输入，为缺失的项创建默认结果
                    if len(validated_results) < len(batch):
                        logger.warning(
                            f"AI筛选返回结果不完整: 期望{len(batch)}, 实际{len(validated_results)}"
                        )
                        # 找出缺失的ID
                        validated_ids = {r["id"] for r in validated_results}
                        for item_id, _ in batch:
                            if item_id not in validated_ids:
                                validated_results.append(
                                    TitleClassificationResult(
                                        id=item_id,
                                        score=0.5,
                                        keep=True,
                                        reason="AI筛选结果不完整，默认保留"
                                    )
                                )
                    
                    # 确保返回结果数量与输入一致
                    if len(validated_results) == len(batch):
                        logger.info(f"AI筛选成功: {len(validated_results)}/{len(batch)}")
                        return validated_results
                    else:
                        logger.warning(
                            f"AI筛选返回结果数量仍不匹配: 期望{len(batch)}, 实际{len(validated_results)}"
                        )
                        # 如果数量仍不匹配，返回默认结果
                        return _create_default_results(batch)
                except json.JSONDecodeError as e:
                    logger.error(f"AI筛选返回的JSON解析失败: {str(e)}")
                    logger.error(f"原始内容前500字符: {content[:500]}")
                    
                    # 尝试多种修复策略
                    validated_results = None
                    
                    # 策略1: 从错误位置提取部分结果
                    try:
                        error_pos = getattr(e, 'pos', None)
                        if error_pos and error_pos > 100:
                            # 找到错误位置之前的最后一个完整对象
                            partial_content = content[:error_pos]
                            # 尝试找到最后一个完整的 }
                            last_brace = partial_content.rfind("}")
                            if last_brace > 0:
                                # 检查这个对象是否完整
                                obj_content = partial_content[:last_brace+1]
                                # 尝试解析这个对象
                                try:
                                    # 尝试提取所有完整的对象
                                    # 使用正则表达式找到所有完整的JSON对象
                                    # 匹配完整的JSON对象 { ... }（简单匹配，不处理嵌套）
                                    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                                    matches = re.findall(pattern, partial_content)
                                    if matches:
                                        # 构建JSON数组
                                        fixed_json = "[" + ",".join(matches) + "]"
                                        partial_results = json.loads(fixed_json)
                                        logger.warning(f"使用正则提取的部分结果: {len(partial_results)} 项")
                                        
                                        validated_results = []
                                        for item in partial_results:
                                            if isinstance(item, dict) and "id" in item:
                                                validated_results.append(
                                                    TitleClassificationResult(
                                                        id=str(item.get("id", "")),
                                                        score=float(item.get("score", 0.5)),
                                                        keep=bool(item.get("keep", True)),
                                                        reason=item.get("reason")
                                                    )
                                                )
                                except:
                                    pass
                    except Exception as e2:
                        logger.warning(f"部分结果提取失败: {str(e2)}")
                    
                    # 策略2: 如果策略1失败，尝试逐行解析
                    if not validated_results:
                        try:
                            # 尝试找到所有看起来像JSON对象的行
                            lines = content.split('\n')
                            objects = []
                            current_obj = ""
                            brace_count = 0
                            
                            for line in lines:
                                current_obj += line + "\n"
                                brace_count += line.count('{') - line.count('}')
                                
                                if brace_count == 0 and current_obj.strip().startswith('{'):
                                    # 找到一个完整的对象
                                    try:
                                        obj = json.loads(current_obj.strip().rstrip(','))
                                        if isinstance(obj, dict) and "id" in obj:
                                            objects.append(obj)
                                    except:
                                        pass
                                    current_obj = ""
                            
                            if objects:
                                logger.warning(f"使用逐行解析提取的结果: {len(objects)} 项")
                                validated_results = []
                                for item in objects:
                                    validated_results.append(
                                        TitleClassificationResult(
                                            id=str(item.get("id", "")),
                                            score=float(item.get("score", 0.5)),
                                            keep=bool(item.get("keep", True)),
                                            reason=item.get("reason")
                                        )
                                    )
                        except Exception as e3:
                            logger.warning(f"逐行解析失败: {str(e3)}")
                    
                    # 如果修复成功，补全缺失项
                    if validated_results:
                        validated_ids = {r["id"] for r in validated_results}
                        for item_id, _ in batch:
                            if item_id not in validated_ids:
                                validated_results.append(
                                    TitleClassificationResult(
                                        id=item_id,
                                        score=0.5,
                                        keep=True,
                                        reason="JSON解析部分失败，默认保留"
                                    )
                                )
                        if len(validated_results) == len(batch):
                            logger.warning(f"使用修复后的部分结果: {len(validated_results)}/{len(batch)}")
                            return validated_results
                    
                    # 如果所有修复策略都失败，返回默认结果
                    logger.warning("所有JSON修复策略都失败，使用默认结果（全部保留）")
                    return _create_default_results(batch)
            else:
                logger.warning(f"AI筛选API返回格式异常: {json.dumps(result, ensure_ascii=False)[:200]}")
                return _create_default_results(batch)
                
    except httpx.HTTPStatusError as e:
        # HTTP状态码错误（4xx, 5xx）
        error_body = ""
        if e.response is not None:
            try:
                error_body = e.response.text[:500]
            except:
                pass
        logger.error(
            f"AI筛选API请求失败(HTTPStatusError): "
            f"status={e.response.status_code if e.response else 'N/A'}, "
            f"url={llm_config.api_url}, "
            f"error={str(e)}, "
            f"response_body={error_body}"
        )
        return _create_default_results(batch)
    except httpx.TimeoutException as e:
        logger.error(f"AI筛选API请求超时: {str(e)}, url={llm_config.api_url}")
        return _create_default_results(batch)
    except httpx.RequestError as e:
        logger.error(f"AI筛选API请求错误(RequestError): {str(e)}, url={llm_config.api_url}")
        return _create_default_results(batch)
    except httpx.HTTPError as e:
        logger.error(f"AI筛选API请求失败(HTTPError): {str(e)}, url={llm_config.api_url}")
        return _create_default_results(batch)
    except Exception as e:
        logger.error(f"AI筛选处理异常: {type(e).__name__}: {str(e)}, url={llm_config.api_url}")
        # 为避免 logger 缺少 debug 方法，这里直接打印堆栈到标准错误输出
        import traceback, sys
        print(traceback.format_exc(), file=sys.stderr)
        return _create_default_results(batch)


def _create_default_results(
    batch: list[tuple[str, str]]
) -> list[TitleClassificationResult]:
    """
    创建默认结果（当AI筛选失败时使用）
    
    Args:
        batch: 标题批次
        
    Returns:
        默认分类结果（全部保留）
    """
    return [
        TitleClassificationResult(
            id=item_id,
            score=0.5,
            keep=True,
            reason="AI筛选失败，默认保留"
        )
        for item_id, _ in batch
    ]
