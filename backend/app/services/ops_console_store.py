from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

from app.services.helpers import new_id
from app.services.time_utils import now_iso


class GroupUploadRow(BaseModel):
    rowNumber: int
    raw: str
    groupName: str | None = None
    city: str | None = None
    district: str | None = None
    groupType: str | None = None
    tags: list[str] = Field(default_factory=list)
    qrUrl: str | None = None
    expiresAt: str | None = None
    note: str | None = None
    success: bool = False
    error: str | None = None


class GroupUploadBatch(BaseModel):
    id: str
    batchName: str
    operatorName: str | None = None
    rows: list[GroupUploadRow] = Field(default_factory=list)
    totalCount: int = 0
    successCount: int = 0
    failedCount: int = 0
    createdAt: str
    updatedAt: str


class SingleGroupResource(BaseModel):
    id: str
    ownerType: str = "ops_admin"
    operatorName: str | None = None
    name: str
    cityMode: str = "city"
    cityLabel: str | None = None
    region: list[str] = Field(default_factory=list)
    groupType: str
    purposes: list[str] = Field(default_factory=list)
    memberRange: str | None = None
    activeLevel: str | None = None
    expiresInDays: int = 5
    expiresAtText: str | None = None
    remark: str | None = None
    customTags: list[str] = Field(default_factory=list)
    qrImageData: str | None = None
    qrStatus: str = "uploaded"
    createdAt: str
    updatedAt: str


class FeedbackTicket(BaseModel):
    id: str
    type: str
    userId: str | None = None
    userNickname: str | None = None
    contact: str | None = None
    content: str
    status: str = "pending"
    replyText: str | None = None
    rewardNote: str | None = None
    operatorName: str | None = None
    createdAt: str
    updatedAt: str


class WecomGroupJoinWayConfig(BaseModel):
    id: str
    configId: str
    remark: str
    chatIdList: list[str] = Field(default_factory=list)
    roomBaseName: str
    roomBaseId: int = 1
    autoCreateRoom: int = 1
    state: str | None = None
    operatorName: str | None = None
    rawResponse: dict = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class GroupBotChannel(BaseModel):
    id: str
    groupId: str
    groupName: str
    webhook: str
    groupType: str = "资源群"
    audience: str | None = None
    cityLabel: str | None = None
    dailyTemplate: str = "midday"
    sendWindow: str | None = None
    ownerName: str | None = None
    remark: str | None = None
    enabled: bool = True
    createdAt: str
    updatedAt: str


class OpsConsoleState(BaseModel):
    singleGroupResources: list[SingleGroupResource] = Field(default_factory=list)
    groupUploadBatches: list[GroupUploadBatch] = Field(default_factory=list)
    feedbackTickets: list[FeedbackTicket] = Field(default_factory=list)
    wecomGroupJoinWays: list[WecomGroupJoinWayConfig] = Field(default_factory=list)
    groupBotChannels: list[GroupBotChannel] = Field(default_factory=list)


class OpsConsoleStore:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> OpsConsoleState:
        if not self.file_path.exists():
            return OpsConsoleState()
        payload = json.loads(self.file_path.read_text(encoding="utf-8") or "{}")
        return OpsConsoleState.model_validate(payload)

    def save(self, state: OpsConsoleState) -> None:
        self.file_path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def preview_group_upload(self, raw_text: str) -> dict:
        rows = self._parse_group_upload_rows(raw_text)
        return self._build_group_upload_result(rows)

    def group_upload_template_csv_bytes(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["群名称", "城市", "区域", "类型", "标签", "二维码链接", "有效期", "备注"])
        writer.writerow(["长沙租房群", "长沙", "岳麓区", "房源", "长租,中介", "https://example.com/qr-1.png", "2026-07-03", "新增渠道"])
        writer.writerow(["上海老板群", "上海", "浦东新区", "老板", "合作,渠道", "https://example.com/qr-2.png", "2026-07-05", "需名片验证"])
        return output.getvalue().encode("utf-8-sig")

    def group_upload_template_xlsx_bytes(self) -> bytes:
        rows = [
            ["群名称", "城市", "区域", "类型", "标签", "二维码链接", "有效期", "备注"],
            ["长沙租房群", "长沙", "岳麓区", "房源", "长租,中介", "https://example.com/qr-1.png", "2026-07-03", "新增渠道"],
            ["上海老板群", "上海", "浦东新区", "老板", "合作,渠道", "https://example.com/qr-2.png", "2026-07-05", "需名片验证"],
        ]
        return self._build_simple_xlsx(rows)

    def preview_group_upload_file(self, filename: str, content: bytes) -> dict:
        rows = self._parse_group_upload_file(filename, content)
        return self._build_group_upload_result(rows)

    def create_group_upload_batch(self, raw_text: str, batch_name: str | None = None, operator_name: str | None = None) -> dict:
        rows = self._parse_group_upload_rows(raw_text)
        summary = self._build_group_upload_result(rows)
        now = now_iso()
        batch = GroupUploadBatch(
            id=new_id("group_upload_batch"),
            batchName=batch_name or f"群二维码批量上传 {now[:10]}",
            operatorName=(operator_name or "").strip() or None,
            rows=rows,
            totalCount=summary["summary"]["totalCount"],
            successCount=summary["summary"]["successCount"],
            failedCount=summary["summary"]["failedCount"],
            createdAt=now,
            updatedAt=now,
        )
        state = self.load()
        state.groupUploadBatches.insert(0, batch)
        self.save(state)
        return batch.model_dump()

    def create_group_upload_batch_from_file(
        self,
        filename: str,
        content: bytes,
        batch_name: str | None = None,
        operator_name: str | None = None,
    ) -> dict:
        rows = self._parse_group_upload_file(filename, content)
        summary = self._build_group_upload_result(rows)
        now = now_iso()
        batch = GroupUploadBatch(
            id=new_id("group_upload_batch"),
            batchName=batch_name or f"群二维码批量上传 {now[:10]}",
            operatorName=(operator_name or "").strip() or None,
            rows=rows,
            totalCount=summary["summary"]["totalCount"],
            successCount=summary["summary"]["successCount"],
            failedCount=summary["summary"]["failedCount"],
            createdAt=now,
            updatedAt=now,
        )
        state = self.load()
        state.groupUploadBatches.insert(0, batch)
        self.save(state)
        return batch.model_dump()

    def list_group_upload_batches(self) -> list[dict]:
        return [item.model_dump() for item in self.load().groupUploadBatches]

    def list_single_group_resources(self) -> list[dict]:
        return [item.model_dump() for item in self.load().singleGroupResources]

    def list_wecom_group_join_ways(self) -> list[dict]:
        return [item.model_dump() for item in self.load().wecomGroupJoinWays]

    def list_group_bot_channels(self, *, include_webhook: bool = False) -> list[dict]:
        channels = [item.model_dump() for item in self.load().groupBotChannels]
        if include_webhook:
            return channels
        for item in channels:
            item["webhook"] = self._mask_webhook(item.get("webhook") or "")
        return channels

    def group_bot_webhook_map(self) -> dict[str, str]:
        return {
            item.groupId: item.webhook
            for item in self.load().groupBotChannels
            if item.enabled and item.groupId and item.webhook.startswith(("http://", "https://"))
        }

    def upsert_group_bot_channel(
        self,
        *,
        group_id: str,
        group_name: str,
        webhook: str,
        group_type: str,
        audience: str,
        city_label: str,
        daily_template: str,
        send_window: str,
        owner_name: str | None,
        remark: str | None,
        enabled: bool,
    ) -> dict:
        group_id = (group_id or "").strip()
        group_name = (group_name or "").strip()
        webhook = (webhook or "").strip()
        if not group_id:
            raise ValueError("群标识不能为空")
        if not group_name:
            raise ValueError("群名称不能为空")
        if not webhook.startswith(("http://", "https://")):
            raise ValueError("webhook 必须是 http 或 https 地址")

        now = now_iso()
        state = self.load()
        existing = next((item for item in state.groupBotChannels if item.groupId == group_id), None)
        if existing:
            existing.groupName = group_name
            existing.webhook = webhook
            existing.groupType = (group_type or "资源群").strip() or "资源群"
            existing.audience = (audience or "").strip() or None
            existing.cityLabel = (city_label or "").strip() or None
            existing.dailyTemplate = (daily_template or "midday").strip() or "midday"
            existing.sendWindow = (send_window or "").strip() or None
            existing.ownerName = (owner_name or "").strip() or None
            existing.remark = (remark or "").strip() or None
            existing.enabled = bool(enabled)
            existing.updatedAt = now
            record = existing
        else:
            record = GroupBotChannel(
                id=new_id("group_bot_channel"),
                groupId=group_id,
                groupName=group_name,
                webhook=webhook,
                groupType=(group_type or "资源群").strip() or "资源群",
                audience=(audience or "").strip() or None,
                cityLabel=(city_label or "").strip() or None,
                dailyTemplate=(daily_template or "midday").strip() or "midday",
                sendWindow=(send_window or "").strip() or None,
                ownerName=(owner_name or "").strip() or None,
                remark=(remark or "").strip() or None,
                enabled=bool(enabled),
                createdAt=now,
                updatedAt=now,
            )
            state.groupBotChannels.insert(0, record)
        self.save(state)
        result = record.model_dump()
        result["webhook"] = self._mask_webhook(result["webhook"])
        return result

    def save_wecom_group_join_way(
        self,
        *,
        config_id: str,
        remark: str,
        chat_id_list: list[str],
        room_base_name: str,
        room_base_id: int,
        auto_create_room: int,
        state_value: str | None,
        operator_name: str | None,
        raw_response: dict,
    ) -> dict:
        now = now_iso()
        record = WecomGroupJoinWayConfig(
            id=new_id("wecom_join_way"),
            configId=config_id,
            remark=remark,
            chatIdList=chat_id_list,
            roomBaseName=room_base_name,
            roomBaseId=room_base_id,
            autoCreateRoom=auto_create_room,
            state=state_value,
            operatorName=(operator_name or "").strip() or None,
            rawResponse=raw_response,
            createdAt=now,
            updatedAt=now,
        )
        state = self.load()
        state.wecomGroupJoinWays.insert(0, record)
        self.save(state)
        return record.model_dump()

    def _mask_webhook(self, url: str) -> str:
        if not url:
            return ""
        if "key=" not in url:
            return url[:36] + "***" if len(url) > 40 else "***"
        prefix, key = url.split("key=", 1)
        return f"{prefix}key={key[:4]}***{key[-4:]}" if len(key) > 8 else f"{prefix}key=***"

    def create_single_group_resource(
        self,
        name: str,
        city_mode: str,
        city_label: str,
        region: list[str],
        group_type: str,
        purposes: list[str],
        member_range: str,
        active_level: str,
        expires_in_days: int,
        remark: str | None,
        custom_tags: list[str],
        qr_image_data: str | None,
        operator_name: str | None = None,
    ) -> dict:
        now = now_iso()
        resource = SingleGroupResource(
            id=new_id("group_resource"),
            operatorName=(operator_name or "").strip() or None,
            name=(name or "").strip(),
            cityMode=(city_mode or "city").strip() or "city",
            cityLabel=(city_label or "").strip() or None,
            region=region or [],
            groupType=(group_type or "").strip() or "房源",
            purposes=[item.strip() for item in purposes if str(item).strip()][:5],
            memberRange=(member_range or "").strip() or None,
            activeLevel=(active_level or "").strip() or None,
            expiresInDays=max(1, int(expires_in_days or 5)),
            expiresAtText=self._expire_text(max(1, int(expires_in_days or 5))),
            remark=(remark or "").strip() or None,
            customTags=[item.strip() for item in custom_tags if str(item).strip()][:4],
            qrImageData=qr_image_data,
            qrStatus="uploaded" if qr_image_data else "missing",
            createdAt=now,
            updatedAt=now,
        )
        state = self.load()
        state.singleGroupResources.insert(0, resource)
        self.save(state)
        return resource.model_dump()

    def list_feedback_tickets(self, status: str | None = None) -> list[dict]:
        tickets = self.load().feedbackTickets
        if status:
            tickets = [item for item in tickets if item.status == status]
        return [item.model_dump() for item in tickets]

    def create_feedback_ticket(
        self,
        ticket_type: str,
        content: str,
        user_id: str | None = None,
        user_nickname: str | None = None,
        contact: str | None = None,
    ) -> dict:
        now = now_iso()
        ticket = FeedbackTicket(
            id=new_id("feedback_ticket"),
            type=(ticket_type or "bug").strip() or "bug",
            userId=(user_id or "").strip() or None,
            userNickname=(user_nickname or "").strip() or None,
            contact=(contact or "").strip() or None,
            content=(content or "").strip(),
            createdAt=now,
            updatedAt=now,
        )
        state = self.load()
        state.feedbackTickets.insert(0, ticket)
        self.save(state)
        return ticket.model_dump()

    def update_feedback_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        reply_text: str | None = None,
        reward_note: str | None = None,
        operator_name: str | None = None,
    ) -> dict | None:
        state = self.load()
        for ticket in state.feedbackTickets:
            if ticket.id != ticket_id:
                continue
            if status is not None:
                ticket.status = status
            if reply_text is not None:
                ticket.replyText = reply_text.strip() or None
            if reward_note is not None:
                ticket.rewardNote = reward_note.strip() or None
            if operator_name is not None:
                ticket.operatorName = operator_name.strip() or None
            ticket.updatedAt = now_iso()
            self.save(state)
            return ticket.model_dump()
        return None

    def _build_group_upload_result(self, rows: list[GroupUploadRow]) -> dict:
        success_rows = [item for item in rows if item.success]
        failed_rows = [item for item in rows if not item.success]
        return {
            "summary": {
                "totalCount": len(rows),
                "successCount": len(success_rows),
                "failedCount": len(failed_rows),
            },
            "rows": [item.model_dump() for item in rows],
        }

    def _parse_group_upload_rows(self, raw_text: str) -> list[GroupUploadRow]:
        rows: list[GroupUploadRow] = []
        for index, raw_line in enumerate((raw_text or "").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = self._split_row(line)
            row = GroupUploadRow(rowNumber=index, raw=raw_line)
            if len(parts) < 7:
                row.error = "字段不足，至少需要：群名称、城市、区域、类型、标签、二维码链接、有效期"
                rows.append(row)
                continue
            row.groupName = parts[0]
            row.city = parts[1]
            row.district = parts[2]
            row.groupType = parts[3]
            row.tags = [item.strip() for item in parts[4].replace("，", ",").split(",") if item.strip()]
            row.qrUrl = parts[5]
            row.expiresAt = parts[6]
            row.note = parts[7] if len(parts) > 7 else None
            row.success = bool(row.groupName and row.city and row.qrUrl and row.expiresAt)
            if not row.success:
                row.error = "必要字段为空"
            rows.append(row)
        return rows

    def _split_row(self, line: str) -> list[str]:
        for separator in ("\t", "|", ","):
            if separator in line:
                return [item.strip() for item in line.split(separator)]
        return [line]

    def _parse_group_upload_file(self, filename: str, content: bytes) -> list[GroupUploadRow]:
        lower = (filename or "").lower()
        if lower.endswith(".csv"):
            table = self._read_csv_rows(content)
        elif lower.endswith(".xlsx"):
            table = self._read_xlsx_rows(content)
        else:
            raise ValueError("仅支持 .xlsx 或 .csv 文件")

        rows: list[GroupUploadRow] = []
        data_rows = self._drop_header_row(table)
        for index, cols in enumerate(data_rows, start=1):
            row = GroupUploadRow(
                rowNumber=index,
                raw=" | ".join(cols),
            )
            padded = cols + [""] * (8 - len(cols))
            row.groupName = padded[0].strip() or None
            row.city = padded[1].strip() or None
            row.district = padded[2].strip() or None
            row.groupType = padded[3].strip() or None
            row.tags = [item.strip() for item in padded[4].replace("，", ",").split(",") if item.strip()]
            row.qrUrl = padded[5].strip() or None
            row.expiresAt = padded[6].strip() or None
            row.note = padded[7].strip() or None
            row.success = bool(row.groupName and row.city and row.qrUrl and row.expiresAt)
            if not row.success:
                row.error = "缺少必要字段：群名称 / 城市 / 二维码链接 / 有效期"
            rows.append(row)
        return rows

    def _drop_header_row(self, table: list[list[str]]) -> list[list[str]]:
        if not table:
            return []
        header = [item.strip().lower() for item in table[0]]
        header_keys = {"群名称", "城市", "区域", "类型", "标签", "二维码链接", "有效期", "备注"}
        if any(item in header_keys for item in header):
            return table[1:]
        return table

    def _read_csv_rows(self, content: bytes) -> list[list[str]]:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        return [[str(cell or "").strip() for cell in row] for row in reader if any(str(cell or "").strip() for cell in row)]

    def _read_xlsx_rows(self, content: bytes) -> list[list[str]]:
        ns = {
            "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
        }
        with ZipFile(io.BytesIO(content)) as zf:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in root.findall("main:si", ns):
                    text = "".join(node.text or "" for node in si.findall(".//main:t", ns))
                    shared_strings.append(text)

            workbook = ET.fromstring(zf.read("xl/workbook.xml"))
            first_sheet = workbook.find("main:sheets/main:sheet", ns)
            if first_sheet is None:
                return []
            rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            target = None
            for rel in rels.findall("rel:Relationship", ns):
                if rel.attrib.get("Id") == rel_id:
                    target = rel.attrib.get("Target")
                    break
            if not target:
                return []
            sheet_path = target if target.startswith("xl/") else f"xl/{target}"
            sheet = ET.fromstring(zf.read(sheet_path))
            rows: list[list[str]] = []
            for row in sheet.findall("main:sheetData/main:row", ns):
                values: list[str] = []
                for cell in row.findall("main:c", ns):
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("main:v", ns)
                    raw = value_node.text if value_node is not None else ""
                    if cell_type == "s" and raw:
                        try:
                            values.append(shared_strings[int(raw)])
                        except Exception:
                            values.append("")
                    else:
                        values.append(raw or "")
                if any(str(item).strip() for item in values):
                    rows.append([str(item or "").strip() for item in values])
            return rows

    def _build_simple_xlsx(self, rows: list[list[str]]) -> bytes:
        shared_strings: list[str] = []
        shared_index: dict[str, int] = {}

        def sst_index(value: str) -> int:
            text = str(value)
            if text not in shared_index:
                shared_index[text] = len(shared_strings)
                shared_strings.append(text)
            return shared_index[text]

        def col_name(index: int) -> str:
            result = ""
            idx = index
            while idx > 0:
                idx, rem = divmod(idx - 1, 26)
                result = chr(65 + rem) + result
            return result

        sheet_rows: list[str] = []
        for row_idx, row in enumerate(rows, start=1):
            cells: list[str] = []
            for col_idx, value in enumerate(row, start=1):
                if value in (None, ""):
                    continue
                cells.append(f'<c r="{col_name(col_idx)}{row_idx}" t="s"><v>{sst_index(str(value))}</v></c>')
            sheet_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')

        shared_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
            + "".join(f"<si><t>{value}</t></si>" for value in shared_strings)
            + "</sst>"
        )
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            + "".join(sheet_rows)
            + "</sheetData></worksheet>"
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="群资源模板" sheetId="1" r:id="rId1"/></sheets></workbook>'
        )
        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            '</Relationships>'
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            '</Types>'
        )

        output = io.BytesIO()
        with ZipFile(output, "w") as zf:
            zf.writestr("[Content_Types].xml", content_types)
            zf.writestr("_rels/.rels", root_rels)
            zf.writestr("xl/workbook.xml", workbook_xml)
            zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
            zf.writestr("xl/sharedStrings.xml", shared_xml)
        return output.getvalue()

    def _expire_text(self, days: int) -> str:
        from datetime import datetime, timedelta
        expire_at = datetime.now() + timedelta(days=days)
        return f"{expire_at.month}月{expire_at.day}日"
