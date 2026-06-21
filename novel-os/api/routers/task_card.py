"""写前 Task Card API —— 生成章节任务卡。"""
from fastapi import APIRouter, HTTPException

from api.main import orchestrator

router = APIRouter()


@router.get("/projects/{project_id}/task-card")
async def get_task_card(project_id: str, chapter: int = 1):
    """获取指定章节的写前任务卡。

    任务卡包含:
        - 项目基本信息
        - 活跃债务（需在本章解决或推进）
        - 活跃伏笔（需在本章埋下或回收）
        - 角色状态（关键角色当前状态）
        - 写作目标（字数、节奏等）
    """
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目未加载")

    state = runtime.state_manager
    debts = state.get_active_debts(chapter)
    foreshadowing = state.get_active_foreshadowing(chapter)
    characters = state.list_characters()

    # 调用 Director Agent 生成任务卡（节拍规划、人物调度、情感坐标）
    director_card = ""
    try:
        context = runtime.batch_writer._build_chapter_context(chapter)
        director_card = runtime.batch_writer._call_director(chapter, context)
    except Exception as exc:
        import logging
        logging.getLogger("novel-os.task_card").warning("Director Agent 任务卡生成失败: %s", exc)

    task_card = {
        "chapter": chapter,
        "project": {
            "name": status.get("name"),
            "genre": status.get("genre"),
            "platform": status.get("platform"),
        },
        "writing_goal": {
            "target_words": runtime.book_config.words_per_chapter,
            "tolerance": getattr(runtime.book_config, "words_tolerance", 450),
        },
        "active_debts": debts,
        "active_foreshadowing": foreshadowing,
        "key_characters": [
            {
                "name": c.get("name"),
                "role": c.get("role"),
                "state": state.get_character_state(c.get("character_id", ""), chapter),
            }
            for c in characters[:5]
        ],
        "director_card": director_card,
    }

    return {"code": 200, "data": task_card}
