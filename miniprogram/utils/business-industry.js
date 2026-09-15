// 商机合作行业字典：一级行业用于粗筛，细分行业用于精准匹配。
// 这里保留已经上线过的名称，新增方向只扩展 children，避免历史名片出现“已保存但无法重新选择”。
const BUSINESS_INDUSTRY_GROUPS = [
  { label: "外贸", children: ["外贸服务", "外贸获客", "报关清关", "国际物流", "海外仓", "外贸培训", "外贸综合"] },
  { label: "电商", children: ["电商运营", "跨境电商", "直播电商", "独立站", "社区团购", "商超零售", "电商供应链"] },
  { label: "企业服务", children: ["企业管理", "人力资源", "财税法律", "知识产权", "软件/SaaS", "咨询顾问", "企业培训"] },
  { label: "物流供应链", children: ["货运代理", "仓储配送", "快递同城", "供应链管理", "批发采购", "采购代理", "工厂货源"] },
  { label: "本地生活", children: ["餐饮服务", "门店运营", "家政服务", "装修设计", "婚庆摄影", "休闲娱乐", "旅游酒店", "宠物服务"] },
  { label: "房产", children: ["房产经纪", "租售服务", "物业管理", "房产装修", "家居建材", "建筑工程", "地产开发"] },
  { label: "设计营销", children: ["品牌设计", "品牌策划", "平面设计", "广告投放", "短视频营销", "社群推广", "内容创作", "摄影摄像"] },
  { label: "教育培训", children: ["职业培训", "升学辅导", "语言培训", "企业培训", "课程开发", "K12教育", "素质教育", "留学服务"] },
  { label: "健康美业", children: ["健康管理", "医疗服务", "医疗器械", "美容美发", "医美服务", "健身运动", "母婴服务", "保健品"] },
  {
    label: "制造业",
    children: [
      "机械设备", "电子产品", "服装纺织", "鞋帽箱包", "家电", "汽车零部件", "五金工具", "模具加工",
      "包装印刷", "食品饮料", "建材家居", "化工材料", "新能源", "医疗器械", "日化用品"
    ]
  },
  { label: "农业食品", children: ["农业种植", "农资服务", "畜牧养殖", "水产养殖", "食品加工", "生鲜果蔬", "宠物食品"] },
  { label: "互联网科技", children: ["软件开发", "AI与大模型", "云计算", "网站建设", "信息安全", "通信服务", "数据服务"] },
  { label: "汽车出行", children: ["汽车销售", "汽车维修", "汽车后市场", "新能源汽车", "共享出行", "物流运输"] },
  { label: "金融保险", children: ["银行服务", "保险服务", "投资理财", "融资服务", "支付服务", "金融科技"] },
  { label: "文化传媒", children: ["影视传媒", "内容创作", "出版发行", "游戏动漫", "体育运动", "演艺娱乐"] },
  { label: "能源环保", children: ["新能源", "节能环保", "电力能源", "环境服务", "循环利用"] },
  { label: "其他服务", children: ["咨询顾问", "金融保险", "法律服务", "个人服务", "综合服务", "其他"] }
];

const BUSINESS_INDUSTRY_OPTIONS = BUSINESS_INDUSTRY_GROUPS.map((item) => item.label);

function getBusinessIndustryGroup(industry) {
  return BUSINESS_INDUSTRY_GROUPS.find((item) => item.label === industry) || null;
}

function getBusinessSubIndustryOptions(industry, placeholder = "请选择细分行业") {
  const group = getBusinessIndustryGroup(industry);
  return [placeholder, ...(group ? group.children : [])];
}

module.exports = {
  BUSINESS_INDUSTRY_GROUPS,
  BUSINESS_INDUSTRY_OPTIONS,
  getBusinessIndustryGroup,
  getBusinessSubIndustryOptions
};
