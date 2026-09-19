"""HTTP layer over ``ProjectStore``: routes, error mapping and CORS.

The request envelopes are pydantic models; the project body itself is validated
by ``backend.project_store.validate_project_payload`` so the dataclasses in
``video_editing_engine`` stay the only definition of the project structure.
Interactive documentation is served at ``/docs`` when the app is running.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import APP_VERSION
from backend.project_store import TITLE_MAX_CHARS, ProjectStore, ProjectStoreError
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
    revision: int = Field(..., ge=1, description="上次读取到的 revision；与服务器不一致时返回 409")
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
    raw = os.environ.get("LINGJIAN_CORS_ORIGINS", "*")
    return [x.strip() for x in raw.split(",") if x.strip()] or ["*"]


def create_app(store: ProjectStore | None = None) -> FastAPI:
    """Build the FastAPI application; pass a store to use a specific workspace (tests do)."""
    store = store or ProjectStore.from_env()
    app = FastAPI(
        title="灵剪 AI 后端", version=APP_VERSION,
        description="工程的创建、读取、保存与删除。保存使用乐观锁：读取时拿到 revision，保存时带回，过期返回 409。",
    )
    app.state.store = store
    app.add_middleware(CORSMiddleware, allow_origins=_cors_origins(), allow_methods=["*"], allow_headers=["*"])

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
        return {"status": "ok", "version": APP_VERSION, "workspace": str(store.workspace)}

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
    return app
