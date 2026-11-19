import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

import '../models/models.dart';

/// 数据仓库：负责加载 assets/data/*.json 本地资源并常驻内存。
///
/// 采用单例模式，App 启动时调用一次 [load]，之后所有页面通过
/// [DataRepository.instance] 读取城市 / 景点 / 酒店 / 美食 / 交通数据。
class DataRepository {
  DataRepository._();
  static final DataRepository instance = DataRepository._();

  bool _loaded = false;
  String? _error;

  List<City> cities = [];
  final Map<String, List<Attraction>> _attractions = {};
  final Map<String, List<Hotel>> _hotels = {};
  final Map<String, List<Food>> _foods = {};
  final Map<String, List<TrainRoute>> _trainRoutes = {};
  List<Airline> airlines = [];
  List<FlightRouteInfo> flightRoutes = [];
  final Map<String, String> _airports = {};
  final List<String> _flightTimeSlots = [];

  bool get isLoaded => _loaded;
  String? get error => _error;

  /// 从资源加载全部 JSON 数据（含 try-catch 异常处理）。
  Future<void> load() async {
    if (_loaded) return;
    try {
      final results = await Future.wait([
        _parseJsonMap('assets/data/cities.json'),
        _parseJsonMap('assets/data/attractions.json'),
        _parseJsonMap('assets/data/hotels.json'),
        _parseJsonMap('assets/data/foods.json'),
        _parseJsonMap('assets/data/transit.json'),
      ]);

      cities = (results[0]['cities'] as List?)
              ?.map((e) => City.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [];

      _fillMap(_attractions, results[1], Attraction.fromJson);
      _fillMap(_hotels, results[2], Hotel.fromJson);
      _fillMap(_foods, results[3], Food.fromJson);

      final transit = results[4];
      final rawTrains = transit['train_routes'] as Map<String, dynamic>? ?? const {};
      _trainRoutes.clear();
      rawTrains.forEach((k, v) {
        _trainRoutes[k] = (v as List)
            .map((e) => TrainRoute.fromJson(e as Map<String, dynamic>))
            .toList();
      });
      airlines = (transit['airlines'] as List?)
              ?.map((e) => Airline.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [];
      flightRoutes = (transit['flight_routes'] as List?)
              ?.map((e) => FlightRouteInfo.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [];
      _airports.clear();
      (transit['airports'] as Map<String, dynamic>? ?? const {}).forEach((k, v) {
        _airports[k] = v.toString();
      });
      _flightTimeSlots
        ..clear()
        ..addAll((transit['flight_time_slots'] as List?)?.map((e) => e.toString()).toList() ?? const []);

      _loaded = true;
      _error = null;
    } catch (e) {
      _error = '数据加载失败：$e';
    }
  }

  /// 解析顶层为 Map 的 JSON 资源。
  Future<Map<String, dynamic>> _parseJsonMap(String asset) async {
    final raw = await rootBundle.loadString(asset);
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  /// 将 {城市名: [items]} 的 JSON 填充到目标 Map。
  void _fillMap<T>(Map<String, List<T>> target, Map<String, dynamic> src,
      T Function(Map<String, dynamic>) fromJson) {
    target.clear();
    src.forEach((k, v) {
      target[k] = (v as List).map((e) => fromJson(e as Map<String, dynamic>)).toList();
    });
  }

  // ---------- 查询接口 ----------

  List<Attraction> attractionsOf(String city) => _attractions[city] ?? const [];
  List<Hotel> hotelsOf(String city) => _hotels[city] ?? const [];
  List<Food> foodsOf(String city) => _foods[city] ?? const [];

  /// 高铁线路原始表（键形如 "北京-上海"）
  Map<String, List<TrainRoute>> get trainRoutes => _trainRoutes;
  String airportOf(String city) => _airports[city] ?? '$city机场';
  List<String> get flightTimeSlots => _flightTimeSlots;

  /// 城市名列表（用于出发/目的地选择）
  List<String> get cityNames => cities.map((c) => c.name).toList();

  /// 从大概住址中提取城市名（把「大概住址」当作默认出发地）。匹配失败返回 null。
  String? cityFromAddress(String address) {
    if (address.trim().isEmpty) return null;
    // 按城市名长度降序匹配，避免「呼和浩特」被「呼和」截断之类的问题
    final names = cityNames.toList()..sort((a, b) => b.length.compareTo(a.length));
    for (final c in names) {
      if (address.contains(c)) return c;
    }
    return null;
  }

  /// 省份列表（去重、保持 cities 出现顺序）
  List<String> get provinces {
    final seen = <String>{};
    final out = <String>[];
    for (final c in cities) {
      if (c.province.isNotEmpty && seen.add(c.province)) out.add(c.province);
    }
    return out;
  }

  /// 某省份下的城市
  List<City> citiesOfProvince(String province) =>
      cities.where((c) => c.province == province).toList();

  /// 按城市 + 名称查找景点（供 AI 上下文 / 途经地还原）
  Attraction? findAttraction(String city, String name) {
    for (final a in attractionsOf(city)) {
      if (a.name == name) return a;
    }
    return null;
  }
}
