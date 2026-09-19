"""Optional FastAPI adapter. Mount in Member 1's app; authenticate every route.

No application, media upload endpoint or project store is created here.
See docs/ai_workflow_integration.md for the backend and browser contracts.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from ai_workflow import AIWorkflow, WorkflowError


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    media_ids: list[StrictStr] = Field(min_length=1, max_length=20)
    revision: StrictInt = Field(ge=0)
    mode: Literal['local', 'cloud'] = 'local'
    target_duration: float = Field(default=30, ge=5, le=180, allow_inf_nan=False, strict=True)
    prompt: StrictStr = Field(default='', max_length=2000)
    cloud_consent: StrictBool = False


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0)
    confirm: StrictBool


class UndoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0)


def create_ai_router(workflow: AIWorkflow, *, current_user) -> APIRouter:
    """current_user is a required host dependency returning a verified user ID.

    Do not derive it from a client-controlled header without authentication.
    The host must provide session/CSRF policy and close workflow on shutdown.
    All blocking handlers are normal def functions, run in FastAPI's threadpool.
    """
    router = APIRouter(prefix='/api', tags=['AI workflow'])
    Actor = Annotated[str, Depends(current_user)]

    def call(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except WorkflowError as exc:
            raise HTTPException(status_code=exc.status, detail={'code': exc.code, 'message': str(exc)}) from None

    @router.get('/ai/capabilities')
    def capabilities(owner_id: Actor):
        if not owner_id:
            raise HTTPException(status_code=401, detail='请先登录。')
        return workflow.capabilities()

    @router.post('/projects/{project_id}/ai/plans', status_code=202)
    def create_plan(project_id: str, body: PlanRequest, owner_id: Actor):
        return call(workflow.create, project_id, owner_id, **body.model_dump())

    @router.get('/projects/{project_id}/ai/plans/{plan_id}')
    def get_plan(project_id: str, plan_id: str, owner_id: Actor):
        return call(workflow.get, project_id, plan_id, owner_id)

    @router.post('/projects/{project_id}/ai/plans/{plan_id}/cancel')
    def cancel_plan(project_id: str, plan_id: str, owner_id: Actor):
        return call(workflow.cancel, project_id, plan_id, owner_id)

    @router.post('/projects/{project_id}/ai/plans/{plan_id}/apply')
    def apply_plan(project_id: str, plan_id: str, body: ApplyRequest, owner_id: Actor):
        return call(workflow.apply, project_id, plan_id, owner_id, **body.model_dump())

    @router.post('/projects/{project_id}/ai/plans/{plan_id}/undo')
    def undo_plan(project_id: str, plan_id: str, body: UndoRequest, owner_id: Actor):
        return call(workflow.undo, project_id, plan_id, owner_id, **body.model_dump())

    return router
