/// 数据模型层
///
/// 对应 assets/data/*.json 的结构（由「云旅AI」Python 数据迁移而来），
/// 以及方案生成 / 历史 / 导出所用到的数据对象。
/// 所有模型均提供 fromJson / toJson，保证「JSON 资源 -> 内存对象 -> 本地存储」的完整链路。
library;

/// 由「点赞数」推导出的展示评分（4.0 ~ 4.9），用于热度排序。
double ratingFromLikes(int likes) {
  final v = 4.0 + likes / 250000.0;
  final r = v > 4.9 ? 4.9 : v;
  return double.parse(r.toStringAsFixed(1));
}

// ===================== 行程估算常量 =====================

/// 每天约 6 小时纯游玩时间（用于按景点时长估算天数）。
const double hoursPerDay = 6.0;

/// 一天三餐人均估算（早餐 15 + 午餐 35 + 晚餐 40）。
const int mealPerDay = 90;

/// 景点之间市内交通，每人每天估算。
const int intraTransportPerDay = 60;

/// 由景点标签估算游玩时长（小时）。数据里没有 `play_hours` 字段，用标签映射做「大概」估算。
double playHoursForTags(List<String> tags) {
  if (tags.contains('主题乐园')) return 5;
  if (tags.contains('自然风光')) return 4;
  if (tags.contains('人文古迹')) return 3;
  if (tags.contains('亲子休闲')) return 3;
  if (tags.contains('美食文化')) return 2;
  if (tags.contains('购物')) return 2;
  if (tags.contains('网红打卡')) return 1.5;
  return 3;
}

/// 热门旅游城市（按省份分组）
class City {
  final String name;
  final String province;
  final String tag;
  final List<String> spots;

  City({required this.name, required this.province, required this.tag, required this.spots});

  factory City.fromJson(Map<String, dynamic> j) => City(
        name: j['name'] as String? ?? '',
        province: j['province'] as String? ?? '',
        tag: j['tag'] as String? ?? '',
        spots: (j['spots'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      );

  Map<String, dynamic> toJson() => {'name': name, 'province': province, 'tag': tag, 'spots': spots};
}

/// 景点
class Attraction {
  final String name;
  final String address;
  final int ticketPrice;
  final String openTime;
  final List<String> tags;
  final String features;
  final String tips;
  final bool indoor;
  final int likes;
  final double playHours; // 游玩时长（小时，估算）

  Attraction({
    required this.name,
    required this.address,
    required this.ticketPrice,
    required this.openTime,
    required this.tags,
    required this.features,
    required this.tips,
    required this.indoor,
    required this.likes,
    double? playHours,
  }) : playHours = playHours ?? playHoursForTags(tags);

  double get rating => ratingFromLikes(likes);
  bool get isFree => ticketPrice == 0;

  factory Attraction.fromJson(Map<String, dynamic> j) {
    final tags = (j['tags'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
    return Attraction(
      name: j['name'] as String? ?? '',
      address: j['address'] as String? ?? '',
      ticketPrice: (j['ticket_price'] as num?)?.toInt() ?? 0,
      openTime: j['open_time'] as String? ?? '',
      tags: tags,
      features: j['features'] as String? ?? '',
      tips: j['tips'] as String? ?? '',
      indoor: j['indoor'] as bool? ?? false,
      likes: (j['likes'] as num?)?.toInt() ?? 0,
      playHours: (j['play_hours'] as num?)?.toDouble() ?? playHoursForTags(tags),
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'address': address,
        'ticket_price': ticketPrice,
        'open_time': openTime,
        'tags': tags,
        'features': features,
        'tips': tips,
        'indoor': indoor,
        'likes': likes,
        'play_hours': playHours,
      };
}

/// 酒店
class Hotel {
  final String name;
  final String roomType;
  final int price;
  final String address;
  final String facilities;
  final String reviews;
  final String tips;
  final String distance;
  final String location; // center / subway / quiet

  Hotel({
    required this.name,
    required this.roomType,
    required this.price,
    required this.address,
    required this.facilities,
    required this.reviews,
    required this.tips,
    required this.distance,
    required this.location,
  });

  factory Hotel.fromJson(Map<String, dynamic> j) => Hotel(
        name: j['name'] as String? ?? '',
        roomType: j['room_type'] as String? ?? '',
        price: (j['price'] as num?)?.toInt() ?? 0,
        address: j['address'] as String? ?? '',
        facilities: j['facilities'] as String? ?? '',
        reviews: j['reviews'] as String? ?? '',
        tips: j['tips'] as String? ?? '',
        distance: j['distance'] as String? ?? '',
        location: j['location'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'room_type': roomType,
        'price': price,
        'address': address,
        'facilities': facilities,
        'reviews': reviews,
        'tips': tips,
        'distance': distance,
        'location': location,
      };
}

/// 美食 / 餐厅
class Food {
  final String name;
  final String address;
  final String cuisine;
  final int avgPrice;
  final String signature;
  final List<String> tags;
  final String reviews;
  final String tips;
  final int likes;

  Food({
    required this.name,
    required this.address,
    required this.cuisine,
    required this.avgPrice,
    required this.signature,
    required this.tags,
    required this.reviews,
    required this.tips,
    required this.likes,
  });

  double get rating => ratingFromLikes(likes);

  factory Food.fromJson(Map<String, dynamic> j) => Food(
        name: j['name'] as String? ?? '',
        address: j['address'] as String? ?? '',
        cuisine: j['cuisine'] as String? ?? '',
        avgPrice: (j['avg_price'] as num?)?.toInt() ?? 0,
        signature: j['signature'] as String? ?? '',
        tags: (j['tags'] as List?)?.map((e) => e.toString()).toList() ?? const [],
        reviews: j['reviews'] as String? ?? '',
        tips: j['tips'] as String? ?? '',
        likes: (j['likes'] as num?)?.toInt() ?? 0,
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'address': address,
        'cuisine': cuisine,
        'avg_price': avgPrice,
        'signature': signature,
        'tags': tags,
        'reviews': reviews,
        'tips': tips,
        'likes': likes,
      };
}

/// 高铁车次
class TrainRoute {
  final String trainNo;
  final String depStation;
  final String arrStation;
  final String depTime;
  final String arrTime;
  final String duration;
  final int secondSeat;
  final int firstSeat;
  String? tag; // 推荐 / 价格最低

  TrainRoute({
    required this.trainNo,
    required this.depStation,
    required this.arrStation,
    required this.depTime,
    required this.arrTime,
    required this.duration,
    required this.secondSeat,
    required this.firstSeat,
    this.tag,
  });

  int get businessSeat => (firstSeat * 1.8).round();
  int get premiumSeat => (firstSeat * 2.2).round();

  factory TrainRoute.fromJson(Map<String, dynamic> j) => TrainRoute(
        trainNo: j['train_no'] as String? ?? '',
        depStation: j['dep_station'] as String? ?? '',
        arrStation: j['arr_station'] as String? ?? '',
        depTime: j['dep_time'] as String? ?? '',
        arrTime: j['arr_time'] as String? ?? '',
        duration: j['duration'] as String? ?? '',
        secondSeat: (j['second_seat'] as num?)?.toInt() ?? 0,
        firstSeat: (j['first_seat'] as num?)?.toInt() ?? 0,
      );
}

/// 航线基准信息（出发/到达/时长/基准价/时/分）
class FlightRouteInfo {
  final String departure;
  final String destination;
  final String duration;
  final int basePrice;
  final int hours;
  final int minutes;

  FlightRouteInfo({
    required this.departure,
    required this.destination,
    required this.duration,
    required this.basePrice,
    required this.hours,
    required this.minutes,
  });

  factory FlightRouteInfo.fromJson(Map<String, dynamic> j) => FlightRouteInfo(
        departure: j['departure'] as String? ?? '',
        destination: j['destination'] as String? ?? '',
        duration: j['duration'] as String? ?? '',
        basePrice: (j['base_price'] as num?)?.toInt() ?? 0,
        hours: (j['hours'] as num?)?.toInt() ?? 2,
        minutes: (j['minutes'] as num?)?.toInt() ?? 30,
      );
}

/// 航空公司
class Airline {
  final String code;
  final String name;
  final String group;
  final String baggage;

  Airline({required this.code, required this.name, required this.group, required this.baggage});

  factory Airline.fromJson(Map<String, dynamic> j) => Airline(
        code: j['code'] as String? ?? '',
        name: j['name'] as String? ?? '',
        group: j['group'] as String? ?? '',
        baggage: j['baggage'] as String? ?? '',
      );
}

/// 航班方案（含多舱位价格）
class FlightOption {
  final String flightNo;
  final String airline;
  final String airlineGroup;
  final String depAirport;
  final String arrAirport;
  final String depTime;
  final String arrTime;
  final String duration;
  final int economyPrice;
  final int superEconomyPrice;
  final int businessPrice;
  final int firstPrice;
  final String baggage;
  final String punctuality;
  String? tag;

  FlightOption({
    required this.flightNo,
    required this.airline,
    required this.airlineGroup,
    required this.depAirport,
    required this.arrAirport,
    required this.depTime,
    required this.arrTime,
    required this.duration,
    required this.economyPrice,
    required this.superEconomyPrice,
    required this.businessPrice,
    required this.firstPrice,
    required this.baggage,
    required this.punctuality,
    this.tag,
  });
}

/// 方案风格（本地规则引擎的 5 种风格）
class PlanStyle {
  final String id;
  final String name;
  final String emoji;
  final String desc;
  final List<String> tagPriority; // 景点 tag 优先级（真实词表）
  final int attractionsPerDay;
  final List<String> foodKeywords; // 美食 cuisine 关键词
  final String spice; // any / spicy / mild

  const PlanStyle({
    required this.id,
    required this.name,
    required this.emoji,
    required this.desc,
    required this.tagPriority,
    required this.attractionsPerDay,
    required this.foodKeywords,
    required this.spice,
  });

  static const List<PlanStyle> all = [
    PlanStyle(id: 'classic', name: '经典打卡', emoji: '🏛️',
        desc: '名胜古迹全覆盖，地标景点一次逛遍',
        tagPriority: ['人文古迹', '网红打卡'], attractionsPerDay: 3,
        foodKeywords: ['当地特色菜', '京菜', '湘菜'], spice: 'any'),
    PlanStyle(id: 'culture', name: '文化深度', emoji: '📚',
        desc: '博物馆+历史街区，深度了解当地文化',
        tagPriority: ['人文古迹', '美食文化'], attractionsPerDay: 2,
        foodKeywords: ['当地特色菜', '小吃', '北京小吃'], spice: 'mild'),
    PlanStyle(id: 'family', name: '亲子休闲', emoji: '👨‍👩‍👧',
        desc: '主题乐园+自然风光，适合带老人小孩',
        tagPriority: ['主题乐园', '自然风光'], attractionsPerDay: 2,
        foodKeywords: ['小吃', '奶茶', '街头小吃'], spice: 'mild'),
    PlanStyle(id: 'foodie', name: '美食探店', emoji: '🍜',
        desc: '以美食为主线，景点轻松辅助安排',
        tagPriority: ['美食文化', '网红打卡'], attractionsPerDay: 2,
        foodKeywords: ['湘菜', '川菜', '烧烤', '米粉', '街头小吃'], spice: 'spicy'),
    PlanStyle(id: 'relax', name: '轻松漫步', emoji: '🌸',
        desc: '少景点多留白，慢游不赶行程',
        tagPriority: ['自然风光', '购物'], attractionsPerDay: 2,
        foodKeywords: ['奶茶', '街头小吃', '烧烤'], spice: 'any'),
  ];

  Map<String, dynamic> toJson() => {
        'id': id, 'name': name, 'emoji': emoji, 'desc': desc,
        'tag_priority': tagPriority, 'attractions_per_day': attractionsPerDay,
        'food_keywords': foodKeywords, 'spice': spice,
      };
}

/// 跨城交通班次（用户在选择时选定的高铁/航班）
class TransitLeg {
  final String from;
  final String to;
  final String mode; // train / flight
  final String label; // 班次号 + 起止时间，如「G301 07:00-12:30」
  final int price;

  const TransitLeg({
    required this.from,
    required this.to,
    required this.mode,
    required this.label,
    required this.price,
  });

  Map<String, dynamic> toJson() => {
        'from': from,
        'to': to,
        'mode': mode,
        'label': label,
        'price': price,
      };

  factory TransitLeg.fromJson(Map<String, dynamic> j) => TransitLeg(
        from: j['from'] as String? ?? '',
        to: j['to'] as String? ?? '',
        mode: j['mode'] as String? ?? 'train',
        label: j['label'] as String? ?? '',
        price: (j['price'] as num?)?.toInt() ?? 0,
      );
}

/// 每日行程
class DayPlan {
  final int day;
  final String title;
  final String weather;
  final int tempLow;
  final int tempHigh;
  final String weatherTip;
  final List<Attraction> attractions;
  final List<Food> foods;
  final Hotel? hotel;
  final String styleId;
  final String styleName;

  DayPlan({
    required this.day,
    required this.title,
    required this.weather,
    required this.tempLow,
    required this.tempHigh,
    required this.weatherTip,
    required this.attractions,
    required this.foods,
    required this.hotel,
    required this.styleId,
    required this.styleName,
  });

  int get attractionsCount => attractions.length;
  int get ticketTotal => attractions.fold(0, (s, a) => s + a.ticketPrice);
  int get foodTotal => foods.fold(0, (s, f) => s + f.avgPrice);

  Map<String, dynamic> toJson() => {
        'day': day,
        'title': title,
        'weather': weather,
        'temp_low': tempLow,
        'temp_high': tempHigh,
        'weather_tip': weatherTip,
        'attractions': attractions.map((e) => e.toJson()).toList(),
        'foods': foods.map((e) => e.toJson()).toList(),
        'hotel': hotel?.toJson(),
        'style_id': styleId,
        'style_name': styleName,
      };

  factory DayPlan.fromJson(Map<String, dynamic> j) => DayPlan(
        day: (j['day'] as num?)?.toInt() ?? 1,
        title: j['title'] as String? ?? '',
        weather: j['weather'] as String? ?? '晴',
        tempLow: (j['temp_low'] as num?)?.toInt() ?? 15,
        tempHigh: (j['temp_high'] as num?)?.toInt() ?? 25,
        weatherTip: j['weather_tip'] as String? ?? '',
        attractions: (j['attractions'] as List?)
                ?.map((e) => Attraction.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        foods: (j['foods'] as List?)
                ?.map((e) => Food.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        hotel: j['hotel'] == null ? null : Hotel.fromJson(j['hotel'] as Map<String, dynamic>),
        styleId: j['style_id'] as String? ?? '',
        styleName: j['style_name'] as String? ?? '',
      );
}

/// 完整行程方案
class Plan {
  final PlanStyle style;
  final String recommendation; // 推荐语（替代评分）
  final int transportTotal; // 交通费合计（市内 + 跨城）
  final List<TransitLeg> transitLegs; // 跨城班次
  final List<DayPlan> itinerary;
  final List<Attraction> attractions;
  final List<Hotel> hotels;
  final List<Food> restaurants;

  Plan({
    required this.style,
    this.recommendation = '',
    this.transportTotal = 0,
    this.transitLegs = const [],
    required this.itinerary,
    required this.attractions,
    required this.hotels,
    required this.restaurants,
  });

  int get totalAttractions => attractions.length;
  int get totalFoods => restaurants.length;
  int get totalDays => itinerary.length;

  /// 门票合计（人均）
  int get ticketTotal => attractions.fold(0, (s, a) => s + a.ticketPrice);

  /// 一天三餐费用（人均，按天数估算）
  int get mealTotal => totalDays * mealPerDay;

  /// 住宿合计（人均，按晚数估算）
  int get hotelTotal {
    if (hotels.isEmpty || totalDays <= 1) return 0;
    return hotels.first.price * (totalDays - 1);
  }

  /// 人均预算合计（门票 + 三餐 + 住宿 + 交通）
  int get budgetTotal => ticketTotal + mealTotal + hotelTotal + transportTotal;

  Map<String, dynamic> toJson() => {
        'style': style.toJson(),
        'recommendation': recommendation,
        'transport_total': transportTotal,
        'transit_legs': transitLegs.map((e) => e.toJson()).toList(),
        'itinerary': itinerary.map((e) => e.toJson()).toList(),
        'attractions': attractions.map((e) => e.toJson()).toList(),
        'hotels': hotels.map((e) => e.toJson()).toList(),
        'restaurants': restaurants.map((e) => e.toJson()).toList(),
      };

  factory Plan.fromJson(Map<String, dynamic> j) {
    final styleJson = j['style'] as Map<String, dynamic>? ?? const {};
    final style = PlanStyle.all.firstWhere(
      (s) => s.id == styleJson['id'],
      orElse: () => PlanStyle.all.first,
    );
    return Plan(
      style: style,
      recommendation: j['recommendation'] as String? ?? '',
      transportTotal: (j['transport_total'] as num?)?.toInt() ?? 0,
      transitLegs: (j['transit_legs'] as List?)
              ?.map((e) => TransitLeg.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      itinerary: (j['itinerary'] as List?)
              ?.map((e) => DayPlan.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      attractions: (j['attractions'] as List?)
              ?.map((e) => Attraction.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      hotels: (j['hotels'] as List?)
              ?.map((e) => Hotel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      restaurants: (j['restaurants'] as List?)
              ?.map((e) => Food.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

/// 出行需求（用户录入）
class TripPreference {
  final String departure;
  final List<String> destinations; // 多目的地（省份城市）
  final String depDate;
  final int days;
  final int people;
  final String ageGroup; // friends / family / couple / solo
  final List<String> tastes; // local / spicy / light / sweet
  final String hotelLevel; // low / mid / high
  final String transportPref; // both / train / flight
  final int budget;

  // ===== 个人信息（可选，来自「我的」页，参与方案生成偏置） =====
  final String address; // 大概住址
  final List<String> attractionPrefs; // 景点偏好标签
  final String travelStyle; // 'fast' 特种兵·性价比 | 'slow' 慢游·感受
  final int accommodationBudget; // 住宿预算（元）
  final int transportBudget; // 出行预算（元）

  /// 每城自定天数（null 表示均分，见 PlanGenerator）
  final Map<String, int>? daysByCity;

  const TripPreference({
    required this.departure,
    required this.destinations,
    required this.depDate,
    required this.days,
    required this.people,
    required this.ageGroup,
    required this.tastes,
    required this.hotelLevel,
    required this.transportPref,
    required this.budget,
    this.address = '',
    this.attractionPrefs = const [],
    this.travelStyle = 'fast',
    this.accommodationBudget = 0,
    this.transportBudget = 0,
    this.daysByCity,
  });

  /// 目的地展示串（单城即城市名，多城用 → 连接）
  String get destinationLabel => destinations.join(' → ');

  /// 带每城天数的展示串（如「昆明3天 → 大理2天」）；无每城天数时退化为 [destinationLabel]。
  String get destinationDaysLabel {
    final m = daysByCity;
    if (m == null || m.isEmpty) return destinationLabel;
    return destinations.map((c) => '$c${m[c] ?? 1}天').join(' → ');
  }

  bool get preferSpicy => tastes.contains('spicy');
  bool get preferMild => tastes.contains('light') || tastes.contains('sweet');
}

/// AI 对话消息
class ChatMessage {
  final String role; // user / assistant
  final String content;

  const ChatMessage({required this.role, required this.content});

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}
