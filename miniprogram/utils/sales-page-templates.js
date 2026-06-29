const SALES_PAGE_TEMPLATES = [
  {
    id: "consultant_classic",
    cardType: "business_card",
    scene: "顾问信任",
    name: "专业顾问",
    subtitle: "适合房产、保险、咨询、顾问",
    badge: "稳重可信",
    tone: "blue",
    layout: "consultant",
    title: "我的专业顾问名片",
    summary: "把身份、服务范围和联系方式整理成一张可信名片。",
    preview: {
      title: "张明",
      subtitle: "资深房产顾问",
      roleBadge: "5年从业经验",
      organization: "链家地产 · 商级经纪人",
      headline: "稳妥、可信、高效",
      contactLine: "138 8888 8888 · zhangming888",
      avatarClass: "avatar-male avatar-suit-blue",
      avatarUrl: "https://teambuy.lifelove.top/media/media_a535beaccd-manual_asset_0afb19f5db.webp",
      chips: ["需求分析", "方案建议", "长期跟进"],
      sections: ["个人介绍", "服务范围", "电话 / 微信"]
    },
    features: ["头像名片", "专业介绍", "电话微信", "留言咨询"],
    defaults: {
      title: "专业顾问",
      company: "我的公司 / 门店",
      serviceScope: "咨询服务 / 客户顾问 / 长期跟进",
      headline: "用专业经验帮你少走弯路",
      bio: "我会根据你的具体需求，提供清晰建议、及时沟通和持续跟进。",
      city: "本地服务"
    }
  },
  {
    id: "store_sales_card",
    cardType: "business_card",
    scene: "门店销售",
    name: "门店名片",
    subtitle: "适合门店、本地生活、美业、装修",
    badge: "到店预约",
    tone: "green",
    layout: "store",
    title: "我的门店名片",
    summary: "突出门店、服务项目、位置和咨询入口。",
    preview: {
      title: "沈若晴",
      subtitle: "茶语时光主理人",
      roleBadge: "同城门店",
      organization: "茶语时光生活馆",
      headline: "品质好茶、健康轻食、好物生活",
      contactLine: "0571-8888 8888 · ruoqingtea",
      avatarClass: "avatar-female avatar-apron-green",
      avatarUrl: "https://teambuy.lifelove.top/media/media_35b3a047fc-manual_asset_25ae3bb5b2.webp",
      chips: ["到店服务", "门店地址", "优惠咨询"],
      sections: ["门店信息", "服务项目", "优惠咨询"]
    },
    features: ["门店信息", "同城服务", "优惠咨询", "位置说明"],
    defaults: {
      title: "门店顾问",
      company: "我的门店",
      serviceScope: "到店咨询 / 预约服务 / 售后跟进",
      headline: "到店前先加我，帮你安排合适时间",
      bio: "欢迎提前沟通需求，我会帮你确认服务项目、时间和注意事项。",
      city: "同城服务"
    }
  },
  {
    id: "expert_personal_brand",
    cardType: "business_card",
    scene: "专家介绍",
    name: "专家介绍",
    subtitle: "适合课程、陪跑、知识服务、专业咨询",
    badge: "专业背书",
    tone: "purple",
    layout: "expert",
    title: "我的专家介绍",
    summary: "突出专业能力、擅长领域和成果背书。",
    preview: {
      title: "林乔",
      subtitle: "商业增长顾问",
      roleBadge: "10年实战经验",
      organization: "景和增长实验室",
      headline: "帮助企业实现增长突破",
      contactLine: "182 8888 8888 · linqiao888",
      avatarClass: "avatar-female avatar-suit-dark",
      avatarUrl: "https://teambuy.lifelove.top/media/media_c8b9458757-manual_asset_b208951151.webp",
      chips: ["增长策略", "案例成果", "专业咨询"],
      sections: ["擅长领域", "服务成果", "专业咨询"]
    },
    features: ["专家人设", "成果背书", "适合领域", "咨询转化"],
    defaults: {
      title: "专业服务者",
      company: "个人品牌 / 工作室",
      serviceScope: "课程咨询 / 陪跑服务 / 专业答疑",
      headline: "把复杂问题讲清楚，把行动路径做出来",
      bio: "我擅长把经验整理成可执行的方法，帮助客户更快理解问题并推进结果。",
      city: "线上 / 本地均可"
    }
  },
  {
    id: "wechat_simple_card",
    cardType: "business_card",
    scene: "简洁微信风",
    name: "简洁微信风",
    subtitle: "适合快速转发、轻个人名片",
    badge: "轻量转发",
    tone: "minimal",
    layout: "wechat",
    title: "我的微信名片",
    summary: "像微信个人页一样轻，客户一眼看到人和联系方式。",
    preview: {
      title: "陈宇",
      subtitle: "自由职业者 / 内容创作者",
      roleBadge: "微信名片",
      organization: "杭州 · 线上沟通",
      headline: "热爱生活，分享成长，连接美好",
      contactLine: "chenyu2024 · chenyu@163.com",
      avatarClass: "avatar-male avatar-casual-light",
      avatarUrl: "https://teambuy.lifelove.top/media/media_94ec97ee72-manual_asset_744c2c96ca.webp",
      chips: ["加我微信", "保存名片", "快速分享"],
      sections: ["头像", "一句话介绍", "联系按钮"]
    },
    features: ["轻名片", "复制微信", "一键分享", "少字段"],
    defaults: {
      title: "微信顾问",
      company: "",
      serviceScope: "咨询 / 沟通 / 转介绍",
      headline: "有需要可以直接联系我",
      bio: "把我推荐给朋友时，可以直接转发这张名片。",
      city: ""
    }
  },
  {
    id: "service_consultation",
    cardType: "service_offer",
    scene: "咨询预约",
    name: "咨询预约",
    subtitle: "适合顾问、课程、陪跑、咨询服务",
    badge: "先聊需求",
    tone: "blue",
    layout: "consultation",
    title: "一对一咨询服务",
    summary: "突出适合谁、能解决什么、如何预约沟通。",
    preview: {
      title: "专业咨询\n预约沟通",
      subtitle: "为你提供专业解决方案",
      headline: "适合有明确问题、需要专业建议的客户",
      avatarUrl: "https://teambuy.lifelove.top/media/media_c8b9458757-manual_asset_b208951151.webp",
      chips: ["专业", "高效", "可回访"],
      sections: ["适合人群", "服务内容", "服务流程"],
      serviceItems: ["一对一咨询", "问题诊断", "解决方案", "持续跟进"],
      bullets: [
        "适合有明确需求，想获得专业建议的客户",
        "先梳理问题，再给出沟通建议",
        "可先预约时间，再深入确认细节"
      ],
      primaryAction: "电话咨询",
      secondaryAction: "微信咨询",
      mockType: "consultation"
    },
    features: ["适合人群", "服务内容", "预约流程", "电话微信"],
    defaults: {
      serviceName: "一对一咨询服务",
      headline: "先沟通需求，再给你清晰建议",
      targetAudience: "适合有明确问题、需要专业建议或长期陪跑的客户",
      serviceContent: "需求梳理、问题分析、方案建议、后续跟进。",
      pricingNote: "按咨询时长或服务内容报价",
      serviceProcess: "提交需求 - 预约沟通 - 输出建议 - 后续跟进",
      caseHighlights: "可补充过往案例、客户反馈或服务成果。",
      serviceArea: "线上 / 本地均可",
      appointmentNote: "建议提前一天预约沟通时间"
    }
  },
  {
    id: "service_pricing",
    cardType: "service_offer",
    scene: "服务报价",
    name: "服务报价",
    subtitle: "适合装修、设计、财税、企业服务",
    badge: "报价清晰",
    tone: "green",
    layout: "pricing",
    title: "服务报价方案",
    summary: "突出服务内容、报价方式和交付流程。",
    preview: {
      title: "专业服务\n标准报价",
      subtitle: "明码标价 / 按需升级",
      headline: "先确认范围，再给报价说明",
      coverUrl: "https://teambuy.lifelove.top/media/media_aa4adc7919-manual_asset_5d2328325f.webp",
      chips: ["空间设计", "施工落地", "软装搭配"],
      sections: ["服务范围", "报价说明", "交付流程"],
      serviceItems: ["空间设计", "施工工地", "软装搭配", "售后维护"],
      quoteTags: ["基础方案", "标准方案", "定制方案"],
      bullets: [
        "报价前先确认服务边界和交付内容",
        "不同需求对应不同服务组合",
        "支持先沟通预算，再安排报价"
      ],
      primaryAction: "电话咨询",
      secondaryAction: "留下联系方式",
      mockType: "pricing"
    },
    features: ["报价说明", "服务范围", "交付流程", "案例图片"],
    defaults: {
      serviceName: "服务报价方案",
      headline: "按需求定制报价，流程清晰可跟进",
      targetAudience: "适合需要明确服务范围和预算的客户",
      serviceContent: "基础咨询、方案制定、执行支持、结果复盘。",
      pricingNote: "根据服务范围、周期和交付内容报价",
      serviceProcess: "需求确认 - 报价沟通 - 签约执行 - 交付验收",
      caseHighlights: "可补充案例图、交付成果或客户评价。",
      serviceArea: "本地 / 线上服务",
      appointmentNote: "预约后先确认需求和预算范围"
    }
  },
  {
    id: "service_case_story",
    cardType: "service_offer",
    scene: "案例背书",
    name: "案例背书",
    subtitle: "适合需要展示成果的服务",
    badge: "成果证明",
    tone: "warm",
    layout: "case",
    title: "案例型服务介绍",
    summary: "用案例、成果和过程证明服务价值。",
    preview: {
      title: "实战案例\n见证成果",
      subtitle: "真实案例 | 成果展示 | 口碑见证",
      headline: "用过程和结果建立信任",
      coverUrl: "https://teambuy.lifelove.top/media/media_3463380142-manual_asset_1dd9a72074.webp",
      caseImageUrls: [
        "https://teambuy.lifelove.top/media/media_3463380142-manual_asset_1dd9a72074.webp",
        "https://teambuy.lifelove.top/media/media_aa4adc7919-manual_asset_5d2328325f.webp",
        "https://teambuy.lifelove.top/media/media_9ff631d3e1-manual_asset_6a708c50d6.webp"
      ],
      chips: ["真实案例", "前后对比", "客户反馈"],
      sections: ["案例亮点", "成果说明", "预约沟通"],
      metricItems: [
        { value: "200+", label: "已服务" },
        { value: "98%", label: "好评率" },
        { value: "5年", label: "经验沉淀" }
      ],
      caseLabels: ["整屋改造前", "改造后", "客户反馈"],
      bullets: [
        "适合先看案例，再判断服务是否匹配",
        "用真实成果和过程建立信任",
        "支持先看案例，再预约沟通"
      ],
      primaryAction: "查看案例",
      secondaryAction: "咨询服务",
      mockType: "case"
    },
    features: ["案例展示", "成果背书", "服务过程", "预约咨询"],
    defaults: {
      serviceName: "案例型服务介绍",
      headline: "先看真实案例，再决定是否沟通",
      targetAudience: "适合重视结果、希望先看案例的客户",
      serviceContent: "围绕客户问题提供定制服务，并沉淀可复盘成果。",
      pricingNote: "按项目复杂度和服务周期报价",
      serviceProcess: "案例了解 - 需求沟通 - 方案定制 - 执行跟进",
      caseHighlights: "在这里写代表案例、前后变化、客户反馈或成果数字。",
      serviceArea: "可线上沟通",
      appointmentNote: "预约后可先发送你的需求或照片资料"
    }
  },
  {
    id: "service_business_opportunity",
    cardType: "service_offer",
    scene: "商机合作",
    name: "商机合作",
    subtitle: "适合保险出单、清关代理、招商招募、批发合作",
    badge: "合作转化",
    tone: "teal",
    layout: "opportunity",
    title: "商机 / 合作信息",
    summary: "把群里的合作信息整理成可咨询、可报名、可追踪的商机页。",
    preview: {
      title: "商机合作\n一页讲清",
      subtitle: "适合群发、私聊和朋友圈转发",
      headline: "先看合作内容、适合对象和联系方式",
      chips: ["合作机会", "适合对象", "快速咨询"],
      sections: ["适合谁", "合作内容", "下一步"],
      serviceItems: ["核心合作", "优势说明", "报名咨询", "电话微信"],
      bullets: [
        "适合需要找代理、渠道、客户或合作方的人",
        "把群消息里的价格、时效、范围和要求整理清楚",
        "客户打开后可直接咨询、报名或复制微信"
      ],
      quoteTags: ["有量有价", "合作共赢", "欢迎咨询"],
      primaryAction: "咨询合作",
      secondaryAction: "复制微信",
      mockType: "opportunity"
    },
    features: ["合作对象", "核心优势", "时间要求", "咨询报名"],
    defaults: {
      serviceName: "商机 / 合作信息",
      headline: "把合作内容、适合对象和联系方式一页讲清",
      targetAudience: "适合想了解合作条件、代理机会、批发货源或专业服务的客户",
      serviceContent: "合作内容、核心优势、适用范围、咨询方式。",
      pricingNote: "可填写价格优势、起批条件、服务费、报价方式或合作政策",
      serviceProcess: "了解合作 - 咨询细节 - 提交信息 - 确认合作",
      caseHighlights: "可补充合作案例、资质背书、工厂/服务优势或客户反馈。",
      serviceArea: "全国 / 指定城市 / 线上咨询",
      appointmentNote: "建议先发送需求、品类、城市或合作意向"
    }
  },
  {
    id: "service_campaign",
    cardType: "service_offer",
    scene: "活动招募",
    name: "活动招募",
    subtitle: "适合体验课、团体服务、短期活动",
    badge: "限时招募",
    tone: "orange",
    layout: "campaign",
    title: "活动招募服务",
    summary: "突出时间、名额、适合人群和报名咨询。",
    preview: {
      title: "精选活动\n限时招募",
      subtitle: "少量活动名额限量开放",
      headline: "名额有限，留下电话确认席位",
      avatarUrl: "https://teambuy.lifelove.top/media/media_35b3a047fc-manual_asset_25ae3bb5b2.webp",
      chips: ["活动倒计时", "名额有限", "立即报名"],
      sections: ["活动亮点", "适合人群", "报名入口"],
      countdown: ["03", "12", "45", "30"],
      countdownLabels: ["天", "时", "分", "秒"],
      bullets: [
        "适合先体验、再决定是否继续服务",
        "活动时间有限，建议尽早确认名额",
        "支持电话、微信和预约报名"
      ],
      primaryAction: "立即报名",
      secondaryAction: "咨询详情",
      mockType: "campaign"
    },
    features: ["活动亮点", "名额提示", "报名咨询", "预约留言"],
    defaults: {
      serviceName: "活动招募服务",
      headline: "限时开放，适合先体验再决定",
      targetAudience: "适合想低成本体验服务、了解方法或加入活动的客户",
      serviceContent: "体验服务、集中答疑、活动陪跑或短期训练。",
      pricingNote: "可填写体验价、活动价或免费咨询",
      serviceProcess: "了解活动 - 留下联系方式 - 确认名额 - 参加体验",
      caseHighlights: "可补充往期活动反馈、现场照片或成果。",
      serviceArea: "线上 / 线下活动",
      appointmentNote: "名额有限，建议尽早预约"
    }
  }
];

function getSalesPageTemplates(cardType) {
  return SALES_PAGE_TEMPLATES.filter((item) => !cardType || item.cardType === cardType);
}

function getSalesPageTemplate(templateId) {
  return SALES_PAGE_TEMPLATES.find((item) => item.id === templateId) || SALES_PAGE_TEMPLATES[0];
}

function templateToneClass(template) {
  return `tone-${(template && template.tone) || "blue"}`;
}

module.exports = {
  SALES_PAGE_TEMPLATES,
  getSalesPageTemplates,
  getSalesPageTemplate,
  templateToneClass
};
