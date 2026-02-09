"""REST API route handlers for /api/v1/."""

from __future__ import annotations

import asyncio
import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from dodo.models import Priority, Status
from dodo.resolve import InvalidDodoNameError, validate_dodo_name


async def _get_service(request: Request):
    """Resolve and validate dodo name from path, return (svc, None) or (None, error_response)."""
    name = request.path_params["name"]
    # _default is the internal name for the global dodo
    if name != "_default":
        try:
            validate_dodo_name(name)
        except InvalidDodoNameError:
            return None, JSONResponse(
                {"error": f"Invalid dodo name: {name}"}, status_code=400,
            )
    svc = await asyncio.to_thread(request.app.state.registry.get_service, name)
    return svc, None


async def health(request: Request) -> JSONResponse:
    """GET /api/v1/health"""
    return JSONResponse({"status": "ok"})


async def list_dodos(request: Request) -> JSONResponse:
    """GET /api/v1/dodos - list available dodos."""
    registry = request.app.state.registry
    dodos = await asyncio.to_thread(registry.list_dodos)
    return JSONResponse(dodos)


async def delete_dodo(request: Request) -> JSONResponse:
    """DELETE /api/v1/dodos/:name - delete a dodo and all its data."""
    name = request.path_params["name"]
    registry = request.app.state.registry
    try:
        await asyncio.to_thread(registry.delete_dodo, name)
    except KeyError:
        return JSONResponse({"error": f"Dodo not found: {name}"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"status": "deleted"})


async def list_todos(request: Request) -> JSONResponse:
    """GET /api/v1/dodos/:name/todos"""
    svc, err = await _get_service(request)
    if err:
        return err

    status_filter = request.query_params.get("status")
    try:
        status = Status(status_filter) if status_filter else None
    except ValueError:
        return JSONResponse(
            {"error": f"Invalid status: {status_filter}. Valid: pending, done"},
            status_code=400,
        )

    items = await asyncio.to_thread(svc.list, status)
    return JSONResponse([item.to_dict() for item in items])


async def add_todo(request: Request) -> JSONResponse:
    """POST /api/v1/dodos/:name/todos"""
    svc, err = await _get_service(request)
    if err:
        return err

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)

    try:
        priority = Priority(body["priority"]) if body.get("priority") else None
    except ValueError:
        return JSONResponse(
            {"error": f"Invalid priority: {body['priority']}"},
            status_code=400,
        )

    tags = body.get("tags")
    item = await asyncio.to_thread(svc.add, text, priority, tags)
    return JSONResponse(item.to_dict(), status_code=201)


async def get_todo(request: Request) -> JSONResponse:
    """GET /api/v1/dodos/:name/todos/:id"""
    svc, err = await _get_service(request)
    if err:
        return err

    todo_id = request.path_params["todo_id"]
    item = await asyncio.to_thread(svc.get, todo_id)
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(item.to_dict())


async def update_todo(request: Request) -> JSONResponse:
    """PATCH /api/v1/dodos/:name/todos/:id"""
    svc, err = await _get_service(request)
    if err:
        return err

    todo_id = request.path_params["todo_id"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not any(k in body for k in ("text", "priority", "tags")):
        return JSONResponse({"error": "no fields to update"}, status_code=400)

    # Validate all fields before applying any (atomic: no partial updates on error)
    priority = None
    if "priority" in body:
        try:
            priority = Priority(body["priority"]) if body["priority"] else None
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid priority: {body['priority']}"}, status_code=400,
            )

    item = None
    try:
        if "text" in body:
            item = await asyncio.to_thread(svc.update_text, todo_id, body["text"])
        if "priority" in body:
            item = await asyncio.to_thread(svc.update_priority, todo_id, priority)
        if "tags" in body:
            item = await asyncio.to_thread(svc.update_tags, todo_id, body["tags"])
    except KeyError:
        return JSONResponse({"error": "not found"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return JSONResponse(item.to_dict())


async def toggle_todo(request: Request) -> JSONResponse:
    """POST /api/v1/dodos/:name/todos/:id/toggle"""
    svc, err = await _get_service(request)
    if err:
        return err

    todo_id = request.path_params["todo_id"]
    try:
        item = await asyncio.to_thread(svc.toggle, todo_id)
    except KeyError:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(item.to_dict())


async def complete_todo(request: Request) -> JSONResponse:
    """POST /api/v1/dodos/:name/todos/:id/complete"""
    svc, err = await _get_service(request)
    if err:
        return err

    todo_id = request.path_params["todo_id"]
    try:
        item = await asyncio.to_thread(svc.complete, todo_id)
    except KeyError:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(item.to_dict())


async def delete_todo(request: Request) -> JSONResponse:
    """DELETE /api/v1/dodos/:name/todos/:id"""
    svc, err = await _get_service(request)
    if err:
        return err

    todo_id = request.path_params["todo_id"]
    try:
        await asyncio.to_thread(svc.delete, todo_id)
    except KeyError:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"status": "deleted"})
