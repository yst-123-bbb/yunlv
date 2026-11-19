import 'package:flutter/material.dart';

import '../models/models.dart';
import '../routes.dart';
import '../services/data_repository.dart';
import '../services/trip_stops.dart';
import '../services/waypoints.dart';
import '../widgets/common.dart';

/// 城市详情页：展示该城市的热门景点推荐，可把想去的景点加入「途经地」。
class CityDetailPage extends StatelessWidget {
  final City city;

  const CityDetailPage({super.key, required this.city});

  @override
  Widget build(BuildContext context) {
    final attractions = DataRepository.instance.attractionsOf(city.name);
    return Scaffold(
      appBar: AppBar(title: Text(city.name)),
      body: Column(
        children: [
          _header(context),
          Expanded(
            child: attractions.isEmpty
                ? const EmptyPlaceholder(icon: Icons.attractions, text: '暂无景点数据')
                : ValueListenableBuilder<List<Waypoint>>(
                    valueListenable: WaypointStore.instance.listenable,
                    builder: (_, items, _) => ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: attractions.length,
                      itemBuilder: (_, i) => _attractionCard(
                        context, attractions[i], items,
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _header(BuildContext context) {
    final accent = Colors.primaries[city.name.hashCode.abs() % Colors.primaries.length];
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [accent.withValues(alpha: 0.85), accent.withValues(alpha: 0.55)],
        ),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Hero(
            tag: 'city-${city.name}',
            child: Material(
              type: MaterialType.transparency,
              child: Text(city.name,
                  style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(height: 4),
          Text('${city.province} · ${city.tag}',
              style: const TextStyle(color: Colors.white70, fontSize: 13)),
          const SizedBox(height: 8),
          Text('热门景点推荐（点击加入途经地）',
              style: TextStyle(color: Colors.white.withValues(alpha: 0.9), fontSize: 12)),
        ],
      ),
    );
  }

  Widget _attractionCard(BuildContext context, Attraction a, List<Waypoint> items) {
    final inList = items.any((w) => w.city == city.name && w.attraction.name == a.name);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          Navigator.of(context).pushNamed(
            Routes.attractionDetail,
            arguments: (city: city.name, attraction: a),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AttractionImage(name: a.name, tags: a.tags, width: 72, height: 72),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(a.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    Row(children: [
                      StarRating(rating: a.rating),
                      const SizedBox(width: 8),
                      Text(a.isFree ? '免费' : '门票 ${a.ticketPrice}元',
                          style: TextStyle(fontSize: 12, color: Colors.orange.shade800)),
                    ]),
                    const SizedBox(height: 6),
                    Text(a.features,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 12, color: Colors.grey[700])),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 6,
                      children: [
                        for (final t in a.tags.take(3)) TagChip(label: t, color: Colors.teal),
                        if (a.indoor) const TagChip(label: '室内', color: Colors.indigo),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: inList ? '移出途经地' : '加入途经地',
                onPressed: () {
                  final added = WaypointStore.instance.toggle(city.name, a);
                  if (added) TripPlanStore.instance.add(city.name);
                },
                icon: Icon(
                  inList ? Icons.check_circle : Icons.add_circle_outline,
                  color: inList ? Theme.of(context).colorScheme.primary : Colors.grey,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
