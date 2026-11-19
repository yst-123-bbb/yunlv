import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../services/data_repository.dart';
import '../services/storage_service.dart';
import '../services/trip_stops.dart';
import '../services/waypoints.dart';
import '../widgets/common.dart';

/// 首页：按「省份 → 城市」浏览热门城市，可搜索城市 / 标签 / 景点，
/// 并维护「途经地」清单（GridView / Hero / GestureDetector / 隐式动画）。
class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final TextEditingController _search = TextEditingController();
  String _query = '';
  bool _infoMissing = false;

  @override
  void initState() {
    super.initState();
    _checkPersonalInfo();
  }

  Future<void> _checkPersonalInfo() async {
    final missing = !await PrefsService.hasPersonalInfo();
    if (mounted) setState(() => _infoMissing = missing);
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  bool _matches(City c) {
    if (_query.isEmpty) return true;
    final q = _query.toLowerCase();
    if (c.name.toLowerCase().contains(q) ||
        c.province.toLowerCase().contains(q) ||
        c.tag.toLowerCase().contains(q)) {
      return true;
    }
    if (c.spots.any((s) => s.toLowerCase().contains(q))) return true;
    final attrs = DataRepository.instance.attractionsOf(c.name);
    return attrs.any((a) => a.name.toLowerCase().contains(q));
  }

  @override
  Widget build(BuildContext context) {
    final repo = DataRepository.instance;
    final filtered = repo.cities.where(_matches).toList();

    // 按省份分组（保持省份出现顺序）
    final grouped = <String, List<City>>{};
    for (final c in filtered) {
      grouped.putIfAbsent(c.province.isEmpty ? '其他' : c.province, () => []).add(c);
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _leftPanel(),
        VerticalDivider(width: 1, thickness: 1, color: Colors.grey.shade200),
        Expanded(child: _cityBrowser(repo, filtered, grouped)),
      ],
    );
  }

  /// 左侧固定栏：AI 助手 + 个人信息提醒 + 行程站点 + 途经地。
  Widget _leftPanel() {
    return Container(
      width: 250,
      color: Colors.white.withValues(alpha: 0.5),
      child: ListView(
        padding: const EdgeInsets.symmetric(vertical: 4),
        children: [
          _aiBanner(),
          _personalInfoBanner(),
          _cityStopBar(),
          _waypointBar(),
        ],
      ),
    );
  }

  /// 右侧城市浏览区：搜索 + 按省份分组的城市列表。
  Widget _cityBrowser(DataRepository repo, List<City> filtered, Map<String, List<City>> grouped) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            controller: _search,
            onChanged: (v) => setState(() => _query = v),
            decoration: InputDecoration(
              hintText: '搜索城市 / 省份 / 标签 / 景点',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _query.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _search.clear();
                        setState(() => _query = '');
                      },
                    ),
              filled: true,
              fillColor: Colors.white,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(28),
                borderSide: BorderSide.none,
              ),
              contentPadding: EdgeInsets.zero,
            ),
          ),
        ),
        Expanded(
          child: ValueListenableBuilder<List<String>>(
            valueListenable: TripPlanStore.instance.listenable,
            builder: (_, stops, _) {
              final stopCities = stops.toSet();
              if (filtered.isEmpty) {
                return const EmptyPlaceholder(icon: Icons.search_off, text: '未找到相关城市');
              }
              return ListView(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                children: [
                  for (final province in repo.provinces)
                    if (grouped.containsKey(province)) ...[
                      SectionTitle(title: '$province（${grouped[province]!.length} 城）'),
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          for (final city in grouped[province]!)
                            _CityCard(
                              city: city,
                              inTrip: stopCities.contains(city.name),
                              onLongPress: () => _addCityStop(city),
                            ),
                        ],
                      ),
                    ],
                ],
              );
            },
          ),
        ),
      ],
    );
  }

  /// 醒目的 AI 助手入口横幅。
  Widget _aiBanner() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () {
            Navigator.of(context).pushNamed(Routes.chat);
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [Color(0xFF26A69A), Color(0xFF00897B)],
              ),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                const Icon(Icons.auto_awesome, color: Colors.white, size: 26),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('AI 助手',
                          style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 2),
                      Text('想问景点门票 / 开放时间 / 特色？点我',
                          style: TextStyle(color: Colors.white.withValues(alpha: 0.9), fontSize: 12)),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: Colors.white),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// 新用户个人信息提醒横幅（未填写时显示）。
  Widget _personalInfoBanner() {
    if (!_infoMissing) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: () async {
            await Navigator.of(context).pushNamed(Routes.settings);
            _checkPersonalInfo();
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.amber.shade50,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.amber.shade200),
            ),
            child: Row(
              children: [
                Icon(Icons.person_pin_circle_outlined, color: Colors.amber.shade800),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text('完善个人信息，让行程更懂你',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                ),
                const Icon(Icons.chevron_right, color: Colors.grey),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// 行程站点栏：展示已加入的多目的地城市，可移除 / 清空（天数生成时自动估算）。
  Widget _cityStopBar() {
    return ValueListenableBuilder<List<String>>(
      valueListenable: TripPlanStore.instance.listenable,
      builder: (_, stops, _) {
        if (stops.isEmpty) return const SizedBox.shrink();
        return AnimatedSize(
          duration: const Duration(milliseconds: 200),
          child: Container(
            margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
            decoration: BoxDecoration(
              color: Colors.orange.shade50,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.map_outlined, color: Colors.orange, size: 20),
                    const SizedBox(width: 8),
                    Text('行程站点',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.orange.shade900)),
                    const SizedBox(width: 6),
                    Text('${stops.length} 城',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    const Spacer(),
                    TextButton(
                      onPressed: () => TripPlanStore.instance.clear(),
                      child: const Text('清空', style: TextStyle(fontSize: 12)),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final c in stops)
                      InputChip(
                        label: Text(c, style: const TextStyle(fontSize: 12)),
                        onDeleted: () => TripPlanStore.instance.remove(c),
                        deleteIconColor: Colors.grey,
                      ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  /// 长按城市：直接加入行程站点（天数生成方案时自动估算）。
  void _addCityStop(City city) {
    TripPlanStore.instance.add(city.name);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('已加入行程：${city.name}')),
    );
  }

  /// 途经地栏：展示已选景点，可移除 / 清空 / 一键开始规划。
  Widget _waypointBar() {
    return ValueListenableBuilder<List<Waypoint>>(
      valueListenable: WaypointStore.instance.listenable,
      builder: (_, items, _) {
        return AnimatedSize(
          duration: const Duration(milliseconds: 200),
          child: Container(
            margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
            decoration: BoxDecoration(
              color: Colors.teal.shade50,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.alt_route, color: Colors.teal, size: 20),
                    const SizedBox(width: 8),
                    Text('途经地', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.teal.shade800)),
                    const SizedBox(width: 6),
                    Text('${items.length} 处',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    const Spacer(),
                    if (items.isNotEmpty)
                      TextButton(
                        onPressed: () => WaypointStore.instance.clear(),
                        child: const Text('清空', style: TextStyle(fontSize: 12)),
                      ),
                  ],
                ),
                if (items.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final w in items)
                        InputChip(
                          label: Text('${w.city} · ${w.attraction.name}',
                              style: const TextStyle(fontSize: 12)),
                          onDeleted: () => WaypointStore.instance.remove(w.city, w.attraction.name),
                          deleteIconColor: Colors.grey,
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonal(
                    onPressed: () {
                      Navigator.of(context).pushNamed(
                        Routes.planChat,
                        arguments: (
                          cities: TripPlanStore.instance.items,
                          waypoints: WaypointStore.instance.items,
                        ),
                      );
                    },
                    child: const Text('开始规划', style: TextStyle(fontSize: 13)),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// 城市卡片：Hero 共享动画 + GestureDetector 点击进入城市详情、长按加入行程站点。
class _CityCard extends StatelessWidget {
  final City city;
  final VoidCallback? onLongPress;
  final bool inTrip;
  const _CityCard({required this.city, this.onLongPress, this.inTrip = false});

  @override
  Widget build(BuildContext context) {
    final accent = Colors.primaries[city.name.hashCode.abs() % Colors.primaries.length];
    return GestureDetector(
      onTap: () {
        Navigator.of(context).pushNamed(Routes.cityDetail, arguments: city);
      },
      onLongPress: onLongPress,
      child: Container(
        width: 150,
        height: 128,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [accent.withValues(alpha: 0.85), accent.withValues(alpha: 0.55)],
          ),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Hero(
                  tag: 'city-${city.name}',
                  child: Material(
                    type: MaterialType.transparency,
                    child: Text(city.name,
                        style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                  ),
                ),
                const SizedBox(height: 4),
                Text(city.tag, style: const TextStyle(color: Colors.white70, fontSize: 11)),
                Text('长按加入行程',
                    style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 9)),
                const Spacer(),
                Wrap(
                  spacing: 5,
                  runSpacing: 3,
                  children: city.spots.take(2).map((s) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.22),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(s, style: const TextStyle(color: Colors.white, fontSize: 10)),
                    );
                  }).toList(),
                ),
              ],
            ),
            if (inTrip)
              const Positioned(
                top: 0,
                right: 0,
                child: Icon(Icons.check_circle, color: Colors.white, size: 18),
              ),
          ],
        ),
      ),
    );
  }
}
