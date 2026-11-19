import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../services/storage_service.dart';
import '../widgets/common.dart';

/// 方案详情页：TabBar 每日行程 + Hero 头部 + 保存/导出/编辑。
class PlanDetailPage extends StatelessWidget {
  final Plan plan;
  final String city;
  final int budget;
  final int? historyId;

  const PlanDetailPage({
    super.key,
    required this.plan,
    required this.city,
    this.budget = 0,
    this.historyId,
  });

  @override
  Widget build(BuildContext context) {
    final tabs = <Widget>[const Tab(text: '总览')];
    for (final d in plan.itinerary) {
      tabs.add(Tab(text: '第${d.day}天'));
    }
    final views = <Widget>[_OverviewTab(plan: plan, budget: budget)];
    for (final d in plan.itinerary) {
      views.add(_DayTab(day: d));
    }

    return DefaultTabController(
      length: tabs.length,
      child: Scaffold(
        appBar: AppBar(
          title: Text('$city · ${plan.style.name}'),
          actions: [
            IconButton(
              tooltip: '保存到我的行程',
              icon: const Icon(Icons.bookmark_add_outlined),
              onPressed: () => _saveToHistory(context),
            ),
            IconButton(
              tooltip: '导出行程单',
              icon: const Icon(Icons.ios_share_outlined),
              onPressed: () => _export(context),
            ),
            IconButton(
              tooltip: '编辑行程',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () {
                Navigator.of(context).pushNamed(
                  Routes.edit,
                  arguments: (plan: plan, city: city, historyId: historyId),
                );
              },
            ),
          ],
          bottom: TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: tabs,
          ),
        ),
        body: Column(
          children: [
            _Header(plan: plan),
            Expanded(child: TabBarView(children: views)),
          ],
        ),
      ),
    );
  }

  Future<void> _saveToHistory(BuildContext context) async {
    try {
      if (historyId != null) {
        await DatabaseService.updateHistory(
          id: historyId!,
          city: city,
          days: plan.totalDays,
          styleName: plan.style.name,
          recommendation: plan.recommendation,
          planJson: _encodePlan(),
        );
      } else {
        await DatabaseService.addHistory(
          city: city,
          days: plan.totalDays,
          styleName: plan.style.name,
          recommendation: plan.recommendation,
          planJson: _encodePlan(),
        );
      }
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已保存到「我的行程」')),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败：$e')));
    }
  }

  Future<void> _export(BuildContext context) async {
    final fmt = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: const Text('选择导出格式'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, 'txt'),
            child: const ListTile(leading: Icon(Icons.description_outlined), title: Text('文本 .txt'), contentPadding: EdgeInsets.zero),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, 'json'),
            child: const ListTile(leading: Icon(Icons.data_object), title: Text('结构化 .json'), contentPadding: EdgeInsets.zero),
          ),
        ],
      ),
    );
    if (fmt == null) return;
    try {
      final path = fmt == 'txt'
          ? await FileStorage.exportPlanText(plan, city)
          : await FileStorage.exportPlanJson(plan, city);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已导出：$path')),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('导出失败：$e')));
    }
  }

  String _encodePlan() {
    return jsonEncode(plan.toJson());
  }
}

/// Hero 头部
class _Header extends StatelessWidget {
  final Plan plan;
  const _Header({required this.plan});

  @override
  Widget build(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    return Hero(
      tag: 'plan-${plan.style.id}',
      child: Material(
        type: MaterialType.transparency,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
          color: primary.withValues(alpha: 0.08),
          child: Row(
            children: [
              Text(plan.style.emoji, style: const TextStyle(fontSize: 30)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(plan.style.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(plan.style.desc, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    const SizedBox(height: 6),
                    Text(plan.recommendation,
                        style: TextStyle(fontSize: 12, color: primary, height: 1.3)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 总览 Tab
class _OverviewTab extends StatelessWidget {
  final Plan plan;
  final int budget;
  const _OverviewTab({required this.plan, this.budget = 0});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _budgetCard(),
        const SectionTitle(title: '行程景点'),
        for (final a in plan.attractions) _AttractionTile(attraction: a),
        if (plan.transitLegs.isNotEmpty) ...[
          const SectionTitle(title: '跨城交通班次'),
          for (final l in plan.transitLegs) _TransitLegTile(leg: l),
        ],
        if (plan.hotels.isNotEmpty) ...[
          const SectionTitle(title: '推荐住宿'),
          for (final h in plan.hotels) _HotelTile(hotel: h),
        ],
        const SectionTitle(title: '推荐餐厅'),
        for (final f in plan.restaurants) _FoodTile(food: f),
      ],
    );
  }

  Widget _budgetCard() {
    final over = budget > 0 && plan.budgetTotal > budget;
    return Card(
      color: Colors.teal.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('预算估算（人均）', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            Center(
              child: BudgetDonutChart(items: [
                (label: '门票', value: plan.ticketTotal, color: Colors.teal),
                (label: '三餐', value: plan.mealTotal, color: Colors.orange),
                (label: '住宿', value: plan.hotelTotal, color: Colors.blue),
                (label: '交通', value: plan.transportTotal, color: Colors.purple),
              ]),
            ),
            if (over) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Colors.redAccent, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text('已超预算 ¥${plan.budgetTotal - budget}，建议减少景点或降低住宿档位',
                          style: const TextStyle(fontSize: 12, color: Colors.redAccent)),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 每日行程 Tab
class _DayTab extends StatelessWidget {
  final DayPlan day;
  const _DayTab({required this.day});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _weatherBar(),
        const SizedBox(height: 8),
        SectionTitle(title: '景点（${day.attractionsCount} 处）'),
        for (final a in day.attractions) _AttractionTile(attraction: a),
        if (day.foods.isNotEmpty) ...[
          const SectionTitle(title: '推荐餐饮'),
          for (final f in day.foods) _FoodTile(food: f),
        ],
        if (day.hotel != null) ...[
          const SectionTitle(title: '住宿'),
          _HotelTile(hotel: day.hotel!),
        ],
      ],
    );
  }

  Widget _weatherBar() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [Colors.blue.shade100, Colors.cyan.shade50]),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Icon(Icons.wb_sunny_outlined, color: Colors.orange.shade700, size: 30),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${day.weather}  ${day.tempLow}~${day.tempHigh}°C',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              Text(day.weatherTip, style: TextStyle(fontSize: 12, color: Colors.grey[700])),
            ],
          ),
        ],
      ),
    );
  }
}

/// 景点卡片
class _AttractionTile extends StatelessWidget {
  final Attraction attraction;
  const _AttractionTile({required this.attraction});

  @override
  Widget build(BuildContext context) {
    final a = attraction;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(a.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Row(
              children: [
                StarRating(rating: a.rating),
                const SizedBox(width: 8),
                Text(a.isFree ? '免费' : '门票 ${a.ticketPrice}元',
                    style: TextStyle(fontSize: 12, color: Colors.orange.shade800)),
              ],
            ),
            const SizedBox(height: 6),
            Text(a.features, style: TextStyle(fontSize: 12, color: Colors.grey[700])),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              children: [
                for (final t in a.tags) TagChip(label: t, color: Colors.teal),
                if (a.indoor) const TagChip(label: '室内', color: Colors.indigo),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 餐厅卡片
class _FoodTile extends StatelessWidget {
  final Food food;
  const _FoodTile({required this.food});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: const Icon(Icons.restaurant, color: Colors.orange),
        title: Text(food.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: Text('${food.cuisine} · ${food.signature}'),
        trailing: Text('人均${food.avgPrice}元', style: TextStyle(fontSize: 13, color: Colors.orange.shade800, fontWeight: FontWeight.w600)),
      ),
    );
  }
}

/// 跨城交通班次卡片
class _TransitLegTile extends StatelessWidget {
  final TransitLeg leg;
  const _TransitLegTile({required this.leg});

  @override
  Widget build(BuildContext context) {
    final isTrain = leg.mode == 'train';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(isTrain ? Icons.train : Icons.flight, color: isTrain ? Colors.teal : Colors.blue),
        title: Text('${leg.from} → ${leg.to}', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: Text(leg.label),
        trailing: Text('${leg.price}元',
            style: TextStyle(fontSize: 13, color: Colors.orange.shade800, fontWeight: FontWeight.w600)),
      ),
    );
  }
}

/// 酒店卡片
class _HotelTile extends StatelessWidget {
  final Hotel hotel;
  const _HotelTile({required this.hotel});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: const Icon(Icons.hotel, color: Colors.blue),
        title: Text(hotel.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: Text('${hotel.roomType} · ${hotel.distance}'),
        trailing: Text('${hotel.price}元/晚', style: TextStyle(fontSize: 13, color: Colors.blue.shade800, fontWeight: FontWeight.w600)),
      ),
    );
  }
}
