import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/models.dart';

/// DeepSeek AI 增强服务。
///
/// 采用「数据注入（RAG 简化版）」：把本地真实景点/酒店/美食数据拼进 Prompt，
/// 让模型基于真实数据作答而非凭空编造。请求失败 / 超时 / 无 Key 时返回 null，
/// 由调用方回退到本地规则引擎（PlanGenerator）。
class DeepSeekService {
  DeepSeekService._();

  /// 尝试用 DeepSeek 生成智能行程文本，失败返回 null。
  static Future<String?> generateTripPlan({
    required TripPreference pref,
    required List<Attraction> attractions,
    required List<Hotel> hotels,
    required List<Food> foods,
  }) async {
    if (!AppConfig.deepseekEnabled) return null;

    final prompt = _buildPrompt(pref, attractions, hotels, foods);
    return _request([
      {'role': 'system', 'content': '你是一位资深旅行规划师。'},
      {'role': 'user', 'content': prompt},
    ]);
  }

  /// AI 对话：基于本地景点数据上下文回答用户问题，失败返回 null。
  static Future<String?> chat(
    List<ChatMessage> history, {
    String? context,
  }) async {
    if (!AppConfig.deepseekEnabled) return null;

    final system = '你是一位资深旅行助手「云旅小助手」，熟悉国内热门城市与景点。'
        '请优先基于用户提供的本地真实景点数据作答；数据里没有的信息要诚实说明，不要编造。'
        '${context == null ? '' : '\n\n【可参考的本地景点数据】\n$context'}';

    return _request([
      {'role': 'system', 'content': system},
      for (final m in history) {'role': m.role, 'content': m.content},
    ]);
  }

  /// 统一 HTTP 请求：POST DeepSeek，返回首个 choice 的 content，失败返回 null。
  static Future<String?> _request(List<Map<String, String>> messages) async {
    try {
      final resp = await http
          .post(
            Uri.parse(AppConfig.deepseekBaseUrl),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ${AppConfig.deepseekApiKey}',
            },
            body: jsonEncode({
              'model': AppConfig.deepseekModel,
              'messages': messages,
              'temperature': 0.7,
              'max_tokens': 2048,
            }),
          )
          .timeout(const Duration(seconds: AppConfig.deepseekTimeoutSeconds));

      if (resp.statusCode != 200) return null;
      final data = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      final choices = data['choices'] as List?;
      if (choices == null || choices.isEmpty) return null;
      final content = (choices.first as Map)['message']?['content'];
      return (content is String && content.isNotEmpty) ? content : null;
    } catch (_) {
      // 网络异常 / 超时 / JSON 解析失败等，一律降级
      return null;
    }
  }

  /// 拼接数据注入 Prompt（多目的地）
  static String _buildPrompt(
    TripPreference p,
    List<Attraction> attractions,
    List<Hotel> hotels,
    List<Food> foods,
  ) {
    final attrLines = attractions
        .take(12)
        .map((a) => '- ${a.name}（${a.address}，门票 ${a.isFree ? '免费' : '${a.ticketPrice}元'}，${a.features}）')
        .join('\n');
    final hotelLines = hotels
        .take(5)
        .map((h) => '- ${h.name}（${h.price}元/晚，${h.facilities}，${h.distance}）')
        .join('\n');
    final foodLines = foods
        .take(10)
        .map((f) => '- ${f.name}（${f.cuisine}，人均 ${f.avgPrice}元，招牌：${f.signature}）')
        .join('\n');

    // 每城天数展示（无每城天数时退化为总天数）
    final daysText = p.daysByCity != null
        ? '${p.destinations.map((c) => '$c ${p.daysByCity![c] ?? 1}天').join('、')}（共 ${p.days} 天）'
        : '${p.days} 天';
    final personalBuf = StringBuffer();
    if (p.address.isNotEmpty) personalBuf.writeln('大概住址：${p.address}');
    if (p.attractionPrefs.isNotEmpty) personalBuf.writeln('景点偏好：${p.attractionPrefs.join('、')}');
    personalBuf.writeln('旅行风格：${p.travelStyle == 'slow' ? '慢游·注重感受' : '特种兵·注重性价比'}');
    if (p.accommodationBudget > 0) personalBuf.writeln('住宿预算上限：${p.accommodationBudget} 元/晚');
    if (p.transportBudget > 0) personalBuf.writeln('出行预算上限：${p.transportBudget} 元');

    return '''
请根据以下信息，为用户生成一份 ${p.days} 天的「${p.destinationLabel}」旅行行程。

【用户需求】
出发城市：${p.departure}
目的地：${p.destinationDaysLabel}
出发日期：${p.depDate}
游玩天数：$daysText
出行人数：${p.people} 人
人群：${p.ageGroup}
饮食偏好：${p.tastes.join('、')}
住宿预算：${p.hotelLevel}
人均预算：${p.budget} 元
${personalBuf.toString()}【本地真实数据（务必基于以下数据作答，不要编造）】
景点：
$attrLines

酒店：
$hotelLines

餐厅：
$foodLines

【输出要求】
1. 行程总览（一句话概括）
2. 按天给出行程（上午/下午/晚上，含景点、餐饮、住宿）
3. 预算估算（门票 + 餐饮 + 住宿 + 交通）
请控制在 800 字以内，用简洁的分点描述。
''';
  }
}
