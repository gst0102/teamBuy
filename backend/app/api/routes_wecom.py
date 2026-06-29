from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_app_service,
    get_ops_console_store,
    get_sync_task_queue,
    get_wecom_archive_client,
    get_wecom_client,
    get_wecom_mock_service,
)
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.imports import MockImportRequest
from app.services.app_service import AppService
from app.services.ops_console_store import OpsConsoleStore
from app.services.sync_task_queue import SyncTaskQueue
from app.services.wecom_archive_client import WecomArchiveClient
from app.services.wecom_client import WecomClient, WecomClientError
from app.services.wecom_crypto import WecomCryptoError, decrypt_aes_message, verify_signature
from app.services.wecom_event_service import parse_callback_body
from app.services.wecom_mock_service import WecomMockService


router = APIRouter(prefix="/api/wecom", tags=["wecom"])
KF_CALLBACK_PATH = "/kf/teamBuy/callback"
ARCHIVE_CALLBACK_PATH = "/archive/callback"
GROUP_BOT_MESSAGE_TEMPLATES = {
    "midday": {
        "label": "中午更新",
        "content": "今日更新：\n{topic} 新增 {count} 条，已整理成合集。\n今天重点是 {focus}。\n需要的直接看小程序。",
    },
    "afternoon": {
        "label": "下午入口",
        "content": "你现在可以直接做这几件事：\n1. 看今天新增\n2. 提交你的资源\n3. 生成同款合集\n需要我帮你整理的，也可以直接私聊我。",
    },
    "evening": {
        "label": "晚间总结",
        "content": "今天已更新 {count} 条内容，补了 {showcaseCount} 个合集。\n明天优先整理 {focus}。\n你手里有资源也可以发我，我一起整理进去。",
    },
}


class GroupBotBroadcastRequest(BaseModel):
    groupIds: list[str] = Field(default_factory=list)
    groupId: str | None = None
    messageType: str = Field(default="text", pattern="^(text|miniapp_card)$")
    template: str = Field(default="custom", pattern="^(midday|afternoon|evening|custom)$")
    content: str | None = None
    variables: dict[str, str | int | float] = Field(default_factory=dict)
    miniappPath: str | None = None
    miniappAppId: str | None = None
    cardTitle: str | None = None
    cardDescription: str | None = None
    dryRun: bool = True


def _register_real_sync_task(sync_task_queue: SyncTaskQueue) -> None:
    async def run(payload: dict):
        return await _run_real_sync(
            max_pages=int(payload.get("maxPages", 10)),
            service=get_app_service(),
            client=get_wecom_client(),
            mock_service=get_wecom_mock_service(),
        )

    sync_task_queue.register("wecom-callback-real-sync", run)


async def recover_persisted_sync_tasks() -> None:
    sync_task_queue = get_sync_task_queue()
    _register_real_sync_task(sync_task_queue)
    sync_task_queue.start_pending()


def _sync_response_has_more(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _notification_reply_text(notification: dict) -> str:
    title = notification.get("title") or "房源资料"
    message = notification.get("message") or ""
    path = notification.get("resultPath") or ""
    if notification.get("status") == "success":
        lines = [
            f"已完成：{title}",
            message,
            "上游电话、中介费、密码锁等敏感信息只在你的账号里查看。",
        ]
        if path:
            lines.append(f"打开小程序查看：{path}")
        return "\n".join([line for line in lines if line])
    return f"整理失败：{title}\n{message}"


async def _send_import_notifications(
    notifications: list[dict],
    service: AppService,
    client: WecomClient,
) -> list[dict]:
    results = []
    if settings.wecom_use_mock:
        return results
    for notification in notifications:
        notification_id = notification.get("id")
        external_user_id = notification.get("externalUserId")
        if not notification_id or not external_user_id:
            continue
        try:
            response = await client.send_customer_service_text(
                external_user_id=external_user_id,
                content=_notification_reply_text(notification),
                open_kfid=settings.wecom_open_kfid or None,
            )
            updated = service.update_import_notification_delivery(notification_id, "sent")
            results.append({"notificationId": notification_id, "status": "sent", "response": response, "notification": updated})
        except Exception as exc:
            updated = service.update_import_notification_delivery(notification_id, "failed", str(exc))
            results.append({"notificationId": notification_id, "status": "failed", "error": str(exc), "notification": updated})
    return results


async def _send_pending_import_notifications(
    service: AppService,
    client: WecomClient,
    limit: int = 20,
) -> list[dict]:
    pending = [
        item
        for item in service.list_import_notifications()
        if item.get("sendStatus") == "pending" and item.get("channel") == "wecom"
    ][:limit]
    return await _send_import_notifications(pending, service, client)


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


def _configured_group_webhooks(store: OpsConsoleStore | None = None) -> dict[str, str]:
    webhooks = settings.group_bot_webhook_map()
    if store:
        webhooks.update(store.group_bot_webhook_map())
    return webhooks


def _mask_webhook(url: str) -> str:
    if "key=" not in url:
        return url[:36] + "***" if len(url) > 40 else "***"
    prefix, key = url.split("key=", 1)
    return f"{prefix}key={key[:4]}***{key[-4:]}" if len(key) > 8 else f"{prefix}key=***"


def _format_group_bot_message(payload: GroupBotBroadcastRequest) -> str:
    if payload.template == "custom":
        content = payload.content or ""
    else:
        variables = {
            "topic": "今日资源",
            "count": 0,
            "focus": "重点资源",
            "showcaseCount": 0,
            **payload.variables,
        }
        try:
            content = GROUP_BOT_MESSAGE_TEMPLATES[payload.template]["content"].format(**variables)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"缺少模板变量: {exc.args[0]}") from exc
    content = content.strip()
    if payload.miniappPath:
        content = f"{content}\n\n小程序入口：{payload.miniappPath.strip()}"
    if not content:
        raise HTTPException(status_code=400, detail="群发内容不能为空")
    if len(content) > 2048:
        raise HTTPException(status_code=400, detail="群发内容不能超过 2048 个字符")
    return content


async def _post_group_bot_webhook(webhook_url: str, content: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            webhook_url,
            json={"msgtype": "text", "text": {"content": content}},
        )
        data = response.json()
    if data.get("errcode") != 0:
        raise WecomClientError(f"企业微信群机器人发送失败: {data}")
    return data


async def _post_group_bot_webhook_payload(webhook_url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(webhook_url, json=payload)
        data = response.json()
    if data.get("errcode") != 0:
        raise WecomClientError(f"企业微信群机器人发送失败: {data}")
    return data


def _build_group_bot_send_payload(payload: GroupBotBroadcastRequest, content: str) -> dict:
    if payload.messageType == "text":
        return {"msgtype": "text", "text": {"content": content}}

    appid = (payload.miniappAppId or settings.wechat_miniapp_appid or "").strip()
    pagepath = (payload.miniappPath or "").strip()
    if not appid:
        raise HTTPException(status_code=400, detail="发送小程序卡片需要 miniappAppId")
    if not pagepath:
        raise HTTPException(status_code=400, detail="发送小程序卡片需要 miniappPath")

    title = (payload.cardTitle or "资料整理助手").strip()
    description = (payload.cardDescription or content).strip()
    return {
        "msgtype": "template_card",
        "template_card": {
            "card_type": "text_notice",
            "source": {
                "desc": "资料整理助手",
                "desc_color": 0,
            },
            "main_title": {
                "title": title[:36],
                "desc": description[:64],
            },
            "emphasis_content": {
                "title": "打开",
                "desc": "小程序",
            },
            "sub_title_text": content[:120],
            "jump_list": [
                {
                    "type": 2,
                    "title": "打开小程序",
                    "appid": appid,
                    "pagepath": pagepath,
                }
            ],
            "card_action": {
                "type": 2,
                "appid": appid,
                "pagepath": pagepath,
            },
        },
    }


def _read_text_file(path) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _mask_path(path) -> str:
    return str(path) if path else ""


async def _download_sync_media(
    messages: list[dict],
    client: WecomClient,
    service: AppService,
) -> dict[str, str]:
    media_urls: dict[str, str] = {}
    for message in messages:
        media_id = message.get("mediaId")
        msg_type = message.get("msgType")
        if not media_id or msg_type not in {"image", "video"} or media_id in media_urls:
            continue
        existing_url = service.get_successful_media_url(media_id)
        if existing_url:
            media_urls[media_id] = existing_url
            continue
        try:
            downloaded = await client.download_media(media_id)
            media_urls[media_id] = service.process_and_store_media(
                media_id=media_id,
                media_type=msg_type,
                content=downloaded.content,
                content_type=downloaded.content_type,
                filename=downloaded.filename,
            )
        except WecomClientError as exc:
            service.save_media_retry_failure(
                media_id=media_id,
                media_type=msg_type,
                open_kfid=message.get("openKfid"),
                error_message=str(exc),
            )
    return media_urls


async def _retry_media_job(job: dict, client: WecomClient, service: AppService):
    downloaded = await client.download_media(job["mediaId"])
    local_url = service.process_and_store_media(
        media_id=job["mediaId"],
        media_type=job["mediaType"],
        content=downloaded.content,
        content_type=downloaded.content_type,
        filename=downloaded.filename,
    )
    return service.save_media_retry_success(
        media_id=job["mediaId"],
        media_type=job["mediaType"],
        open_kfid=job.get("openKfid"),
        local_media_url=local_url,
    )


@router.get(KF_CALLBACK_PATH, response_class=PlainTextResponse)
def verify_callback(
    msg_signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
    echostr: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    if token is not None and token != settings.wecom_callback_token:
        raise HTTPException(status_code=403, detail="token 验证失败")
    if echostr and msg_signature and timestamp and nonce:
        if not verify_signature(settings.wecom_callback_token, timestamp, nonce, echostr, msg_signature):
            raise HTTPException(status_code=403, detail="企业微信签名验证失败")
        if settings.wecom_encoding_aes_key and settings.wecom_corp_id:
            try:
                return PlainTextResponse(decrypt_aes_message(settings.wecom_encoding_aes_key, echostr, settings.wecom_corp_id))
            except WecomCryptoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(echostr or "verified")


@router.post(KF_CALLBACK_PATH, response_model=ApiResponse[dict])
async def receive_callback(
    request: Request,
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
    mock_service: WecomMockService = Depends(get_wecom_mock_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    raw_body = await request.body()
    try:
        payload = parse_callback_body(
            raw_body,
            request.headers.get("content-type", ""),
            settings,
            {
                "msg_signature": request.query_params.get("msg_signature"),
                "timestamp": request.query_params.get("timestamp"),
                "nonce": request.query_params.get("nonce"),
            },
        )
    except (ValueError, WecomCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if settings.wecom_use_mock:
        fixture = payload.get("fixture", "note")
        external_user_id = payload.get("externalUserId") or payload.get("ExternalUserID") or "external_demo"
        conversation_id = payload.get("conversationId") or payload.get("Token") or "conv_demo"
        result = service.trigger_mock_import(external_user_id, conversation_id, fixture)
        return ApiResponse(message="callback mock import completed", data={"callback": payload, "syncResult": result})

    _register_real_sync_task(sync_task_queue)
    task = sync_task_queue.enqueue("wecom-callback-real-sync", payload={"maxPages": 10})
    return ApiResponse(
        message="callback real sync queued",
        data={"callback": payload, "syncTask": task.model_dump()},
    )


@router.get(ARCHIVE_CALLBACK_PATH, response_class=PlainTextResponse)
def verify_archive_callback(
    msg_signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
    echostr: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    callback_token = settings.wecom_archive_callback_token or settings.wecom_callback_token
    callback_aes_key = settings.wecom_archive_encoding_aes_key or settings.wecom_encoding_aes_key
    if token is not None and token != callback_token:
        raise HTTPException(status_code=403, detail="token 验证失败")
    if echostr and msg_signature and timestamp and nonce:
        if not verify_signature(callback_token, timestamp, nonce, echostr, msg_signature):
            raise HTTPException(status_code=403, detail="企业微信签名验证失败")
        if callback_aes_key and settings.wecom_corp_id:
            try:
                return PlainTextResponse(decrypt_aes_message(callback_aes_key, echostr, settings.wecom_corp_id))
            except WecomCryptoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(echostr or "verified")


@router.post(ARCHIVE_CALLBACK_PATH, response_model=ApiResponse[dict])
async def receive_archive_callback(request: Request):
    raw_body = await request.body()
    try:
        payload = parse_callback_body(
            raw_body,
            request.headers.get("content-type", ""),
            settings,
            {
                "msg_signature": request.query_params.get("msg_signature"),
                "timestamp": request.query_params.get("timestamp"),
                "nonce": request.query_params.get("nonce"),
            },
            token=settings.wecom_archive_callback_token or settings.wecom_callback_token,
            encoding_aes_key=settings.wecom_archive_encoding_aes_key or settings.wecom_encoding_aes_key,
        )
    except (ValueError, WecomCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(message="archive callback received", data={"callback": payload})


@router.post("/mock-sync", response_model=ApiResponse[dict])
def mock_sync(payload: MockImportRequest, service: AppService = Depends(get_app_service)):
    result = service.trigger_mock_import(payload.externalUserId, payload.conversationId, payload.fixture)
    return ApiResponse(data=result, message="mock import completed")


@router.get("/notifications", response_model=ApiResponse[list[dict]])
def list_notifications(service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_import_notifications())


@router.get("/sync-tasks", response_model=ApiResponse[list[dict]])
def list_sync_tasks(sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue)):
    return ApiResponse(data=[item.model_dump() for item in sync_task_queue.list_recent()])


@router.get("/sync-tasks/logs", response_model=ApiResponse[list[dict]])
def list_sync_task_logs(
    task_id: str | None = Query(default=None, alias="taskId"),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    return ApiResponse(data=[item.model_dump() for item in sync_task_queue.list_logs(task_id)])


@router.get("/media-retries", response_model=ApiResponse[list[dict]])
def list_media_retries(status: str | None = Query(default=None), service: AppService = Depends(get_app_service)):
    statuses = {status} if status else None
    return ApiResponse(data=service.list_media_retry_jobs(statuses))


@router.get("/import-failures", response_model=ApiResponse[dict])
def list_import_failures(
    limit: int = Query(default=100, ge=1, le=500),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_import_failures(limit=limit))


@router.get("/retry-dashboard", response_model=ApiResponse[dict])
def get_retry_dashboard(
    limit: int = Query(default=100, ge=1, le=500),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_wecom_retry_dashboard(limit=limit))


@router.post("/import-failures/retry", response_model=ApiResponse[dict])
def retry_import_failure(
    import_batch_id: str = Query(..., alias="importBatchId"),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(data=service.retry_failed_import(import_batch_id, notification_channel="wecom"))


@router.post("/media-retries/retry", response_model=ApiResponse[dict])
async def retry_media_retries(
    media_id: str | None = Query(default=None),
    status: str = Query(default="failed"),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    jobs = service.list_media_retry_jobs({status})
    if media_id:
        jobs = [item for item in jobs if item["mediaId"] == media_id]
    retried = []
    failed = []
    for job in jobs:
        try:
            retried.append((await _retry_media_job(job, client, service)).model_dump())
        except WecomClientError as exc:
            failed_job = service.save_media_retry_failure(
                media_id=job["mediaId"],
                media_type=job["mediaType"],
                open_kfid=job.get("openKfid"),
                error_message=str(exc),
            )
            failed.append(failed_job.model_dump())
    return ApiResponse(data={"retried": retried, "failed": failed})


@router.get("/config-check", response_model=ApiResponse[dict])
def config_check(client: WecomClient = Depends(get_wecom_client)):
    missing = settings.missing_wecom_fields()
    return ApiResponse(
        success=not missing,
        message="wecom config ready" if not missing else "wecom config incomplete",
        data={
            "useMock": settings.wecom_use_mock,
            "callbackUrl": f"{settings.public_base_url.rstrip('/')}/api/wecom{KF_CALLBACK_PATH}" if settings.public_base_url else "",
            "missing": missing,
            "configured": client.is_configured(),
        },
    )


@router.get("/group-bot/config", response_model=ApiResponse[dict])
def group_bot_config(
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token or admin_token)
    webhooks = _configured_group_webhooks(store)
    return ApiResponse(
        success=bool(webhooks),
        message="group bot configured" if webhooks else "group bot webhooks are not configured",
        data={
            "configured": bool(webhooks),
            "groups": [{"groupId": group_id, "webhook": _mask_webhook(url)} for group_id, url in webhooks.items()],
            "templates": {
                key: {"label": value["label"], "content": value["content"]}
                for key, value in GROUP_BOT_MESSAGE_TEMPLATES.items()
            },
        },
    )


@router.post("/group-bot/broadcast", response_model=ApiResponse[dict])
async def group_bot_broadcast(
    payload: GroupBotBroadcastRequest,
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token or admin_token)
    webhooks = _configured_group_webhooks(store)
    if not webhooks:
        raise HTTPException(status_code=400, detail="WECOM_GROUP_BOT_WEBHOOKS 未配置")

    group_ids = payload.groupIds or ([payload.groupId] if payload.groupId else [])
    group_ids = [item.strip() for item in group_ids if item and item.strip()]
    if not group_ids:
        raise HTTPException(status_code=400, detail="至少需要一个 groupId")
    unknown_groups = [group_id for group_id in group_ids if group_id not in webhooks]
    if unknown_groups:
        raise HTTPException(status_code=400, detail=f"未配置的 groupId: {', '.join(unknown_groups)}")

    content = _format_group_bot_message(payload)
    send_payload = _build_group_bot_send_payload(payload, content)
    results = []
    for group_id in group_ids:
        if payload.dryRun:
            results.append({"groupId": group_id, "status": "dryRun", "webhook": _mask_webhook(webhooks[group_id])})
            continue
        try:
            if payload.messageType == "text":
                response = await _post_group_bot_webhook(webhooks[group_id], content)
            else:
                response = await _post_group_bot_webhook_payload(webhooks[group_id], send_payload)
            results.append({"groupId": group_id, "status": "sent", "response": response})
        except WecomClientError as exc:
            results.append({"groupId": group_id, "status": "failed", "error": str(exc)})
    failed_count = len([item for item in results if item["status"] == "failed"])
    return ApiResponse(
        success=failed_count == 0,
        message="group bot broadcast dry run" if payload.dryRun else "group bot broadcast completed",
        data={
            "dryRun": payload.dryRun,
            "messageType": payload.messageType,
            "template": payload.template,
            "content": content,
            "sendPayload": send_payload if payload.dryRun else None,
            "targetCount": len(group_ids),
            "sentCount": len([item for item in results if item["status"] == "sent"]),
            "failedCount": failed_count,
            "results": results,
        },
    )


@router.get("/customer-service-config", response_model=ApiResponse[dict])
def customer_service_config():
    corp_id = settings.wecom_corp_id
    open_kfid = settings.wecom_open_kfid
    ext_info_url = f"https://work.weixin.qq.com/kfid/{open_kfid}" if open_kfid else ""
    return ApiResponse(
        success=bool(corp_id and ext_info_url),
        message="wecom customer service config ready" if corp_id and ext_info_url else "wecom customer service config incomplete",
        data={
            "corpId": corp_id,
            "openKfid": open_kfid,
            "extInfoUrl": ext_info_url,
            "configured": bool(corp_id and ext_info_url),
        },
    )


@router.get("/archive/config-check", response_model=ApiResponse[dict])
def archive_config_check():
    missing = settings.missing_wecom_archive_fields()
    public_key = _read_text_file(settings.wecom_archive_public_key_path)
    private_key_exists = bool(settings.wecom_archive_private_key_path and settings.wecom_archive_private_key_path.exists())
    sdk_exists = bool(settings.wecom_archive_sdk_lib_path and settings.wecom_archive_sdk_lib_path.exists())
    return ApiResponse(
        success=not missing,
        message="wecom archive config ready" if not missing else "wecom archive config incomplete",
        data={
            "enabled": settings.wecom_archive_enabled,
            "callbackUrl": f"{settings.public_base_url.rstrip('/')}/api/wecom{ARCHIVE_CALLBACK_PATH}" if settings.public_base_url else "",
            "callbackTokenConfigured": bool(settings.wecom_archive_callback_token or settings.wecom_callback_token),
            "callbackAesKeyConfigured": bool(settings.wecom_archive_encoding_aes_key or settings.wecom_encoding_aes_key),
            "corpIdConfigured": bool(settings.wecom_corp_id),
            "archiveSecretConfigured": bool(settings.wecom_archive_secret),
            "privateKeyPath": _mask_path(settings.wecom_archive_private_key_path),
            "privateKeyReadable": private_key_exists,
            "publicKeyPath": _mask_path(settings.wecom_archive_public_key_path),
            "publicKey": public_key,
            "sdkLibPath": _mask_path(settings.wecom_archive_sdk_lib_path),
            "sdkLibReadable": sdk_exists,
            "sdkConfigured": sdk_exists and bool(settings.wecom_archive_secret and settings.wecom_archive_private_key_path),
            "pullLimit": settings.wecom_archive_pull_limit,
            "workerEnabled": settings.wecom_archive_worker_enabled,
            "workerIntervalSeconds": settings.wecom_archive_worker_interval_seconds,
            "missing": missing,
            "docs": {
                "official": "https://developer.work.weixin.qq.com/document/path/91360",
                "local": "docs/stage2-docs/10-wecom-archive-config.md",
            },
        },
    )


@router.post("/archive/pull", response_model=ApiResponse[dict])
def pull_archive_messages(
    limit: int | None = Query(default=None, ge=1, le=1000),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    archive_client: WecomArchiveClient = Depends(get_wecom_archive_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(
        message="archive messages pulled",
        data=service.pull_wecom_archive_messages(archive_client, limit or settings.wecom_archive_pull_limit),
    )


@router.post("/archive/process", response_model=ApiResponse[dict])
async def process_archive_messages(
    limit: int = Query(default=100, ge=1, le=1000),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    archive_client: WecomArchiveClient = Depends(get_wecom_archive_client),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    result = service.process_wecom_archive_messages(limit=limit, archive_client=archive_client)
    notifications = [
        item.get("notification")
        for item in result.get("processed", [])
        if isinstance(item, dict) and item.get("notification")
    ]
    result["notificationSendResults"] = await _send_import_notifications(notifications, service, client)
    return ApiResponse(
        message="archive messages processed",
        data=result,
    )


@router.post("/notifications/send-pending", response_model=ApiResponse[list[dict]])
async def send_pending_import_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(
        message="pending import notifications sent",
        data=await _send_pending_import_notifications(service, client, limit),
    )


@router.post("/archive/media-backfill", response_model=ApiResponse[dict])
def backfill_archive_media(
    limit: int = Query(default=100, ge=1, le=1000),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    archive_client: WecomArchiveClient = Depends(get_wecom_archive_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(
        message="archive media backfilled",
        data=service.backfill_wecom_archive_media(archive_client=archive_client, limit=limit),
    )


@router.get("/archive/cursor", response_model=ApiResponse[dict | None])
def get_archive_cursor(
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    corp_id = settings.wecom_corp_id or "default"
    cursor = service.get_wecom_archive_cursor(corp_id)
    return ApiResponse(data=cursor.model_dump() if cursor else None)


@router.get("/archive/messages", response_model=ApiResponse[list[dict]])
def list_archive_messages(
    limit: int = Query(default=100, ge=1, le=500),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(data=service.list_wecom_archive_messages(limit=limit))


@router.post("/archive/mock-messages", response_model=ApiResponse[dict])
def save_archive_mock_messages(
    payload: dict,
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    corp_id = payload.get("corpId") or settings.wecom_corp_id or "default"
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")
    return ApiResponse(data=service.save_wecom_archive_messages(corp_id, messages))


@router.post("/real-sync", response_model=ApiResponse[dict])
async def import_real_sync(
    max_pages: int = Query(default=10, ge=1, le=50),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
    mock_service: WecomMockService = Depends(get_wecom_mock_service),
):
    result = await _run_real_sync(max_pages, service, client, mock_service)
    return ApiResponse(
        success=result.get("syncStatus") != "running",
        message="sync_msg task already running" if result.get("syncStatus") == "running" else "real sync_msg imported",
        data=result,
    )


async def _run_real_sync(
    max_pages: int,
    service: AppService,
    client: WecomClient,
    mock_service: WecomMockService,
) -> dict:
    open_kfid = settings.wecom_open_kfid or "default"
    source = "mock-real-sync-response" if settings.wecom_use_mock else "wecom-sync-msg"
    sync_lock = service.acquire_sync_lock(open_kfid, source, settings.wecom_sync_lock_timeout_seconds)
    if sync_lock is None:
        running = service.get_sync_cursor(open_kfid)
        return {
            "openKfid": open_kfid,
            "syncStatus": "running",
            "lockedAt": running.lockedAt if running else None,
            "lockTimeoutSeconds": settings.wecom_sync_lock_timeout_seconds,
        }

    cursor = sync_lock.cursor or settings.wecom_sync_cursor or None
    page_results = []
    imported_batch_ids: list[str] = []
    deduplicated_count = 0
    last_cursor = cursor
    last_has_more = sync_lock.hasMore
    try:
        for page in range(1, max_pages + 1):
            if settings.wecom_use_mock:
                sync_response = mock_service.load_real_sync_response()
            else:
                try:
                    sync_response = await client.sync_msg(cursor=cursor)
                except WecomClientError as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc

            synced_messages = service.normalize_sync_response(
                sync_response,
                fallback_open_kfid=settings.wecom_open_kfid or None,
            )
            media_url_by_id = {}
            if not settings.wecom_use_mock:
                media_url_by_id = await _download_sync_media(synced_messages, client, service)
            result = service.import_synced_messages(
                synced_messages,
                media_url_by_id=media_url_by_id,
                allow_media_storage_fallback=settings.wecom_use_mock,
                notification_channel="mock" if settings.wecom_use_mock else "wecom",
            )
            notification_send_results = await _send_import_notifications(result.get("notifications", []), service, client)
            next_cursor = sync_response.get("next_cursor") or sync_response.get("cursor") or sync_response.get("token")
            has_more = _sync_response_has_more(sync_response.get("has_more"))
            sync_cursor = service.advance_sync_cursor(
                open_kfid=open_kfid,
                cursor=next_cursor,
                has_more=has_more,
                source=source,
                payload=sync_response,
            )
            page_results.append(
                {
                    "page": page,
                    "cursor": cursor,
                    "nextCursor": next_cursor,
                    "hasMore": has_more,
                    "importResult": result,
                    "notificationSendResults": notification_send_results,
                }
            )
            imported_batch_ids.extend(result["importBatchIds"])
            deduplicated_count += result["deduplicatedCount"]
            cursor = next_cursor
            last_cursor = sync_cursor.cursor
            last_has_more = sync_cursor.hasMore
            if settings.wecom_use_mock or not has_more or not next_cursor:
                break
    except Exception as exc:
        service.release_sync_lock(open_kfid, sync_lock.lockToken or "", "failed", str(exc))
        raise
    service.release_sync_lock(open_kfid, sync_lock.lockToken or "", "success")

    return {
        "source": source,
        "openKfid": open_kfid,
        "syncStatus": "success",
        "pagesSynced": len(page_results),
        "nextCursor": last_cursor,
        "hasMore": last_has_more,
        "importResult": {
            "importBatchIds": imported_batch_ids,
            "deduplicatedCount": deduplicated_count,
        },
        "pageResults": page_results,
    }


@router.post("/real-sync/unlock", response_model=ApiResponse[dict])
def unlock_real_sync(
    open_kfid: str | None = Query(default=None),
    reason: str = Query(default="manual force release"),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    target_open_kfid = open_kfid or settings.wecom_open_kfid or "default"
    cursor = service.force_release_sync_lock(target_open_kfid, reason)
    if not cursor:
        return ApiResponse(
            success=False,
            message="sync lock not found",
            data={"openKfid": target_open_kfid},
        )
    return ApiResponse(
        message="sync lock released",
        data={
            "openKfid": cursor.openKfid,
            "syncStatus": cursor.syncStatus,
            "lastError": cursor.lastError,
            "lockedAt": cursor.lockedAt,
        },
    )
