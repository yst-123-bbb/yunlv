import '../models/models.dart';
import 'data_repository.dart';

/// 交通查询服务：高铁车次 + 航班方案。
///
/// 移植自 云旅ai 的 data/train_data.py、data/flight_data.py 兜底逻辑：
/// 真实线路优先，缺失城市自动生成兜底车次 / 航班（带舱位价格与推荐标签）。
class TransitService {
  TransitService._();

  /// 高铁方案：优先真实线路，缺失时生成 6 趟兜底车次。
  static List<TrainRoute> trainRoutes(String departure, String destination) {
    final repo = DataRepository.instance;
    final k1 = '$departure-$destination';
    final k2 = '$destination-$departure';

    final List<TrainRoute> raw;
    if (repo.trainRoutes.containsKey(k1)) {
      raw = List.of(repo.trainRoutes[k1]!);
    } else if (repo.trainRoutes.containsKey(k2)) {
      raw = List.of(repo.trainRoutes[k2]!);
    } else {
      raw = _genericTrains(departure, destination);
    }

    if (raw.isNotEmpty) raw.first.tag = '推荐';
    if (raw.length >= 3) {
      var lowest = 0;
      for (var i = 0; i < raw.length; i++) {
        if (raw[i].secondSeat < raw[lowest].secondSeat) lowest = i;
      }
      if (lowest != 0) raw[lowest].tag = '价格最低';
    }
    return raw;
  }

  static List<TrainRoute> _genericTrains(String dep, String dest) {
    final list = <TrainRoute>[];
    for (var i = 0; i < 6; i++) {
      final h1 = 7 + i * 2;
      final h2 = h1 + 5;
      list.add(TrainRoute(
        trainNo: 'G${301 + i * 17}',
        depStation: '$dep站',
        arrStation: '$dest站',
        depTime: '${h1.toString().padLeft(2, '0')}:00',
        arrTime: '${h2.toString().padLeft(2, '0')}:30',
        duration: '5小时${30 + i * 5}分',
        secondSeat: 400 + i * 80,
        firstSeat: 700 + i * 100,
      ));
    }
    return list;
  }

  /// 航班方案：匹配航线基准，按时段生成航班（含多舱位价格）。
  static List<FlightOption> flightOptions(String departure, String destination) {
    final repo = DataRepository.instance;

    FlightRouteInfo? matched;
    for (final r in repo.flightRoutes) {
      if ((r.departure == departure && r.destination == destination) ||
          (r.departure == destination && r.destination == departure)) {
        matched = r;
        break;
      }
    }

    final duration = matched?.duration ?? '2h30m';
    final basePrice = matched?.basePrice ?? 880;
    final hours = matched?.hours ?? 2;
    final minutes = matched?.minutes ?? 30;
    final depAp = repo.airportOf(departure);
    final arrAp = repo.airportOf(destination);

    final slots = repo.flightTimeSlots.isEmpty
        ? const ['06:30', '08:00', '09:30', '11:00', '13:00', '14:30', '16:00', '17:30', '19:00', '21:00']
        : repo.flightTimeSlots;
    final airlines = repo.airlines;

    final flights = <FlightOption>[];
    for (var i = 0; i < slots.length; i++) {
      final t = slots[i];
      final air = airlines.isEmpty
          ? Airline(code: 'CA', name: '国航', group: '星空联盟', baggage: '手提7kg+托运20kg免费')
          : airlines[i % airlines.length];
      final fno = '${air.code}${1000 + i * 137}';
      final arrTime = _addHours(t, hours, minutes);
      var economy = basePrice + i * 50 - 80;
      if (economy < 400) economy = 400;

      flights.add(FlightOption(
        flightNo: fno,
        airline: air.name,
        airlineGroup: air.group,
        depAirport: depAp,
        arrAirport: arrAp,
        depTime: t,
        arrTime: arrTime,
        duration: duration,
        economyPrice: economy,
        superEconomyPrice: (economy * 1.5).round(),
        businessPrice: economy * 3,
        firstPrice: economy * 5,
        baggage: air.baggage,
        punctuality: '${80 + (i * 3) % 15}%',
      ));
    }

    if (flights.isNotEmpty) flights.first.tag = '推荐';
    if (flights.length >= 3) {
      var lowest = 0;
      for (var i = 0; i < flights.length; i++) {
        if (flights[i].economyPrice < flights[lowest].economyPrice) lowest = i;
      }
      if (lowest != 0) flights[lowest].tag = '价格最低';
    }
    if (flights.length >= 5) flights[2].tag ??= '时间最好';
    return flights;
  }

  /// 时间加法（跨天取模 24 小时）
  static String _addHours(String time, int hours, int minutes) {
    try {
      final parts = time.split(':');
      var h = int.parse(parts[0]) + hours;
      var m = int.parse(parts[1]) + minutes;
      h += m ~/ 60;
      m = m % 60;
      h = h % 24;
      return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}';
    } catch (_) {
      return time;
    }
  }
}
