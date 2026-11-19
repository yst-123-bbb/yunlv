import 'dart:math';

import '../models/models.dart';
import 'waypoints.dart';

/// 本地规则引擎：多风格行程方案生成器（移植自 云旅ai 的 core/plan_generator.py）。
///
/// 与 Python 原版的差异：打分逻辑按真实数据 schema（tags/features/likes/ticket_price）
/// 重写，风格词表也映射到真实标签（人文古迹 / 自然风光 / 主题乐园 / 网红打卡 / 美食文化 / 购物）。
///
/// 支持多目的地：天数按城市均分，途经地景点优先编排。
class PlanGenerator {
  PlanGenerator._();

  /// 为同一出行需求生成多个风格方案，并按评分降序排列。
  ///
  /// [cities] 有序目的地列表；[attractionsByCity]/[hotelsByCity]/[foodsByCity] 按城市分组；
  /// [waypoints] 用户想去的途经地（提供时严格只编排这些景点，不自动补齐其它景点）。
  static List<Plan> generatePlans({
    required List<String> cities,
    required Map<String, List<Attraction>> attractionsByCity,
    required Map<String, List<Hotel>> hotelsByCity,
    required Map<String, List<Food>> foodsByCity,
    required int days,
    Map<String, int>? daysByCity,
    List<Waypoint> waypoints = const [],
    String budgetLevel = 'mid',
    TripPreference? preference,
    List<TransitLeg> legs = const [],
    String? onlyStyle,
  }) {
    if (cities.isEmpty) return [];

    // 天数分配：提供 daysByCity 时按「每城自定天数」；否则均分（每城至少 1 天，城市数超过天数取前 N 城）。
    final Map<String, int> alloc;
    final List<String> effCities;
    if (daysByCity != null && daysByCity.isNotEmpty) {
      effCities = cities;
      alloc = {for (final c in cities) c: daysByCity[c] ?? 1};
    } else {
      effCities = cities.length > days ? cities.sublist(0, days) : cities;
      alloc = _allocateDays(effCities, days);
    }
    final multi = effCities.length > 1;

    final plans = <Plan>[];

    // 指定 onlyStyle 时只生成该风格（对话中用户选定风格后出单一行程）；否则生成前 4 种风格。
    final styles = onlyStyle != null
        ? PlanStyle.all.where((s) => s.id == onlyStyle).toList()
        : PlanStyle.all.take(4).toList();

    for (final style in styles) {
      final allAttrs = <Attraction>[];
      final allFoods = <Food>[];
      final allHotels = <Hotel>[];
      final itinerary = <DayPlan>[];

      var dayOffset = 0;
      for (final city in effCities) {
        final cityDays = alloc[city] ?? 1;

        // 1. 景点选择：用户选了途经地 → 严格只编排这些景点；未选 → 按风格评分自动筛选
        final wpAttrs = waypoints
            .where((w) => w.city == city)
            .map((w) => w.attraction)
            .toList();

        final List<Attraction> cityAttrs;
        if (waypoints.isNotEmpty) {
          // 严格模式：仅使用用户选择的途经地景点，不自动补齐其它景点
          cityAttrs = wpAttrs;
        } else {
          final rest = attractionsByCity[city] ?? const <Attraction>[];
          final scored = <({int score, Attraction attr})>[];
          for (final a in rest) {
            scored.add((score: _matchScore(a, style, preference), attr: a));
          }
          scored.sort((x, y) => y.score.compareTo(x.score));

          final needed = style.attractionsPerDay * cityDays;
          cityAttrs = scored.take(max(0, needed)).map((e) => e.attr).toList();
        }
        if (cityAttrs.isEmpty) continue;

        // 2. 酒店 / 餐厅
        final cityHotels = _selectHotels(hotelsByCity[city] ?? const [], budgetLevel);
        final cityFoods = _selectFoods(foodsByCity[city] ?? const [], style, budgetLevel, preference, cityDays);

        // 3. 按天编排
        final cityItinerary = _assignByDays(
          city,
          cityDays,
          cityAttrs,
          cityFoods,
          cityHotels,
          style,
          dayOffset: dayOffset,
          includeCity: multi,
        );
        itinerary.addAll(cityItinerary);
        dayOffset += cityDays;

        allAttrs.addAll(cityAttrs);
        allFoods.addAll(cityFoods);
        allHotels.addAll(cityHotels.take(3).toList());
      }

      if (itinerary.isEmpty) continue;

      final totalDays = itinerary.length;
      plans.add(Plan(
        style: style,
        recommendation: _recommendText(style, totalDays, allAttrs.length, preference),
        transportTotal:
            legs.fold<int>(0, (s, l) => s + l.price) + intraTransportPerDay * totalDays,
        transitLegs: legs,
        itinerary: itinerary,
        attractions: allAttrs,
        hotels: allHotels.take(3).toList(),
        restaurants: allFoods,
      ));
    }

    // 取消评分制：按风格固定顺序返回（不再按评分排序）
    return plans;
  }

  /// 按各城景点的游玩时长估算天数（每城至少 1 天，单城上限 7 天）。
  static Map<String, int> estimateDaysByCity(Map<String, List<Attraction>> byCity) {
    final out = <String, int>{};
    byCity.forEach((city, attrs) {
      final totalHours = attrs.fold<double>(0, (s, a) => s + a.playHours);
      var days = (totalHours / hoursPerDay).ceil();
      days = days < 1 ? 1 : (days > 7 ? 7 : days);
      out[city] = days;
    });
    return out;
  }

  /// 生成方案推荐语（替代评分）。
  static String _recommendText(PlanStyle style, int days, int attrCount, TripPreference? p) {
    final pace = p != null && p.travelStyle == 'slow' ? '节奏舒缓，慢游感受' : '行程紧凑，性价比高';
    return '${style.name} · ${style.desc}。共 $days 天、$attrCount 个景点，$pace。';
  }

  /// 把总天数尽量均分到各城市（每城至少 1 天）。
  static Map<String, int> _allocateDays(List<String> cities, int days) {
    final n = cities.length;
    final base = days ~/ n;
    final rem = days % n;
    final out = <String, int>{};
    for (var i = 0; i < n; i++) {
      out[cities[i]] = base + (i < rem ? 1 : 0);
    }
    return out;
  }

  /// 由字符串种子生成稳定伪随机数：同一「城市 + 天数」得到相同结果，
  /// 让天气/温度不会每次进入详情页都跳变。
  static int _stableInt(String seed, int max) {
    var h = 0;
    for (final c in seed.codeUnits) {
      h = (h * 31 + c) & 0x7fffffff;
    }
    return h % max;
  }

  /// 按预算档位筛选酒店。
  static List<Hotel> _selectHotels(List<Hotel> hotels, String budgetLevel) {
    final (int lo, int hi) = switch (budgetLevel) {
      'low' => (0, 350),
      'high' => (500, 1 << 30),
      _ => (250, 650),
    };
    var chosen = hotels.where((h) => h.price >= lo && h.price <= hi).toList();
    if (chosen.isEmpty) chosen = hotels.take(3).toList();
    return chosen;
  }

  /// 按风格 / 口味 / 预算筛选餐厅。
  static List<Food> _selectFoods(List<Food> foods, PlanStyle style, String budgetLevel,
      TripPreference? p, int days) {
    final scored = <({int score, Food food})>[];
    for (final f in foods) {
      scored.add((score: _foodScore(f, style, budgetLevel, p), food: f));
    }
    scored.sort((x, y) => y.score.compareTo(x.score));
    return scored.take(days * 3).map((e) => e.food).toList();
  }

  /// 景点与风格匹配度（0-100）
  static int _matchScore(Attraction a, PlanStyle style, TripPreference? preference) {
    var score = 0;
    final text = '${a.tags.join(' ')} ${a.features}';
    for (final tag in style.tagPriority) {
      if (a.tags.contains(tag)) {
        score += 30;
      } else if (text.contains(tag)) {
        score += 15;
      }
    }
    // 用户「景点偏好」命中加分
    if (preference != null) {
      for (final pref in preference.attractionPrefs) {
        if (a.tags.contains(pref) || text.contains(pref)) {
          score += 12;
          break;
        }
      }
    }
    // 热度（rating 4.0~4.9 -> 0~18 分）
    score += ((a.rating - 4.0) * 20).round();
    if (a.isFree) score += 5;
    return score.clamp(0, 100);
  }

  /// 餐厅匹配度（0-100）
  static int _foodScore(Food f, PlanStyle style, String budgetLevel, TripPreference? p) {
    var score = 0;
    final tags = f.tags.join(' ');
    // 风格菜系匹配
    for (final kw in style.foodKeywords) {
      if (f.cuisine.contains(kw)) {
        score += 30;
        break;
      }
    }
    // 辣度偏好
    final spicyCuisine = f.cuisine.contains('川') || f.cuisine.contains('湘');
    if (p != null && p.preferSpicy && (tags.contains('重辣') || tags.contains('微辣') || spicyCuisine)) {
      score += 20;
    } else if (p != null && p.preferMild && tags.contains('不辣')) {
      score += 20;
    } else if (style.spice == 'spicy' && (tags.contains('重辣') || spicyCuisine)) {
      score += 10;
    } else if (style.spice == 'mild' && tags.contains('不辣')) {
      score += 10;
    }
    // 热度
    score += ((f.rating - 4.0) * 20).round();
    // 预算贴合
    if (budgetLevel == 'low' && f.avgPrice <= 80) score += 20;
    if (budgetLevel == 'high' && f.avgPrice >= 100) score += 20;
    return score.clamp(0, 100);
  }

  /// 将景点 / 餐厅分配到各天（天数编号从 [dayOffset] 起，可带城市前缀）。
  static List<DayPlan> _assignByDays(
    String city,
    int days,
    List<Attraction> attractions,
    List<Food> foods,
    List<Hotel> hotels,
    PlanStyle style, {
    int dayOffset = 0,
    bool includeCity = false,
  }) {
    final perDay = max(1, (attractions.length + days - 1) ~/ days);
    final itinerary = <DayPlan>[];
    final hotel = hotels.isNotEmpty ? hotels.first : null;

    var idx = 0;
    for (var d = 0; d < days; d++) {
      final dayAttrs = attractions.skip(idx).take(perDay).toList();
      idx += perDay;

      final dayFoods = foods.skip(d * 2).take(2).toList();
      final dayNumber = dayOffset + d + 1;
      final seed = '$city#$dayNumber';
      final weather = ['晴', '多云', '阴'][_stableInt('$seed-w', 3)];
      final tempLow = 15 + _stableInt('$seed-l', 8);
      final tempHigh = 22 + _stableInt('$seed-h', 11);
      final prefix = includeCity ? '$city · ' : '';

      itinerary.add(DayPlan(
        day: dayOffset + d + 1,
        title: '第${dayOffset + d + 1}天 · $prefix${style.name}游',
        weather: weather,
        tempLow: tempLow,
        tempHigh: tempHigh,
        weatherTip: weather == '阴' ? '可能有零星小雨，备好雨具' : '天气良好，适合出行',
        attractions: dayAttrs,
        foods: dayFoods,
        hotel: d < days - 1 ? hotel : null,
        styleId: style.id,
        styleName: style.name,
      ));
    }
    return itinerary;
  }

  /// 生成方案摘要文本（供导出 / 展示）
  static String planSummary(Plan plan) {
    final style = plan.style;
    final buf = StringBuffer();
    buf.writeln('${style.emoji} 【${style.name}】 推荐：${plan.recommendation}');
    buf.writeln('  ${style.desc}');
    buf.writeln('  景点 ${plan.totalAttractions} 处 | 餐厅 ${plan.totalFoods} 家 | ${plan.totalDays} 天');
    return buf.toString();
  }
}
