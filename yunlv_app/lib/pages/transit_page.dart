import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/data_repository.dart';
import '../services/transit_service.dart';
import '../widgets/common.dart';

/// 交通查询页：TabBar 切换「高铁 / 航班」，SimpleDialog 选择城市，查询结果列表。
class TransitPage extends StatefulWidget {
  const TransitPage({super.key});

  @override
  State<TransitPage> createState() => _TransitPageState();
}

class _TransitPageState extends State<TransitPage> {
  String _departure = '北京';
  String _destination = '长沙';
  List<TrainRoute> _trains = [];
  List<FlightOption> _flights = [];
  bool _searched = false;

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    final repo = DataRepository.instance;
    if (repo.cityNames.isEmpty) await repo.load();
    setState(() {
      _trains = TransitService.trainRoutes(_departure, _destination);
      _flights = TransitService.flightOptions(_departure, _destination);
      _searched = true;
    });
  }

  Future<void> _pickCity(bool isDeparture) async {
    final names = DataRepository.instance.cityNames;
    final current = isDeparture ? _departure : _destination;
    final v = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final primary = Theme.of(ctx).colorScheme.primary;
        return SimpleDialog(
          title: Text(isDeparture ? '选择出发地' : '选择目的地'),
          children: [
            for (final n in names)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(ctx, n),
                child: Row(
                  children: [
                    Icon(
                      n == current ? Icons.check_circle : Icons.circle_outlined,
                      size: 20,
                      color: n == current ? primary : Colors.grey,
                    ),
                    const SizedBox(width: 12),
                    Text(n, style: const TextStyle(fontSize: 15)),
                  ],
                ),
              ),
          ],
        );
      },
    );
    if (v != null) {
      setState(() => isDeparture ? _departure = v : _destination = v);
      _search();
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('交通查询'),
          bottom: const TabBar(tabs: [Tab(text: '🚄 高铁'), Tab(text: '✈️ 航班')]),
        ),
        body: Column(
          children: [
            _routeHeader(),
            Expanded(
              child: _searched
                  ? TabBarView(children: [_trainTab(), _flightTab()])
                  : const Center(child: CircularProgressIndicator()),
            ),
          ],
        ),
      ),
    );
  }

  Widget _routeHeader() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Expanded(
            child: _cityButton(_departure, true),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Icon(Icons.swap_horiz, color: Colors.teal),
          ),
          Expanded(
            child: _cityButton(_destination, false),
          ),
          IconButton(
            tooltip: '查询',
            icon: const Icon(Icons.search, color: Colors.teal),
            onPressed: _search,
          ),
        ],
      ),
    );
  }

  Widget _cityButton(String city, bool isDeparture) {
    return InkWell(
      onTap: () => _pickCity(isDeparture),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: Colors.teal.shade50,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(city, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const Icon(Icons.arrow_drop_down, size: 20, color: Colors.grey),
          ],
        ),
      ),
    );
  }

  // ---------- 高铁 ----------

  Widget _trainTab() {
    if (_trains.isEmpty) {
      return const EmptyPlaceholder(icon: Icons.train_outlined, text: '暂无高铁数据');
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _trains.length,
      itemBuilder: (_, i) => _trainCard(_trains[i]),
    );
  }

  Widget _trainCard(TrainRoute t) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(t.trainNo, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.teal)),
                const SizedBox(width: 8),
                if (t.tag != null) TagChip(label: t.tag!, color: Colors.orange),
                const Spacer(),
                Text(t.duration, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(t.depTime, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 2),
                      Text(t.depStation, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    children: [
                      Icon(Icons.train, color: Colors.blueGrey[300], size: 28),
                      const SizedBox(height: 4),
                      Container(
                        width: double.infinity,
                        height: 1,
                        color: Colors.blueGrey[200],
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(t.arrTime, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 2),
                      Text(t.arrStation, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 10),
            Row(
              children: [
                _seatPrice('二等座', t.secondSeat),
                const SizedBox(width: 16),
                _seatPrice('一等座', t.firstSeat),
                const SizedBox(width: 16),
                _seatPrice('商务座', t.businessSeat),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _seatPrice(String label, int price) {
    return Row(
      children: [
        Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
        const SizedBox(width: 4),
        Text('¥$price', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.redAccent)),
      ],
    );
  }

  // ---------- 航班 ----------

  Widget _flightTab() {
    if (_flights.isEmpty) {
      return const EmptyPlaceholder(icon: Icons.flight_outlined, text: '暂无航班数据');
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _flights.length,
      itemBuilder: (_, i) => _flightCard(_flights[i]),
    );
  }

  Widget _flightCard(FlightOption f) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.airplanemode_active, size: 18, color: Colors.teal.shade700),
                const SizedBox(width: 8),
                Text(f.airline, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                const SizedBox(width: 6),
                Text(f.flightNo, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                const SizedBox(width: 8),
                if (f.tag != null) TagChip(label: f.tag!, color: Colors.orange),
                const Spacer(),
                Text('准点率 ${f.punctuality}', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(f.depTime, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                      Text(f.depAirport, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    children: [
                      Text(f.duration, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                      const SizedBox(height: 4),
                      Container(
                        width: double.infinity,
                        height: 1,
                        color: Colors.blueGrey[200],
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(f.arrTime, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                      Text(f.arrAirport, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 10),
            Row(
              children: [
                _seatPrice('经济舱', f.economyPrice),
                const SizedBox(width: 16),
                _seatPrice('超经舱', f.superEconomyPrice),
                const SizedBox(width: 16),
                _seatPrice('商务舱', f.businessPrice),
              ],
            ),
            const SizedBox(height: 6),
            Text('行李：${f.baggage}', style: TextStyle(fontSize: 11, color: Colors.grey[500])),
          ],
        ),
      ),
    );
  }
}
