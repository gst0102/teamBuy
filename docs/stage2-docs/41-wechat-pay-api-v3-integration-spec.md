# 微信支付 API v3 接入规格

## 目标

客户信息链会员使用微信小程序支付。支付成功的唯一依据是服务端验签、解密并校验后的微信支付回调；小程序端 `wx.requestPayment` 的成功回调只用于刷新页面，不能直接开通权益。

## 闭环

1. 小程序创建会员订单，后端生成本系统订单号。
2. 后端使用商户 API 私钥调用 `/v3/pay/transactions/jsapi`，传入小程序 AppID、商户号、订单金额和用户 openid。
3. 后端使用同一商户私钥生成 `timeStamp`、`nonceStr`、`package`、`signType`、`paySign`，小程序调用 `wx.requestPayment`。
4. 微信支付向公开回调地址发送加密通知；后端先校验平台证书签名，再使用 API v3 Key 解密。
5. 后端校验 AppID、商户号、订单号、金额、币种、用户 openid 和 `trade_state=SUCCESS`，通过统一幂等方法开通会员权益。

## 环境变量

- `WECHAT_PAY_ENABLED`：显式开关，默认 `false`。
- `WECHAT_PAY_MCH_ID`：商户号，当前为 `1111636477`。
- `WECHAT_PAY_API_V3_KEY`：32 字节 API v3 Key，只放服务器环境。
- `WECHAT_PAY_CERT_SERIAL_NO` 与 `WECHAT_PAY_PRIVATE_KEY_PATH`：商户 API 证书序列号和私钥。
- `WECHAT_PAY_PLATFORM_CERT_SERIAL_NO` 与 `WECHAT_PAY_PLATFORM_CERT_PATH`：用于回调验签的平台证书序列号和公钥证书；如果商户后台采用“微信支付公钥”模式，路径可指向微信支付公钥 PEM，但仍必须填写对应的公钥 ID。
- `WECHAT_PAY_NOTIFY_URL`：必须是公网 HTTPS 且不能携带查询参数。

商户私钥、API v3 Key 和平台证书不进入小程序、代码仓库或聊天记录。真实支付只有在所有必需配置存在且 `WECHAT_PAY_ENABLED=true` 时才会放行。

## 安全与状态规则

- 生产环境禁止测试确认和测试退款；真实支付模式在任何环境也禁止测试确认。
- 同一用户同一会员方案 30 分钟内复用待支付订单，降低重复下单和状态混乱。
- 回调使用原始 body 验签，拒绝缺少签名头、时间戳超过 5 分钟或平台证书序列号不匹配的请求。
- 已使用的微信交易流水不能绑定其他订单；同一订单同一流水重复通知返回成功且不重复发放权益。
- 金额、币种、AppID、商户号和 payer openid 任一不一致，都不改变订单状态。

## 当前边界

本轮已完成本地代码、签名/解密/回调幂等测试和小程序调用链；源项目的商户 API 私钥、商户 API 证书、API v3 Key 和微信支付公钥已复制到本地 `backend/.env` / `backend/secrets/`。源项目没有提供平台验签 ID，现已由负责人补入 teamBuy 本地环境；具体值不写入文档。`WECHAT_PAY_ENABLED` 仍为 `false`，上线前还需确认支付权限、回调地址和交易类小程序订单发货要求。
