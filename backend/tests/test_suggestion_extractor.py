import json

from backend.services import suggestion_extractor as extractor


def _catalog():
    return {
        "resumes": [{"id": 11, "title": "Backend resume"}],
        "jobs": [{"id": 21, "title": "Backend Engineer", "company": "Acme"}],
        "applications": [{"id": 31, "job_id": 21, "stage": "applied"}],
        "interviews": [{"id": 41, "job_id": 21, "title": "Acme interview"}],
        "skills": [{"id": 51, "skill": "Python"}],
    }


def _tool_result(suggestions):
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "propose_career_suggestions",
                                "arguments": json.dumps(
                                    {"suggestions": suggestions}, ensure_ascii=False
                                ),
                            }
                        }
                    ]
                }
            }
        ]
    }


def _raw(resource_type, payload, *, intent="explicit", confidence=0.95, title="Add record"):
    return {
        "resource_type": resource_type,
        "title": title,
        "reason": "This is concrete and useful.",
        "intent": intent,
        "confidence": confidence,
        "payload": payload,
        "relation_hints": {},
    }


def _configure(monkeypatch, suggestions):
    monkeypatch.setenv("CAREER_SUGGESTIONS_ENABLED", "true")
    monkeypatch.setattr(extractor, "load_career_catalog", lambda user_id: _catalog())
    captured = {}

    def complete(*args, **kwargs):
        captured.update(kwargs)
        return _tool_result(suggestions)

    monkeypatch.setattr(extractor, "get_ai_response_with_tools", complete)
    return captured


def test_explicit_skill_suggestion_is_canonical_and_uses_forced_no_retry_call(monkeypatch):
    captured = _configure(
        monkeypatch,
        [
            _raw(
                "skills",
                {
                    "skill": "Redis",
                    "target_level": "Production caching and rate limiting",
                    "status": "completed",
                    "progress": 100,
                    "notes": "Suggested from the target role",
                },
            )
        ],
    )

    drafts = extractor.extract_career_suggestions(
        7,
        "请添加一个 Redis 学习计划",
        "我建议先学习缓存和限流。",
    )

    assert len(drafts) == 1
    assert drafts[0]["payload"]["status"] == "planned"
    assert drafts[0]["payload"]["progress"] == 0
    assert drafts[0]["relation_hints"] == {}
    assert captured["max_retries"] == 0
    assert captured["timeout"] == 8
    assert captured["tool_choice"] == extractor.FORCED_TOOL_CHOICE


def test_low_confidence_or_unverified_explicit_intent_is_filtered(monkeypatch):
    _configure(
        monkeypatch,
        [
            _raw(
                "skills",
                {"skill": "Redis"},
                intent="high_confidence",
                confidence=0.89,
            ),
            _raw("skills", {"skill": "Kafka"}, intent="explicit", confidence=1),
        ],
    )

    assert extractor.extract_career_suggestions(7, "Redis 是什么？", "Redis 是缓存。") == []


def test_application_requires_explicit_application_intent_and_owned_job(monkeypatch):
    application = _raw(
        "applications",
        {"job_id": 21, "stage": "applied", "notes": "Submitted today"},
    )
    _configure(monkeypatch, [application])
    assert extractor.extract_career_suggestions(
        7, "请记录我已经投递了 Acme 的后端岗位", "好的。"
    )[0]["payload"]["job_id"] == 21

    application["payload"]["job_id"] = 999
    _configure(monkeypatch, [application])
    assert extractor.extract_career_suggestions(
        7, "请记录我已经投递了另一个岗位", "好的。"
    ) == []


def test_application_without_unique_job_stays_pending_for_user_selection(monkeypatch):
    _configure(
        monkeypatch,
        [_raw("applications", {"stage": "applied", "notes": "Applied today"})],
    )

    drafts = extractor.extract_career_suggestions(
        7,
        "Please record that I applied, but let me choose the matching saved job",
        "I will prepare a pending application record for confirmation.",
    )

    assert drafts[0]["payload"]["job_id"] is None

    monkeypatch.setattr(
        extractor,
        "load_career_catalog",
        lambda user_id: {"jobs": [], "interviews": []},
    )
    assert extractor.extract_career_suggestions(
        7,
        "Please record that I applied",
        "I will prepare a pending application record for confirmation.",
    ) == []


def test_user_id_in_top_level_or_payload_is_rejected(monkeypatch):
    top_level = _raw("skills", {"skill": "Redis"})
    top_level["user_id"] = 999
    payload_level = _raw("skills", {"skill": "Kafka", "user_id": 999})
    _configure(monkeypatch, [top_level, payload_level])

    assert extractor.extract_career_suggestions(
        7, "请添加 Redis 和 Kafka 学习计划", "好的。"
    ) == []


def test_nested_report_user_id_is_rejected(monkeypatch):
    _configure(
        monkeypatch,
        [
            _raw(
                "reports",
                {
                    "kind": "career_plan",
                    "title": "Backend plan",
                    "summary": "A concrete plan",
                    "payload": {"schema_version": 1, "user_id": 999},
                },
            )
        ],
    )
    assert extractor.extract_career_suggestions(
        7, "请保存这份职业计划", "这里是计划。"
    ) == []


def test_concrete_interview_date_counts_as_explicit_interview_intent(monkeypatch):
    _configure(
        monkeypatch,
        [
            _raw(
                "interviews",
                {"job_id": 21, "title": "Acme backend interview"},
            )
        ],
    )
    drafts = extractor.extract_career_suggestions(
        7, "我周五有 Acme 后端岗位的面试", "建议提前复习系统设计。"
    )
    assert drafts[0]["payload"]["status"] == "planned"


def test_interview_question_batch_keeps_only_reference_fields(monkeypatch):
    _configure(
        monkeypatch,
        [
            _raw(
                "interview_questions",
                {
                    "interview_id": 41,
                    "questions": [
                        {
                            "question": "Redis 缓存穿透如何处理？",
                            "reference_answer": "空值缓存或布隆过滤器。",
                            "coaching_notes": "比较不同方案的误判和一致性成本。",
                        }
                    ],
                },
            )
        ],
    )

    drafts = extractor.extract_career_suggestions(
        7, "请添加一道面试题", "我准备了一道 Redis 题。"
    )
    question = drafts[0]["payload"]["questions"][0]
    assert "position" not in question
    assert question["reference_answer"]
    assert question["coaching_notes"]
    assert "answer" not in question
    assert "feedback" not in question
    assert "score" not in question


def test_model_failure_and_bad_json_degrade_to_empty(monkeypatch):
    monkeypatch.setenv("CAREER_SUGGESTIONS_ENABLED", "true")
    monkeypatch.setattr(extractor, "load_career_catalog", lambda user_id: _catalog())
    monkeypatch.setattr(
        extractor,
        "get_ai_response_with_tools",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("slow")),
    )
    assert extractor.extract_career_suggestions(7, "请保存 Redis", "好的") == []

    monkeypatch.setattr(
        extractor,
        "get_ai_response_with_tools",
        lambda *args, **kwargs: {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "propose_career_suggestions",
                                    "arguments": "{bad json",
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )
    assert extractor.extract_career_suggestions(7, "请保存 Redis", "好的") == []


def test_disabled_feature_does_not_read_catalog_or_call_model(monkeypatch):
    monkeypatch.setenv("CAREER_SUGGESTIONS_ENABLED", "false")
    monkeypatch.setattr(
        extractor,
        "load_career_catalog",
        lambda user_id: (_ for _ in ()).throw(AssertionError("catalog called")),
    )
    assert extractor.extract_career_suggestions(7, "请保存", "好的") == []
