// 云旅 App 单元测试：验证核心业务逻辑（评分换算 / 方案序列化 / 交通兜底）。
import 'package:flutter_test/flutter_test.dart';

import 'package:yunlv_app/models/models.dart';
import 'package:yunlv_app/services/plan_generator.dart';
import 'package:yunlv_app/services/transit_service.dart';

void main() {
  test('评分由点赞数换算且封顶 4.9', () {
    expect(ratingFromLikes(0), 4.0);
    expect(ratingFromLikes(250000), 4.9); // 0 赞 -> 4.0，25w 赞 -> 4.9
    expect(ratingFromLikes(100000000), 4.9); // 超过上限封顶
  });

  test('Plan 序列化后能无损还原（推荐语 + 交通费 + 班次）', () {
    final style = PlanStyle.all.first;
    final plan = Plan(
      style: style,
      recommendation: '经典打卡 · 名胜古迹全覆盖。共 3 天、8 个景点，行程紧凑，性价比高。',
      transportTotal: 420,
      transitLegs: const [
        TransitLeg(from: '北京', to: '上海', mode: 'train', label: 'G301 07:00-12:30', price: 553),
      ],
      itinerary: const [],
      attractions: [
        Attraction(
          name: '测试景点',
          address: '测试地址',
          ticketPrice: 30,
          openTime: '09:00-18:00',
          tags: const ['人文古迹'],
          features: '特色',
          tips: '',
          indoor: false,
          likes: 50000,
        ),
      ],
      hotels: const [],
      restaurants: const [],
    );
    final restored = Plan.fromJson(plan.toJson());
    expect(restored.recommendation, plan.recommendation);
    expect(restored.transportTotal, 420);
    expect(restored.transitLegs.length, 1);
    expect(restored.transitLegs.first.from, '北京');
    expect(restored.style.id, style.id);
    expect(restored.totalAttractions, 1);
    expect(restored.attractions.first.name, '测试景点');
  });

  test('estimateDaysByCity 按景点游玩时长估算天数', () {
    Attraction attr(String name, List<String> tags) => Attraction(
          name: name,
          address: '地址',
          ticketPrice: 0,
          openTime: '09:00-18:00',
          tags: tags,
          features: '',
          tips: '',
          indoor: false,
          likes: 0,
        );
    final days = PlanGenerator.estimateDaysByCity({
      '上海': [attr('迪士尼', const ['主题乐园']), attr('外滩', const ['人文古迹'])],
      '苏州': [attr('拙政园', const ['人文古迹'])],
    });
    // 迪士尼 5h + 外滩 3h = 8h -> ceil(8/6)=2 天；拙政园 3h -> ceil(3/6)=1 天
    expect(days['上海'], 2);
    expect(days['苏州'], 1);
  });

  test('生成方案含非空推荐语，交通费含跨城 + 市内每日估算', () {
    Attraction attr(String name, List<String> tags) => Attraction(
          name: name,
          address: '地址',
          ticketPrice: 50,
          openTime: '09:00-18:00',
          tags: tags,
          features: '自然风光',
          tips: '',
          indoor: false,
          likes: 10000,
        );
    final plans = PlanGenerator.generatePlans(
      cities: const ['昆明'],
      days: 2,
      attractionsByCity: {
        '昆明': [attr('滇池', const ['自然风光']), attr('石林', const ['自然风光'])],
      },
      hotelsByCity: const {},
      foodsByCity: const {},
      legs: const [
        TransitLeg(from: '北京', to: '昆明', mode: 'flight', label: 'CA1401 08:00-11:30', price: 900),
      ],
    );
    expect(plans, isNotEmpty);
    final p = plans.first;
    expect(p.recommendation, isNotEmpty);
    // 跨城 900 + 市内 60 * 2 天 = 1020
    expect(p.transportTotal, 900 + 60 * 2);
    expect(p.budgetTotal, greaterThanOrEqualTo(p.transportTotal));
  });

  test('无真实线路时自动生成兜底车次并标记推荐', () {
    final trains = TransitService.trainRoutes('上海', '广州');
    expect(trains, isNotEmpty);
    expect(trains.first.tag, '推荐');
    expect(trains.length, 6);
  });

  test('提供 daysByCity 时按每城天数分配行程（昆明3天 → 大理2天）', () {
    Attraction attr(String name, List<String> tags) => Attraction(
          name: name,
          address: '地址',
          ticketPrice: 0,
          openTime: '09:00-18:00',
          tags: tags,
          features: '自然风光，人文古迹',
          tips: '',
          indoor: false,
          likes: 10000,
        );

    final plans = PlanGenerator.generatePlans(
      cities: const ['昆明', '大理'],
      days: 5,
      daysByCity: const {'昆明': 3, '大理': 2},
      attractionsByCity: {
        '昆明': [attr('滇池', const ['自然风光']), attr('石林', const ['自然风光']), attr('翠湖', const ['自然风光'])],
        '大理': [attr('洱海', const ['自然风光']), attr('大理古城', const ['人文古迹'])],
      },
      hotelsByCity: const {},
      foodsByCity: const {},
    );

    expect(plans, isNotEmpty);
    final top = plans.first;
    expect(top.itinerary.length, 5); // 3 + 2
    // 前 3 天在昆明，后 2 天在大理（多目的地会带城市前缀）
    expect(top.itinerary.take(3).every((d) => d.title.contains('昆明')), isTrue);
    expect(top.itinerary.skip(3).every((d) => d.title.contains('大理')), isTrue);
  });
}
