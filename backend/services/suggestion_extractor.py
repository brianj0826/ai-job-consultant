"""Extract validated, user-confirmable career record suggestions from chat."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from typing import Any, Optional

from backend.schemas.career import (
    ApplicationSuggestionCreate,
    InterviewCreate,
    JobCreate,
    QuestionCreate,
    ReportCreate,
    ResumeCreate,
    SkillCreate,
)
from backend.services import career as career_service
from backend.services.deepseek_api import get_ai_response_with_tools


logger = logging.getLogger("aiagent.career_suggestion_extractor")

RESOURCE_TYPES = {
    "resumes",
    "jobs",
    "applications",
    "interviews",
    "reports",
    "skills",
    "interview_questions",
}

RESOURCE_MODELS = {
    "resumes": ResumeCreate,
    "jobs": JobCreate,
    "applications": ApplicationSuggestionCreate,
    "interviews": InterviewCreate,
    "reports": ReportCreate,
    "skills": SkillCreate,
}

ALLOWED_PAYLOAD_FIELDS = {
    "resumes": {"title", "target_role", "content", "source_name", "is_primary"},
    "jobs": {"title", "company", "description", "source_url", "status"},
    "applications": {"job_id", "stage", "next_action", "deadline", "notes"},
    "interviews": {"job_id", "title", "status", "overall_score"},
    "reports": {"kind", "title", "entity_type", "entity_id", "summary", "payload"},
    "skills": {"skill", "target_level", "status", "progress", "due_date", "notes"},
    "interview_questions": {"interview_id", "questions"},
}

EXPLICIT_SAVE_PATTERN = re.compile(
    r"(?:保存|添加|记录|加入|创建|新建|存入|存下|建个|帮我存|制定.{0,6}计划|"
    r"安排.{0,6}面试|模拟面试|出.{0,6}(?:面试)?题|生成.{0,6}(?:面试)?题|"
    r"已经?投递|投递了|投了)|"
    r"\b(?:save|add|record|create|track|schedule|plan|applied)\b",
    re.IGNORECASE,
)
APPLICATION_INTENT_PATTERN = re.compile(
    r"(?:保存|添加|记录|跟踪).{0,20}(?:投递|申请)|"
    r"(?:已经?投递|投递了|投了|已经?申请|申请了)|"
    r"\b(?:record|track|save|add).{0,30}(?:application|applied)|"
    r"\b(?:i\s+(?:have\s+)?applied|applied\s+(?:for|to))\b",
    re.IGNORECASE,
)
INTERVIEW_INTENT_PATTERN = re.compile(
    r"(?:安排|创建|添加|记录|模拟|准备).{0,20}(?:面试)|"
    r"(?:面试).{0,20}(?:今天|明天|后天|周[一二三四五六日天]|星期|月|日|号|点)|"
    r"(?:今天|明天|后天|周[一二三四五六日天]|星期[一二三四五六日天]|"
    r"\d{1,2}月\d{0,2}[日号]?).{0,30}(?:面试)|"
    r"\b(?:schedule|record|add|mock|prepare).{0,30}interview\b",
    re.IGNORECASE,
)
DATE_EXPRESSION_PATTERN = re.compile(
    r"\b\d{4}[-/.]\d{1,2}(?:[-/.]\d{1,2})?\b|"
    r"\b\d{1,2}[-/.]\d{1,2}\b|"
    r"(?:今天|明天|后天|本周|下周|这个月|本月|下个月|月底|年末|年底|"
    r"周[一二三四五六日天]|星期[一二三四五六日天]|\d{1,2}月\d{0,2}[日号]?)|"
    r"\b(?:today|tomorrow|next\s+(?:week|month)|this\s+(?:week|month)|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


SUGGESTION_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_career_suggestions",
        "description": "Propose structured career records that the user may confirm and add.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["suggestions"],
            "properties": {
                "suggestions": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "resource_type",
                            "title",
                            "reason",
                            "intent",
                            "confidence",
                            "payload",
                        ],
                        "properties": {
                            "resource_type": {
                                "type": "string",
                                "enum": sorted(RESOURCE_TYPES),
                            },
                            "title": {"type": "string"},
                            "reason": {"type": "string"},
                            "intent": {
                                "type": "string",
                                "enum": ["explicit", "high_confidence"],
                            },
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "payload": {"type": "object"},
                            "relation_hints": {"type": "object"},
                        },
                    },
                }
            },
        },
    },
}

FORCED_TOOL_CHOICE = {
    "type": "function",
    "function": {"name": "propose_career_suggestions"},
}

EXTRACTION_SYSTEM_PROMPT = """你是职业数据建议识别器，只能调用 propose_career_suggestions。
你的输出不是写数据库，而是生成等待用户确认的 create 建议。最多 3 条。

仅在以下情况建议：
1. 用户明确要求保存、添加、记录或创建；或
2. 内容是关于用户本人的、高置信度、已经足够具体且可执行的职业事实/计划。

闲聊、假设、教学示例、第三方经历、低置信度信息一律返回空数组。不要生成更新、删除、设为主简历或自动推进状态的建议。不要编造日期、关系 ID、简历正文或 JD。

类型与默认值：
- resumes：必须包含完整简历正文；is_primary=false。
- jobs：必须有明确岗位和足够 JD；status=saved。
- applications：仅当用户明确要记录申请或表示已经投递；只有目录中唯一明确匹配时才填写 job_id，否则省略并让用户选择。
- interviews：仅当用户明确安排、记录或模拟面试；status=planned，overall_score=null。
- reports：kind 只能是 resume_analysis/job_match/interview_review/career_plan；payload.schema_version=1；entity_type/entity_id 同时有或同时无。
- skills：status=planned、progress=0；只有用户提到日期时才能填写 due_date。
- interview_questions：只有目录中唯一明确匹配时才填写 interview_id，否则省略并让用户选择；questions 为 1 至 10 题；每题只能写 question、reference_answer、coaching_notes，不能填写 position、用户 answer、feedback 或 score。

不支持跨建议依赖：如果投递、面试或题目所需的关联记录尚不存在，就不要生成该建议。
intent=explicit 仅用于用户明确要求或明确陈述已发生事实；否则只能在 confidence>=0.9 时使用 high_confidence。
不得输出 user_id，也不得使用目录外的关系 ID。"""


def suggestions_enabled() -> bool:
    return os.getenv("CAREER_SUGGESTIONS_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def suggestion_timeout_seconds() -> float:
    raw = os.getenv("CAREER_SUGGESTION_TIMEOUT_SECONDS", "8")
    try:
        return max(1.0, min(float(raw), 30.0))
    except (TypeError, ValueError):
        return 8.0


def _items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return [item for item in result["items"] if isinstance(item, dict)]
    return []


def _compact(items: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{field: item.get(field) for field in fields if item.get(field) is not None} for item in items]


def load_career_catalog(user_id: int) -> dict[str, list[dict[str, Any]]]:
    """Load only identifiers and labels needed for ownership-safe relation matching."""
    loaders = {
        "resumes": (career_service.list_resumes, ("id", "title", "target_role")),
        "jobs": (career_service.list_jobs, ("id", "title", "company", "status")),
        "applications": (career_service.list_applications, ("id", "job_id", "stage")),
        "interviews": (career_service.list_interviews, ("id", "job_id", "title", "status")),
        "skills": (career_service.list_skills, ("id", "skill", "status")),
    }
    catalog: dict[str, list[dict[str, Any]]] = {}
    for resource_type, (loader, fields) in loaders.items():
        try:
            catalog[resource_type] = _compact(_items(loader(user_id, limit=30)), fields)
        except Exception as error:
            # Suggestions are optional. A catalog read failure must not fail chat.
            logger.warning(
                "Career suggestion catalog read failed type=%s error=%s",
                resource_type,
                type(error).__name__,
            )
            catalog[resource_type] = []
    return catalog


def _model_validate(model_type, value: dict[str, Any]):
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(value)
    return model_type.parse_obj(value)


def _model_dump_json(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _owned_ids(catalog: dict[str, list[dict[str, Any]]], resource_type: str) -> set[int]:
    return {
        int(item["id"])
        for item in catalog.get(resource_type, [])
        if isinstance(item.get("id"), int) or str(item.get("id", "")).isdigit()
    }


def _relation_is_owned(
    resource_type: str,
    payload: dict[str, Any],
    catalog: dict[str, list[dict[str, Any]]],
) -> bool:
    if resource_type == "applications":
        owned_jobs = _owned_ids(catalog, "jobs")
        return (
            bool(owned_jobs)
            if payload.get("job_id") is None
            else payload.get("job_id") in owned_jobs
        )
    if resource_type == "interviews" and payload.get("job_id") is not None:
        return payload["job_id"] in _owned_ids(catalog, "jobs")
    if resource_type == "interview_questions":
        owned_interviews = _owned_ids(catalog, "interviews")
        return (
            bool(owned_interviews)
            if payload.get("interview_id") is None
            else payload.get("interview_id") in owned_interviews
        )
    if resource_type == "reports" and payload.get("entity_id") is not None:
        entity_catalog = {
            "resume": "resumes",
            "job": "jobs",
            "application": "applications",
            "interview": "interviews",
            "skill": "skills",
        }.get(payload.get("entity_type"))
        return bool(entity_catalog) and payload["entity_id"] in _owned_ids(catalog, entity_catalog)
    return True


def _safe_relation_hints(resource_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if resource_type in {"applications", "interviews"} and payload.get("job_id"):
        return {"job_id": payload["job_id"]}
    if resource_type == "interview_questions" and payload.get("interview_id"):
        return {"interview_id": payload["interview_id"]}
    if resource_type == "reports" and payload.get("entity_id"):
        return {"entity_type": payload["entity_type"], "entity_id": payload["entity_id"]}
    return {}


def _validate_question_batch(payload: dict[str, Any]) -> dict[str, Any]:
    interview_id = payload.get("interview_id")
    if interview_id is not None and (
        not isinstance(interview_id, int) or interview_id <= 0
    ):
        raise ValueError("invalid interview_id")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 10:
        raise ValueError("questions must contain 1 to 10 items")

    normalized = []
    allowed = {"question", "reference_answer", "coaching_notes"}
    for question in questions:
        if not isinstance(question, dict) or set(question) - allowed:
            raise ValueError("invalid question fields")
        candidate = {
            "question": question.get("question"),
            "answer": "",
            "score": None,
            "feedback": "",
            "reference_answer": question.get("reference_answer", ""),
            "coaching_notes": question.get("coaching_notes", ""),
        }
        validated = _model_dump_json(_model_validate(QuestionCreate, candidate))
        normalized.append(
            {
                key: validated[key]
                for key in ("question", "reference_answer", "coaching_notes")
            }
        )
    return {"interview_id": interview_id, "questions": normalized}


def _validate_payload(
    resource_type: str,
    payload: dict[str, Any],
    user_message: str,
    catalog: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    def contains_user_id(value: Any) -> bool:
        if isinstance(value, dict):
            return "user_id" in value or any(contains_user_id(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_user_id(item) for item in value)
        return False

    if contains_user_id(payload):
        raise ValueError("user_id is server controlled")
    if set(payload) - ALLOWED_PAYLOAD_FIELDS[resource_type]:
        raise ValueError("unknown payload fields")

    if resource_type == "interview_questions":
        normalized = _validate_question_batch(payload)
    else:
        prepared = dict(payload)
        if resource_type == "resumes":
            prepared["is_primary"] = False
        elif resource_type == "jobs":
            prepared["status"] = "saved"
        elif resource_type == "interviews":
            prepared["status"] = "planned"
            prepared["overall_score"] = None
        elif resource_type == "reports":
            report_payload = prepared.get("payload")
            if not isinstance(report_payload, dict):
                report_payload = {}
            prepared["payload"] = {**report_payload, "schema_version": 1}
            if (prepared.get("entity_type") is None) != (prepared.get("entity_id") is None):
                raise ValueError("report relation must be a pair")
        elif resource_type == "skills":
            prepared["status"] = "planned"
            prepared["progress"] = 0
            if prepared.get("due_date") is not None and not DATE_EXPRESSION_PATTERN.search(user_message):
                raise ValueError("skill due date was not supplied by the user")
        normalized = _model_dump_json(_model_validate(RESOURCE_MODELS[resource_type], prepared))

    if (
        resource_type == "applications"
        and normalized.get("stage") not in career_service.APPLICATION_STAGES
    ):
        raise ValueError("invalid application stage")
    if resource_type == "reports" and normalized.get("kind") not in career_service.REPORT_KINDS:
        raise ValueError("invalid report kind")
    if resource_type == "resumes" and len(normalized.get("content", "").strip()) < 80:
        raise ValueError("resume content is incomplete")
    if resource_type == "jobs" and len(normalized.get("description", "").strip()) < 40:
        raise ValueError("job description is incomplete")
    if not _relation_is_owned(resource_type, normalized, catalog):
        raise ValueError("relation does not belong to the user")
    return normalized


def _parse_tool_arguments(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    try:
        message = result["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        if function.get("name") != "propose_career_suggestions":
            continue
        arguments = function.get("arguments", "{}")
        try:
            decoded = json.loads(arguments) if isinstance(arguments, str) else arguments
        except (json.JSONDecodeError, TypeError):
            return []
        suggestions = decoded.get("suggestions") if isinstance(decoded, dict) else None
        return suggestions if isinstance(suggestions, list) else []
    return []


def _recent_context(messages: Optional[list[dict[str, Any]]]) -> list[dict[str, str]]:
    result = []
    for message in (messages or [])[-6:]:
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            result.append({"role": role, "content": content[:4000]})
    return result


def extract_career_suggestions(
    user_id: int,
    user_message: str,
    assistant_response: str,
    *,
    recent_messages: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Return up to three validated suggestion drafts; never raise to chat."""
    if not suggestions_enabled() or not user_message.strip() or not assistant_response.strip():
        return []

    started = time.monotonic()
    try:
        catalog = load_career_catalog(user_id)
        request_messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "recent_conversation": _recent_context(recent_messages),
                        "latest_user_message": user_message[:20_000],
                        "assistant_response": assistant_response[:30_000],
                        "career_catalog": catalog,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ]
        result = get_ai_response_with_tools(
            request_messages,
            tools=[SUGGESTION_TOOL],
            tool_choice=FORCED_TOOL_CHOICE,
            timeout=suggestion_timeout_seconds(),
            max_retries=0,
        )
        raw_suggestions = _parse_tool_arguments(result)[:3]
        explicit_message = bool(EXPLICIT_SAVE_PATTERN.search(user_message))
        application_intent = bool(APPLICATION_INTENT_PATTERN.search(user_message))
        interview_intent = bool(INTERVIEW_INTENT_PATTERN.search(user_message))

        drafts: list[dict[str, Any]] = []
        fingerprints: set[str] = set()
        for raw in raw_suggestions:
            if not isinstance(raw, dict):
                continue
            if set(raw) - {
                "resource_type",
                "title",
                "reason",
                "intent",
                "confidence",
                "payload",
                "relation_hints",
            }:
                continue
            resource_type = raw.get("resource_type")
            title = raw.get("title")
            reason = raw.get("reason", "")
            payload = raw.get("payload")
            intent = raw.get("intent")
            confidence = raw.get("confidence")
            if (
                resource_type not in RESOURCE_TYPES
                or not isinstance(title, str)
                or not title.strip()
                or len(title.strip()) > 255
                or not isinstance(reason, str)
                or len(reason) > 1000
                or not isinstance(payload, dict)
                or isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not math.isfinite(float(confidence))
                or not 0 <= float(confidence) <= 1
            ):
                continue
            resource_explicit = explicit_message or (
                resource_type == "applications" and application_intent
            ) or (resource_type == "interviews" and interview_intent)
            is_explicit = intent == "explicit" and resource_explicit
            if not is_explicit and not (intent == "high_confidence" and float(confidence) >= 0.9):
                continue
            if resource_type == "applications" and not application_intent:
                continue
            if resource_type == "interviews" and not interview_intent:
                continue
            normalized = _validate_payload(resource_type, payload, user_message, catalog)
            draft = {
                "resource_type": resource_type,
                "title": title.strip(),
                "reason": reason.strip(),
                "payload": normalized,
                "relation_hints": _safe_relation_hints(resource_type, normalized),
            }
            fingerprint = json.dumps(
                {"resource_type": resource_type, "payload": normalized},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            if fingerprint not in fingerprints:
                fingerprints.add(fingerprint)
                drafts.append(draft)
        logger.info(
            "Career suggestion extraction count=%s elapsed_ms=%s",
            len(drafts),
            round((time.monotonic() - started) * 1000),
        )
        return drafts[:3]
    except Exception as error:
        logger.warning(
            "Career suggestion extraction failed error=%s elapsed_ms=%s",
            type(error).__name__,
            round((time.monotonic() - started) * 1000),
        )
        return []
