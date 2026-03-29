"""
文本预处理器
负责分句、去格式、编码标准化、长度校验
"""

import re
import hashlib
from dataclasses import dataclass, field


@dataclass
class ProcessedText:
    """预处理后的文本结构"""
    full_text: str
    sentences: list[str]
    paragraphs: list[str]
    word_count: int
    language: str
    content_hash: str
    paragraph_offsets: list[tuple[int, int]] = field(default_factory=list)


class TextPreprocessor:
    """文本预处理管道"""

    # 中文句子结束标点
    ZH_SENTENCE_ENDINGS = re.compile(r'([。！？；…]+)')
    # 英文句子结束标点
    EN_SENTENCE_ENDINGS = re.compile(r'([.!?;]+)\s')
    # HTML/Markdown/LaTeX标记
    FORMAT_PATTERNS = [
        (re.compile(r'<[^>]+>'), ''),              # HTML tags
        (re.compile(r'\$\$?[^$]+\$\$?'), ''),      # LaTeX math
        (re.compile(r'\\[a-zA-Z]+\{[^}]*\}'), ''), # LaTeX commands
        (re.compile(r'#{1,6}\s'), ''),              # Markdown headers
        (re.compile(r'\*{1,3}([^*]+)\*{1,3}'), r'\1'),  # Markdown bold/italic
        (re.compile(r'\[([^\]]+)\]\([^)]+\)'), r'\1'),   # Markdown links
    ]

    MIN_TEXT_LENGTH = 200   # 最小文本长度（字符）
    MAX_TEXT_LENGTH = 60000  # 最大文本长度（字符）

    def process(self, raw_text: str, language: str = "auto") -> ProcessedText:
        """执行完整预处理管道"""
        # 1. 编码标准化
        text = self._normalize_encoding(raw_text)

        # 2. 去除格式标记
        text = self._strip_formatting(text)

        # 3. 清理多余空白
        text = self._clean_whitespace(text)

        # 4. 检测语言
        if language == "auto":
            language = self._detect_language(text)

        # 5. 长度校验
        self._validate_length(text)

        # 6. 计算内容hash（用于缓存）
        content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

        # 7. 分段
        paragraphs, paragraph_offsets = self._segment_paragraphs(text)

        # 8. 分句
        sentences = self._segment_sentences(text, language)

        # 9. 字数统计
        word_count = self._count_words(text, language)

        return ProcessedText(
            full_text=text,
            sentences=sentences,
            paragraphs=paragraphs,
            word_count=word_count,
            language=language,
            content_hash=content_hash,
            paragraph_offsets=paragraph_offsets,
        )

    def _normalize_encoding(self, text: str) -> str:
        """编码标准化为UTF-8"""
        # 全角转半角（数字和字母）
        result = []
        for char in text:
            code = ord(char)
            if 0xFF01 <= code <= 0xFF5E:
                # 全角ASCII -> 半角（保留中文标点不转换）
                if 0xFF10 <= code <= 0xFF19 or 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A:
                    result.append(chr(code - 0xFEE0))
                else:
                    result.append(char)
            else:
                result.append(char)
        return ''.join(result)

    def _strip_formatting(self, text: str) -> str:
        """去除格式标记"""
        for pattern, replacement in self.FORMAT_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _clean_whitespace(self, text: str) -> str:
        """清理多余空白"""
        # 合并多个空行为一个
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 去除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()

    def _detect_language(self, text: str) -> str:
        """简单的语言检测"""
        # 统计中文字符占比
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.replace(' ', '').replace('\n', ''))
        if total_chars == 0:
            return "zh"
        zh_ratio = zh_chars / total_chars
        return "zh" if zh_ratio > 0.3 else "en"

    def _validate_length(self, text: str) -> None:
        """长度校验"""
        if len(text) < self.MIN_TEXT_LENGTH:
            raise ValueError(
                f"文本过短（{len(text)}字符），最少需要{self.MIN_TEXT_LENGTH}字符。"
                f"过短的文本可能导致分析结果不可靠。"
            )
        if len(text) > self.MAX_TEXT_LENGTH:
            raise ValueError(
                f"文本过长（{len(text)}字符），最多支持{self.MAX_TEXT_LENGTH}字符。"
                f"请分段提交。"
            )

    def _segment_paragraphs(self, text: str) -> tuple[list[str], list[tuple[int, int]]]:
        """分段"""
        paragraphs = []
        offsets = []
        current_pos = 0

        for para in text.split('\n\n'):
            para = para.strip()
            if para and len(para) > 20:  # 忽略过短的段落
                start = text.find(para, current_pos)
                end = start + len(para)
                paragraphs.append(para)
                offsets.append((start, end))
                current_pos = end

        # 如果没有明显分段，按长度切分
        if len(paragraphs) <= 1 and len(text) > 500:
            paragraphs = []
            offsets = []
            # 按句号分段，每段约300-500字
            sentences = self._segment_sentences(text, "zh")
            current_para = []
            current_len = 0
            para_start = 0
            for sent in sentences:
                current_para.append(sent)
                current_len += len(sent)
                if current_len >= 300:
                    para_text = ''.join(current_para)
                    para_start_pos = text.find(para_text[: 20], para_start)
                    if para_start_pos == -1:
                        para_start_pos = para_start
                    paragraphs.append(para_text)
                    offsets.append((para_start_pos, para_start_pos + len(para_text)))
                    para_start = para_start_pos + len(para_text)
                    current_para = []
                    current_len = 0
            if current_para:
                para_text = ''.join(current_para)
                paragraphs.append(para_text)
                offsets.append((para_start, para_start + len(para_text)))

        return paragraphs, offsets

    def _segment_sentences(self, text: str, language: str) -> list[str]:
        """分句"""
        if language == "zh":
            # 中文：按中文标点分句
            parts = self.ZH_SENTENCE_ENDINGS.split(text)
            sentences = []
            i = 0
            while i < len(parts):
                sent = parts[i]
                # 将标点附加到句子末尾
                if i + 1 < len(parts):
                    sent += parts[i + 1]
                    i += 2
                else:
                    i += 1
                sent = sent.strip()
                if sent and len(sent) > 5:
                    sentences.append(sent)
            return sentences
        else:
            # 英文：按英文标点分句
            parts = self.EN_SENTENCE_ENDINGS.split(text)
            sentences = []
            i = 0
            while i < len(parts):
                sent = parts[i]
                if i + 1 < len(parts):
                    sent += parts[i + 1]
                    i += 2
                else:
                    i += 1
                sent = sent.strip()
                if sent and len(sent) > 10:
                    sentences.append(sent)
            return sentences

    def _count_words(self, text: str, language: str) -> int:
        """字数统计"""
        if language == "zh":
            # 中文：统计字符数（不含标点和空格）
            zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            en_words = len(re.findall(r'[a-zA-Z]+', text))
            return zh_chars + en_words
        else:
            return len(text.split())
