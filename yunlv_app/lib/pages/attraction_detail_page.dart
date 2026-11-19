import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../services/trip_stops.dart';
import '../services/waypoints.dart';
import '../widgets/common.dart';

/// 景点详情页：完整景点信息 + 加入途经地 / 问 AI。
class AttractionDetailPage extends StatefulWidget {
  final String city;
  final Attraction attraction;

  const AttractionDetailPage({super.key, required this.city, required this.attraction});

  @override
  State<AttractionDetailPage> createState() => _AttractionDetailPageState();
}

class _AttractionDetailPageState extends State<AttractionDetailPage> {
  @override
  Widget build(BuildContext context) {
    final a = widget.attraction;
    return Scaffold(
      appBar: AppBar(title: const Text('景点详情')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          AttractionImage(name: a.name, tags: a.tags, width: double.infinity, height: 160),
          const SizedBox(height: 12),
          _header(a),
          const SizedBox(height: 12),
          _infoRow(Icons.place_outlined, '地址', a.address),
          _infoRow(Icons.schedule_outlined, '开放时间', a.openTime),
          _infoRow(Icons.payments_outlined, '门票', a.isFree ? '免费' : '${a.ticketPrice} 元/人'),
          _infoRow(Icons.star_outline, '热度', '${a.likes} 人点赞 · 评分 ${a.rating}'),
          _infoRow(Icons.meeting_room_outlined, '类型', a.indoor ? '室内' : '户外'),
          const SectionTitle(title: '特色亮点'),
          Text(a.features, style: const TextStyle(height: 1.6)),
          const SectionTitle(title: '游玩贴士'),
          Text(a.tips.isEmpty ? '暂无贴士' : a.tips, style: const TextStyle(height: 1.6)),
          const SectionTitle(title: '标签'),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final t in a.tags) TagChip(label: t, color: Colors.teal),
              if (a.indoor) const TagChip(label: '室内', color: Colors.indigo),
            ],
          ),
        ],
      ),
      bottomNavigationBar: _bottomBar(a),
    );
  }

  Widget _header(Attraction a) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Colors.teal.shade400, Colors.teal.shade700],
        ),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(a.name,
                    style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                Text('${widget.city} · ${a.tags.isNotEmpty ? a.tags.first : ''}',
                    style: const TextStyle(color: Colors.white70, fontSize: 13)),
                const SizedBox(height: 8),
                Row(children: [
                  StarRating(rating: a.rating, size: 18),
                  const SizedBox(width: 10),
                  Text(a.isFree ? '免费' : '门票 ${a.ticketPrice}元',
                      style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
                ]),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 12),
          SizedBox(width: 76, child: Text(label, style: TextStyle(color: Colors.grey[600], fontSize: 14))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500))),
        ],
      ),
    );
  }

  Widget _bottomBar(Attraction a) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        child: Row(
          children: [
            Expanded(
              child: ValueListenableBuilder<List<Waypoint>>(
                valueListenable: WaypointStore.instance.listenable,
                builder: (_, items, _) {
                  final inList = items.any((w) => w.city == widget.city && w.attraction.name == a.name);
                  return FilledButton.icon(
                    onPressed: () {
                      final added = WaypointStore.instance.toggle(widget.city, a);
                      if (added) TripPlanStore.instance.add(widget.city);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(added ? '已加入途经地（并加入行程站点）' : '已移出途经地')),
                      );
                    },
                    icon: Icon(inList ? Icons.check_circle : Icons.add_location_alt_outlined),
                    label: Text(inList ? '已加入途经地' : '加入途经地'),
                  );
                },
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filledTonal(
              tooltip: '问 AI',
              onPressed: () {
                Navigator.of(context).pushNamed(Routes.chat, arguments: a);
              },
              icon: const Icon(Icons.auto_awesome, color: Colors.teal),
            ),
          ],
        ),
      ),
    );
  }
}
