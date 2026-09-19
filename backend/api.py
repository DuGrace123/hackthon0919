"""HTTP layer over ``ProjectStore``: routes, error mapping and CORS.

The request envelopes are pydantic models; the project body itself is validated
by ``backend.project_store.validate_project_payload`` so the dataclasses in
``video_editing_engine`` stay the only definition of the project structure.
Interactive documentation is served at ``/docs`` when the app is running.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt

from backend import APP_VERSION
from backend.ai_adapter import LOCAL_OWNER, ProjectStoreAIBackend, resolve_ffmpeg
from backend.project_store import CAPTION_MAX_CHARS, TITLE_MAX_CHARS, ProjectStore, ProjectStoreError
from ai_workflow import AIWorkflow, WorkflowError, config_from_environment
from ai_workflow_api import create_ai_router
from video_editing_engine import Clip, Project


def _example_project() -> dict:
    project = Project("示例：旅行 Vlog")
    project.clips = [
        Clip("D:/footage/DJI_0001.MP4", 2.0, 6.5, "DJI_0001.MP4", caption="从这里出发"),
        Clip("D:/footage/DJI_0002.MP4", 0.0, 4.0, "DJI_0002.MP4", transition="dissolve"),
    ]
    return project.to_dict()


EXAMPLE_PROJECT = _example_project()

ERROR_DOC = {
    400: {"description": "工程 ID 格式不正确（code=invalid_project_id）"},
    404: {"description": "工程不存在（code=project_not_found）"},
    409: {"description": "revision 已过期，detail.current 为服务器当前版本（code=revision_conflict）"},
    422: {"description": "请求或工程内容无效，detail.errors 列出每个问题（code=invalid_request / invalid_project）"},
}


class CreateProjectRequest(BaseModel):
    title: str | None = Field(None, max_length=TITLE_MAX_CHARS, examples=["我的旅行 Vlog"])
    ratio: str | None = Field(None, description="画幅比例，宽:高", examples=["9:16"])
    project: dict[str, Any] | None = Field(
        None, description="可选：完整的 .ljproject 内容，用于导入桌面版工程；给出时 title/ratio 覆盖其中的同名字段",
        examples=[EXAMPLE_PROJECT],
    )


class SaveProjectRequest(BaseModel):
    revision: StrictInt = Field(..., ge=1, description="上次读取到的 revision；与服务器不一致时返回 409")
    project: dict[str, Any] = Field(..., description="完整工程内容（version 5 结构，见 docs/backend_api.md）", examples=[EXAMPLE_PROJECT])


class ProjectRecordResponse(BaseModel):
    id: str
    revision: int
    created_at: str
    updated_at: str
    recovered_from_backup: bool = False
    project: dict[str, Any]


class ProjectSummaryResponse(BaseModel):
    id: str
    title: str
    revision: int
    updated_at: str
    clip_count: int
    duration: float
    recovered_from_backup: bool = False


def _cors_origins() -> list[str]:
    raw = os.environ.get("LINGJIAN_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [x.strip().rstrip('/') for x in raw.split(",") if x.strip()]
    if '*' in origins:
        raise ValueError('LINGJIAN_CORS_ORIGINS must list explicit browser origins; wildcard is not supported')
    return origins


def create_app(store: ProjectStore | None = None, *, ffmpeg: str | None = None) -> FastAPI:
    """Build the FastAPI application; pass a store to use a specific workspace (tests do)."""
    store = store or ProjectStore.from_env()
    adapter = ProjectStoreAIBackend(store, resolve_ffmpeg(ffmpeg))
    workflow = AIWorkflow(adapter, adapter.ffmpeg, cloud_config=config_from_environment(), caption_limit=CAPTION_MAX_CHARS)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            workflow.close()

    app = FastAPI(
        title="灵剪 AI 后端", version=APP_VERSION,
        description="工程保存与 AI 方案预览、应用、撤销。保存时带回 revision，过期返回 409；AI 接口目前仅供本机访问。",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.ai_workflow = workflow
    origins = _cors_origins()
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Content-Type"])

    @app.middleware('http')
    async def check_browser_origin(request: Request, call_next):
        origin = request.headers.get('origin')
        local_host = request.url.hostname in ('localhost', '127.0.0.1', '::1')
        own_origin = f'{request.url.scheme}://{request.url.netloc}'
        if origin and origin not in origins and not (local_host and origin == own_origin):
            return JSONResponse(status_code=403, content={'detail': {'code': 'origin_not_allowed', 'message': '此网页来源未获允许。'}})
        return await call_next(request)

    def current_local_user(request: Request) -> str:
        # ProjectStore is a single local workspace, not a multi-user identity store.
        # Keep the newly enabled media/cloud operations inaccessible from the LAN.
        client_host = request.client.host if request.client else ''
        hostname = urlsplit('//' + request.headers.get('host', '')).hostname
        if client_host not in ('127.0.0.1', '::1') or hostname not in ('localhost', '127.0.0.1', '::1'):
            raise HTTPException(status_code=403, detail={'code': 'local_only', 'message': '当前 AI 接口仅供本机使用。'})
        return LOCAL_OWNER

    @app.exception_handler(ProjectStoreError)
    async def _store_error(_: Request, exc: ProjectStoreError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.to_detail()})

    @app.exception_handler(RequestValidationError)
    async def _request_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"path": ".".join(str(x) for x in e.get("loc", ()) if x != "body"), "message": str(e.get("msg", ""))}
                  for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": {"code": "invalid_request", "message": "请求格式不正确", "errors": errors}})

    api = APIRouter(prefix="/api/v1")

    @api.get("/health", tags=["系统"], summary="服务状态")
    def health() -> dict:
        return {"status": "ok", "version": APP_VERSION, "workspace": str(store.workspace),
                "ai": workflow.capabilities()}

    @api.get('/projects/{project_id}/ai/sources', tags=['AI workflow'])
    def ai_sources(project_id: str, owner_id: str = Depends(current_local_user)) -> dict:
        try:
            return adapter.list_sources(project_id, owner_id)
        except WorkflowError as exc:
            raise HTTPException(status_code=exc.status, detail={'code': exc.code, 'message': str(exc)}) from None

    @api.get("/projects", response_model=list[ProjectSummaryResponse], tags=["工程"], summary="列出工程")
    def list_projects() -> list[dict]:
        return store.list()

    @api.post("/projects", response_model=ProjectRecordResponse, status_code=201, tags=["工程"], summary="创建工程",
              responses={422: ERROR_DOC[422]})
    def create_project(body: CreateProjectRequest) -> dict:
        return store.create(body.title, body.ratio, body.project).to_dict()

    @api.get("/projects/{project_id}", response_model=ProjectRecordResponse, tags=["工程"], summary="读取工程",
             responses={400: ERROR_DOC[400], 404: ERROR_DOC[404]})
    def get_project(project_id: str) -> dict:
        return store.get(project_id).to_dict()

    @api.put("/projects/{project_id}", response_model=ProjectRecordResponse, tags=["工程"], summary="保存工程（乐观锁）",
             responses=ERROR_DOC)
    def save_project(project_id: str, body: SaveProjectRequest) -> dict:
        return store.save(project_id, body.project, body.revision).to_dict()

    @api.delete("/projects/{project_id}", status_code=204, tags=["工程"], summary="删除工程",
                responses={400: ERROR_DOC[400], 404: ERROR_DOC[404]})
    def delete_project(project_id: str) -> Response:
        store.delete(project_id)
        return Response(status_code=204)

    app.include_router(api)
    app.include_router(create_ai_router(workflow, current_user=current_local_user, prefix='/api/v1'))
    return app
