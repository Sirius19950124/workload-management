# -*- coding: utf-8 -*-
"""
AI 智能出题服务
支持: 1. 文件文本提取(PDF/Word/TXT)  2. 调用Claude API生成题目
"""

import os
import json
import re
import requests


def get_ai_config():
    """AI配置：全部从数据库读取，不硬编码"""
    try:
        from app.models import WorkloadSettings
        api_key = (WorkloadSettings.get_value('ai_api_key') or '').strip()
        model = (WorkloadSettings.get_value('ai_model') or '').strip()
        base_url = (WorkloadSettings.get_value('ai_api_base_url') or '').strip()
    except Exception:
        api_key, model, base_url = '', '', ''

    if not api_key:
        raise ValueError("未配置AI API Key，请在「设置→在线培训考试→成绩统计」中填写API Key、模型和接口地址")

    return {
        'api_key': api_key,
        'model': model or 'glm-5v-turbo',
        'api_base_url': base_url or 'https://open.bigmodel.cn/api/anthropic',
    }


def extract_text_from_file(file_path):
    """
    从上传的文件中提取纯文本内容
    支持格式: PDF, Word(.docx), TXT
    返回: 提取的文本字符串, 文件类型标识
    """
    if not os.path.exists(file_path):
        return '', 'unknown'

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.pdf':
            return _extract_pdf_text(file_path), 'pdf'
        elif ext in ('.docx', '.doc'):
            return _extract_docx_text(file_path), 'word'
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(), 'txt'
        else:
            # 尝试作为文本读取
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(), 'txt'
    except Exception as e:
        print(f"[AI] 文本提取失败: {e}")
        return '', ext.lstrip('.')


def _extract_pdf_text(pdf_path):
    """提取PDF文件文本"""
    try:
        import PyPDF2
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n'.join(text_parts)
    except ImportError:
        print("[AI] PyPDF2未安装，无法提取PDF文本")
        return ''
    except Exception as e:
        print(f"[AI] PDF提取错误: {e}")
        return ''


def _extract_docx_text(docx_path):
    """提取Word文档文本"""
    try:
        from docx import Document
        doc = Document(docx_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n'.join(paragraphs)
    except ImportError:
        print("[AI] python-docx未安装，无法提取Word文本")
        return ''
    except Exception as e:
        print(f"[AI] Word提取错误: {e}")
        return ''


def build_generation_prompt(material_text, question_types, count, difficulty=None):
    """
    构建AI出题Prompt

    Args:
        material_text: 培训资料文本内容
        question_types: list of str, 如 ['single_choice', 'multiple_choice']
        count: int, 生成题目数量
        difficulty: str, 难度偏好 easy/medium/hard/auto

    Returns:
        (system_prompt, user_prompt) tuple
    """
    type_map = {
        'single_choice': '单选题',
        'multiple_choice': '多选题',
        'true_false': '判断题',
        'fill_blank': '填空题',
    }
    type_desc = '、'.join([type_map.get(t, t) for t in question_types])

    system_prompt = f"""你是一个专业的医学考试命题专家，专门为康复科治疗师培训考核出题。
你的任务是根据提供的培训材料内容，生成{count}道{type_desc}。

严格要求：
1. 所有题目必须严格基于提供的材料内容，不得超出材料范围
2. 题目应覆盖材料的核心知识点和关键信息
3. 难度适中，适合康复科治疗师的专业水平
4. 每道题必须有明确且唯一的正确答案
5. 填空题答案要简洁明确（关键词即可）
6. 选项内容要具有迷惑性但明显有正误之分"""

    # 截断过长的材料文本（保留约8000字符）
    if len(material_text) > 8000:
        material_text = material_text[:8000] + '\n...(以下内容省略)'

    user_prompt = f"""请根据以下培训材料，生成{count}道{type_desc}。

【难度要求】{'自动匹配' if not difficulty or difficulty == 'auto' else {'简单' if difficulty == 'easy' else '中等' if difficulty == 'medium' else '困难'}}

【材料内容】
{material_text}

请严格按以下JSON格式输出，不要添加任何其他文字、解释或markdown标记：
{{
  "questions": [
    {{
      "question_type": "single_choice",
      "question_text": "题干内容",
      "options": [
        {{"label": "A", "text": "选项A内容"}},
        {{"label": "B", "text": "选项B内容"}},
        {{"label": "C", "text": "选项C内容"}},
        {{"label": "D", "text": "选项D内容"}}
      ],
      "answer": "B",
      "analysis": "解析说明",
      "difficulty": "medium"
    }}
  ]
}}

注意：
- single_choice(单选): answer为单个选项label如"B"
- multiple_choice(多选): answer为多个label组合如"AC"，options必须有4个选项
- true_false(判断题): answer为"T"或"F"，options字段设为[{{"label":"T","text":"正确"}},{{"label":"F","text":"错误"}}]
- fill_blank(填空题): options设为空数组[]，answer为标准答案文本

现在请生成题目："""

    return system_prompt, user_prompt


def call_ai_api(system_prompt, user_prompt, max_retries=3):
    """
    调用AI API生成题目（Anthropic Messages API 兼容格式）
    通过智谱 /api/anthropic 端点调用 glm-5v-turbo 等模型
    """
    config = get_ai_config()

    if not config['api_key']:
        raise ValueError("未配置AI API Key，请在设置中填写")

    # 智谱Anthropic兼容端点: /api/anthropic/v1 + /messages
    base_url = (config['api_base_url'] or 'https://open.bigmodel.cn/api/anthropic').rstrip('/')
    api_url = base_url + '/v1/messages'
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': config['api_key'],
        'anthropic-version': '2023-06-01',
    }
    payload = {
        'model': config['model'],
        'max_tokens': 4096,
        'system': system_prompt,
        'messages': [
            {'role': 'user', 'content': user_prompt}
        ]
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            print(f"[AI] 调用 {config['model']} (第{attempt+1}次)...")
            response = requests.post(api_url, headers=headers, json=payload, timeout=120)

            if response.status_code == 200:
                data = response.json()
                content_blocks = data.get('content', [])
                if content_blocks:
                    text = ''.join(block.get('text', '') for block in content_blocks if block.get('type') == 'text')
                    if text.strip():
                        print(f"[AI] API调用成功，返回{text[:100]}...")
                        return text
                raise ValueError("API返回内容为空")
            elif response.status_code == 429:
                import time
                wait_time = min(60, (attempt + 1) * 10)
                print(f"[AI] API限流，等待{wait_time}秒后重试...")
                time.sleep(wait_time)
                last_error = f"API限流 (HTTP 429)"
            else:
                error_detail = response.text[:500]
                last_error = f"API错误 (HTTP {response.status_code}): {error_detail}"
                print(f"[AI] API错误: {last_error}")

        except requests.exceptions.Timeout:
            last_error = "API请求超时"
            print(f"[AI] {last_error} (第{attempt+1}次)")
        except requests.exceptions.RequestException as e:
            last_error = f"网络请求异常: {str(e)}"
            print(f"[AI] {last_error} (第{attempt+1}次)")
        except Exception as e:
            last_error = str(e)
            print(f"[AI] 异常: {last_error} (第{attempt+1}次)")

    raise ValueError(f"AI出题失败，已重试{max_retries}次。最后错误: {last_error}")


def parse_questions_from_response(response_text):
    """
    从AI响应中解析并验证题目JSON

    Args:
        response_text: AI返回的原始文本

    Returns:
        list: 解析出的题目字典列表
    """
    text = response_text.strip()

    # 尝试直接解析JSON
    questions = _try_parse_json(text)

    if not questions:
        # 尝试用正则提取JSON部分
        json_match = re.search(r'\{[\s\S]*"questions"[\s\S]*\}', text)
        if json_match:
            questions = _try_parse_json(json_match.group())

    if not questions:
        # 尝试提取数组部分
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            raw_array = '[' + array_match.group() + ']'
            try:
                data = json.loads(raw_array)
                if isinstance(data, list):
                    questions = data
            except:
                pass

    if not questions:
        raise ValueError("无法从AI响应中解析出有效的题目JSON")

    # 验证并清洗每道题
    validated = []
    for i, q in enumerate(questions):
        validated_q = _validate_question(q, i)
        if validated_q:
            validated.append(validated_q)

    if not validated:
        raise ValueError("所有生成的题目均未通过验证")

    print(f"[AI] 成功解析并验证 {len(validated)} 道题目")
    return validated


def _try_parse_json(text):
    """尝试解析JSON字符串"""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and 'questions' in data:
            return data['questions']
        elif isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def _validate_question(q, index):
    """
    验证单道题目的完整性

    Returns:
        dict: 清洗后的题目字典，或None(无效题目)
    """
    required_fields = ['question_type', 'question_text', 'answer']
    valid_types = {'single_choice', 'multiple_choice', 'true_false', 'fill_blank'}

    # 检查必填字段
    for field in required_fields:
        if field not in q or not str(q[field]).strip():
            print(f"[AI] 第{index+1}题缺少必填字段: {field}")
            return None

    # 验证题型
    qtype = q.get('question_type', '')
    if qtype not in valid_types:
        print(f"[AI] 第{index+1}题题型无效: {qtype}")
        return None

    # 清洗选项
    options = q.get('options', [])
    if qtype in ('single_choice', 'multiple_choice'):
        if not isinstance(options, list) or len(options) < 2:
            print(f"[AI] 第{index+1}题选项不足")
            return None
        # 确保每个选项有label和text
        cleaned_options = []
        for opt in options:
            if isinstance(opt, dict) and opt.get('label') and opt.get('text'):
                cleaned_options.append({
                    'label': str(opt['label']).strip(),
                    'text': str(opt['text']).strip()
                })
        if len(cleaned_options) < 2:
            print(f"[AI] 第{index+1}题有效选项不足")
            return None
        options = cleaned_options
    elif qtype == 'true_false':
        options = [
            {'label': 'T', 'text': '正确'},
            {'label': 'F', 'text': '错误'}
        ]
    else:
        options = []

    # 构建最终题目字典
    return {
        'question_type': qtype,
        'question_text': str(q['question_text']).strip(),
        'options': json.dumps(options, ensure_ascii=False) if options else '',
        'answer': str(q['answer']).strip(),
        'analysis': str(q.get('analysis', '')).strip() if q.get('analysis') else '',
        'difficulty': q.get('difficulty', 'medium') if q.get('difficulty') in ('easy', 'medium', 'hard') else 'medium',
        'score': 2,
        'source': 'ai_generated'
    }


def generate_questions(material_text, question_types, count=10, difficulty=None):
    """
    主函数：根据资料文本生成题目

    Args:
        material_text: 培训资料文本
        question_types: 题型列表, 如 ['single_choice', 'true_false']
        count: 生成数量
        difficulty: 难度

    Returns:
        list: 题目字典列表（可直接用于QuestionBank创建）
    """
    if not material_text or not material_text.strip():
        raise ValueError("资料文本为空，无法生成题目")

    # 构建prompt
    system_prompt, user_prompt = build_generation_prompt(
        material_text, question_types, count, difficulty
    )

    # 调用API
    response_text = call_ai_api(system_prompt, user_prompt)

    # 解析结果
    questions = parse_questions_from_response(response_text)

    return questions
