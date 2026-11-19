/// 全局配置与常量
///
/// 说明：本 App 采用「AI 优先、本地兜底」架构：
///  - 填了 [deepseekApiKey] 且开关打开时，优先调用 DeepSeek 大模型生成智能行程；
///  - Key 为空 / 请求失败 / 超时 / 断网时，自动回退到本地规则引擎，业务闭环不中断。
class AppConfig {
  AppConfig._();

  // ===================== DeepSeek AI 增强配置 =====================
  // 在下方填入你的 DeepSeek API Key（https://platform.deepseek.com 申请）。
  // 留空则 AI 增强关闭，App 完全走本地规则引擎（离线可用，演示更稳定）。
  // ⚠️ 提交作业前如需隐藏密钥，可将此处置空（App 仍离线可用）。
  // （已置空：提交的源码与发布产物中不再包含任何 API 密钥）
  static const String deepseekApiKey = '';

  /// DeepSeek 官方接口地址
  static const String deepseekBaseUrl =
      'https://api.deepseek.com/v1/chat/completions';

  /// 模型名（deepseek-chat 为对话模型；deepseek-reasoner 为推理模型）
  static const String deepseekModel = 'deepseek-chat';

  /// 请求超时（秒）
  static const int deepseekTimeoutSeconds = 30;

  /// 是否启用 AI 增强（有 Key 才启用）
  static bool get deepseekEnabled => deepseekApiKey.isNotEmpty;

  // ===================== 本地偏好键名 =====================
  static const String prefsBudgetLevel = 'budget_level'; // low/mid/high
  static const String prefsDefaultDeparture = 'default_departure';
  static const String prefsSpicy = 'prefer_spicy'; // bool
  static const String prefsLight = 'prefer_light'; // bool
  static const String prefsAiEnabled = 'ai_enabled'; // bool

  // ===================== 个人信息偏好键名 =====================
  static const String prefsAddress = 'address'; // String 大概住址
  static const String prefsPreferSweet = 'prefer_sweet'; // bool 甜口（旧，迁入 tastes）
  static const String prefsAttractionPref = 'attraction_pref'; // List<String> 景点偏好标签
  static const String prefsTravelStyle = 'travel_style'; // 'fast' 特种兵 | 'slow' 慢游
  static const String prefsAccommodationBudget = 'accommodation_budget'; // int 住宿预算(元)
  static const String prefsTransportBudget = 'transport_budget'; // int 出行预算(元)
  static const String prefsTotalBudget = 'total_budget'; // int 总预算上限(元)
  static const String prefsTastes = 'tastes'; // List<String> 口味偏好（多选）
  static const String prefsOnboarded = 'onboarded'; // bool 是否已完成首次引导

  // ===================== 口味偏好选项（多选） =====================
  static const Map<String, String> tasteOptions = {
    'local': '当地特色',
    'spicy': '嗜辣',
    'light': '清淡',
    'sweet': '甜口',
    'seafood': '海鲜',
    'hotpot': '火锅',
    'bbq': '烧烤',
    'noodles': '面食',
    'veggie': '素食',
    'drinks': '饮品甜点',
  };
}
