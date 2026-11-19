import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../widgets/common.dart';

/// 方案列表页：展示多风格方案（Hero 共享动画 + 评分排序）。
class PlanListPage extends StatelessWidget {
  final TripPreference pref;
  final List<Plan> plans;
  final String? aiText;

  const PlanListPage({super.key, required this.pref, required this.plans, this.aiText});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('${pref.destinationLabel} · 行程方案')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildAiBanner(context),
          const SizedBox(height: 8),
          SectionTitle(title: '共 ${plans.length} 个方案'),
          for (final p in plans) _PlanCard(plan: p, city: pref.destinationLabel, budget: pref.budget),
        ],
      ),
    );
  }

  Widget _buildAiBanner(BuildContext context) {
    if (aiText != null) {
      return Card(
        color: Colors.teal.shade50,
        child: ListTile(
          leading: const Icon(Icons.auto_awesome, color: Colors.teal),
          title: const Text('AI 智能行程已生成', style: TextStyle(fontWeight: FontWeight.w700)),
          subtitle: const Text('点击查看 DeepSeek 基于本地数据生成的智能行程'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _showAiText(context),
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        children: [
          Icon(Icons.offline_bolt_outlined, color: Colors.grey, size: 20),
          SizedBox(width: 8),
          Expanded(child: Text('已用本地规则引擎生成（未启用 AI 或 AI 不可用，自动降级）', style: TextStyle(fontSize: 12, color: Colors.grey))),
        ],
      ),
    );
  }

  void _showAiText(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.7,
        maxChildSize: 0.95,
        builder: (_, controller) => Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('AI 智能行程', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              Expanded(
                child: SingleChildScrollView(
                  controller: controller,
                  child: Text(aiText ?? '', style: const TextStyle(height: 1.6)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 单个方案卡片
class _PlanCard extends StatelessWidget {
  final Plan plan;
  final String city;
  final int budget;
  const _PlanCard({required this.plan, required this.city, this.budget = 0});

  @override
  Widget build(BuildContext context) {
    final style = plan.style;
    final over = budget > 0 && plan.budgetTotal > budget;
    return Hero(
      tag: 'plan-${style.id}',
      child: Card(
        margin: const EdgeInsets.only(bottom: 12),
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () {
            Navigator.of(context).pushNamed(
              Routes.planDetail,
              arguments: (plan: plan, city: city, budget: budget, historyId: null),
            );
          },
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(style.emoji, style: const TextStyle(fontSize: 32)),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(style.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                          const SizedBox(height: 4),
                          Text(style.desc, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                const Divider(height: 1),
                const SizedBox(height: 12),
                Row(
                  children: [
                    _metric(Icons.attractions_outlined, '景点 ${plan.totalAttractions} 处'),
                    _metric(Icons.restaurant_outlined, '餐厅 ${plan.totalFoods} 家'),
                    _metric(Icons.calendar_month_outlined, '${plan.totalDays} 天'),
                    const Spacer(),
                    Text('约 ${plan.budgetTotal} 元/人',
                        style: TextStyle(
                            fontSize: 13,
                            color: over ? Colors.redAccent : Colors.grey[700],
                            fontWeight: FontWeight.w600)),
                  ],
                ),
                const SizedBox(height: 10),
                Text(plan.recommendation,
                    style: TextStyle(fontSize: 12, color: Colors.teal.shade700, height: 1.4)),
                if (over) ...[
                  const SizedBox(height: 6),
                  Text('已超预算 ¥${plan.budgetTotal - budget}，建议减少景点或降低住宿档位',
                      style: const TextStyle(fontSize: 12, color: Colors.redAccent, fontWeight: FontWeight.w600)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _metric(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(right: 14),
      child: Row(
        children: [
          Icon(icon, size: 16, color: Colors.grey[600]),
          const SizedBox(width: 4),
          Text(text, style: TextStyle(fontSize: 13, color: Colors.grey[700])),
        ],
      ),
    );
  }
}
