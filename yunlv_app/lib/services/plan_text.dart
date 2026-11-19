import '../models/models.dart';

/// 生成可读的行程单文本（桌面端文件导出与 Web 端下载共用，纯函数无 IO）。
String buildPlanText(Plan plan, String city) {
  final style = plan.style;
  final b = StringBuffer();
  b.writeln('============================================================');
  b.writeln('  ✈ $city · ${style.name}方案  共 ${plan.totalDays} 天');
  b.writeln('  ${style.desc}');
  b.writeln('============================================================');

  for (final day in plan.itinerary) {
    b.writeln();
    b.writeln('  第${day.day}天 · ${day.title}');
    b.writeln('  天气: ${day.weather} ${day.tempLow}~${day.tempHigh}°C | ${day.weatherTip}');
    b.writeln('  ----------------------------------------------------------');
    for (var i = 0; i < day.attractions.length; i++) {
      final a = day.attractions[i];
      b.writeln('  ${i + 1}. ${a.name}');
      b.writeln('     地址: ${a.address}');
      if (a.isFree) {
        b.writeln('     免费开放  开放时间 ${a.openTime}');
      } else {
        b.writeln('     门票: ${a.ticketPrice}元  开放时间 ${a.openTime}');
      }
      b.writeln('     特色: ${a.features}');
    }
    if (day.foods.isNotEmpty) {
      b.writeln('  🍜 推荐餐饮:');
      for (final f in day.foods) {
        b.writeln('     · ${f.name}  ${f.cuisine} 人均${f.avgPrice}元  ${f.signature}');
      }
    }
    if (day.hotel != null) {
      final h = day.hotel!;
      b.writeln('  🏨 住宿: ${h.name}  约${h.price}元/晚');
      b.writeln('     ${h.address}  ${h.distance}');
    }
  }

  b.writeln();
  b.writeln('============================================================');
  b.writeln('  📊 方案摘要');
  b.writeln('    推荐：${plan.recommendation}');
  b.writeln('    景点 ${plan.totalAttractions} 处 | 餐厅 ${plan.totalFoods} 家');
  b.writeln('    人均预算明细：门票 ${plan.ticketTotal} 元 | 三餐 ${plan.mealTotal} 元');
  b.writeln('                 住宿 ${plan.hotelTotal} 元 | 交通 ${plan.transportTotal} 元');
  b.writeln('                 合计：约 ${plan.budgetTotal} 元');
  if (plan.transitLegs.isNotEmpty) {
    b.writeln('  🚄 跨城交通班次：');
    for (final l in plan.transitLegs) {
      b.writeln('     · ${l.from} → ${l.to}  ${l.label}  ${l.price}元');
    }
  }
  b.writeln('============================================================');
  return b.toString();
}
