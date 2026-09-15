# 数据结构

## 1. 核心实体

v0.1 核心实体：

- User
- ImportBatch
- RawMessage
- Card
- CardMedia
- ViewEvent
- RelayEntry
- Category

## 2. TypeScript 类型定义

```ts
export type ImportStatus = "pending" | "success" | "failed" | "claimed";
export type CardStatus = "draft" | "published" | "archived";
export type ViewType = "logged_in" | "anonymous";
export type RelayStatus = "active" | "deleted";
export type FollowUpStatus = "pending" | "followed";

export interface User {
  id: string;
  openid: string;
  unionid?: string;
  nickname: string;
  avatarUrl: string;
  phone?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ImportBatch {
  id: string;
  externalUserId: string;
  conversationId: string;
  claimedByUserId?: string;
  status: ImportStatus;
  titleCandidate: string;
  sourceType: "wechat_note" | "miniapp_link" | "mp_link" | "web_link" | "unknown";
  errorMessage?: string;
  rawMessageIds: string[];
  generatedCardId?: string;
  startedAt: string;
  endedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface RawMessage {
  id: string;
  importBatchId?: string;
  externalUserId: string;
  conversationId: string;
  msgType: "text" | "image" | "link" | "location" | "video" | "file" | "unknown";
  content: Record<string, unknown>;
  mediaId?: string;
  localMediaUrl?: string;
  receivedAt: string;
  createdAt: string;
}

export interface Card {
  id: string;
  ownerUserId: string;
  importBatchId?: string;
  sourceCardId?: string;
  status: CardStatus;
  title: string;
  coverUrl?: string;
  detailText: string;
  projectName?: string;
  locationText?: string;
  phone?: string;
  relayNotice?: string;
  sourceUrl?: string;
  enabledFields: string[];
  categoryIds: string[];
  media: CardMedia[];
  relayConfig: RelayConfig;
  publishedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CardMedia {
  id: string;
  cardId: string;
  type: "image" | "video";
  url: string;
  sortOrder: number;
  sourceMediaId?: string;
  createdAt: string;
}

export interface RelayConfig {
  enabled: boolean;
  requirePhone: boolean;
  requireAddress: boolean;
}

export interface ViewEvent {
  id: string;
  cardId: string;
  viewerUserId?: string;
  viewType: ViewType;
  anonymousId?: string;
  nickname?: string;
  avatarUrl?: string;
  viewedAt: string;
  dateKey: string;
}

export interface RelayEntry {
  id: string;
  cardId: string;
  userId: string;
  nickname: string;
  avatarUrl: string;
  maskedNickname: string;
  phone?: string;
  address?: string;
  status: RelayStatus;
  followUpStatus: FollowUpStatus;
  createdAt: string;
  updatedAt: string;
}

export interface Category {
  id: string;
  ownerUserId: string;
  name: string;
  sortOrder: number;
  createdAt: string;
}
```

## 3. JSON 样例

```json
{
  "user": {
    "id": "user_001",
    "openid": "openid_mock_001",
    "nickname": "张三",
    "avatarUrl": "https://example.com/avatar.png",
    "createdAt": "2026-06-08T10:00:00+08:00",
    "updatedAt": "2026-06-08T10:00:00+08:00"
  },
  "importBatch": {
    "id": "import_001",
    "externalUserId": "external_001",
    "conversationId": "conv_001",
    "claimedByUserId": "user_001",
    "status": "claimed",
    "titleCandidate": "城南新盘周末看房活动",
    "sourceType": "wechat_note",
    "rawMessageIds": ["msg_001", "msg_002"],
    "generatedCardId": "card_001",
    "startedAt": "2026-06-08T10:01:00+08:00",
    "endedAt": "2026-06-08T10:02:00+08:00",
    "createdAt": "2026-06-08T10:01:00+08:00",
    "updatedAt": "2026-06-08T10:02:00+08:00"
  },
  "card": {
    "id": "card_001",
    "ownerUserId": "user_001",
    "importBatchId": "import_001",
    "status": "published",
    "title": "城南新盘周末看房活动",
    "coverUrl": "https://example.com/cover.jpg",
    "detailText": "本周末开放样板间，支持预约看房。",
    "projectName": "城南花园",
    "locationText": "城南新区",
    "phone": "13800000000",
    "relayNotice": "感兴趣请接龙报名。",
    "sourceUrl": "https://example.com/source",
    "enabledFields": ["projectName", "locationText", "phone", "relayNotice"],
    "categoryIds": ["cat_001"],
    "media": [
      {
        "id": "media_001",
        "cardId": "card_001",
        "type": "image",
        "url": "https://example.com/image1.jpg",
        "sortOrder": 1,
        "createdAt": "2026-06-08T10:02:00+08:00"
      }
    ],
    "relayConfig": {
      "enabled": true,
      "requirePhone": true,
      "requireAddress": false
    },
    "publishedAt": "2026-06-08T10:05:00+08:00",
    "createdAt": "2026-06-08T10:02:00+08:00",
    "updatedAt": "2026-06-08T10:05:00+08:00"
  }
}
```

## 4. 字段说明

| 字段 | 说明 |
|---|---|
| `externalUserId` | 企业微信客服侧外部联系人标识 |
| `conversationId` | 客服会话标识 |
| `claimedByUserId` | 认领导入记录的小程序用户 |
| `sourceCardId` | 一键复用时指向原卡片 |
| `enabledFields` | 卡片查看页启用展示的字段 |
| `anonymousId` | 匿名浏览者的临时标识 |
| `maskedNickname` | 普通用户可见的脱敏昵称 |
| `dateKey` | 浏览统计日期，如 `2026-06-08` |

## 5. 后续扩展字段建议

- `teamId`：团队素材库
- `templateId`：行业模板
- `paidPlan`：订阅计划
- `exportedAt`：接龙名单导出时间
- `shareChannel`：分享来源
- `parseConfidence`：解析置信度
- `llmTraceId`：大模型调用追踪 ID
