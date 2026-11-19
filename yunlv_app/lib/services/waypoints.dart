import 'package:flutter/foundation.dart';

import '../models/models.dart';

/// 途经地：用户想去的景点（归属城市 + 景点对象）。
class Waypoint {
  final String city;
  final Attraction attraction;

  const Waypoint({required this.city, required this.attraction});
}

/// 途经地状态单例：会话级内存态，首页 / 录入页共享。
///
/// 用户在城市 / 景点浏览时把想去的景点加入「途经地」，生成方案时这些景点会被优先编排。
class WaypointStore {
  WaypointStore._();
  static final WaypointStore instance = WaypointStore._();

  final ValueNotifier<List<Waypoint>> _items = ValueNotifier([]);

  ValueListenable<List<Waypoint>> get listenable => _items;

  List<Waypoint> get items => List.unmodifiable(_items.value);

  int get count => _items.value.length;

  bool contains(String city, String name) =>
      _items.value.any((w) => w.city == city && w.attraction.name == name);

  /// 加入 / 移除切换，返回切换后是否已加入。
  bool toggle(String city, Attraction attraction) {
    final idx = _items.value
        .indexWhere((w) => w.city == city && w.attraction.name == attraction.name);
    if (idx >= 0) {
      _items.value = [..._items.value]..removeAt(idx);
      return false;
    }
    _items.value = [..._items.value, Waypoint(city: city, attraction: attraction)];
    return true;
  }

  void remove(String city, String name) {
    _items.value = _items.value
        .where((w) => !(w.city == city && w.attraction.name == name))
        .toList();
  }

  void clear() => _items.value = [];
}
