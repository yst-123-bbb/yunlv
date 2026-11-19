import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/data_repository.dart';
import '../services/storage_service.dart';
import '../widgets/common.dart';

/// 行程编辑页：增删景点 + 拖拽排序（ReorderableListView）+ 实时预算（ValueNotifier）
/// + Listener 指针事件 + AnimatedContainer 隐式动画。
class EditPage extends StatefulWidget {
  final Plan plan;
  final String city;
  final int? historyId;

  const EditPage({super.key, required this.plan, required this.city, this.historyId});

  @override
  State<EditPage> createState() => _EditPageState();
}

class _EditPageState extends State<EditPage> {
  late final List<Attraction> _items = List.of(widget.plan.attractions);
  final ValueNotifier<int> _totalTicket = ValueNotifier(0);
  bool _pressed = false; // Listener 指针按下状态

  @override
  void initState() {
    super.initState();
    _recalc();
  }

  void _recalc() {
    _totalTicket.value = _items.fold(0, (s, a) => s + a.ticketPrice);
  }

  @override
  void dispose() {
    _totalTicket.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('编辑行程'),
        actions: [
          TextButton.icon(
            onPressed: _save,
            icon: const Icon(Icons.save_outlined),
            label: const Text('保存'),
          ),
        ],
      ),
      body: Column(
        children: [
          _budgetHeader(),
          Expanded(
            child: _items.isEmpty
                ? const EmptyPlaceholder(icon: Icons.attractions, text: '暂无景点，点击右下角添加')
                : ReorderableListView.builder(
                    padding: const EdgeInsets.all(12),
                    buildDefaultDragHandles: false,
                    itemCount: _items.length,
                    onReorderItem: _onReorder,
                    itemBuilder: (_, i) => _itemRow(_items[i], i),
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addAttraction,
        icon: const Icon(Icons.add),
        label: const Text('添加景点'),
      ),
    );
  }

  void _onReorder(int oldIndex, int newIndex) {
    setState(() {
      final item = _items.removeAt(oldIndex);
      _items.insert(newIndex, item);
    });
    _recalc();
  }

  /// 实时预算头：ValueListenableBuilder + Listener + AnimatedContainer（隐式动画）。
  Widget _budgetHeader() {
    final primary = Theme.of(context).colorScheme.primary;
    return ValueListenableBuilder<int>(
      valueListenable: _totalTicket,
      builder: (_, total, _) => Listener(
        onPointerDown: (_) => setState(() => _pressed = true),
        onPointerUp: (_) => setState(() => _pressed = false),
        onPointerCancel: (_) => setState(() => _pressed = false),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          color: _pressed ? primary.withValues(alpha: 0.12) : Colors.teal.shade50,
          child: Row(
            children: [
              const Icon(Icons.account_balance_wallet_outlined, color: Colors.teal),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('实时预算统计', style: TextStyle(fontWeight: FontWeight.w700)),
                    Text('按住此卡片可看到 Listener 指针监听效果', style: TextStyle(fontSize: 11, color: Colors.grey[600])),
                  ],
                ),
              ),
              Text('景点 ${_items.length} 处', style: const TextStyle(fontSize: 13)),
              const SizedBox(width: 12),
              Text('门票合计 $total 元',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.teal)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _itemRow(Attraction a, int index) {
    return Padding(
      key: ObjectKey(a),
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        child: ListTile(
          leading: ReorderableDragStartListener(
            index: index,
            child: const Icon(Icons.drag_indicator, color: Colors.grey),
          ),
          title: Text(a.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          subtitle: Text(a.isFree ? '免费开放' : '门票 ${a.ticketPrice}元'),
          trailing: IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
            tooltip: '删除',
            onPressed: () {
              setState(() => _items.removeAt(index));
              _recalc();
            },
          ),
        ),
      ),
    );
  }

  Future<void> _addAttraction() async {
    final pool = DataRepository.instance.attractionsOf(widget.city);
    final existing = _items.map((e) => e.name).toSet();
    final available = pool.where((a) => !existing.contains(a.name)).toList();

    if (available.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('该城市景点已全部加入')));
      return;
    }

    final picked = await showModalBottomSheet<Attraction>(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('选择要添加的景点', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            ),
            Expanded(
              child: ListView.builder(
                itemCount: available.length,
                itemBuilder: (_, i) {
                  final a = available[i];
                  return ListTile(
                    leading: const Icon(Icons.add_location_alt_outlined, color: Colors.teal),
                    title: Text(a.name),
                    subtitle: Text(a.isFree ? '免费' : '门票 ${a.ticketPrice}元'),
                    onTap: () => Navigator.pop(ctx, a),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );

    if (picked != null) {
      setState(() => _items.add(picked));
      _recalc();
    }
  }

  Future<void> _save() async {
    final rebuilt = _rebuildPlan();
    try {
      if (widget.historyId != null) {
        // 来自历史方案：回写更新，避免重复新增一条
        await DatabaseService.updateHistory(
          id: widget.historyId!,
          city: widget.city,
          days: rebuilt.totalDays,
          styleName: rebuilt.style.name,
          recommendation: rebuilt.recommendation,
          planJson: jsonEncode(rebuilt.toJson()),
        );
      } else {
        await DatabaseService.addHistory(
          city: widget.city,
          days: rebuilt.totalDays,
          styleName: rebuilt.style.name,
          recommendation: rebuilt.recommendation,
          planJson: jsonEncode(rebuilt.toJson()),
        );
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已保存编辑结果到「我的行程」')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败：$e')));
    }
  }

  /// 用编辑后的景点列表重建方案（按新顺序重新编排天数）。
  Plan _rebuildPlan() {
    final days = widget.plan.totalDays;
    final perDay = (_items.length + days - 1) ~/ days;
    final itinerary = <DayPlan>[];
    var idx = 0;
    for (var d = 0; d < days; d++) {
      final dayAttrs = _items.skip(idx).take(perDay).toList();
      idx += perDay;
      itinerary.add(DayPlan(
        day: d + 1,
        title: '第${d + 1}天 · ${widget.plan.style.name}游',
        weather: '晴',
        tempLow: 18,
        tempHigh: 26,
        weatherTip: '编辑后的行程',
        attractions: dayAttrs,
        foods: const [],
        hotel: null,
        styleId: widget.plan.style.id,
        styleName: widget.plan.style.name,
      ));
    }
    return Plan(
      style: widget.plan.style,
      recommendation: widget.plan.recommendation,
      transportTotal: widget.plan.transportTotal,
      transitLegs: widget.plan.transitLegs,
      itinerary: itinerary,
      attractions: _items,
      hotels: widget.plan.hotels,
      restaurants: widget.plan.restaurants,
    );
  }
}
