# WeCom Archive Core

`wecom-archive-core` is the shared, single-owner ingestion service for WeCom
conversation archives.

It deliberately owns only the platform responsibilities:

- the official Finance SDK and archive credentials;
- the single global `seq` cursor per enterprise;
- decryption, idempotent persistence and project routing;
- retryable fan-out delivery to registered projects;
- a protected media proxy so projects do not need the Finance SDK.

Product projects must not run their own Finance SDK worker when they use this
service. They keep their own business database, processing state and project
token. A project is added by registering an entry in
`WECOM_ARCHIVE_CORE_PROJECTS_JSON` and implementing the event receiver contract
described below.

## Event contract

The core sends `POST` requests to each matched project's `endpointUrl` with:

```json
{
  "schemaVersion": 1,
  "eventId": "archive_<stream-hash>_<seq>",
  "streamKey": "archive_<corp-hash>",
  "seq": 123,
  "message": {
    "seq": 123,
    "msgId": "...",
    "action": "send_msg",
    "fromUser": "...",
    "toList": [],
    "roomId": "...",
    "msgTime": 1710000000,
    "msgType": "text",
    "decryptedPayload": {
      "text": {"content": "..."}
    },
    "mediaRefs": []
  }
}
```

The core never forwards the Finance SDK ciphertext or RSA-wrapped random key.
`sdkfileid` values are replaced with opaque `mediaId` values. A project can
download the media through the authenticated media endpoint:

```text
GET /v1/projects/{projectId}/media/{eventId}/{mediaId}
X-WeCom-Archive-Project-Token: <project token>
```

For a project added after events have already been ingested, an administrator
can backfill matching deliveries without replaying the Finance SDK cursor:

```text
POST /v1/admin/replay/{projectId}?afterSeq=0&limit=1000
X-Archive-Admin-Token: <admin token>
```

Receivers must be idempotent. A repeated event is a successful delivery, not a
new business action. The receiver should return any 2xx response after the
event has been durably accepted.

Routes may use `chatIds` for group messages. One-to-one messages have no
`roomId`, so a route must explicitly set `includeDirectMessages: true`; it may
further restrict those messages with `fromUserIds` and/or `toUserIds`. Empty
`chatIds` still do not match groups unless `allowAllChats: true` is set.

## Retention

The core is an encrypted relay, not a project system of record. By default,
`WECOM_ARCHIVE_CORE_RAW_RETENTION_HOURS=24`. The worker deletes messages older
than that only when every delivery is `delivered`; pending or failed deliveries
remain eligible for retry. Projects must persist the event before returning
2xx. After cleanup, the core replay and media proxy cannot recover that event,
but each project's own business database is unaffected.

## Local run

```bash
cp .env.example .env
docker compose -f docker-compose.yml up --build
```

The real Finance SDK library and private key are mounted at runtime. They must
not be copied into Git or into the image.
