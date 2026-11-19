import 'package:flutter/foundation.dart';

/// 行程站点状态单例（会话级内存态，同 [WaypointStore]）。
///
/// 存放「大的途径地 / 多目的地」的城市列表（不存天数——游玩天数在生成方案时
/// 按各城景点的游玩时长自动估算）。首页长按城市加入、录入页添加/移除，都通过
/// [TripPlanStore.instance] 读写，内部用 [ValueNotifier] 驱动界面响应式更新。
class TripPlanStore {
  TripPlanStore._();

  static final TripPlanStore instance = TripPlanStore._();

  final ValueNotifier<List<String>> _cities = ValueNotifier([]);

  ValueListenable<List<String>> get listenable => _cities;

  List<String> get items => List.unmodifiable(_cities.value);

  int get count => _cities.value.length;

  bool has(String city) => _cities.value.contains(city);

  /// 加入一个城市（去重，追加到末尾）。
  void add(String city) {
    if (has(city)) return;
    _cities.value = [..._cities.value, city];
  }

  void remove(String city) {
    _cities.value = _cities.value.where((c) => c != city).toList();
  }

  void clear() => _cities.value = [];
}
