"""
OCR Service — PDF图像识别与文本提取

流程：
1. 使用 PyMuPDF 将 PDF 每页渲染为图片
2. 将图片发送到配置的视觉模型（OCR任务类型）进行文字识别
3. 合并所有页面的文本
4. 使用 LLM 评估 OCR 文本质量，给出准确率参考指标
"""

import base64
import logging
from typing import Optional

import fitz  # pymupdf

from app.services.llm_gateway.client import LLMClient

logger = logging.getLogger(__name__)

# 页面渲染DPI（平衡清晰度与性能）
RENDER_DPI = 200
# 单次OCR最大页数
MAX_OCR_PAGES = 50


async def check_ocr_available(llm_client: LLMClient) -> bool:
    """检查是否配置了OCR模型"""
    route = llm_client.model_routes.get("ocr", {})
    return bool(route.get("primary"))


async def ocr_pdf(
    pdf_bytes: bytes,
    llm_client: LLMClient,
    max_pages: int = MAX_OCR_PAGES,
) -> dict:
    """
    对PDF进行OCR识别。

    Args:
        pdf_bytes: PDF文件的二进制内容
        llm_client: LLM客户端实例
        max_pages: 最大处理页数

    Returns:
        {
            "text": str,           # OCR识别出的文本
            "page_count": int,     # 总页数
            "processed_pages": int, # 实际处理的页数
            "accuracy_estimate": float,  # 文本准确率估计 (0-1)
            "accuracy_note": str,  # 准确率说明
        }
    """
    # 1. 打开PDF并渲染页面为图片
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    pages_to_process = min(total_pages, max_pages)

    logger.info(f"OCR开始: 总页数={total_pages}, 处理页数={pages_to_process}")

    page_texts: list[str] = []

    for page_idx in range(pages_to_process):
        page = doc[page_idx]

        # 渲染为PNG图片
        mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode("ascii")

        # 调用视觉模型进行OCR
        try:
            page_text = await llm_client.chat_with_image(
                task_type="ocr",
                system_prompt=(
                    "你是一个专业的OCR文字识别系统。请精确识别图片中的所有文字内容，"
                    "保持原始的段落结构和格式。只输出识别到的文字内容，不要添加任何额外说明。"
                    "如果图片中没有文字，输出空字符串。"
                    "注意保留原文的标点符号、换行和缩进。"
                ),
                user_prompt=f"请识别这张图片（第{page_idx + 1}/{pages_to_process}页）中的所有文字内容：",
                image_base64=img_base64,
                mime_type="image/png",
                max_tokens=4096,
                temperature=0.1,
            )
            if page_text and page_text.strip():
                page_texts.append(page_text.strip())
                logger.info(f"OCR第{page_idx + 1}页完成，提取文字{len(page_text)}字符")
            else:
                logger.info(f"OCR第{page_idx + 1}页无文字内容")
        except Exception as e:
            logger.warning(f"OCR第{page_idx + 1}页失败: {e}")
            continue

    doc.close()

    full_text = "\n\n".join(page_texts)

    if not full_text.strip():
        return {
            "text": "",
            "page_count": total_pages,
            "processed_pages": pages_to_process,
            "accuracy_estimate": 0.0,
            "accuracy_note": "未能从PDF中识别到任何文字内容",
        }

    # 2. 使用LLM评估OCR质量
    accuracy_estimate, accuracy_note = await _evaluate_ocr_quality(
        full_text, llm_client
    )

    return {
        "text": full_text,
        "page_count": total_pages,
        "processed_pages": pages_to_process,
        "accuracy_estimate": accuracy_estimate,
        "accuracy_note": accuracy_note,
    }


async def _evaluate_ocr_quality(
    text: str,
    llm_client: LLMClient,
) -> tuple[float, str]:
    """
    使用LLM评估OCR文本质量。

    Returns:
        (accuracy_estimate, accuracy_note)
    """
    # 截取前2000字符用于质量评估
    sample = text[:2000]

    try:
        response = await llm_client.chat(
            task_type="ocr",
            system_prompt=(
                "你是一个文本质量评估专家。请评估以下OCR识别文本的质量，"
                "考虑以下因素：\n"
                "1. 文字是否有明显乱码或无意义字符\n"
                "2. 标点符号是否合理\n"
                "3. 语句是否连贯通顺\n"
                "4. 是否有大量错别字或识别错误\n"
                "5. 段落结构是否合理\n\n"
                "请严格按照以下JSON格式回复（不要添加其他内容）：\n"
                '{"accuracy": 0.85, "note": "文本整体识别质量良好，少量标点可能有误"}\n'
                "其中 accuracy 为 0.0-1.0 之间的浮点数，"
                "note 为一句话简要说明。"
            ),
            user_prompt=f"请评估以下OCR识别文本的质量：\n\n{sample}",
            response_format="json",
            max_tokens=256,
            temperature=0.1,
        )

        import json
        result = json.loads(response.strip())
        accuracy = float(result.get("accuracy", 0.7))
        accuracy = max(0.0, min(1.0, accuracy))
        note = result.get("note", "OCR识别完成")
        return accuracy, note

    except Exception as e:
        logger.warning(f"OCR质量评估失败: {e}")
        return 0.7, "OCR识别完成（质量评估不可用）"
