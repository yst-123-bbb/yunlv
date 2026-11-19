import 'package:flutter/material.dart';

import '../config.dart';
import '../models/models.dart';
import '../routes.dart';
import '../services/data_repository.dart';
import '../services/deepseek_service.dart';
import '../services/plan_generator.dart';
import '../services/storage_service.dart';
import '../services/transit_service.dart';
import '../services/trip_stops.dart';
import '../services/waypoints.dart';
import '../widgets/common.dart';

/// 需求录入页：表单 + SimpleDialog 选择 + 多选目的地 + 途经地（显式动画加载）。
class InputPage extends StatefulWidget {
  final String? destination;
  const InputPage({super.key, this.destination});

  @override
  State<InputPage> createState() => _InputPageState();
}

class _InputPageState extends State<InputPage> {
  late String _departure;
  late DateTime _depDate;
  late int _people;
  String _ageGroup = 'friends';
  final Set<String> _tastes = {'local'};
  String _hotelLevel = 'mid';
  String _transportPref = 'both';
  int _budget = 2000;
  List<TransitLeg> _legs = [];

  static const Map<String, String> _ageLabels = {
    'friends': '朋友结伴',
    'family': '家庭亲子',
    'couple': '情侣出行',
    'solo': '独自旅行',
  };
  static const Map<String, String> _levelLabels = {'low': '经济型', 'mid': '舒适型', 'high': '高档型'};
  static const Map<String, String> _transportLabels = {'both': '高铁+航班', 'train': '高铁优先', 'flight': '航班优先'};

  @override
  void initState() {
    super.initState();
    _departure = '北京';
    _depDate = DateTime.now();
    _people = 2;
    if (widget.destination != null) {
      TripPlanStore.instance.add(widget.destination!);
    }
    TripPlanStore.instance.listenable.addListener(_onStopsChanged);
    _loadPrefs();
  }

  @override
  void dispose() {
    TripPlanStore.instance.listenable.removeListener(_onStopsChanged);
    super.dispose();
  }

  void _onStopsChanged() {
    if (!mounted) return;
    setState(() => _ensureLegs());
  }

  Future<void> _loadPrefs() async {
    final dep = await PrefsService.loadDefaultDeparture();
    final address = await PrefsService.loadAddress();
    final level = await PrefsService.loadBudgetLevel();
    final tastes = await PrefsService.loadTastes();
    if (!mounted) return;
    setState(() {
      // 默认出发地 = 大概住址（匹配到城市则用它，否则回退历史默认 / 北京）
      _departure = DataRepository.instance.cityFromAddress(address) ?? dep;
      _hotelLevel = level;
      _tastes
        ..clear()
        ..addAll(tastes.isEmpty ? const ['local'] : tastes);
      // 尚无行程站点时，用途经地城市预填
      if (TripPlanStore.instance.items.isEmpty) {
        for (final c in WaypointStore.instance.items.map((w) => w.city).toSet()) {
          TripPlanStore.instance.add(c);
        }
      }
    });
    _ensureLegs();
  }

  String get _dateText =>
      '${_depDate.year}-${_depDate.month.toString().padLeft(2, '0')}-${_depDate.day.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('定制行程')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
        children: [
          _destinationBanner(),
          const SizedBox(height: 12),
          _buildStops(),
          _fieldRow(Icons.flight_takeoff_outlined, '出发地', _departure,
              () => _pickCity(true)),
          _fieldRow(Icons.event_outlined, '出发日期', _dateText, _pickDate),
          _fieldRow(Icons.group_outlined, '出行人数', '$_people 人', _pickPeople),
          _fieldRow(Icons.emoji_people_outlined, '出行人群', _ageLabels[_ageGroup]!, _pickAgeGroup),
          _fieldRow(Icons.hotel_outlined, '住宿预算', _levelLabels[_hotelLevel]!, _pickLevel),
          _fieldRow(Icons.directions_transit_outlined, '交通偏好', _transportLabels[_transportPref]!, _pickTransport),
          _fieldRow(Icons.payments_outlined, '人均预算', '$_budget 元', _pickBudget),
          const SizedBox(height: 8),
          _buildLegs(),
          _buildWaypoints(),
          const SizedBox(height: 8),
          _buildTastes(),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _generate,
            icon: const Icon(Icons.auto_awesome),
            label: const Padding(
              padding: EdgeInsets.symmetric(vertical: 14),
              child: Text('生成行程方案', style: TextStyle(fontSize: 16)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _destinationBanner() {
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Colors.teal.shade400, Colors.teal.shade700],
    );
    return ValueListenableBuilder<List<String>>(
      valueListenable: TripPlanStore.instance.listenable,
      builder: (_, cities, _) {
        final label = cities.isEmpty ? '请长按城市或点击「添加」' : cities.join(' → ');
        return Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: gradient,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Row(
            children: [
              const Icon(Icons.cloud_outlined, color: Colors.white, size: 34),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(cities.isEmpty ? '目的地' : '目的地（${cities.length} 城 · 天数自动估算）',
                        style: const TextStyle(color: Colors.white70, fontSize: 12)),
                    const SizedBox(height: 4),
                    Text(
                      label,
                      style: const TextStyle(
                          color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  /// 目的地站点编辑区：添加 / 移除。
  Widget _buildStops() {
    return ValueListenableBuilder<List<String>>(
      valueListenable: TripPlanStore.instance.listenable,
      builder: (_, cities, _) {
        return Card(
          elevation: 0,
          margin: const EdgeInsets.symmetric(vertical: 4),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.place_outlined, color: Colors.teal, size: 18),
                    const SizedBox(width: 8),
                    const Text('目的地（长按城市 / 点击添加）',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    const Spacer(),
                    TextButton.icon(
                      onPressed: _pickDestinations,
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('添加'),
                    ),
                  ],
                ),
                if (cities.isEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('尚未添加目的地，点击「添加」或在首页长按城市',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  )
                else ...[
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final c in cities)
                        InputChip(
                          label: Text(c, style: const TextStyle(fontSize: 12)),
                          onDeleted: () => TripPlanStore.instance.remove(c),
                          deleteIconColor: Colors.grey,
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _fieldRow(IconData icon, String label, String value, VoidCallback onTap) {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: ListTile(
        leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
        title: Text(label),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 180),
              child: Text(value,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.right,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            ),
            const Icon(Icons.chevron_right, color: Colors.grey),
          ],
        ),
        onTap: onTap,
      ),
    );
  }

  // ---------- 跨城交通班次 ----------

  List<String> get _legRoute {
    final cities = TripPlanStore.instance.items;
    if (cities.isEmpty) return [];
    return [_departure, ...cities, _departure];
  }

  /// 保证 `_legs` 与当前「出发地 → 目的地… → 出发地」路线一致；不一致时用推荐高铁重建。
  void _ensureLegs() {
    final route = _legRoute;
    final pairs = <(String, String)>[];
    for (var i = 0; i < route.length - 1; i++) {
      if (route[i] != route[i + 1]) pairs.add((route[i], route[i + 1]));
    }
    final matches = _legs.length == pairs.length &&
        List.generate(
              pairs.length,
              (i) => _legs[i].from == pairs[i].$1 && _legs[i].to == pairs[i].$2,
            ).every((e) => e);
    if (!matches) {
      _legs = [for (final p in pairs) _defaultLeg(p.$1, p.$2)];
    }
  }

  TransitLeg _defaultLeg(String from, String to) {
    final trains = TransitService.trainRoutes(from, to);
    final t = trains.first;
    return TransitLeg(
      from: from,
      to: to,
      mode: 'train',
      label: '${t.trainNo} ${t.depTime}-${t.arrTime}',
      price: t.secondSeat,
    );
  }

  Widget _buildLegs() {
    if (_legs.isEmpty) return const SizedBox.shrink();
    return Card(
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(children: [
              Icon(Icons.directions_transit_outlined, color: Colors.teal, size: 18),
              SizedBox(width: 8),
              Text('跨城交通班次（点击选择）',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 4),
            for (var i = 0; i < _legs.length; i++)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: Icon(_legs[i].mode == 'train' ? Icons.train : Icons.flight,
                    color: Colors.teal),
                title: Text('${_legs[i].from} → ${_legs[i].to}',
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                subtitle: Text(_legs[i].label, style: const TextStyle(fontSize: 12)),
                trailing: Text('¥${_legs[i].price}',
                    style: TextStyle(
                        fontSize: 13, color: Colors.orange.shade800, fontWeight: FontWeight.w600)),
                onTap: () => _pickLeg(i),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _pickLeg(int index) async {
    final leg = _legs[index];
    final mode = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: Text('${leg.from} → ${leg.to}',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: const Text('选择出行方式'),
            ),
            ListTile(
              leading: const Icon(Icons.train, color: Colors.teal),
              title: const Text('高铁'),
              onTap: () => Navigator.pop(ctx, 'train'),
            ),
            ListTile(
              leading: const Icon(Icons.flight, color: Colors.blue),
              title: const Text('飞机'),
              onTap: () => Navigator.pop(ctx, 'flight'),
            ),
          ],
        ),
      ),
    );
    if (mode == null) return;
    final picked = await _pickSchedule(leg.from, leg.to, mode);
    if (picked != null && mounted) {
      setState(() => _legs[index] = picked);
    }
  }

  Future<TransitLeg?> _pickSchedule(String from, String to, String mode) {
    final isTrain = mode == 'train';
    return showModalBottomSheet<TransitLeg>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(children: [
                Icon(isTrain ? Icons.train : Icons.flight, color: Colors.teal),
                const SizedBox(width: 8),
                Text('$from → $to · ${isTrain ? '高铁' : '航班'}班次',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ]),
            ),
            const Divider(height: 1),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 420),
              child: ListView(
                shrinkWrap: true,
                children: [
                  if (isTrain)
                    for (final t in TransitService.trainRoutes(from, to))
                      _scheduleTile(ctx, Icons.train, Colors.teal,
                          '${t.trainNo}  ${t.depTime} → ${t.arrTime}',
                          '${t.depStation} - ${t.arrStation} · ${t.duration}',
                          '¥${t.secondSeat}',
                          TransitLeg(from: from, to: to, mode: 'train',
                              label: '${t.trainNo} ${t.depTime}-${t.arrTime}', price: t.secondSeat))
                  else
                    for (final f in TransitService.flightOptions(from, to))
                      _scheduleTile(ctx, Icons.flight, Colors.blue,
                          '${f.flightNo}  ${f.depTime} → ${f.arrTime}',
                          '${f.airline} · ${f.duration}',
                          '¥${f.economyPrice}',
                          TransitLeg(from: from, to: to, mode: 'flight',
                              label: '${f.flightNo} ${f.depTime}-${f.arrTime}', price: f.economyPrice)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _scheduleTile(BuildContext ctx, IconData icon, Color color, String title,
      String subtitle, String price, TransitLeg leg) {
    return ListTile(
      leading: Icon(icon, color: color),
      title: Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 12)),
      trailing: Text(price,
          style: TextStyle(fontSize: 14, color: Colors.orange.shade800, fontWeight: FontWeight.w700)),
      onTap: () => Navigator.pop(ctx, leg),
    );
  }

  /// 途经地区块（来自首页浏览，可移除）
  Widget _buildWaypoints() {
    return ValueListenableBuilder<List<Waypoint>>(
      valueListenable: WaypointStore.instance.listenable,
      builder: (_, items, _) {
        if (items.isEmpty) return const SizedBox.shrink();
        return Card(
          elevation: 0,
          margin: const EdgeInsets.symmetric(vertical: 4),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Icon(Icons.alt_route, color: Colors.teal, size: 18),
                  const SizedBox(width: 8),
                  Text('途经地（${items.length} 处，将优先编排）',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                ]),
                const SizedBox(height: 8),
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
            ),
          ),
        );
      },
    );
  }

  Widget _buildTastes() {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('口味偏好', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: AppConfig.tasteOptions.entries.map((e) {
                final selected = _tastes.contains(e.key);
                return FilterChip(
                  label: Text(e.value),
                  selected: selected,
                  onSelected: (v) => setState(() {
                    v ? _tastes.add(e.key) : _tastes.remove(e.key);
                  }),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  // ---------- 选择器（SimpleDialog） ----------

  Future<T?> _pick<T>(String title, List<T> values, List<String> labels, T current) {
    return showDialog<T>(
      context: context,
      builder: (ctx) {
        final primary = Theme.of(ctx).colorScheme.primary;
        return SimpleDialog(
          title: Text(title),
          children: [
            for (var i = 0; i < values.length; i++)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(ctx, values[i]),
                child: Row(
                  children: [
                    Icon(
                      values[i] == current ? Icons.check_circle : Icons.circle_outlined,
                      size: 20,
                      color: values[i] == current ? primary : Colors.grey,
                    ),
                    const SizedBox(width: 12),
                    Text(labels[i], style: const TextStyle(fontSize: 15)),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  Future<void> _pickCity(bool isDeparture) async {
    final names = DataRepository.instance.cityNames;
    final v = await _pick<String>('选择城市', names, names, _departure);
    if (v != null) {
      setState(() {
        _departure = v;
        _ensureLegs();
      });
    }
  }

  /// 添加目的地：底部弹层按「省份 → 城市」勾选，结果同步到行程站点。
  Future<void> _pickDestinations() async {
    final picked = await showModalBottomSheet<Set<String>>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => _DestinationPicker(
        current: TripPlanStore.instance.items.toSet(),
      ),
    );
    if (picked != null) {
      // 移除被取消勾选的城市
      for (final c in List.of(TripPlanStore.instance.items)) {
        if (!picked.contains(c)) TripPlanStore.instance.remove(c);
      }
      // 新增勾选的城市
      for (final c in picked) {
        TripPlanStore.instance.add(c);
      }
    }
  }

  Future<void> _pickDate() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _depDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (d != null) setState(() => _depDate = d);
  }

  Future<void> _pickPeople() async {
    final v = await _pick<int>('出行人数', List.generate(6, (i) => i + 1), List.generate(6, (i) => '${i + 1} 人'), _people);
    if (v != null) setState(() => _people = v);
  }

  Future<void> _pickAgeGroup() async {
    final v = await _pick<String>('出行人群', _ageLabels.keys.toList(), _ageLabels.values.toList(), _ageGroup);
    if (v != null) setState(() => _ageGroup = v);
  }

  Future<void> _pickLevel() async {
    final v = await _pick<String>('住宿预算', _levelLabels.keys.toList(), _levelLabels.values.toList(), _hotelLevel);
    if (v != null) setState(() => _hotelLevel = v);
  }

  Future<void> _pickTransport() async {
    final v = await _pick<String>('交通偏好', _transportLabels.keys.toList(), _transportLabels.values.toList(), _transportPref);
    if (v != null) setState(() => _transportPref = v);
  }

  /// 人均预算：自由填写
  Future<void> _pickBudget() async {
    final controller = TextEditingController(text: _budget == 0 ? '' : '$_budget');
    final v = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('人均预算（元）'),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(hintText: '自由填写，如 3000'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, int.tryParse(controller.text.trim()) ?? 0),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    if (v != null) setState(() => _budget = v);
  }

  // ---------- 生成 ----------

  Future<void> _generate() async {
    final cities = TripPlanStore.instance.items;
    if (cities.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先添加目的地（首页长按城市，或点击「添加」）')),
      );
      return;
    }
    if (cities.contains(_departure)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('出发地不能包含在目的地中')),
      );
      return;
    }

    // 读取个人信息偏好（参与方案生成偏置）
    final address = await PrefsService.loadAddress();
    final attractionPrefs = await PrefsService.loadAttractionPref();
    final travelStyle = await PrefsService.loadTravelStyle();
    final accBudget = await PrefsService.loadAccommodationBudget();
    final transBudget = await PrefsService.loadTransportBudget();
    final totalBudget = await PrefsService.loadTotalBudget();
    if (!mounted) return;

    // 显式动画加载框
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const _GeneratingDialog(),
    );
    await Future.delayed(const Duration(milliseconds: 700));

    final repo = DataRepository.instance;
    final attractionsByCity = <String, List<Attraction>>{};
    final hotelsByCity = <String, List<Hotel>>{};
    final foodsByCity = <String, List<Food>>{};
    final allAttractions = <Attraction>[];
    final allHotels = <Hotel>[];
    final allFoods = <Food>[];
    for (final c in cities) {
      final attrs = repo.attractionsOf(c);
      final hotels = repo.hotelsOf(c);
      final foods = repo.foodsOf(c);
      attractionsByCity[c] = attrs;
      hotelsByCity[c] = hotels;
      foodsByCity[c] = foods;
      allAttractions.addAll(attrs);
      allHotels.addAll(hotels);
      allFoods.addAll(foods);
    }
    final waypoints =
        WaypointStore.instance.items.where((w) => cities.contains(w.city)).toList();

    // 游玩天数：选了途经地则按其景点时长估算，否则按各城全部景点时长估算
    final Map<String, int> daysByCity;
    if (waypoints.isNotEmpty) {
      final wpByCity = <String, List<Attraction>>{};
      for (final w in waypoints) {
        wpByCity.putIfAbsent(w.city, () => []).add(w.attraction);
      }
      daysByCity = PlanGenerator.estimateDaysByCity(wpByCity);
    } else {
      daysByCity = PlanGenerator.estimateDaysByCity(attractionsByCity);
    }
    final days = daysByCity.values.fold<int>(0, (s, d) => s + d);
    _ensureLegs();
    final legs = List<TransitLeg>.of(_legs);

    final pref = TripPreference(
      departure: _departure,
      destinations: cities,
      depDate: _dateText,
      days: days,
      people: _people,
      ageGroup: _ageGroup,
      tastes: _tastes.toList(),
      hotelLevel: _hotelLevel,
      transportPref: _transportPref,
      budget: totalBudget > 0 ? totalBudget : _budget,
      address: address,
      attractionPrefs: attractionPrefs,
      travelStyle: travelStyle,
      accommodationBudget: accBudget,
      transportBudget: transBudget,
      daysByCity: daysByCity,
    );

    final plans = PlanGenerator.generatePlans(
      cities: cities,
      attractionsByCity: attractionsByCity,
      hotelsByCity: hotelsByCity,
      foodsByCity: foodsByCity,
      days: days,
      daysByCity: daysByCity,
      waypoints: waypoints,
      budgetLevel: _hotelLevel,
      preference: pref,
      legs: legs,
    );

    // AI 增强（可选，失败自动降级）
    String? aiText;
    final aiEnabled = await PrefsService.loadAiEnabled();
    if (aiEnabled) {
      aiText = await DeepSeekService.generateTripPlan(
        pref: pref,
        attractions: allAttractions,
        hotels: allHotels,
        foods: allFoods,
      );
    }

    if (!mounted) return;
    Navigator.of(context).pop(); // 关闭加载框
    if (plans.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('数据不足，无法生成方案')),
      );
      return;
    }
    Navigator.of(context).pushNamed(
      Routes.planList,
      arguments: (pref: pref, plans: plans, aiText: aiText),
    );
  }
}

/// 多选目的地弹层：按省份分组勾选城市。
class _DestinationPicker extends StatefulWidget {
  final Set<String> current;
  const _DestinationPicker({required this.current});

  @override
  State<_DestinationPicker> createState() => _DestinationPickerState();
}

class _DestinationPickerState extends State<_DestinationPicker> {
  late final Set<String> _selected = Set.of(widget.current);

  @override
  Widget build(BuildContext context) {
    final repo = DataRepository.instance;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      builder: (_, controller) => Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
            child: Row(
              children: [
                const Text('选择目的地（可多选）',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const Spacer(),
                Text('已选 ${_selected.length} 城',
                    style: TextStyle(color: Colors.grey[600], fontSize: 13)),
                TextButton(
                  onPressed: () => Navigator.pop(context, _selected),
                  child: const Text('完成'),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView(
              controller: controller,
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                for (final p in repo.provinces) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 14, 20, 4),
                    child: Text('$p（${repo.citiesOfProvince(p).length} 城）',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.teal.shade700)),
                  ),
                  for (final c in repo.citiesOfProvince(p))
                    CheckboxListTile(
                      dense: true,
                      title: Text(c.name),
                      subtitle: Text(c.tag, style: const TextStyle(fontSize: 12)),
                      value: _selected.contains(c.name),
                      onChanged: (v) => setState(() {
                        v == true ? _selected.add(c.name) : _selected.remove(c.name);
                      }),
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 生成中对话框（显式旋转动画）
class _GeneratingDialog extends StatelessWidget {
  const _GeneratingDialog();

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: SizedBox(
          height: 130,
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                LoadingSpinner(message: '正在生成智能行程…'),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
